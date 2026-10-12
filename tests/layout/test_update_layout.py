from pathlib import Path
from types import SimpleNamespace

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
    result = update.update_layout(project, candidate=project.pcb_path)
    assert result['exit_code'] == 1 and not result['applied']
    with pytest.raises(RuntimeError, match='run preview again'):
        update.update_layout(project, candidate=project.pcb_path, apply=True)
    assert project.pcb_path.read_bytes() == before


def test_apply_invalidates_old_release_state(project_copy, staged_candidate, tmp_path):
    project = load_project(project_copy)
    candidate = tmp_path / 'candidate.kicad_pcb'
    candidate.write_bytes(project.pcb_path.read_bytes() + b'\n')
    workspace = project.root / '.pcb-copilot'
    workspace.mkdir(exist_ok=True)
    (workspace / 'release.json').write_text('{}')
    update.update_layout(project, candidate=candidate)
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
        update.update_layout(project, candidate=project.pcb_path)
    assert project.pcb_path.read_bytes() == before
    assert not list((project.root / '.pcb-copilot').glob('layout-*'))


def test_copper_loss_is_blocking_even_when_no_drc_measurement(tmp_path):
    findings = update.nonregression_findings({'footprints': {'U1': {}}, 'tracks': 10, 'zones': 1},
                                          {'footprints': {'U1': {}}, 'tracks': 0, 'zones': 0},
                                          unconnected=None)
    assert any(item['severity'] == 'block' for item in findings)


@pytest.mark.parametrize('failure', [None, 'links', 'parity', 'placement', 'drc', 'unconnected'])
def test_first_layout_uses_all_candidate_gates_before_creating_board(
    project_copy, tmp_path, monkeypatch, failure,
):
    project = load_project(project_copy)
    candidate = tmp_path / 'first-board.kicad_pcb'
    candidate.write_bytes(project.pcb_path.read_bytes())
    project.pcb_path.unlink()
    # Isolate tool execution while exercising the real preparation, snapshot,
    # gating and publication path. No baseline PCB may be silently created.
    (project.root / 'layout-intent.yaml').unlink(missing_ok=True)
    calls = []
    monkeypatch.setattr(update, 'discover_toolchain', lambda _: SimpleNamespace(kipython=Path('python')))

    def inspect_native(_toolchain, pcb):
        assert pcb.is_file(), 'native inspection must never receive the missing baseline'
        assert pcb.read_bytes() == candidate.read_bytes()
        calls.append('native')
        return {'footprints': {'U1': {}}, 'tracks': 5, 'zones': 1}

    def gate(name):
        def run(context):
            assert context.pcb_path.is_file()
            calls.append(name)
            return failure != name, f'{name} result'
        return run

    def drc(pcb, output):
        assert pcb.is_file()
        calls.append('drc')
        return (int(failure == 'drc'), 0, int(failure == 'unconnected'))

    def links(context, toolchain):
        calls.append('links')
        return [update._finding('layout.schematic_links', 'conflicting ID')] if failure == 'links' else []

    def topology(pcb, toolchain):
        calls.append('topology')
        return {'findings': [], 'counts': {}}

    monkeypatch.setattr(update, 'native_board', inspect_native)
    monkeypatch.setattr(update.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0))
    monkeypatch.setattr(update, 'check_parity', gate('parity'))
    monkeypatch.setattr(update, 'check_placement', gate('placement'))
    monkeypatch.setattr(update, 'drc_once', drc)
    monkeypatch.setattr(update, '_bind_candidate_links', links)
    monkeypatch.setattr(update, 'inspect_routing', topology)
    monkeypatch.setattr(update, 'render_layout_preview', lambda *args: [])
    monkeypatch.setattr(update, 'check_evidence', lambda *args: [])

    result = update.update_layout(project, candidate=candidate)

    assert calls == ['links', 'parity', 'placement', 'drc', 'drc', 'topology', 'native']
    assert (project.root / '.pcb-copilot/preview/routing-topology.json').is_file()
    assert result['comparison']['before']['footprints'] == {}
    assert not result['applied']
    assert not project.pcb_path.exists()
    if failure is None:
        result = update.update_layout(project, candidate=candidate, apply=True)
        assert result['applied']
        assert calls == ['links', 'parity', 'placement', 'drc', 'drc', 'topology', 'native'] * 2
        assert project.pcb_path.read_bytes() == candidate.read_bytes()
    else:
        assert result['exit_code'] == 1
        with pytest.raises(RuntimeError, match='run preview again'):
            update.update_layout(project, candidate=candidate, apply=True)
        assert not project.pcb_path.exists()


