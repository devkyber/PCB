"""Board migration must preserve the accepted circuit, including mechanical refs."""

import json
from collections import defaultdict

import pytest
from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.utils.geometry import kicad_to_mcp_xy

from pcb_copilot.schematic.io import load_schematic_intent


def test_baro_intent_preserves_accepted_components_and_connectivity(repo_root):
    root = repo_root / 'projects/baro-bmp390'
    intent = load_schematic_intent(root / 'schematic-intent.yaml')
    baseline = json.loads((root / 'netmap.json').read_text(encoding='utf-8'))
    assert {c.ref: {p: v.net for p, v in c.pins.items()}
            for c in intent.components if c.pins and not c.ref.startswith('#')} == baseline['nets']
    source = sch_io.parse_file(root / 'baro-bmp390.kicad_sch')
    actual = {ed.get_symbol_property(s, 'Reference'): s for s in ed.iter_instance_symbols(source)
              if not ed.get_symbol_property(s, 'Reference').startswith('#PWR')}
    assert {c.ref for c in intent.components} == set(actual)
    for component in intent.components:
        symbol = actual[component.ref]
        assert component.value == ed.get_symbol_property(symbol, 'Value')
        assert component.footprint == (ed.get_symbol_property(symbol, 'Footprint') or '~')
        assert component.symbol == str(ed.find_child(symbol, 'lib_id')[1])
    assert {c.ref: [n.pin for n in c.no_connects] for c in intent.components if c.no_connects} == {
        'H1': ['1'], 'H2': ['1'],
    }
    assert next(c for c in intent.components if c.ref == 'U1').pin_map_evidence_id is not None
    assert next(c for c in intent.components if c.ref == 'J1').pin_map_evidence_id is None


@pytest.mark.slow
def test_baro_draft_preserves_circuit_and_avoids_title_block(project_copy):
    from pcb_copilot.project import load_project
    from pcb_copilot.schematic.commands import draft_schematic

    project = load_project(project_copy)
    before = {p: p.read_bytes() for p in project_copy.glob('*.kicad_*')}
    report = draft_schematic(project, project_copy / 'schematic-intent.yaml')
    assert report['exit_code'] == 0, report['findings']
    assert any(f['reference'] == 'J1' and f['severity'] == 'review' for f in report['findings'])
    tree = sch_io.parse_file(report['schematic'])
    for symbol in ed.iter_instance_symbols(tree):
        if ed.get_symbol_property(symbol, 'Reference').startswith('#'):
            continue
        at = ed.find_child(symbol, 'at')
        assert 20 <= float(at[2]) <= 145, 'components must stay above the A4 title area'
    metrics = json.loads(__import__('pathlib').Path(report['metrics']).read_text())['sheets'][0]
    assert metrics['junction_count'] > 0
    assert all(p.read_bytes() == data for p, data in before.items())


def test_local_wire_does_not_run_through_sensor_body(project_copy):
    from pcb_copilot.drafts import create_draft
    from pcb_copilot.models import DraftKind
    from pcb_copilot.project import load_project
    from pcb_copilot.schematic.render import render_schematic_draft

    project = load_project(project_copy)
    intent = load_schematic_intent(project_copy / 'schematic-intent.yaml')
    path = render_schematic_draft(project, intent, create_draft(project, DraftKind.SCHEMATIC))
    tree = sch_io.parse_file(path)
    pins = [p['position_mm'] for p in ed.list_pins_for_symbol(tree, 'U1')]
    xmin, xmax = min(p[0] for p in pins), max(p[0] for p in pins)
    ymin, ymax = min(p[1] for p in pins), max(p[1] for p in pins)
    for node in tree:
        if not isinstance(node, list) or str(node[0]) != 'wire':
            continue
        points = [(float(p[1]), ed.page_height_mm(tree) - float(p[2]))
                  for p in ed.find_child(node, 'pts')[1:]]
        a, b = points
        if abs(a[1] - b[1]) < 0.001:
            assert not (ymin + 0.01 < a[1] < ymax - 0.01
                        and min(a[0], b[0]) < xmax - 0.01 and max(a[0], b[0]) > xmin + 0.01), points
        else:
            assert not (xmin + 0.01 < a[0] < xmax - 0.01
                        and min(a[1], b[1]) < ymax - 0.01 and max(a[1], b[1]) > ymin + 0.01), points


