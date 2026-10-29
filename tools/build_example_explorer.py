"""Build or verify the offline example workbench from real saved native sources.

Build requires KiCad Python to read pad/track geometry. Verification needs only
the locked Python workspace and never reruns or approves native CAD checks.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from kicad_claude.adapters import sch_io

from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.project import load_project
from pcb_copilot.review.report import verify_report
from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import copy_inputs, input_hashes

# Both direct script execution and pytest/module imports use the same helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_examples import _capture, _object, check_example
from example_explorer_html import render_explorer
from media_publication import publish_bundle

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'docs/demos/example-explorer'
BOARDS = {
    'usb-c-power': ('USB-C power entry', 'Independent CC resistors / fused 5 V bench power', 'usb-c-review', [
        'Externally qualified 4.75–5.25 V source; at most 500 mA total board and load near 23 °C.',
        'No PD, current-advertisement detector, active current limiter or reverse-current protection.',
        'The PPTC is not a 500 mA current limiter. The TVS is not a 5 V overvoltage regulator.',
        'F1 has no 3D body model. Connector fit, protection coordination, assembly and human decisions remain open.',
    ]),
    'i2c-sensor': ('I²C temperature sensor', 'MCP9808 / address shunts / open-drain ALERT', 'i2c-review', [
        'Common-ground, same-rail 3.3 V host. No level shifting, back-power protection or interface ESD qualification.',
        'Default address 0x18; A0/A1/A2 shunts select through 0x1F. Power off before changing shunts.',
        'Fixed 4.7 kΩ bus pullups need review with the actual host and cable. ALERT is disabled until firmware enables it.',
        'Temperature behavior, physical fit, supplier assembly and human release decisions remain open.',
    ]),
    'rs485-interface': ('RS-485 interface', 'THVD1450 / explicit control defaults / removable termination', 'rs485-review', [
        'Short common-ground bench link at 3.3 V. No isolation, surge/EMC or cable-system qualification.',
        'DE and active-low receiver-enable have pull-down defaults: driver off, receiver on.',
        'Fit termination only at the two physical bus ends. Evaluate actual differential loading and resistor power.',
        'UART drain and transceiver enable timing need host-specific implementation. Hardware, assembly and human decisions remain open.',
    ]),
}
CAPTIONS = {
    'model': 'Recorded native KiCad 3D render of an unbuilt prototype. Missing models remain absent; fit is unqualified.',
    'schematic': 'Native vector PDF rendered to a page image. Download the PDF below for readable circuit-scale inspection.',
    'top': 'Native top copper and silkscreen. Inspect clearances, pad connections and physical markings in the saved CAD.',
    'bottom': 'Native bottom copper and silkscreen, mirrored as viewed from the underside.',
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def uri(path: Path, kind: str) -> str:
    return f'data:{kind};base64,' + base64.b64encode(path.read_bytes()).decode()


def asset_paths(repository: Path, name: str) -> dict:
    root = repository / 'examples' / name
    packet = repository / 'docs/demos' / BOARDS[name][2]
    return {'model': root / 'output/board-3d.png', 'schematic': packet / 'schematic-001.png',
            'top': packet / 'top-copper.png', 'bottom': packet / 'bottom-copper.png',
            'pdf': packet / 'schematic.pdf', 'packet_manifest': packet / 'manifest.json',
            'packet_source': packet / 'source.json', 'review': packet / 'review.json',
            'capture': root / 'output/SOURCE.json', 'erc': root / 'output/erc.json', 'drc': root / 'output/drc.json'}


def _safe_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {'https', 'http'} or not parsed.netloc or parsed.username or parsed.password:
        return None
    return value


def _fields(project) -> dict:
    fields = {}
    for file in schematic_files(project.schematic_path):
        for symbol in sch_io.find_children(sch_io.parse_file(file), 'symbol'):
            values = {str(p[1]): str(p[2]) for p in sch_io.find_children(symbol, 'property')}
            if values.get('Reference') and not values['Reference'].startswith('#'):
                fields[values['Reference']] = values
    return fields


def component_metadata(project) -> dict:
    fields, evidence = _fields(project), load_evidence_index(project.evidence_index_path)
    result = {}
    for ref, values in fields.items():
        if not values.get('Footprint'):
            continue
        mpn = values.get('MPN', '')
        records = [record for record in evidence.records if ref in record.component_refs or mpn in record.part_numbers]
        records.sort(key=lambda record: (record.trust_tier.value != 'manufacturer', record.title or record.path))
        result[ref] = {'value': values.get('Value', ''), 'mpn': mpn,
                       'footprint': values['Footprint'].split(':')[-1],
                       'sources': [{'title': record.title or record.path, 'url': _safe_url(record.source_url),
                                    'manufacturer': record.manufacturer, 'revision': record.revision,
                                    'retrieved_on': record.retrieved_on.isoformat(), 'sha256': record.sha256}
                                   for record in records]}
    return result


def reconcile_geometry(geometry: dict, netmap: dict) -> None:
    """Fail closed when the displayed native pins disagree with declared intent."""
    actual = {}
    for component in geometry['components']:
        ref = component['reference']
        if ref in actual:
            raise ValueError(f'duplicate native reference: {ref}')
        actual[ref] = {}
        for pad in component['pads']:
            if pad['number']:
                previous = actual[ref].setdefault(pad['number'], pad['net'])
                if previous != pad['net']:
                    raise ValueError(f'conflicting native pad net: {ref}.{pad["number"]}')
    numbered = {ref: pins for ref, pins in actual.items() if pins}
    expected = {ref: {str(number): net.lstrip('/') for number, net in pins.items()}
                for ref, pins in netmap['nets'].items() if pins}
    if numbered != expected:
        raise ValueError('explorer exact numbered-pad inventory or native pin nets differ from netmap')


def capture(repository: Path, name: str, temporary: Path) -> tuple[dict, dict]:
    check_example(repository, name)
    project = load_project(repository / 'examples' / name)
    before = input_hashes(project)
    title, subtitle, packet_name, boundaries = BOARDS[name]
    packet = repository / 'docs/demos' / packet_name
    if verify_report(packet, project=project)['exit_code']:
        raise ValueError('recorded review packet is stale or inconsistent')
    copied_root = temporary / name
    copy_inputs(project, copied_root, before)
    copied = load_project(copied_root)
    if input_hashes(copied) != before:
        raise RuntimeError('source changed during explorer snapshot creation')
    tools = discover_toolchain(repository)
    if tools.kipython is None:
        raise RuntimeError('KiCad Python is required to extract native board geometry')
    result = subprocess.run([str(tools.kipython), '-I', str(Path(__file__).with_name('explorer_native.py')),
                             str(copied.pcb_path)], capture_output=True, encoding='utf-8',
                            errors='replace', timeout=90, check=False)
    if result.returncode:
        raise RuntimeError('native explorer extraction failed: ' + result.stderr)
    geometry = json.loads(result.stdout, object_pairs_hook=_object)
    reconcile_geometry(geometry, json.loads(copied.netmap_path.read_bytes(), object_pairs_hook=_object))
    metadata = component_metadata(copied)
    for component in geometry['components']:
        expected = metadata[component['reference']]
        if any(component[key] != expected[key] for key in ('value', 'footprint')):
            raise ValueError('native component value or footprint differs from saved schematic')
        component.update(expected)
    erc_path, drc_path = project.root / 'output/erc.json', project.root / 'output/drc.json'
    erc, drc = json.loads(erc_path.read_bytes()), json.loads(drc_path.read_bytes())
    image_files = {'model': project.root / 'output/board-3d.png',
                   'schematic': packet / 'schematic-001.png', 'top': packet / 'top-copper.png',
                   'bottom': packet / 'bottom-copper.png'}
    artifacts = [*image_files.values(), packet / 'schematic.pdf', packet / 'manifest.json',
                 packet / 'source.json', packet / 'review.json', project.root / 'output/SOURCE.json', erc_path, drc_path]
    source_artifacts = {p.relative_to(repository).as_posix(): digest(p) for p in artifacts}
    if input_hashes(project) != before or input_hashes(copied) != before:
        raise RuntimeError('source changed during explorer extraction')
    return {'id': name, 'title': title, 'subtitle': subtitle, 'boundaries': boundaries,
            'erc': sum(len(sheet['violations']) for sheet in erc['sheets']),
            'drc': len(drc['violations']), 'unconnected': len(drc['unconnected_items']),
            'source_inputs': before, 'pcb_sha256': before[project.pcb_path.relative_to(project.root).as_posix()],
            'geometry': geometry, 'images': {key: {'uri': uri(path, 'image/png'), 'caption': CAPTIONS[key]}
                                          for key, path in image_files.items()},
            'pdf': uri(packet / 'schematic.pdf', 'application/pdf'),
            'review_url': f'https://github.com/devkyber/PCB/blob/main/docs/demos/{packet_name}/review.json'}, source_artifacts


def _data(payload: bytes) -> dict:
    match = re.search(rb'<script type="application/json" id="explorer-data">(.*?)</script>', payload, re.DOTALL)
    if not match:
        raise ValueError('explorer lacks its embedded source data')
    return json.loads(match[1], object_pairs_hook=_object)


def _check_sources(repository: Path, manifest: dict) -> None:
    if manifest.get('source_cad_unchanged') is not True:
        raise ValueError('explorer has no source-preservation assertion')
    if not manifest.get('source_projects') or not set(manifest['source_projects']) <= set(BOARDS):
        raise ValueError('explorer source projects must be documented examples')
    required_artifacts = {p.relative_to(repository).as_posix()
                          for name in manifest['source_projects'] for p in asset_paths(repository, name).values()}
    if set(manifest.get('source_artifacts', {})) != required_artifacts:
        raise ValueError('explorer source artifact inventory is incomplete or unexpected')
    for name, expected in manifest['source_projects'].items():
        check_example(repository, name)
        project = load_project(repository / 'examples' / name)
        if input_hashes(project) != expected:
            raise ValueError('explorer inputs are stale: ' + name)
        if verify_report(repository / 'docs/demos' / BOARDS[name][2], project=project)['exit_code']:
            raise ValueError('explorer review source is stale: ' + name)
    for name, expected in manifest['source_artifacts'].items():
        _, payload, _ = _capture(repository, name)
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError('explorer source artifact is stale: ' + name)


def validate_embedded_board(repository: Path, board: dict) -> None:
    name = board['id']
    paths = asset_paths(repository, name)
    project = load_project(repository / 'examples' / name)
    title, subtitle, _packet, boundaries = BOARDS[name]
    if (board['title'], board['subtitle'], board['boundaries']) != (title, subtitle, boundaries):
        raise ValueError('explorer circuit description differs from the supported example')
    if set(board.get('images', {})) != {'model', 'schematic', 'top', 'bottom'}:
        raise ValueError('explorer omits required native images')
    for key in ('model', 'schematic', 'top', 'bottom', 'pdf'):
        value = board['pdf'] if key == 'pdf' else board['images'][key]['uri']
        mime = 'application/pdf' if key == 'pdf' else 'image/png'
        if value != uri(paths[key], mime):
            raise ValueError('explorer embedded artifact differs from native source: ' + key)
        if key != 'pdf' and board['images'][key]['caption'] != CAPTIONS[key]:
            raise ValueError('explorer native view scope differs from the captured example')
    if board['review_url'] != f'https://github.com/devkyber/PCB/blob/main/docs/demos/{BOARDS[name][2]}/review.json':
        raise ValueError('explorer review URL differs from the captured example')
    erc, drc = json.loads(paths['erc'].read_bytes()), json.loads(paths['drc'].read_bytes())
    counts = (sum(len(sheet['violations']) for sheet in erc['sheets']), len(drc['violations']), len(drc['unconnected_items']))
    if (any(type(board[key]) is not int for key in ('erc', 'drc', 'unconnected'))
            or (board['erc'], board['drc'], board['unconnected']) != counts):
        raise ValueError('explorer finding counts differ from native reports')
    expected = component_metadata(project)
    components = board['geometry']['components']
    if len(components) != len(expected) or {p['reference'] for p in components} != set(expected):
        raise ValueError('explorer physical component inventory differs from saved schematic')
    for component in components:
        if any(component.get(key) != value for key, value in expected[component['reference']].items()):
            raise ValueError('explorer component identity or evidence differs from saved sources')
    if board['pcb_sha256'] != board['source_inputs'][project.pcb_path.relative_to(project.root).as_posix()]:
        raise ValueError('explorer PCB fingerprint differs from its input ledger')
    reconcile_geometry(board['geometry'], json.loads(project.netmap_path.read_bytes(), object_pairs_hook=_object))


def verify(repository: Path, output: Path) -> dict:
    _, manifest_bytes, manifest_version = _capture(output, 'manifest.json')
    manifest = json.loads(manifest_bytes, object_pairs_hook=_object)
    if (type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1
            or set(manifest.get('outputs', {})) != {'index.html'}):
        raise ValueError('invalid explorer manifest inventory')
    _, payload, payload_version = _capture(output, 'index.html')
    if {p.name for p in output.iterdir()} != {'index.html', 'manifest.json'}:
        raise ValueError('unexpected files in explorer packet inventory')
    record = manifest['outputs']['index.html']
    if hashlib.sha256(payload).hexdigest() != record['sha256'] or len(payload) != record['bytes']:
        raise ValueError('explorer output bytes do not match the manifest')
    data = _data(payload)
    if (len(data['boards']) != len(manifest['source_projects'])
            or {board['id']: board['source_inputs'] for board in data['boards']} != manifest['source_projects']):
        raise ValueError('explorer embedded source ledger differs from manifest')
    if render_explorer(data) != payload:
        raise ValueError('explorer HTML differs from the supported renderer')
    _check_sources(repository, manifest)
    for board in data['boards']:
        validate_embedded_board(repository, board)
    _check_sources(repository, manifest)
    for name, expected_payload, expected_version in (('manifest.json', manifest_bytes, manifest_version),
                                                     ('index.html', payload, payload_version)):
        _, current, version = _capture(output, name)
        if current != expected_payload or version != expected_version:
            raise RuntimeError('explorer changed during verification')
    return {'integrity_valid': True, 'current_source_matches': True, 'boards': len(data['boards']),
            'scope': 'Recorded source/output byte identities and native pin-net agreement; no native rerun or engineering approval.'}


def build(repository: Path, output: Path, names: list[str]) -> dict:
    if not names or len(names) != len(set(names)) or not set(names) <= set(BOARDS):
        raise ValueError('select each documented example at most once')
    with tempfile.TemporaryDirectory(prefix='pcb-example-explorer-') as directory:
        work = Path(directory)
        boards, artifacts = [], {}
        for name in names:
            board, source = capture(repository, name, work)
            boards.append(board)
            artifacts.update(source)
        payload = render_explorer({'schema_version': 1, 'boards': boards})
        stage = work / 'publish'
        stage.mkdir()
        (stage / 'index.html').write_bytes(payload)
        manifest = {'schema_version': 1, 'generated_utc': datetime.now(UTC).isoformat(),
                    'source_cad_unchanged': True,
                    'source_projects': {board['id']: board['source_inputs'] for board in boards},
                    'source_artifacts': artifacts,
                    'generators': {p.name: digest(p) for p in (Path(__file__), Path(__file__).with_name('explorer_native.py'),
                                                             Path(__file__).with_name('example_explorer_html.py'))},
                    'outputs': {'index.html': {'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}},
                    'scope': 'Offline recorded native views and connectivity map; no hardware communication or fabrication approval.'}
        (stage / 'manifest.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
        verify(repository, stage)
        publish_bundle(stage, output, 'manifest.json', source_check=lambda: _check_sources(repository, manifest))
    return verify(repository, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--example', choices=tuple(BOARDS), action='append')
    parser.add_argument('--verify', action='store_true', help='verify the retained explorer without KiCad')
    args = parser.parse_args(argv)
    try:
        result = verify(ROOT, args.output) if args.verify else build(ROOT, args.output, args.example or list(BOARDS))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f'Example explorer failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
