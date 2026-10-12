import json

import pytest

from pcb_copilot.project import load_project
from pcb_copilot.transaction import project_lock, replace_bytes
from pcb_copilot.update_guard import begin_update


def preview(project, sources, options=None, *, exit_code=0, applied=False):
    with project_lock(project) as workspace:
        guard = begin_update(project, workspace, 'layout', sources, options or {}, apply=False)
        guard.check()
        replace_bytes(guard.report_path, json.dumps({
            'exit_code': exit_code, 'applied': applied, 'findings': [],
            'preview_binding': guard.binding,
        }).encode())
    return guard


def apply(project, sources, options=None):
    with project_lock(project) as workspace:
        return begin_update(project, workspace, 'layout', sources, options or {}, apply=True)


def test_missing_preview_blocks_without_touching_cad(project_copy):
    project = load_project(project_copy)
    before = project.pcb_path.read_bytes()
    with pytest.raises(RuntimeError, match='run preview again'):
        apply(project, {'candidate.kicad_pcb': project.pcb_path})
    assert project.pcb_path.read_bytes() == before


@pytest.mark.parametrize('edit', ['source', 'source_path', 'options', 'companion_added', 'companion_removed'])
def test_request_changes_invalidate_preview(project_copy, tmp_path, edit):
    project = load_project(project_copy)
    candidate = tmp_path / 'external.kicad_pcb'
    candidate.write_bytes(project.pcb_path.read_bytes())
    companion = candidate.with_suffix('.kicad_dru')
    if edit == 'companion_removed':
        companion.write_bytes(b'(version 1)')
    sources = {'candidate.kicad_pcb': candidate, 'candidate.kicad_dru': companion}
    preview(project, sources, {'route': 'human'})
    options = {'route': 'human'}
    if edit == 'source':
        candidate.write_bytes(candidate.read_bytes() + b'\n')
    elif edit == 'source_path':
        replacement = tmp_path / 'same-bytes.kicad_pcb'
        replacement.write_bytes(candidate.read_bytes())
        sources['candidate.kicad_pcb'] = replacement
    elif edit == 'options':
        options['route'] = 'candidate_all'
    elif edit == 'companion_added':
        companion.write_bytes(b'(version 1)')
    else:
        companion.unlink()
    with pytest.raises(RuntimeError, match='run preview again'):
        apply(project, sources, options)


@pytest.mark.parametrize('state', ['failed', 'applied', 'interrupted', 'malformed'])
def test_only_successful_unconsumed_preview_can_authorize_apply(project_copy, state):
    project = load_project(project_copy)
    sources = {'candidate.kicad_pcb': project.pcb_path}
    guard = preview(project, sources, exit_code=int(state == 'failed'), applied=state == 'applied')
    if state == 'interrupted':
        with project_lock(project) as workspace:
            begin_update(project, workspace, 'layout', sources, {}, apply=False)
    elif state == 'malformed':
        guard.report_path.write_text('{')
    with pytest.raises(RuntimeError, match='run preview again'):
        apply(project, sources)


def test_apply_attempt_consumes_preview_even_if_later_step_fails(project_copy):
    project = load_project(project_copy)
    sources = {'candidate.kicad_pcb': project.pcb_path}
    preview(project, sources)
    apply(project, sources)
    with pytest.raises(RuntimeError, match='run preview again'):
        apply(project, sources)


@pytest.mark.parametrize('suffix', ['.kicad_pcb', '.kicad_sch', '.kicad_pro'])
def test_editor_lock_allows_preview_but_blocks_apply(project_copy, suffix):
    project = load_project(project_copy)
    target = project.pcb_path.with_suffix(suffix)
    lock = target.with_name('~' + target.name + '.lck')
    lock.write_text('editor pid')
    sources = {'candidate.kicad_pcb': project.pcb_path}
    preview(project, sources)
    with pytest.raises(RuntimeError, match='save and close'):
        apply(project, sources)
    assert lock.read_text() == 'editor pid'


def test_editor_opened_during_processing_blocks_commit(project_copy):
    project = load_project(project_copy)
    sources = {'candidate.kicad_pcb': project.pcb_path}
    preview(project, sources)
    guard = apply(project, sources)
    lock = project.pcb_path.with_name('~' + project.pcb_path.name + '.lck')
    lock.write_text('editor pid')
    with pytest.raises(RuntimeError, match='save and close'):
        guard.check(apply=True)


def test_staging_preserves_external_source_and_detects_later_change(project_copy, tmp_path):
    project = load_project(project_copy)
    source = tmp_path / 'external-intent.yaml'
    source.write_bytes(b'initial request')
    guard = preview(project, {'sheets/intent.yaml': source})
    staged = guard.stage(tmp_path / 'stage')
    staged['sheets/intent.yaml'].write_bytes(b'changed by native tool')
    assert source.read_bytes() == b'initial request'
    guard.check()
    source.write_bytes(b'new owner request')
    with pytest.raises(RuntimeError, match='update source changed'):
        guard.check()
