import json

from pcb_copilot.project import load_project
from pcb_copilot.review.checks import current_checks


def _ownership(project_copy):
    check = next(item for item in current_checks()
                 if item.check_id == 'schematic_ownership')
    return check.run(load_project(project_copy))


def test_current_owner_and_netmap_agree(project_copy):
    result = _ownership(project_copy)

    assert result.passed
    assert 'matches the current schematic' in result.detail




def test_stale_netmap_is_rejected(project_copy):
    path = project_copy / 'netmap.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['nets']['U1']['2'] = 'WRONG'
    path.write_text(json.dumps(data), encoding='utf-8')

    result = _ownership(project_copy)

    assert not result.passed
    assert 'netmap is stale' in result.detail
