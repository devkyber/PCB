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
    assert re.search(r'\(date "\d{4}-\d{2}-\d{2}"\)', text)


def test_all_wire_endpoints_are_on_kicad_grid(rendered):
    text = rendered.read_text(encoding="utf-8")
    points = [
        (float(x), float(y))
        for x, y in re.findall(r"\(xy\s+([-0-9.]+)\s+([-0-9.]+)\)", text)
    ]
    assert points
    assert all(abs(value / 1.27 - round(value / 1.27)) < 0.002 for point in points for value in point)


def test_renderer_checks_real_symbol_pins_even_without_inventory(project_copy, repo_root):
    from pcb_copilot.drafts import create_draft
    from pcb_copilot.models import DraftKind
    from pcb_copilot.project import load_project
    from pcb_copilot.schematic.io import load_schematic_intent
    from pcb_copilot.schematic.render import render_schematic_draft

    project = load_project(project_copy)
    intent = load_schematic_intent(repo_root / 'tests/fixtures/schematic/two-block.yaml')
    missing = intent.components[0].model_copy(update={
        'pin_inventory': frozenset(), 'pins': {'1': intent.components[0].pins['1']},
    })
    intent = intent.model_copy(update={'components': (missing, *intent.components[1:])})
    draft = create_draft(project, DraftKind.SCHEMATIC)
    with pytest.raises(ValueError, match='pin inventory mismatch'):
        render_schematic_draft(project, intent, draft)
    assert not draft.root.exists()


def test_pin_stub_uses_symbol_origin_not_pin_column_center(rendered):
    from kicad_claude.adapters import sch_editor as ed
    from kicad_claude.adapters import sch_io

    tree = sch_io.parse_file(rendered)
    # This connector's lone ground pin exits left; its power stub must not
    # double back through the connector body when the pin box is asymmetric.
    px, py = ed.get_pin_position(tree, 'J1', '2')
    wires = [ed.find_child(n, 'pts') for n in tree if isinstance(n, list) and str(n[0]) == 'wire']
    point = (px, ed.page_height_mm(tree) - py)
    touching = [pts for pts in wires if any(abs(float(p[1]) - point[0]) < 0.01
                and abs(float(p[2]) - point[1]) < 0.01 for p in pts[1:])]
    assert touching
    assert all(float(p[1]) <= px + 0.01 for pts in touching for p in pts[1:])


def test_block_headings_are_rendered_above_components(rendered):
    from kicad_claude.adapters import sch_io

    tree = sch_io.parse_file(rendered)
    texts = {n[1]: n for n in tree if isinstance(n, list) and str(n[0]) == 'text'}
    assert {'Power and input', 'Sensor and output'} <= texts.keys()
    assert float(sch_io.find_child(texts['Power and input'], 'at')[2]) < 30


def test_rows_leave_rail_space_below_tall_symbol(repo_root, tmp_path):
    import shutil

    from pcb_copilot.drafts import create_draft
    from pcb_copilot.models import DraftKind
    from pcb_copilot.project import load_project
    from pcb_copilot.schematic.io import load_schematic_intent
    from pcb_copilot.schematic.models import SchematicIntent
    from pcb_copilot.schematic.render import (
        SymbolPlacer,
        ed,
        render_schematic_draft,
        sch_io,
    )

    root = tmp_path / 'tms-v3'
    shutil.copytree(repo_root / 'projects/tms-v3', root, ignore=shutil.ignore_patterns('.pcb-copilot'))
    original = load_schematic_intent(root / 'schematic-intent.yaml')
    parts = []
    for ref in ('U2', 'C1'):
        part = next(c for c in original.components if c.ref == ref)
        parts.append(part.model_copy(update={'block': 'test', 'pins': {
            p: conn.model_copy(update={'style': 'label', 'net': f'{ref}_{p}'}) for p, conn in part.pins.items()
        }}))
    intent = SchematicIntent(schema_version=1, title='Tall chip fixture', revision='T1',
                             sheets=[{'id': 'main', 'title': 'Main', 'page': 'A3'}],
                             blocks=[{'id': 'test', 'title': 'Test', 'sheet': 'main', 'flow_order': 0}],
                             components=parts)
    project = load_project(root)
    path = render_schematic_draft(project, intent, create_draft(project, DraftKind.SCHEMATIC))
    tree = sch_io.parse_file(path)
    geometry = SymbolPlacer(ed, tree)
    chip, cap = geometry.bbox('U2'), geometry.bbox('C1')
    assert chip[1] - cap[3] >= 15, 'tall chip needs clearance for rail stubs and fields'
    assert chip[3] <= ed.page_height_mm(tree) - 30, 'chip must clear the heading'


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
