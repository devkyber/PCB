"""Read-only KiCad-Python extraction for the example explorer.

The connectivity map deliberately omits filled zones, arcs and custom pads.
Native copper images remain the complete geometric inspection surface.
"""

from __future__ import annotations

import json
import sys

import pcbnew


def mm(value):
    return round(pcbnew.ToMM(value), 6)


def point(value):
    return [mm(value.x), mm(value.y)]


def extract(path):
    board = pcbnew.LoadBoard(path)
    box = board.GetBoardEdgesBoundingBox()
    parts = []
    for footprint in board.GetFootprints():
        pads = []
        for pad in footprint.Pads():
            drill = pad.GetDrillSize()
            pads.append({'number': str(pad.GetNumber()), 'net': str(pad.GetNetname()).lstrip('/'),
                         'position': point(pad.GetPosition()), 'size': point(pad.GetSize()),
                         'drill': point(drill), 'angle': pad.GetOrientationDegrees(),
                         'shape': str(pad.GetShape()),
                         'layers': [name for layer, name in ((pcbnew.F_Cu, 'top'), (pcbnew.B_Cu, 'bottom'))
                                    if pad.IsOnLayer(layer)]})
        parts.append({'reference': footprint.GetReference(), 'value': footprint.GetValue(),
                      'footprint': str(footprint.GetFPID().GetLibItemName()),
                      'position': point(footprint.GetPosition()), 'pads': pads})
    tracks, vias, omitted_arcs = [], [], 0
    for track in board.GetTracks():
        if isinstance(track, pcbnew.PCB_VIA):
            vias.append({'position': point(track.GetPosition()), 'width': mm(track.GetWidth(pcbnew.F_Cu)),
                         'drill': mm(track.GetDrillValue()), 'net': str(track.GetNetname()).lstrip('/')})
        elif isinstance(track, pcbnew.PCB_ARC):
            omitted_arcs += 1
        else:
            tracks.append({'start': point(track.GetStart()), 'end': point(track.GetEnd()),
                           'width': mm(track.GetWidth()), 'net': str(track.GetNetname()).lstrip('/'),
                           'side': 'top' if track.GetLayer() == pcbnew.F_Cu else 'bottom'})
    return {'kicad_version': pcbnew.GetBuildVersion(),
            'bounds': [mm(box.GetX()), mm(box.GetY()), mm(box.GetWidth()), mm(box.GetHeight())],
            'components': sorted(parts, key=lambda item: item['reference']),
            'tracks': tracks, 'vias': vias, 'omitted_arcs': omitted_arcs,
            'scope': 'Native pad centers and straight tracks; zones, arcs and exact custom-pad shapes omitted. '
                     'Not a clearance, current-capacity or mechanical inspection.'}


if __name__ == '__main__':
    print(json.dumps(extract(sys.argv[1])))
