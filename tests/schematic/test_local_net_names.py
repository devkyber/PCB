import importlib

import pytest

from pcb_copilot.schematic.io import load_schematic_intent
from pcb_copilot.schematic.wiring import (
    PinRef,
    StubCrossingError,
    WireCorridor,
    WireSegment,
    connect_local,
)


def test_local_wire_names_survive_kicad_export(rendered, repo_root):
    # The renderer makes the repository's existing extractor importable.
    nets = importlib.import_module('extract_netmap').extract(rendered)['nets']
    assert nets['J1']['1'] == 'INPUT'
    assert nets['R1']['1'] == 'INPUT'
    assert nets['R3']['1'] == 'INPUT'
    intent = load_schematic_intent(repo_root / 'tests/fixtures/schematic/two-block.yaml')
    assert nets == {c.ref: {pin: connection.net for pin, connection in c.pins.items()}
                    for c in intent.components}


def test_unroutable_connection_adds_no_partial_wires():
    class Editor:
        def __init__(self):
            self.segments = [WireSegment((5, -1), (5, 11), 'OTHER')]

        def pin_position(self, pin):
            return (0, 0) if pin.ref == 'A' else (10, 10)

        def add_segment(self, segment):
            self.segments.append(segment)

    editor = Editor()
    before = list(editor.segments)
    with pytest.raises(StubCrossingError):
        connect_local(editor, PinRef('A', '1'), PinRef('B', '1'),
                      WireCorridor(0, 0, 10, 10), net='INPUT')
    assert editor.segments == before
