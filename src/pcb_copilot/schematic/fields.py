"""Place component fields in free lead directions without moving symbols."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from kicad_claude.adapters import sch_io
from kicad_claude.utils.geometry import rotate_xy

DOCS = Path(__file__).resolve().parents[3] / 'docs'
if str(DOCS) not in sys.path:
    sys.path.insert(0, str(DOCS))
_helpers = importlib.import_module('schematic_layout_helpers')


def _outline_points(ed, definition):
    """Include common body outlines that may extend beyond the pin box.

    This is not a complete font/curve bounds engine. Pin extents remain the
    fallback; explicit rectangles, polylines and circles extend that envelope.
    """
    for unit in ed.find_children(definition, 'symbol'):
        for graphic in unit[2:]:
            if not isinstance(graphic, list) or not graphic:
                continue
            kind = str(graphic[0])
            if kind == 'rectangle':
                for key in ('start', 'end'):
                    point = ed.find_child(graphic, key)
                    yield float(point[1]), float(point[2])
            elif kind == 'polyline':
                points = ed.find_child(graphic, 'pts')
                for point in ed.find_children(points, 'xy'):
                    yield float(point[1]), float(point[2])
            elif kind == 'circle':
                center = ed.find_child(graphic, 'center')
                radius = float(ed.find_child(graphic, 'radius')[1])
                for dx, dy in ((-radius, -radius), (-radius, radius),
                               (radius, -radius), (radius, radius)):
                    yield float(center[1]) + dx, float(center[2]) + dy


def place_component_fields(ed, tree, symbols, labels, ref: str) -> None:
    """Keep fields off the body and outward pin lanes in MCP coordinates.

    This is local placement, not a sheet-wide text collision guarantee.
    Capacitor/resistor fields already use the measured passive placement.
    """
    if ref.startswith('#'):
        return
    symbol = ed.find_symbol_by_reference(tree, ref)
    if symbol is None:
        raise KeyError(f'no symbol with reference {ref!r}')
    lib_id = ed.find_child(symbol, 'lib_id')
    if lib_id and str(lib_id[1]) in {'Device:C', 'Device:R'}:
        return
    box = symbols.bbox(ref)
    if box is None:
        return
    x, y = symbols._origin(ref)
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    definition = ed.find_lib_symbol_def(tree, lib_id[1])
    rotation = float(ed.find_child(symbol, 'at')[3])
    for px, py in _outline_points(ed, definition):
        dx, dy = rotate_xy(px, py, rotation)
        x0, y0 = min(x0, x + dx), min(y0, y + dy)
        x1, y1 = max(x1, x + dx), max(y1, y + dy)
    positions = [tuple(pin['position_mm']) for pin in ed.list_pins_for_symbol(tree, ref)]
    directions = {
        _helpers.pin_exit_orientation_for_symbol(px, py, x, y, positions)
        for px, py in positions
    }
    clearance, separation = 5.08, 2.54
    justification = None
    if directions <= {'left', 'right'}:
        reference = (x, y1 + clearance)
        value = (x, y0 - clearance)
    elif directions <= {'up', 'down'}:
        reference = (x1 + clearance, y + separation / 2)
        value = (x1 + clearance, y - separation / 2)
        justification = 'left'
    elif 'up' not in directions:
        reference = (x, y1 + clearance + separation)
        value = (x, y1 + clearance)
    elif 'down' not in directions:
        reference = (x, y0 - clearance)
        value = (x, y0 - clearance - separation)
    else:
        # A three/four-sided package has no free horizontal text band.
        # Use a side when free, otherwise the corner outside both pin spans.
        side_x = x0 - clearance if 'right' in directions and 'left' not in directions else x1 + clearance
        justification = 'right' if side_x < x else 'left'
        center_y = y if directions != {'left', 'right', 'up', 'down'} else y1 + clearance
        reference = (side_x, center_y + separation / 2)
        value = (side_x, center_y - separation / 2)
    labels.set_property_pos(ref, 'Reference', *reference)
    labels.set_property_pos(ref, 'Value', *value)
    # Side fields must extend away from the body, even for long part names.
    # Clear old justification for centered fields rather than inheriting a
    # library's unrelated alignment.
    for prop in ed.find_children(symbol, 'property'):
        if prop[1] not in {'Reference', 'Value'}:
            continue
        effects = ed.find_child(prop, 'effects')
        old = ed.find_child(effects, 'justify')
        if old is not None:
            effects.remove(old)
        if justification:
            effects.append([sch_io.sym('justify'), sch_io.sym(justification)])