@pytest.mark.slow
def test_imu_int1_wire_avoids_generated_ground_value_text(repo_root, tmp_path):
    """Use KiCad's PDF glyph rectangle, independent of the envelope helper."""
    import shutil

    import pymupdf

    from pcb_copilot.project import load_project
    from pcb_copilot.schematic.commands import draft_schematic
    from pcb_copilot.schematic.fields import text_field_envelope

    root = tmp_path / 'imu-icm42688'
    shutil.copytree(repo_root / 'projects/imu-icm42688', root,
                    ignore=shutil.ignore_patterns('.pcb-copilot'))
    project = load_project(root)
    accepted = {path: path.read_bytes() for path in
                (project.schematic_path, project.pcb_path, project.netmap_path)}
    report = draft_schematic(project, root / 'schematic-intent.yaml')
    assert report['exit_code'] == 0, report['findings']

    tree = sch_io.parse_file(report['schematic'])
    page_height = ed.page_height_mm(tree)

    def key(point):
        return tuple(round(float(value), 3) for value in point)

    wires = []
    for node in ed.find_children(tree, 'wire'):
        points = [kicad_to_mcp_xy(float(point[1]), float(point[2]), page_height)
                  for point in ed.find_child(node, 'pts')[1:]]
        wires.append((key(points[0]), key(points[1])))

    ground_pin = key(ed.get_pin_position(tree, 'U1', '6'))
    ground_stub = next(segment for segment in wires if ground_pin in segment)
    ground_end = ground_stub[ground_stub.index(ground_pin) - 1]
    power_symbols = []
    for symbol in ed.iter_instance_symbols(tree):
        ref = ed.get_symbol_property(symbol, 'Reference')
        if ref.startswith('#PWR') and ed.get_symbol_property(symbol, 'Value') == 'GND':
            power_symbols.append((ref, key(ed.get_pin_position(tree, ref, '1'))))
    ground_ref = next(ref for ref, point in power_symbols if point == ground_end)
    ground_symbol = ed.find_symbol_by_reference(tree, ground_ref)
    value = next(prop for prop in ed.find_children(ground_symbol, 'property')
                 if prop[1] == 'Value')
    value_at = ed.find_child(value, 'at')
    value_anchor = kicad_to_mcp_xy(float(value_at[1]), float(value_at[2]), page_height)

    with pymupdf.open(report['pdf']) as document:
        page = document[0]
        scale_x = page.rect.width / 297.0
        scale_y = page.rect.height / page_height
        anchor_pdf = pymupdf.Point(value_anchor[0] * scale_x,
                                   (page_height - value_anchor[1]) * scale_y)
        rectangles = page.search_for('GND')
        text_rect = next(rect for rect in rectangles if rect.contains(anchor_pdf))
        text_box = (
            text_rect.x0 / scale_x,
            page_height - text_rect.y1 / scale_y,
            text_rect.x1 / scale_x,
            page_height - text_rect.y0 / scale_y,
        )

    envelope = text_field_envelope(ed, tree, ground_ref, 'Value')
    assert envelope is not None
    assert envelope.x_min <= text_box[0]
    assert envelope.y_min <= text_box[1]
    assert envelope.x_max >= text_box[2]
    assert envelope.y_max >= text_box[3]

    by_point = defaultdict(list)
    for index, segment in enumerate(wires):
        for point in segment:
            by_point[point].append(index)
    pending = [key(ed.get_pin_position(tree, 'U1', '4'))]
    visited_points = set(pending)
    int1_segments = set()
    while pending:
        point = pending.pop()
        for index in by_point[point]:
            int1_segments.add(index)
            for endpoint in wires[index]:
                if endpoint not in visited_points:
                    visited_points.add(endpoint)
                    pending.append(endpoint)
    assert key(ed.get_pin_position(tree, 'TP3', '1')) in visited_points

    x_min, y_min, x_max, y_max = text_box

    def intersects_text(segment):
        (ax, ay), (bx, by) = segment
        return not (max(ax, bx) < x_min or min(ax, bx) > x_max
                    or max(ay, by) < y_min or min(ay, by) > y_max)

    assert not any(intersects_text(wires[index]) for index in int1_segments)
    assert all(path.read_bytes() == payload for path, payload in accepted.items())


@pytest.mark.slow
@pytest.mark.parametrize('board,pages', [('imu-icm42688', 1), ('gnss-neom9n', 1), ('tms-v3', 7)])
def test_real_board_draft_round_trip_preserves_sources(repo_root, tmp_path, board, pages):
    import shutil
    from pathlib import Path

    import pymupdf

    from pcb_copilot.project import load_project
    from pcb_copilot.schematic.commands import draft_schematic

    root = tmp_path / board
    shutil.copytree(repo_root / 'projects' / board, root,
                    ignore=shutil.ignore_patterns('.pcb-copilot'))
    project = load_project(root)
    before = {path: path.read_bytes() for path in
              (project.schematic_path, project.pcb_path, project.netmap_path)}
    report = draft_schematic(project, root / 'schematic-intent.yaml')
    assert report['exit_code'] == 0, report['findings']
    assert report['human_review'] == 'pending'
    with pymupdf.open(report['pdf']) as pdf:
        assert len(pdf) == pages
    metrics = json.loads(Path(report['metrics']).read_text(encoding='utf-8'))['sheets']
    assert sum(sheet['junction_count'] for sheet in metrics) > 0
    assert all(sheet['title_complete'] for sheet in metrics)
    assert all(path.read_bytes() == payload for path, payload in before.items())
