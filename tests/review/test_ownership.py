import json

from pcb_copilot.project import load_project
from pcb_copilot.review.legacy import legacy_checks


def _ownership(project_copy):
    check = next(item for item in legacy_checks()
                 if item.check_id == 'schematic_ownership')
    return check.run(load_project(project_copy))


def test_current_owner_and_netmap_agree(project_copy):
    result = _ownership(project_copy)

    assert result.passed
    assert 'human-owned' in result.detail


def test_invalid_owner_is_rejected(project_copy):
    (project_copy / 'SCHEMATIC_OWNER').write_text('guess\n', encoding='utf-8')

    result = _ownership(project_copy)

    assert not result.passed
    assert 'SCHEMATIC_OWNER' in result.detail


def test_stale_netmap_is_rejected(project_copy):
    path = project_copy / 'netmap.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['nets']['U1']['2'] = 'WRONG'
    path.write_text(json.dumps(data), encoding='utf-8')

    result = _ownership(project_copy)

    assert not result.passed
    assert 'netmap.json disagrees' in result.detail
