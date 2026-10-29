"""Offline checks for the documented examples, without rerunning native CAD tools.

Checks archive integrity, exact selected-part coverage, local footprint receipts,
and whether published native artifacts still match their recorded source bytes.
Known native findings remain findings; byte verification never qualifies a PCB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath

from kicad_claude.adapters import sch_io

from pcb_copilot.evidence.commands import verify_evidence, verify_schematic_evidence
from pcb_copilot.layout.footprints import resolve_footprint
from pcb_copilot.project import load_project
from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.transaction import input_hashes

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ('gpio-indicator', 'usb-c-power', 'i2c-sensor', 'rs485-interface')


def _object(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f'duplicate example manifest key: {key}')
        document[key] = value
    return document


def _path(root: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or ':' in relative or '\\' in relative
            or PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts
            or PurePosixPath(relative).as_posix() != relative):
        raise ValueError('artifact path must be canonical and contained')
    path = root
    for part in PurePosixPath(relative).parts:
        path /= part
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'artifact path must not be aliased: {relative}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('artifact path escapes example')
    return path


def _footprints(project) -> int:
    references = {}
    for path in schematic_files(project.schematic_path):
        for symbol in sch_io.find_children(sch_io.parse_file(path), 'symbol'):
            fields = {str(p[1]): str(p[2]) for p in sch_io.find_children(symbol, 'property')}
            ref = fields.get('Reference', '')
            on_board = sch_io.find_child(symbol, 'on_board')
            if not ref or ref.startswith('#') or (on_board and str(on_board[1]) == 'no'):
                continue
            footprint = fields.get('Footprint', '')
            if not footprint:
                raise ValueError(f'{ref}: physical schematic part has no footprint')
            if ref in references and references[ref] != footprint:
                raise ValueError(f'{ref}: conflicting footprint assignments')
            references[ref] = footprint
    if not references:
        raise ValueError('no physical footprints were inspected')
    for ref, lib_id in references.items():
        resolved = resolve_footprint(project, ref, lib_id)
        if resolved.fidelity != 'real':
            raise ValueError(f'{ref}: placeholder or unverified footprint geometry')
    return len(references)


def check_example(repository: Path, name: str) -> dict:
    if name not in EXAMPLES:
        raise ValueError('select a documented active example')
    project = load_project(repository / 'examples' / name)
    before = input_hashes(project)
    for result in (verify_evidence(project), verify_schematic_evidence(project)):
        if result.exit_code:
            raise ValueError('; '.join((*result.machine_failures, *result.conflicts)))
    count = _footprints(project)
    manifest_path = _path(project.root, 'output/SOURCE.json')
    manifest = json.loads(manifest_path.read_bytes(), object_pairs_hook=_object)
    if not isinstance(manifest, dict):
        raise ValueError('example capture manifest must be an object')  # noqa: TRY004 -- Invalid artifact schema, not an API argument type.
    legacy = name == 'gpio-indicator'
    captured = manifest.get('inputs') if legacy else manifest.get('source_inputs')
    if (manifest.get('schema_version') != 1 or captured != before
            or (not legacy and manifest.get('source_cad_unchanged') is not True)):
        raise ValueError('published artifact capture is stale or has no preserved source identity')
    if not legacy and manifest.get('source_project') != 'examples/' + name:
        raise ValueError('artifact capture names the wrong source project')
    outputs = manifest.get('outputs')
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError('example capture has no output inventory')
    verified = set()
    for relative, record in outputs.items():
        path = _path(project.root if legacy else manifest_path.parent, relative)
        if not path.is_file() or path == manifest_path or path.stat().st_nlink != 1:
            raise ValueError(f'captured output missing or aliased: {relative}')
        digest = record if legacy else record.get('sha256') if isinstance(record, dict) else None
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError(f'invalid output digest: {relative}')
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError(f'captured output hash mismatch: {relative}')
        if not legacy and (type(record.get('bytes')) is not int or record['bytes'] != len(payload)):
            raise ValueError(f'captured output byte count mismatch: {relative}')
        verified.add(path.relative_to(manifest_path.parent).as_posix())
    required = {'schematic.pdf', 'schematic.png', 'assembly.png'}
    if (not required <= verified or not {'top-copper.png', 'board-front.png', 'front.png'}.intersection(verified)
            or not {'bottom-copper.png', 'board-back.png', 'back.png'}.intersection(verified)):
        raise ValueError('example capture omits required native review views')
    if input_hashes(project) != before:
        raise RuntimeError('example source inputs changed during verification')
    return {'example': name, 'archive_and_selected_part_coverage': True,
            'physical_footprints_verified': count, 'source_input_entries': len(before),
            'captured_artifacts_verified': len(verified), 'native_review_rerun': False,
            'scope': 'Offline source/artifact and footprint lineage checks; recorded native findings remain unresolved.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--example', choices=EXAMPLES, action='append', help='default: all documented examples')
    args = parser.parse_args(argv)
    results, failures = [], []
    for name in args.example or EXAMPLES:
        try:
            results.append(check_example(ROOT, name))
        except (OSError, ValueError, RuntimeError) as exc:
            failures.append({'example': name, 'error': str(exc)})
    print(json.dumps({'results': results, 'failures': failures,
                      'scope': 'No native ERC/DRC, physical inspection, bench test or fabrication approval is performed.'}, indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
