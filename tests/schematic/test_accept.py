import json
from dataclasses import replace

import pytest

from pcb_copilot.accept import StaleDraftError, accept_schematic, load_draft
from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.models import Lifecycle
from pcb_copilot.project import load_project
from pcb_copilot.schematic.commands import draft_schematic
from pcb_copilot.schematic.io import load_schematic_intent, save_schematic_intent
from pcb_copilot.state import effective_lifecycle


@pytest.fixture
def reviewed_candidate(project_copy, repo_root, tmp_path):
    project = load_project(project_copy)
    intent = load_schematic_intent(repo_root / 'tests/fixtures/schematic/parent-child.yaml')
    record = load_evidence_index(project.evidence_index_path).records[0]
    components = tuple(c.model_copy(update={
        'pin_map_evidence_id': record.id,
        'evidence_part_number': min(record.part_numbers),
    }) for c in intent.components)
    intent_path = tmp_path / 'intent.yaml'
    save_schematic_intent(intent.model_copy(update={'components': components}), intent_path)
    report = draft_schematic(project, intent_path)
    assert report['exit_code'] == 0
    return project, load_draft(project, report['draft_id'])


def test_accept_rejects_stale_base(reviewed_candidate):
    project, draft = reviewed_candidate
    with project.schematic_path.open('ab') as stream:
        stream.write(b'\n')
    with pytest.raises(StaleDraftError):
        accept_schematic(project, draft)


def test_accept_rejects_changed_previewed_child(reviewed_candidate):
    project, draft = reviewed_candidate
    with (draft.root / 'sensor.kicad_sch').open('ab') as stream:
        stream.write(b'\n')
    with pytest.raises(ValueError, match='review artifacts'):
        accept_schematic(project, draft)


def test_accept_hierarchy_awaits_human_review_without_changing_pcb(reviewed_candidate):
    project, draft = reviewed_candidate
    pcb = project.pcb_path.read_bytes()
    original = project.schematic_path.read_bytes()
    state_dir = project.root / '.pcb-copilot'
    (state_dir / 'release.json').write_text(
        json.dumps({'lifecycle': 'RELEASED', 'schematic_hash': 'old', 'pcb_hash': 'old'}),
        encoding='utf-8',
    )
    result = accept_schematic(project, draft)
    assert result.lifecycle == Lifecycle.DRAFT
    assert effective_lifecycle(project) == Lifecycle.DRAFT
    assert not (state_dir / 'release.json').exists()
    assert json.loads((state_dir / 'review.json').read_text())['lifecycle'] == 'DRAFT'
    assert project.pcb_path.read_bytes() == pcb
    assert (project.root / 'sensor.kicad_sch').is_file()
    netmap = json.loads(project.netmap_path.read_text())
    assert netmap['nets']['U1']['7'] == 'DATA_READY'
    assert netmap['no_connect']['U1'] == ['1', '2', '3', '4', '5', '6', '8']
    assert (project.root / '.pcb-copilot/acceptances' / draft.id / project.schematic_path.name).read_bytes() == original
    with (project.root / 'sensor.kicad_sch').open('ab') as stream:
        stream.write(b'\n')
    assert effective_lifecycle(project) == Lifecycle.DRAFT


def test_forged_draft_root_rejected(reviewed_candidate, tmp_path):
    project, draft = reviewed_candidate
    with pytest.raises(ValueError, match='draft root'):
        accept_schematic(project, replace(draft, root=tmp_path))


def test_traversal_draft_id_rejected(project_copy):
    with pytest.raises(ValueError):
        load_draft(load_project(project_copy), '../outside')


def test_write_failure_rolls_back_every_accepted_file(reviewed_candidate, monkeypatch):
    import pcb_copilot.accept as module

    project, draft = reviewed_candidate
    paths = [project.schematic_path, project.netmap_path, project.root / 'SCHEMATIC_OWNER']
    before = {p: p.read_bytes() for p in paths}
    original = module._replace_bytes

    def fail_netmap(path, payload):
        if path == project.netmap_path:
            raise OSError('injected replacement failure')
        original(path, payload)

    monkeypatch.setattr(module, '_replace_bytes', fail_netmap)
    with pytest.raises(OSError, match='injected'):
        accept_schematic(project, draft)
    assert all(p.read_bytes() == data for p, data in before.items())
    assert not (project.root / 'sensor.kicad_sch').exists()
    assert not (project.root / '.pcb-copilot/accept.lock').exists()


def test_review_write_failure_restores_prior_release(reviewed_candidate, monkeypatch):
    import pcb_copilot.accept as module

    project, draft = reviewed_candidate
    state_dir = project.root / '.pcb-copilot'
    release = state_dir / 'release.json'
    release.write_bytes(b'{"lifecycle":"RELEASED"}\n')
    original_schematic = project.schematic_path.read_bytes()
    original_release = release.read_bytes()
    replace_bytes = module._replace_bytes

    def fail_review(path, payload):
        if path == state_dir / 'review.json':
            raise OSError('injected review write failure')
        replace_bytes(path, payload)

    monkeypatch.setattr(module, '_replace_bytes', fail_review)
    with pytest.raises(OSError, match='injected review write failure'):
        accept_schematic(project, draft)
    assert project.schematic_path.read_bytes() == original_schematic
    assert release.read_bytes() == original_release
    assert not (state_dir / 'accept.lock').exists()
