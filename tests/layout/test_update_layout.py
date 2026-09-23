from pathlib import Path

import pytest

from pcb_copilot.layout import update
from pcb_copilot.project import load_project


@pytest.fixture
def staged_candidate(monkeypatch):
    def prepare(snapshot, intent, candidate, route, output):
        if candidate is not None:
            snapshot.pcb_path.write_bytes(candidate.read_bytes())
        (output / 'layout.svg').write_text('<svg/>')
        return snapshot.pcb_path, [], {'before': {'tracks': 50}, 'after': {'tracks': 51}}
    monkeypatch.setattr(update, '_prepare_candidate', prepare)
    return prepare


def test_layout_preview_does_not_change_design_or_leave_drafts(project_copy, staged_candidate):
    project = load_project(project_copy)
    before = project.pcb_path.read_bytes()
    result = update.update_layout(project, candidate=project.pcb_path)
    assert not result['applied']
    assert result['exit_code'] == 0
    assert project.pcb_path.read_bytes() == before
    assert Path(result['preview']).is_file()
    assert not (project.root / '.pcb-copilot/drafts').exists()
    assert not list((project.root / '.pcb-copilot').glob('layout-*'))


def test_blocked_layout_cannot_be_applied(project_copy, monkeypatch):
    project = load_project(project_copy)
    before = project.pcb_path.read_bytes()
    def blocked(snapshot, intent, candidate, route, output):
        snapshot.pcb_path.write_bytes(b'incomplete candidate')
        return snapshot.pcb_path, [{'code': 'routing', 'severity': 'block', 'message': '7 unconnected'}], {}
    monkeypatch.setattr(update, '_prepare_candidate', blocked)
    result = update.update_layout(project, candidate=project.pcb_path, apply=True)
    assert result['exit_code'] == 1 and not result['applied']
    assert project.pcb_path.read_bytes() == before


def test_apply_invalidates_old_release_state(project_copy, staged_candidate, tmp_path):
    project = load_project(project_copy)
    candidate = tmp_path / 'candidate.kicad_pcb'
    candidate.write_bytes(project.pcb_path.read_bytes() + b'\n')
    workspace = project.root / '.pcb-copilot'
    workspace.mkdir(exist_ok=True)
    (workspace / 'release.json').write_text('{}')
    result = update.update_layout(project, candidate=candidate, apply=True)
    assert result['applied'] and result['lifecycle'] == 'DRAFT'
    assert project.pcb_path.read_bytes() == candidate.read_bytes()
    assert not (workspace / 'release.json').exists()


def test_candidate_exception_preserves_root_and_cleans_transaction(project_copy, monkeypatch):
    project = load_project(project_copy)
    before = project.pcb_path.read_bytes()
    def fail(snapshot, *args):
        snapshot.pcb_path.write_bytes(b'partial')
        raise RuntimeError('native tool failed')
    monkeypatch.setattr(update, '_prepare_candidate', fail)
    with pytest.raises(RuntimeError, match='native tool failed'):
        update.update_layout(project, candidate=project.pcb_path, apply=True)
    assert project.pcb_path.read_bytes() == before
    assert not list((project.root / '.pcb-copilot').glob('layout-*'))


def test_copper_loss_is_blocking_even_when_no_drc_measurement(tmp_path):
    findings = update.nonregression_findings({'footprints': {'U1': {}}, 'tracks': 10, 'zones': 1},
                                          {'footprints': {'U1': {}}, 'tracks': 0, 'zones': 0},
                                          unconnected=None)
    assert any(item['severity'] == 'block' for item in findings)
