"""Locate awkward copper joins without mistaking them for electrical opens.

Native DRC determines connectivity. This advisory audit measures straight-track
geometry and native pad contacts; it neither rewrites owner copper nor infers
current requirements from a net name or the widest track on a net.
"""

from __future__ import annotations

import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from pcb_copilot.review.models import CheckResult, CheckScope
from pcb_copilot.toolchain import discover_toolchain

SCOPE = CheckScope(
    'covered straight tracks, short segments and off-centre native pad contacts',
    'electrical connectivity, ampacity, via/zone/arc topology or whether an off-centre entry is intentional',
    True, True,
)

_READ = r'''
import json, sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
tracks = [t for t in b.GetTracks() if type(t) == pcbnew.PCB_TRACK]
def xy(p): return [pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)]
data = {'tracks': [], 'pad_contacts': [], 'arcs': 0, 'custom_pads_skipped': 0}
groups = {}
for t in tracks:
    data['tracks'].append({'id': t.m_Uuid.AsString(), 'net': t.GetNetname(),
        'layer': b.GetLayerName(t.GetLayer()), 'start': xy(t.GetStart()),
        'end': xy(t.GetEnd()), 'width': pcbnew.ToMM(t.GetWidth()),
        'locked': t.IsLocked()})
    if t.GetNetCode() > 0:
        groups.setdefault((t.GetNetCode(), t.GetLayer()), []).append(t)
data['arcs'] = sum(type(t) == pcbnew.PCB_ARC for t in b.GetTracks())
for fp in b.GetFootprints():
    for p in fp.Pads():
        if not p.GetNumber() or p.GetNetCode() <= 0:
            continue
        # Custom/offset anchors need intentional entry points, not a guessed centre.
        offset = p.GetOffset()
        if p.GetShape() == pcbnew.PAD_SHAPE_CUSTOM or offset.x or offset.y:
            data['custom_pads_skipped'] += 1
            continue
        for (net, layer), members in groups.items():
            if net != p.GetNetCode() or not p.IsOnLayer(layer):
                continue
            shape = p.GetEffectiveShape(layer)
            hits = [t.m_Uuid.AsString() for t in members
                    if shape.Collide(t.GetEffectiveShape(layer), 0)]
            if hits:
                data['pad_contacts'].append({'ref': fp.GetReference(), 'pad': p.GetNumber(),
                    'center': xy(p.GetPosition()), 'net': p.GetNetname(),
                    'layer': b.GetLayerName(layer), 'tracks': hits})
print('ROUTING_GEOMETRY=' + json.dumps(data))
'''


def read_geometry(pcb: Path, toolchain=None) -> dict:
    toolchain = toolchain or discover_toolchain(Path(__file__).resolve().parents[3])
    if toolchain.kipython is None:
        raise ValueError('KiCad Python is required for native pad-contact inspection')
    result = subprocess.run([str(toolchain.kipython), '-I', '-c', _READ, str(pcb)],
                            capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=60, check=False)
    if result.returncode:
        raise RuntimeError(f'native routing inspection failed: {result.stderr or result.stdout}')
    line = next((line for line in result.stdout.splitlines()
                 if line.startswith('ROUTING_GEOMETRY=')), None)
    if line is None:
        raise ValueError('native routing inspection omitted its result')
    return json.loads(line.partition('=')[2])


def point_segment_distance(point, start, end) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    denominator = dx * dx + dy * dy
    if denominator == 0:
        return math.dist(point, start)
    fraction = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy)
                            / denominator))
    return math.dist(point, (start[0] + fraction * dx, start[1] + fraction * dy))


