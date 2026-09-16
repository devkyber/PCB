import re

import pytest

from pcb_copilot.schematic.quality import (
    analyse_schematic,
    count_global_labels,
    no_symbol_or_text_overlap,
)
from pcb_copilot.schematic.wiring import (
    PinRef,
    WireCorridor,
    connect_local,
)


def test_renderer_uses_wires_inside_blocks_and_labels_between_blocks(rendered):
    metrics = analyse_schematic(rendered)

    assert metrics.junction_count >= 1
    assert metrics.drawn_connection_ratio >= 0.60
    assert count_global_labels(rendered, "SENSOR_OUT") == 2
    assert no_symbol_or_text_overlap(rendered)


def test_renderer_uses_graphical_power_symbols_and_complete_title(rendered):
    text = rendered.read_text(encoding="utf-8")
    metrics = analyse_schematic(rendered)

    assert '(lib_id "power:GND")' in text
    assert metrics.title_complete


def test_all_wire_endpoints_are_on_kicad_grid(rendered):
    text = rendered.read_text(encoding="utf-8")
    points = [
        (float(x), float(y))
        for x, y in re.findall(r"\(xy\s+([-0-9.]+)\s+([-0-9.]+)\)", text)
    ]
    assert points
    assert all(abs(value / 1.27 - round(value / 1.27)) < 0.002 for point in points for value in point)


class FakeEditor:
    def __init__(self):
        self.positions = {("A", "1"): (0.0, 0.0), ("B", "1"): (10.0, 10.0)}
        self.segments = []

    def pin_position(self, pin):
        return self.positions[(pin.ref, pin.pin)]

    def add_segment(self, segment):
        self.segments.append(segment)


def test_local_connection_rejects_route_outside_corridor():
    editor = FakeEditor()
    with pytest.raises(ValueError, match="corridor"):
        connect_local(
            editor,
            PinRef("A", "1"),
            PinRef("B", "1"),
            WireCorridor(0, 0, 5, 5),
            net="DATA",
        )