def test_invalid_existing_board_is_not_treated_as_missing(project_copy, tmp_path, monkeypatch):
    project = load_project(project_copy)
    candidate = tmp_path / 'candidate.kicad_pcb'
    candidate.write_bytes(project.pcb_path.read_bytes())
    project.pcb_path.write_bytes(b'invalid existing CAD')
    monkeypatch.setattr(update, 'discover_toolchain', lambda _: SimpleNamespace())

    def reject_existing(_toolchain, pcb, *, require_outline, allow_duplicate_references):
        assert pcb.read_bytes() == b'invalid existing CAD'
        assert require_outline is False
        assert allow_duplicate_references is True
        raise ValueError('existing board cannot be parsed')

    monkeypatch.setattr(update, 'native_board', reject_existing)
    with pytest.raises(ValueError, match='existing board cannot be parsed'):
        update.update_layout(project, candidate=candidate)
    assert project.pcb_path.read_bytes() == b'invalid existing CAD'


@pytest.mark.parametrize('edit', ['pcb', 'schematic', 'settings'])
def test_new_owner_edit_after_layout_preview_is_preserved(project_copy, staged_candidate, tmp_path, edit):
    project = load_project(project_copy)
    candidate = tmp_path / 'candidate.kicad_pcb'
    candidate.write_bytes(project.pcb_path.read_bytes())
    update.update_layout(project, candidate=candidate)
    path = {'pcb': project.pcb_path, 'schematic': project.schematic_path,
            'settings': project.pcb_path.with_suffix('.kicad_pro')}[edit]
    owner_edit = path.read_bytes() + b'\n'
    path.write_bytes(owner_edit)
    with pytest.raises(RuntimeError, match='run preview again'):
        update.update_layout(project, candidate=candidate, apply=True)
    assert path.read_bytes() == owner_edit


def test_external_candidate_is_staged_and_concurrent_edit_preserved(project_copy, tmp_path, monkeypatch):
    project = load_project(project_copy)
    candidate = tmp_path / 'candidate.kicad_pcb'
    original = project.pcb_path.read_bytes()
    candidate.write_bytes(original)

    def prepare(snapshot, intent, staged, route, output):
        assert staged != candidate
        assert staged.read_bytes() == original
        staged.write_bytes(b'zone fill changed staged copy')
        candidate.write_bytes(b'owner changed external candidate')
        return staged, [], {}

    monkeypatch.setattr(update, '_prepare_candidate', prepare)
    with pytest.raises(RuntimeError, match='update source changed'):
        update.update_layout(project, candidate=candidate)
    assert project.pcb_path.read_bytes() == original
    assert candidate.read_bytes() == b'owner changed external candidate'


def test_candidate_extension_is_not_silently_rewritten(project_copy, tmp_path):
    project = load_project(project_copy)
    wrong = tmp_path / 'candidate.txt'
    wrong.write_bytes(b'not a board')
    wrong.with_suffix('.kicad_pcb').write_bytes(project.pcb_path.read_bytes())
    with pytest.raises(ValueError, match='existing .kicad_pcb'):
        update.update_layout(project, candidate=wrong)


def test_intent_route_options_must_match_preview(project_copy, staged_candidate):
    project = load_project(project_copy)
    intent = project.root / 'layout-intent.yaml'
    before = project.pcb_path.read_bytes()
    update.update_layout(project, intent, route='human')
    with pytest.raises(RuntimeError, match='run preview again'):
        update.update_layout(project, intent, route='candidate_all', apply=True)
    assert project.pcb_path.read_bytes() == before
    update.update_layout(project, intent, route='human')
    assert update.update_layout(project, intent, route='human', apply=True)['applied']