def analyze_geometry(data: dict) -> list[dict]:
    """Geometry thresholds are drawing heuristics, never clearance/current limits."""
    findings = []
    groups = defaultdict(list)
    by_id = {track['id']: track for track in data['tracks']}
    for track in data['tracks']:
        if track['net']:
            groups[(track['net'], track['layer'])].append(track)
    for group in groups.values():
        for track in sorted(group, key=lambda item: item['id']):
            length = math.dist(track['start'], track['end'])
            base = {'net': track['net'], 'layer': track['layer'], 'track': track['id'],
                    'at_mm': track['start'], 'locked': track.get('locked', False)}
            covered = None
            for other in group:
                if other['id'] == track['id'] or other['width'] < track['width']:
                    continue
                radius = (other['width'] - track['width']) / 2
                # A capsule is convex: containment of both endpoint disks proves
                # containment of the complete smaller straight-track capsule.
                distances = [point_segment_distance(p, other['start'], other['end'])
                             for p in (track['start'], track['end'])]
                if max(distances) > radius + 1e-9:
                    continue
                other_length = math.dist(other['start'], other['end'])
                if (abs(other_length - length) < 1e-9
                        and abs(other['width'] - track['width']) < 1e-9
                        and other['id'] > track['id']):
                    continue  # Report identical duplicates once, deterministically.
                covered = other
                break
            if covered is not None:
                findings.append({**base, 'code': 'covered_track', 'covering_track': covered['id'],
                                 'length_mm': length, 'width_mm': track['width']})
            elif length < 1e-9:
                findings.append({**base, 'code': 'zero_length_track'})
            elif length < 0.25 and length < track['width']:
                findings.append({**base, 'code': 'short_track', 'length_mm': length,
                                 'width_mm': track['width']})
    for contact in data['pad_contacts']:
        tracks = [by_id[identity] for identity in contact['tracks']]
        if not tracks:
            continue
        distances = [point_segment_distance(contact['center'], t['start'], t['end']) for t in tracks]
        if min(distances) > 0.05:
            findings.append({'code': 'off_center_pad_contact', 'ref': contact['ref'],
                             'pad': contact['pad'], 'net': contact['net'], 'layer': contact['layer'],
                             'at_mm': contact['center'], 'offset_mm': min(distances),
                             'tracks': contact['tracks']})
    return findings


def inspect_routing(pcb: Path, toolchain=None) -> dict:
    data = read_geometry(pcb, toolchain)
    findings = analyze_geometry(data)
    return {'findings': findings, 'counts': dict(Counter(f['code'] for f in findings)),
            'straight_tracks': len(data['tracks']), 'arcs_not_audited': data['arcs'],
            'custom_pads_not_audited': data['custom_pads_skipped']}


def describe(finding: dict) -> str:
    where = f"{finding['net']} on {finding['layer']} at ({finding['at_mm'][0]:.4f}, {finding['at_mm'][1]:.4f}) mm"
    if finding['code'] == 'off_center_pad_contact':
        return (f"{finding['ref']}.{finding['pad']}: track copper contacts the pad, but its centreline "
                f"misses the pad anchor by {finding['offset_mm']:.3f} mm; {where}. "
                'Inspect the intended pad entry; this is not an electrical-open finding.')
    if finding['code'] == 'covered_track':
        return (f"Track {finding['track']} is fully covered by same-net track {finding['covering_track']}; "
                f'{where}. Inspect redundant/overlaid routing before cleanup.')
    return (f"Track {finding['track']}: {finding['code'].replace('_', ' ')}; {where}. "
            'Inspect for a patched join; short pad escapes can be intentional.')


class RoutingTopologyCheck:
    check_id = 'routing_topology'
    scope = SCOPE

    def run(self, project) -> CheckResult:
        report = inspect_routing(project.pcb_path)
        detail = (f"Inspected {report['straight_tracks']} straight tracks: {report['counts'] or 'no findings'}. "
                  f"Excluded {report['arcs_not_audited']} arcs and {report['custom_pads_not_audited']} custom/offset pads. "
                  'Native DRC remains the connectivity gate; copper was not changed.')
        return CheckResult(self.check_id, True, detail, self.scope,
                           advisories=tuple(describe(f) for f in report['findings']))
