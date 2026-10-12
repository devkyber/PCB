"""Read-only native pin audit and historical copper comparison.

Run with KiCad Python. Fresh schematic export supplies pin membership.
The static P1 reference detects changed nets on unchanged geometry; changed
routes are reported for review, never restored or treated as a fabrication pass.
"""
import argparse
import collections
import hashlib
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

P = Path(__file__).resolve().parents[1]
REFERENCE = Path(__file__).with_name('authored-copper-reference.json')
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(project, candidate):
    return {str(path): digest(path) for path in sorted(
        {*project.glob('*.kicad_sch'), candidate, REFERENCE})}


def rounded(point):
    return tuple(round(value, 5) for value in point)


def track_key(item):
    return (tuple(sorted(rounded(point) for point in item['ends'])),
            round(item['width'], 5), item['layer'])


def compare_reference(expected, actual, key):
    """Only surviving reference geometry has an independently recorded net."""
    by_geometry = collections.defaultdict(list)
    for item in actual:
        by_geometry[key(item)].append(item['net'])
    wrong_net, changed_geometry = [], []
    for item in expected:
        found = by_geometry.get(key(item))
        if found is None:
            changed_geometry.append(item)
        elif any(net != item['net'] for net in found):
            wrong_net.append({'intended': item, 'actual_nets': found})
    keys = {key(item) for item in expected}
    return {'reference_count': len(expected), 'actual_count': len(actual),
            'wrong_net': wrong_net, 'missing_or_replaced_geometry': changed_geometry,
            'new_geometry': [item for item in actual if key(item) not in keys]}


def pin_errors(native, pad_nets):
    errors = []
    for key, intended in native.items():
        actual = pad_nets.get(key)
        if actual is None or any(name != intended for name in actual):
            errors.append({'ref': key[0], 'pin': key[1],
                           'intended': intended, 'actual': actual})
    for key, actual in pad_nets.items():
        if key not in native and any(actual):
            errors.append({'ref': key[0], 'pin': key[1],
                           'intended': 'NO NATIVE PIN', 'actual': actual})
    return errors


def reference_origin(board, pcb):
    edges = [item for item in board.GetDrawings() if item.GetLayer() == pcb.Edge_Cuts]
    if len(edges) != 4 or any(item.GetShape() != pcb.SHAPE_T_SEGMENT for item in edges):
        return None
    segments = [(tuple(item.GetStart()), tuple(item.GetEnd())) for item in edges]
    endpoints = [point for segment in segments for point in segment]
    x0, y0 = (min(point[axis] for point in endpoints) for axis in (0, 1))
    side = pcb.FromMM(100)
    corners = [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)]
    expected = {tuple(sorted((corners[i], corners[(i + 1) % 4]))) for i in range(4)}
    if {tuple(sorted(segment)) for segment in segments} != expected:
        return None
    return x0, y0


def audit(candidate, project=P, cli=CLI):
    import pcbnew as pcb

    before = source_hashes(project, candidate)
    with tempfile.TemporaryDirectory(prefix='rover-pin-audit-') as temporary:
        netlist = Path(temporary) / 'current.xml'
        result = subprocess.run([str(cli), 'sch', 'export', 'netlist', '--format',
                                 'kicadxml', '-o', str(netlist),
                                 str(project / 'rover-pdb.kicad_sch')],
                                capture_output=True, text=True, timeout=180, check=False)
        if result.returncode:
            raise RuntimeError(f'Fresh native netlist failed: {result.stderr or result.stdout}')
        native = {}
        for net in ET.parse(netlist).findall('./nets/net'):
            name = net.get('name', '')
            if name.startswith('unconnected-'):
                name = ''
            for node in net.findall('node'):
                native[(node.get('ref'), node.get('pin'))] = name

    board = pcb.LoadBoard(str(candidate))
    pad_nets = collections.defaultdict(list)
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNumber():
                name = pad.GetNetname()
                if name.startswith('unconnected-'):
                    name = ''
                pad_nets[(footprint.GetReference(), pad.GetNumber())].append(name)
    errors = pin_errors(native, pad_nets)
    origin = reference_origin(board, pcb)
    historical = {'status': 'not_comparable',
                  'reason': 'Historical geometry applies only to the 100 x 100 mm P1 outline.'}
    wrong_net_count = 0
    if origin is not None:
        def position(point):
            return tuple(round(pcb.ToMM(point[axis] - origin[axis]), 6) for axis in (0, 1))
        vias, tracks = [], []
        arcs = 0
        for item in board.GetTracks():
            if isinstance(item, pcb.PCB_VIA):
                vias.append({'xy': position(item.GetPosition()), 'net': item.GetNetname()})
            elif isinstance(item, pcb.PCB_ARC):
                arcs += 1
            else:
                tracks.append({'ends': sorted((position(item.GetStart()), position(item.GetEnd()))),
                               'width': pcb.ToMM(item.GetWidth()),
                               'layer': board.GetLayerName(item.GetLayer()), 'net': item.GetNetname()})
        reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
        historical = {'status': 'compared', 'reference_sha256': before[str(REFERENCE)],
                      'vias': compare_reference(reference['vias'], vias, lambda item: rounded(item['xy'])),
                      'tracks': compare_reference(reference['tracks'], tracks, track_key),
                      'uncompared_arcs': arcs}
        wrong_net_count = sum(len(historical[k]['wrong_net']) for k in ('vias', 'tracks'))
    unchanged = before == source_hashes(project, candidate)
    return {'candidate': str(candidate), 'source_hashes': before,
            'inputs_unchanged_during_audit': unchanged,
            'native_pin_count': len(native),
            'pcb_numbered_pad_count': sum(map(len, pad_nets.values())),
            'pin_errors': errors, 'historical_copper': historical,
            'passed': unchanged and not errors and not wrong_net_count,
            'scope': 'Native pin membership and net identity on surviving historical geometry only. '
                     'Changed/new routes require native DRC and engineering review; no routing is restored.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', nargs='?', type=Path, default=P / 'rover-pdb.kicad_pcb')
    parser.add_argument('--output', type=Path, default=P / '.pcb-copilot/review/net-intent.json')
    args = parser.parse_args()
    report = audit(args.candidate.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'pin_errors': len(report['pin_errors']),
                      'historical_comparison': report['historical_copper']['status'],
                      'report': str(args.output)}, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
