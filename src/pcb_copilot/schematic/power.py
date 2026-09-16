"""Grid-based spacing hints for crowded horizontal power-pin columns."""

from __future__ import annotations

import sys
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[3] / 'docs'
if str(_DOCS) not in sys.path:
    sys.path.insert(0, str(_DOCS))

from schematic_layout_helpers import (
    DEFAULT_STUB_MM,
    GRID_MM,
    pin_exit_orientation_for_symbol,
)


def power_stub_length(
    ed, tree: list, ref: str, pin: str, origin: tuple[float, float]
) -> float | None:
    """Alternate horizontal-column stubs by eight grid steps (10.16 mm).

    This is a spacing hint, not a glyph collision solver. Pass the result to
    LabelPlacer.auto so its existing crossing checks still govern the wire.
    One/two-pin parts and vertical exits retain the normal power stub policy.
    Nonadjacent glyphs and nearby signal text/wires still need visual review.
    """
    positions = [tuple(item['position_mm']) for item in ed.list_pins_for_symbol(tree, ref)]
    if len(positions) <= 2:
        return None
    x, y = ed.get_pin_position(tree, ref, pin)
    direction = pin_exit_orientation_for_symbol(x, y, *origin, positions)
    if direction not in {'left', 'right'}:
        return None
    column = sorted({round(py, 3) for px, py in positions if abs(px - x) < 0.05})
    if len(column) < 2:
        return None
    rank = column.index(round(y, 3))
    # Four grid steps separate glyph centers but can put the shorter rail's
    # outward Value text directly over its neighbor's ground triangle.
    # Eight steps clear both stock glyph and short rail-name envelopes.
    return round(DEFAULT_STUB_MM + (rank % 2) * 8 * GRID_MM, 3)
