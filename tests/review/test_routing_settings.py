import json
from types import SimpleNamespace

import pytest

from pcb_copilot.project import load_project
from pcb_copilot.review.commands import review_project
from pcb_copilot.review.models import FindingKind
from pcb_copilot.review.routing_settings import RoutingSettingsCheck


def audit(tmp_path, body, *, classes=(), patterns=(), presets=(), assignments=None):
    board = tmp_path / 'board.kicad_pcb'
    board.write_text(f'(kicad_pcb {body})', encoding='utf-8')
    board.with_suffix('.kicad_pro').write_text(json.dumps({
        'net_settings': {
            'classes': [{'name': 'Default', 'track_width': 0.25}, *classes],
            'netclass_patterns': list(patterns),
            'netclass_assignments': assignments,
        },
        'board': {'design_settings': {'track_widths': list(presets)}},
    }), encoding='utf-8')
    return RoutingSettingsCheck().run(SimpleNamespace(pcb_path=board))


def test_wide_supply_with_thin_sense_branch_gets_advice_not_a_minimum_rule(tmp_path, tree_hash):
    result = audit(tmp_path, '''
        (segment (width 2) (net "/power/VBAT"))
        (segment (width 0.25) (net "/power/VBAT"))
    ''')
    before = tree_hash(tmp_path)
    repeat = RoutingSettingsCheck().run(SimpleNamespace(pcb_path=tmp_path / 'board.kicad_pcb'))

    assert result == repeat
    assert tree_hash(tmp_path) == before
    assert result.passed  # convenience warning must not itself block fabrication
    assert len(result.advisories) == 2
    assert '0.25–2 mm' in result.advisories[0]
    assert 'low-current branches' in result.advisories[0]
    assert 'ampacity' in result.scope.does_not_prove


@pytest.mark.parametrize('assignment', ['pattern', 'direct', 'legacy'])
def test_assigned_class_handles_wide_route_without_requiring_duplicate_presets(tmp_path, assignment):
    power = {'name': 'Power', 'track_width': 2.0}
    patterns, direct = [], None
    if assignment == 'pattern':
        patterns = [{'netclass': 'Power', 'pattern': '/power/V*'}]
    elif assignment == 'direct':
        direct = {'/power/VBAT': ['Power']}
    else:
        power['nets'] = ['/power/VBAT']
    result = audit(tmp_path, '''
        (segment (width 2) (net "/power/VBAT"))
        (segment (width 0.15) (net "/power/VBAT"))
    ''', classes=[power], patterns=patterns, assignments=direct)

    assert result.passed
    assert not result.advisories


def test_unassigned_class_does_not_hide_missing_route_defaults(tmp_path):
    result = audit(tmp_path, '(segment (width 2) (net "+12V"))',
                   classes=[{'name': 'Power', 'track_width': 2}], presets=[0, 0.25, 2])

    assert len(result.advisories) == 1
    assert 'no stored non-Default class assignment' in result.advisories[0]


def test_wrong_assigned_class_width_still_warns(tmp_path):
    result = audit(tmp_path, '(segment (width 2) (net "+12V"))',
                   classes=[{'name': 'Power', 'track_width': 0.3}],
                   patterns=[{'netclass': 'Power', 'pattern': '+12V'}])

    assert result.passed
    assert len(result.advisories) == 2


def test_only_native_routes_are_counted_and_sensor_ground_widths_are_not_power_candidates(tmp_path):
    result = audit(tmp_path, '''
        (gr_text "(segment (locked yes)) (via)" (at 0 0))
        (footprint "Example" (locked yes) (fp_line (width 3)))
        (segment (width 2) (net "ADC_IN"))
        (segment (width 3) (net "GND"))
        (segment (width 0.25) (net "+3V3"))
    ''')

    assert '3 segments, 0 arcs, 0 vias; 0 locked' in result.detail
    assert not result.advisories


def test_numeric_nets_arcs_and_old_and_new_lock_forms(tmp_path):
    result = audit(tmp_path, '''
        (net 1 "+5V")
        (segment locked (width 1) (net 1))
        (arc (locked no) (width 1) (net 1))
        (via (locked yes) (net 1))
    ''', presets=[1])

    assert '1 segments, 1 arcs, 1 vias; 2 locked' in result.detail
    assert any('Intentional locks are valid' in item for item in result.advisories)
    assert any('+5V' in item for item in result.advisories)


def test_missing_companion_settings_is_an_explicit_advisory(tmp_path):
    board = tmp_path / 'board.kicad_pcb'
    board.write_text('(kicad_pcb (segment (width 2) (net "VBAT")))')
    result = RoutingSettingsCheck().run(SimpleNamespace(pcb_path=board))

    assert result.passed
    assert any('.kicad_pro is missing' in item for item in result.advisories)


def test_registry_exposes_locked_route_as_nonblocking_warning(project_copy, tree_hash):
    project = load_project(project_copy)
    # Dedicated fixture contents avoid relying on the actual design's current locks.
    project.pcb_path.write_text('(kicad_pcb (segment (locked yes) (width 0.25) (net "SDA")))')
    before = tree_hash(project_copy)
    report = review_project(project, checks=(RoutingSettingsCheck(),))

    assert not report.blocking
    assert report.findings
    assert all(item.kind == FindingKind.ENGINEERING_WARNING and not item.blocking
               for item in report.findings)
    assert tree_hash(project_copy) == before


def test_malformed_settings_are_not_claimed_to_have_passed(tmp_path):
    board = tmp_path / 'board.kicad_pcb'
    board.write_text('(kicad_pcb)')
    board.with_suffix('.kicad_pro').write_text('{broken')

    with pytest.raises(json.JSONDecodeError):
        RoutingSettingsCheck().run(SimpleNamespace(pcb_path=board))
