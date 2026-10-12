"""Fault injection for assembly errors that electrical DRC cannot detect."""
import copy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import sexpdata
from kicad_claude.adapters import sch_io as s

from pcb_copilot.assembly import (
    audit_assembly,
    corrected_position,
    digest,
    model_inventory,
    pad_geometry_digest,
    polarity_labels,
    rotation_rule,
    supplier_review,
)


@pytest.fixture
def assembly_case(tmp_path):
    (tmp_path / 'evidence').mkdir()
    evidence = tmp_path / 'evidence/placement.txt'
    evidence.write_text('Synthetic placement evidence for automated tests only.')
    pcb = tmp_path / 'test.kicad_pcb'
    pcb.write_text('synthetic board bytes')
    fp = sexpdata.loads('''(footprint "Header:1x3" (layer "F.Cu") (at 10 20 90)
      (property "Reference" "J1") (property "MPN" "EXACT-MPN") (property "LCSC" "C123")
      (fp_rect (start -1 -1) (end 1 6) (layer "F.Fab"))
      (pad "1" thru_hole rect (at 0 0 90) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask"))
      (pad "2" thru_hole circle (at 0 2.54 90) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask"))
      (pad "3" thru_hole circle (at 0 5.08 90) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask")))''')
    rule = {'mpn': 'EXACT-MPN', 'footprint': 'Header:1x3', 'side': 'top',
            'pad_geometry_sha256': pad_geometry_digest(fp), 'degrees': -90,
            'basis': 'derived_from_preview', 'evidence': 'evidence/placement.txt',
            'evidence_sha256': digest(evidence), 'reason': 'test-only horizontal pin row'}
    plan = {'centroid_offsets': {'Header:1x3': {'x_mm': 0, 'y_mm': 2.54}},
            'rotation_offsets': {'C123': rule}, 'model_contracts': {}}
    return SimpleNamespace(root=tmp_path, pcb_path=pcb), fp, plan


def test_vendor_correction_must_not_rotate_the_centroid_offset(assembly_case):
    project, fp, plan = assembly_case
    x, y, angle, _ = corrected_position(project, fp, plan, 10, -20, 90, 'top')
    assert (x, y, angle) == pytest.approx((12.54, -20, 0))
    # Using corrected 0 for the offset would wrongly move Y and leave X unchanged.


def test_rotation_contract_survives_board_move_and_native_rotation(assembly_case):
    project, fp, plan = assembly_case
    before = pad_geometry_digest(fp)
    s.find_child(fp, 'at')[1:] = [123, 456, 180]
    for pad in s.find_children(fp, 'pad'):
        s.find_child(pad, 'at')[3] = 180
    assert pad_geometry_digest(fp) == before
    assert rotation_rule(project, fp, plan)['degrees'] == -90


@pytest.mark.parametrize('fault', ['mpn', 'part', 'footprint', 'side', 'pad_number', 'pad_position', 'evidence'])
def test_exact_part_rules_cannot_silently_follow_replacements(assembly_case, fault):
    project, fp, plan = assembly_case
    if fault in {'mpn', 'part'}:
        key = 'MPN' if fault == 'mpn' else 'LCSC'
        next(p for p in s.find_children(fp, 'property') if str(p[1]) == key)[2] = 'OTHER'
    elif fault == 'footprint':
        fp[1] = 'Header:OTHER'
    elif fault == 'side':
        s.find_child(fp, 'layer')[1] = 'B.Cu'
    elif fault == 'pad_number':
        s.find_children(fp, 'pad')[0][1] = '3'
    elif fault == 'pad_position':
        s.find_child(s.find_children(fp, 'pad')[0], 'at')[1] = 0.5
    else:
        (project.root / 'evidence/placement.txt').write_text('changed evidence')
    if fault == 'part':
        assert rotation_rule(project, fp, plan) is None
        assert not audit_assembly(project, {'J1': fp}, {'J1'}, plan)['passed']
    else:
        with pytest.raises(ValueError, match='changed|identity'):
            rotation_rule(project, fp, plan)


def test_wrong_p3_silk_fails_even_when_copper_nets_are_unchanged():
    fp = sexpdata.loads('''(footprint "rover:WirePads_test" (property "Reference" "P3")
      (pad "1" smd rect (at -4.5 0) (net "GND"))
      (pad "2" smd rect (at 4.5 0) (net "+12V"))
      (fp_text user "+" (at -4.5 4.2) (layer "F.Silkscreen"))
      (fp_text user "GND" (at 4.5 4.2) (layer "F.Silkscreen")))''')
    original_pads = copy.deepcopy(s.find_children(fp, 'pad'))
    _, issues = polarity_labels({'P3': fp})
    assert len(issues) == 2
    for index, text in enumerate(s.find_children(fp, 'fp_text'), 1):
        text[2] = '${SHORT_NET_NAME(' + str(index) + ')}'
    rows, issues = polarity_labels({'P3': fp})
    assert not issues
    assert [r['shown'] for r in rows] == ['GND', '+12V']
    assert s.find_children(fp, 'pad') == original_pads
    # A net variable pointing at the other pad is still wrong.
    s.find_children(fp, 'fp_text')[0][2] = '${SHORT_NET_NAME(2)}'
    assert polarity_labels({'P3': fp})[1]


def test_missing_model_and_modified_model_contract_fail(assembly_case):
    project, fp, plan = assembly_case
    assert model_inventory(project, {'J1': fp}, {'J1'}, plan)[1]
    model = project.root / 'test.step'
    model.write_text('Synthetic model bytes, not real production geometry.' * 2)
    fp.append(sexpdata.loads('''(model "${KIPRJMOD}/test.step"
       (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))'''))
    plan['model_contracts']['C123'] = {'mpn': 'EXACT-MPN', 'footprint': 'Header:1x3',
        'path': '${KIPRJMOD}/test.step', 'sha256': digest(model), 'offset': [0, 0, 0],
        'scale': [1, 1, 1], 'rotate': [0, 0, 0], 'fidelity': 'synthetic test fixture'}
    assert not model_inventory(project, {'J1': fp}, {'J1'}, plan)[1]
    m = s.find_child(fp, 'model')
    s.find_child(s.find_child(m, 'rotate'), 'xyz')[3] = 90
    assert model_inventory(project, {'J1': fp}, {'J1'}, plan)[1]
    s.find_child(s.find_child(m, 'rotate'), 'xyz')[3] = 0
    model.write_text('different model contents' * 3)
    assert model_inventory(project, {'J1': fp}, {'J1'}, plan)[1]


@pytest.mark.parametrize('changed', ['test.kicad_pcb', 'bom.csv', 'cpl.csv', 'evidence/placement.txt'])
def test_supplier_review_is_bound_to_current_upload_bytes(assembly_case, changed):
    project, _, plan = assembly_case
    for name in ('bom.csv', 'cpl.csv'):
        (project.root / name).write_text('synthetic upload ' + name)
    assert not supplier_review(project, project.root, plan)['passed']
    rule = plan['rotation_offsets']['C123']
    plan['supplier_review'] = {
        'reviewer': 'AUTOMATED TEST FIXTURE ONLY', 'reviewed_on': datetime.now(UTC).date().isoformat(),
        'pcb_sha256': digest(project.pcb_path), 'bom_sha256': digest(project.root / 'bom.csv'),
        'cpl_sha256': digest(project.root / 'cpl.csv'), 'evidence': rule['evidence'],
        'evidence_sha256': rule['evidence_sha256'],
    }
    assert supplier_review(project, project.root, plan)['passed']
    (project.root / changed).write_text('changed file')
    assert not supplier_review(project, project.root, plan)['passed']
