"""Look up LCSC identity and import supplier CAD with archived provenance."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from kicad_claude.adapters import sch_io

from pcb_copilot.evidence.archive import archive_document
from pcb_copilot.evidence.commands import download_url
from pcb_copilot.evidence.models import EvidenceRole, TrustTier
from pcb_copilot.parts_converter import convert
from pcb_copilot.project import load_project
from pcb_copilot.transaction import apply_files, copy_inputs, input_hashes, project_lock


def lookup_part(lcsc: str, *, downloader=download_url) -> tuple[dict, dict, bytes]:
    lcsc = lcsc.upper().strip()
    if not re.fullmatch(r'C[1-9][0-9]*', lcsc):
        raise ValueError('provide an LCSC C-number, for example C5124834')
    url = f'https://easyeda.com/api/products/{lcsc}/components'
    raw = downloader(url)
    response = json.loads(raw)
    if not isinstance(response, dict) or response.get('success') is not True:
        raise ValueError('supplier returned no successful component record')
    cad = response.get('result')
    if not isinstance(cad, dict):
        raise ValueError('supplier component record is malformed')
    data = cad.get('dataStr')
    head = data.get('head') if isinstance(data, dict) else None
    parameters = head.get('c_para') if isinstance(head, dict) else None
    if not isinstance(parameters, dict) or not isinstance(cad.get('lcsc'), dict):
        raise ValueError('supplier component identity is malformed')
    if (parameters.get('Supplier Part') != lcsc
            or cad.get('lcsc', {}).get('number') != lcsc):
        raise ValueError('supplier response does not match the requested C-number')
    mpn = parameters.get('Manufacturer Part', '')
    if not isinstance(mpn, str):
        raise ValueError('supplier manufacturer part identity is malformed')
    mpn = mpn.strip()
    if not mpn:
        raise ValueError('supplier returned no manufacturer part identity')
    return {
        'lcsc': lcsc, 'manufacturer_part': mpn,
        'manufacturer': parameters.get('Manufacturer', ''),
        'package': parameters.get('package', ''),
        'source_url': url, 'catalog_url': f'https://www.lcsc.com/product-detail/{lcsc}.html',
        'fetched_utc': datetime.now(UTC).isoformat(),
        'review_required': 'Supplier CAD identity is not a verified datasheet pin map or stock quotation.',
    }, cad, raw


def _register(root: Path, library: str, *, symbols: bool) -> None:
    filename, head, suffix = ('sym-lib-table', 'sym_lib_table', '.kicad_sym') if symbols else (
        'fp-lib-table', 'fp_lib_table', '.pretty')
    path = root / filename
    tree = sch_io.parse_file(path) if path.is_file() else [sch_io.sym(head), [sch_io.sym('version'), 7]]
    if sch_io.head_of(tree) != head:
        raise ValueError(f'malformed {filename}')
    uri = '${KIPRJMOD}/libs/' + library + suffix
    matches = [entry for entry in sch_io.find_children(tree, 'lib')
               if sch_io.find_child(entry, 'name')[1] == library]
    if matches:
        if len(matches) != 1 or sch_io.find_child(matches[0], 'uri')[1] != uri:
            raise ValueError(f'existing library registration conflicts: {library}')
        return
    tree.append([sch_io.sym('lib'), [sch_io.sym('name'), library], [sch_io.sym('type'), 'KiCad'],
                 [sch_io.sym('uri'), uri], [sch_io.sym('options'), ''],
                 [sch_io.sym('descr'), 'Real LCSC footprints via easyeda2kicad']])
    sch_io.write_file(path, tree)


def import_part(project, lcsc: str, expected_mpn: str, *, downloader=download_url,
                converter=convert) -> dict:
    metadata, cad, raw = lookup_part(lcsc, downloader=downloader)
    if metadata['manufacturer_part'].casefold() != expected_mpn.strip().casefold():
        raise ValueError(f'LCSC identity mismatch: requested {expected_mpn}, supplier reports '
                         + metadata['manufacturer_part'])
    expected = input_hashes(project)
    library = 'lcsc_' + metadata['lcsc']
    if any((project.root / 'libs' / (library + suffix)).exists()
           for suffix in ('.kicad_sym', '.pretty', '.3dshapes')):
        raise ValueError(f'{library} is already imported; existing library assets are preserved')
    with project_lock(project):
        with tempfile.TemporaryDirectory(prefix='pcb-parts-') as directory:
            staged_root = Path(directory) / project.root.name
            copy_inputs(project, staged_root, expected)
            staged = load_project(staged_root)
            result = converter(cad, metadata['lcsc'], staged.root / 'libs')
            symbol = sch_io.parse_file(result['symbol_path'])
            footprint = sch_io.parse_file(result['footprint_path'])
            if (sch_io.head_of(symbol) != 'kicad_symbol_lib'
                    or not sch_io.find_children(symbol, 'symbol')
                    or sch_io.head_of(footprint) not in {'footprint', 'module'}
                    or not sch_io.find_children(footprint, 'pad')):
                raise ValueError('supplier conversion produced incomplete symbol or footprint')
            _register(staged.root, library, symbols=True)
            _register(staged.root, library, symbols=False)
            record = archive_document(
                staged, expected_mpn, metadata['source_url'], {EvidenceRole.CAD_LIBRARY}, raw,
                datetime.now(UTC).date(), manufacturer=metadata['manufacturer'],
                title=f'{metadata["lcsc"]} supplier CAD for {expected_mpn}', trust_tier=TrustTier.SUPPLIER,
            )
            changes = {}
            after = input_hashes(staged)
            for relative, digest in after.items():
                if digest is not None and digest != expected.get(relative):
                    changes[project.root / relative] = (staged.root / relative).read_bytes()
            apply_files(project, changes, expected)
            return {**metadata, 'imported': True, 'evidence_id': record.id,
                    'symbol': f'{library}:{result["symbol_name"]}',
                    'footprint': f'{library}:{result["footprint_name"]}',
                    'pin_count': result['pin_count'], 'warnings': result['warnings'],
                    'files': sorted(path.relative_to(project.root).as_posix() for path in changes),
                    'next': 'Use these IDs and the LCSC number in schematic/layout intent. '
                            'Archive the exact manufacturer datasheet with research --add; '
                            'verify symbol pin numbers and footprint against it before applying.'}
