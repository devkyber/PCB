import pytest

from pcb_copilot.copper_features import copper_feature_type
from pcb_copilot.review.checks import _parts
from pcb_copilot.review.placement import (
    check_courtyard_overlap,
    check_pads_inside_board,
)


def feature(ref='NT1', lib='NetTie:NetTie-2', groups='(net_tie_pad_groups "1, 2")'):
    return f'''\n\t(footprint "{lib}"
\t\t(layer "F.Cu")
\t\t(at 5 5)
\t\t(property "Reference" "{ref}")
\t\t(property "Value" "COPPER FEATURE")
\t\t(attr smd exclude_from_bom exclude_from_pos_files)
\t\t{groups}
\t\t(pad "1" smd rect (at -0.25 0) (size 0.5 0.5) (layers "F.Cu"))
\t\t(pad "2" smd rect (at 0.25 0) (size 0.5 0.5) (layers "F.Cu"))
\t)'''


def board(*fps):
    return ('(kicad_pcb\n\t(gr_rect (start 0 0) (end 10 10) '
            '(layer "Edge.Cuts"))' + ''.join(fps) + ')')


def test_native_net_tie_is_not_an_assembly_body_but_still_has_pad_bounds():
    tie = feature()
    package = feature('U1', 'Package:IC', '').replace(
        '(attr smd exclude_from_bom exclude_from_pos_files)', '(attr smd)')
    assert copper_feature_type(tie) == 'net_tie'
    assert check_courtyard_overlap(board(package, tie))[0] == 'PASS'
    assert check_courtyard_overlap(board(package, package.replace('U1', 'U2')))[0] == 'FAIL'
    assert check_pads_inside_board(board(tie.replace('(at 5 5)', '(at 0 5)')))[0] == 'FAIL'


@pytest.mark.parametrize('change', [
    lambda x: x.replace('exclude_from_bom', ''),
    lambda x: x.replace('exclude_from_pos_files', ''),
    lambda x: x.replace('(layers "F.Cu")', '(layers "F.Cu" "F.Paste")'),
    lambda x: x.replace('(net_tie_pad_groups "1, 2")', '(net_tie_pad_groups "1, 3")'),
    lambda x: x.replace('(net_tie_pad_groups "1, 2")', ''),
    lambda x: x.replace('(net_tie_pad_groups "1, 2")', '(net_tie_pad_groups "1" "2")'),
    lambda x: x.replace('(at 5 5)', '(at 5 5) (property "MPN" "PurchasedPart")'),
    lambda x: x.replace('(at 5 5)', '(at 5 5) (property "LCSC Part" "C12345")'),
    lambda x: x.replace('(at 5 5)', '(at 5 5) (model "part.step")'),
    lambda x: x.replace('(at 5 5)', '(at 5 5) (fp_rect (start -1 -1) (end 1 1) (layer "F.CrtYd"))'),
])
def test_excluded_packages_and_malformed_ties_keep_placement_and_source_checks(change):
    suspect = change(feature())
    assert copper_feature_type(suspect) is None
    package = feature('U1', 'Package:IC', '')
    assert check_courtyard_overlap(board(package, suspect))[0] == 'FAIL'


def test_wire_lands_keep_assembly_access_courtyard():
    wire = feature('P1', 'rover:WirePads_2_6x8_P12', '').replace(
        '(at 5 5)', '(at 5 5) (fp_rect (start -2 -2) (end 2 2) (layer "F.CrtYd"))')
    assert copper_feature_type(wire) == 'wire_pad'
    assert check_courtyard_overlap(board(wire, feature('U1', 'IC', '')))[0] == 'FAIL'
    assert copper_feature_type(wire.replace('WirePads_2_6x8_P12', 'PinHeader_1x02')) is None
    assert copper_feature_type(wire.replace('"P1"', '"U1"')) is None


def test_native_wire_pad_label_is_not_a_purchased_mpn():
    wire = feature('P1', 'rover:WirePads_2_6x8_P12', '').replace('exclude_from_pos_files', '')
    wire = wire.replace('(property "Value" "COPPER FEATURE")',
                        '(property "Value" "BATTERY IN") (property "MPN" "BATTERY IN")')
    assert copper_feature_type(wire) == 'wire_pad'
    assert copper_feature_type(wire.replace('(property "MPN" "BATTERY IN")',
                                           '(property "MPN" "Connector123")')) is None
    assert copper_feature_type(wire.replace('(attr smd', '(property "LCSC Part" "C123") (attr smd')) is None
    assert copper_feature_type(wire.replace('exclude_from_bom', '')) is None
    assert copper_feature_type(wire.replace('(layers "F.Cu")', '(layers "F.Cu" "F.Paste")')) is None
    assert copper_feature_type(wire.replace('WirePads_2_6x8_P12', 'Connector_2')) is None


def test_only_recognized_copper_features_are_omitted_from_datasheet_inventory(tmp_path):
    # A tiny project-like object is sufficient: _parts only reads pcb_path.
    from types import SimpleNamespace
    pcb = tmp_path / 'candidate.kicad_pcb'
    pcb.write_text(board(feature(), feature('P1', 'rover:WirePads_2', ''),
                         feature('P2', 'Connector:Terminal', ''),
                         feature('U1', 'IC', ''),
                         feature('NT2').replace('exclude_from_bom', '')))
    parts = list(_parts(SimpleNamespace(pcb_path=pcb), datasheets=True))
    assert {part.reference for part in parts} == {'P2', 'U1', 'NT2'}
