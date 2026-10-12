"""The historical intent audit must not demand restoration of owner routing."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'projects/rover-pdb/layout/audit_net_intent.py'
spec = importlib.util.spec_from_file_location('rover_copper_audit', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def track(net='VBAT', width=1):
    return {'ends': [[0, 0], [5, 0]], 'width': width, 'layer': 'F.Cu', 'net': net}


def test_same_geometry_wrong_net_is_error():
    result = audit.compare_reference([track()], [track('GND')], audit.track_key)
    assert len(result['wrong_net']) == 1


def test_owner_replaced_route_is_reported_separately():
    result = audit.compare_reference([track()], [track(width=2)], audit.track_key)
    assert result['wrong_net'] == []
    assert result['missing_or_replaced_geometry'] == [track()]
    assert result['new_geometry'] == [track(width=2)]


def test_mixed_duplicate_nets_cannot_hide_wrong_net():
    result = audit.compare_reference([track()], [track(), track('GND')], audit.track_key)
    assert len(result['wrong_net']) == 1


def test_pin_audit_rejects_missing_changed_and_extra_connected_pads():
    errors = audit.pin_errors({('U1', '1'): 'VBAT', ('U1', '2'): 'GND'},
                             {('U1', '1'): ['GND'], ('U2', '1'): ['VBAT']})
    assert len(errors) == 3


def test_duplicate_numbered_pads_must_all_match():
    assert audit.pin_errors({('U1', '1'): 'GND'}, {('U1', '1'): ['GND', 'GND']}) == []
    assert audit.pin_errors({('U1', '1'): 'GND'}, {('U1', '1'): ['GND', 'VBAT']})
