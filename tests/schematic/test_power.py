"""Spacing regressions using the accepted IMU symbol, without file mutations."""

import pytest
from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.utils.geometry import mcp_to_kicad_xy
from kicad_claude.utils.kicad_paths import find_symbol_lib_dirs
from schematic_layout_helpers import (
    GRID_MM,
    LabelPlacer,
    StubCrossingError,
    SymbolPlacer,
)

from pcb_copilot.schematic.power import power_stub_length


@pytest.fixture
def imu_tree(repo_root):
    return sch_io.parse_file(
        repo_root / 'projects/imu-icm42688/imu-icm42688.kicad_sch'
    )


@pytest.mark.parametrize('pins', [('8', '9'), ('5', '6')])
def test_adjacent_imu_power_endpoints_have_horizontal_glyph_clearance(imu_tree, pins):
    origin = SymbolPlacer(ed, imu_tree)._origin('U1')
    labels = LabelPlacer(ed, imu_tree)
    endpoints = []
    for pin, net in zip(pins, ('+3V3', 'GND')):
        length = power_stub_length(ed, imu_tree, 'U1', pin, origin)
        assert length is not None
        assert length / GRID_MM == pytest.approx(round(length / GRID_MM))
        endpoint = labels.auto('U1', pin, net, *origin, stub_mm=length)
        assert endpoint[1] == ed.get_pin_position(imu_tree, 'U1', pin)[1]
        endpoints.append(endpoint)
    assert abs(endpoints[0][0] - endpoints[1][0]) >= 5.08 - 1e-6


@pytest.mark.parametrize('ref,pin', [('C1', '1'), ('C1', '2'), ('TP1', '1')])
def test_one_and_two_pin_symbols_keep_default_power_stubs(imu_tree, ref, pin):
    origin = SymbolPlacer(ed, imu_tree)._origin(ref)
    assert power_stub_length(ed, imu_tree, ref, pin, origin) is None


def test_vertical_ic_pins_keep_default_power_stubs(imu_tree):
    # Rotate only this in-memory tree; the accepted file remains read-only.
    symbol = ed.find_symbol_by_reference(imu_tree, 'U1')
    ed.find_child(symbol, 'at')[3] = 90
    origin = SymbolPlacer(ed, imu_tree)._origin('U1')
    assert power_stub_length(ed, imu_tree, 'U1', '8', origin) is None


def test_every_imu_column_stub_is_positive_and_grid_aligned(imu_tree):
    origin = SymbolPlacer(ed, imu_tree)._origin('U1')
    for item in ed.list_pins_for_symbol(imu_tree, 'U1'):
        length = power_stub_length(ed, imu_tree, 'U1', item['number'], origin)
        assert length is not None and length > 0
        assert length / GRID_MM == pytest.approx(round(length / GRID_MM))


def test_staggered_stub_still_refuses_an_electrical_crossing(imu_tree):
    origin = SymbolPlacer(ed, imu_tree)._origin('U1')
    length = power_stub_length(ed, imu_tree, 'U1', '8', origin)
    labels = LabelPlacer(ed, imu_tree)
    point = ed.get_pin_position(imu_tree, 'U1', '8')
    # A foreign net already touching this pin must block every exit direction.
    labels._segments.append((point, point, 'TEST', '1', 'FOREIGN_NET'))
    with pytest.raises(StubCrossingError):
        labels.auto('U1', '8', '+3V3', *origin, stub_mm=length)


@pytest.mark.parametrize('board,rails', [
    ('imu-icm42688', [('8', '+3V3'), ('9', 'GND')]),
    ('imu-icm42688', [('7', 'GND'), ('6', 'GND')]),
])
def test_power_value_text_clears_adjacent_real_power_glyph(repo_root, board, rails):
    """Catch a stagger that clears pins but puts a rail name on a triangle."""
    imu_tree = sch_io.parse_file(repo_root / f'projects/{board}/{board}.kicad_sch')
    library = find_symbol_lib_dirs()[0] / 'power.kicad_sym'
    placed = []

    def place(library_name, name, ref, value, x, y, rotation):
        definition = ed.fetch_symbol_def(library, name)
        ed.add_symbol(
            imu_tree, qualified_lib_id=f'{library_name}:{name}', reference=ref,
            value=value, x_mm=x, y_mm=y, rotation=rotation,
            sym_def_node=definition, project_name='spacing-test',
        )
        placed.append((ref, definition))

    labels = LabelPlacer(ed, imu_tree, place_symbol=place)
    origin = SymbolPlacer(ed, imu_tree)._origin('U1')
    for pin, net in rails:
        labels.auto('U1', pin, net, *origin,
                    stub_mm=power_stub_length(ed, imu_tree, 'U1', pin, origin))

    def points(node):
        for child in node:
            if isinstance(child, list):
                if str(child[0]) == 'xy':
                    yield float(child[1]), float(child[2])
                else:
                    yield from points(child)

    text_boxes, glyph_boxes = [], []
    for ref, definition in placed:
        node = ed.find_symbol_by_reference(imu_tree, ref)
        value = next(p for p in ed.find_children(node, 'property') if p[1] == 'Value')
        at = ed.find_child(value, 'at')
        x, y = mcp_to_kicad_xy(float(at[1]), float(at[2]), ed.page_height_mm(imu_tree))
        font = ed.find_child(ed.find_child(value, 'effects'), 'font')
        size = ed.find_child(font, 'size')
        # Conservative text envelope from actual placed font and string;
        # centered stock Value fields have no left/right justification.
        half_width = len(value[2]) * float(size[1]) / 2
        half_height = float(size[2]) / 2
        text_boxes.append((x-half_width, y-half_height, x+half_width, y+half_height))
        ox, oy = ed.get_pin_position(imu_tree, ref, '1')
        vertices = list(points(definition))
        assert vertices, 'stock power glyph must expose its actual polyline'
        glyph_boxes.append((ox+min(x for x, y in vertices), oy+min(y for x, y in vertices),
                            ox+max(x for x, y in vertices), oy+max(y for x, y in vertices)))

    for text, glyph in [(text_boxes[0], glyph_boxes[1]), (text_boxes[1], glyph_boxes[0]),
                        (glyph_boxes[0], glyph_boxes[1])]:
        # Require positive breathing room beyond the actual glyph envelope.
        assert (text[2] + 0.25 <= glyph[0] or glyph[2] + 0.25 <= text[0]
                or text[3] + 0.25 <= glyph[1] or glyph[3] + 0.25 <= text[1])
