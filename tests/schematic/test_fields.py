"""Field placement must respect the real lead directions of accepted symbols."""

import copy

import pytest
from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.utils.geometry import kicad_to_mcp_xy

from pcb_copilot.schematic.render import LabelPlacer, SymbolPlacer
from tests.board_fixtures import board_source


@pytest.fixture
def gnss_fields(repo_root):
    tree = sch_io.parse_file(board_source(repo_root, 'gnss-neom9n') / 'gnss-neom9n.kicad_sch')
    symbols = SymbolPlacer(ed, tree)
    labels = LabelPlacer(ed, tree, symbols=symbols)
    return tree, symbols, labels


def _fields(tree, ref):
    symbol = ed.find_symbol_by_reference(tree, ref)
    result = {}
    for field in ed.find_children(symbol, 'property'):
        if field[1] in {'Reference', 'Value'}:
            at = ed.find_child(field, 'at')
            result[field[1]] = kicad_to_mcp_xy(at[1], at[2], ed.page_height_mm(tree))
    return result


def test_battery_fields_stay_beside_vertical_leads(gnss_fields):
    from pcb_copilot.schematic.fields import place_component_fields

    tree, symbols, labels = gnss_fields
    place_component_fields(ed, tree, symbols, labels, 'BT1')
    fields = _fields(tree, 'BT1')
    box = symbols.bbox('BT1')
    for x, _y in fields.values():
        assert x >= box[2] + 5.08 - 0.001
    assert abs(fields['Reference'][1] - fields['Value'][1]) >= 2.54 - 0.001


def test_coax_fields_stay_above_downward_ground_lead(gnss_fields):
    from pcb_copilot.schematic.fields import place_component_fields

    tree, symbols, labels = gnss_fields
    place_component_fields(ed, tree, symbols, labels, 'J2')
    fields = _fields(tree, 'J2')
    top = max(symbols.bbox('J2')[3], symbols._origin('J2')[1])
    assert all(y >= top + 5.08 - 0.001 for _x, y in fields.values())
    assert abs(fields['Reference'][1] - fields['Value'][1]) >= 2.54 - 0.001


@pytest.mark.parametrize('ref', ('J1', 'J3', 'U1', 'U2'))
def test_horizontal_pin_fields_clear_top_and_bottom(gnss_fields, ref):
    from pcb_copilot.schematic.fields import place_component_fields

    tree, symbols, labels = gnss_fields
    origin = symbols._origin(ref)
    box = symbols.bbox(ref)
    place_component_fields(ed, tree, symbols, labels, ref)
    fields = _fields(tree, ref)
    assert fields['Reference'][0] == pytest.approx(origin[0])
    assert fields['Value'][0] == pytest.approx(origin[0])
    assert fields['Reference'][1] >= max(origin[1], box[3]) + 5.08 - 0.001
    assert fields['Value'][1] <= min(origin[1], box[1]) - 5.08 + 0.001


@pytest.mark.parametrize('ref', ('C1', 'R1', '#FLG01'))
def test_existing_passive_and_pseudo_fields_are_unchanged(gnss_fields, ref):
    from pcb_copilot.schematic.fields import place_component_fields

    tree, symbols, labels = gnss_fields
    before = copy.deepcopy(ed.find_symbol_by_reference(tree, ref))
    place_component_fields(ed, tree, symbols, labels, ref)
    assert ed.find_symbol_by_reference(tree, ref) == before


def test_field_placement_preserves_component_and_pin_positions(gnss_fields):
    from pcb_copilot.schematic.fields import place_component_fields

    tree, symbols, labels = gnss_fields
    origin = symbols._origin('J2')
    pins = ed.list_pins_for_symbol(tree, 'J2')
    place_component_fields(ed, tree, symbols, labels, 'J2')
    assert symbols._origin('J2') == origin
    assert ed.list_pins_for_symbol(tree, 'J2') == pins


def test_text_field_envelope_rejects_rotated_text_outside_power_value_scope(gnss_fields):
    from pcb_copilot.schematic.fields import text_field_envelope

    tree, _symbols, _labels = gnss_fields
    symbol = ed.find_symbol_by_reference(tree, 'U1')
    value = next(prop for prop in ed.find_children(symbol, 'property')
                 if prop[1] == 'Value')
    ed.find_child(value, 'at')[3] = 90

    with pytest.raises(ValueError, match='unrotated'):
        text_field_envelope(ed, tree, 'U1', 'Value')


def test_tvs_fields_clear_body_wider_than_pin_column(repo_root):
    from pcb_copilot.schematic.fields import place_component_fields

    tree = sch_io.parse_file(repo_root / 'projects/tms-v3/load-cell-ads1256.kicad_sch')
    symbols = SymbolPlacer(ed, tree)
    labels = LabelPlacer(ed, tree, symbols=symbols)
    origin = symbols._origin('D2')
    # This real symbol's body rectangle is +/-10.16 mm, but the pins span
    # only +/-5.08 mm. A pin box alone put both fields on the body edge.
    symbol = ed.find_symbol_by_reference(tree, 'D2')
    ed.find_child(symbol, 'at')[3] = 0
    pins = ed.list_pins_for_symbol(tree, 'D2')
    place_component_fields(ed, tree, symbols, labels, 'D2')
    for name, (x, _y) in _fields(tree, 'D2').items():
        assert x >= origin[0] + 10.16 + 5.08 - 0.001
        field = next(p for p in ed.find_children(symbol, 'property') if p[1] == name)
        effects = ed.find_child(field, 'effects')
        assert ed.find_child(effects, 'justify')[1:] == [sch_io.sym('left')]
    assert ed.list_pins_for_symbol(tree, 'D2') == pins
