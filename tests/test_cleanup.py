from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from pcb_copilot import cleanup
from pcb_copilot.project import load_project


def _preview(project_copy, name, payload=b'regenerable preview'):
    path = project_copy / '.pcb-copilot/preview' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_preview_is_read_only_and_empty_project_gets_no_workspace(project_copy, tree_hash):
    project = load_project(project_copy)
    before = tree_hash(project_copy)
    assert cleanup.clean_project(project)['file_count'] == 0
    assert not (project_copy / '.pcb-copilot').exists()
    path = _preview(project_copy, 'layout.svg')
    before = tree_hash(project_copy)

    result = cleanup.clean_project(project)

    assert result['applied'] is False
    assert result['file_count'] == 1
    assert result['files'][0]['path'] == '.pcb-copilot/preview/layout.svg'
    assert result['bytes'] == path.stat().st_size
    assert len(result['files'][0]['sha256']) == 64
    assert tree_hash(project_copy) == before


def test_apply_removes_only_allowlisted_files_and_invalidates_bindings(project_copy):
    project = load_project(project_copy)
    for name in (*cleanup.PREVIEW_BINDINGS, *cleanup.PREVIEW_ARTIFACTS):
        _preview(project_copy, name)
    for name in ('.pcb-copilot/preview/owner-note.md', '.pcb-copilot/preview/source/layout.svg',
                 '.pcb-copilot/reports/human-review.md', '.pcb-copilot/release.json',
                 '.pcb-copilot/acceptances/completed/board.kicad_pcb',
                 '.pcb-copilot/drafts/candidate.kicad_pcb', 'fabrication/release.zip',
                 'evidence/extra.pdf', 'review-signoff.yaml'):
        path = project_copy / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'owner retained bytes\r\n')
    expected = {p: p.read_bytes() for p in project_copy.rglob('*') if p.is_file()
                and not (p.parent == project_copy / '.pcb-copilot/preview'
                         and p.name in (*cleanup.PREVIEW_BINDINGS, *cleanup.PREVIEW_ARTIFACTS))}

    result = cleanup.clean_project(project, apply=True)

    assert result['applied'] is True
    assert result['file_count'] == len(cleanup.PREVIEW_BINDINGS) + len(cleanup.PREVIEW_ARTIFACTS)
    assert all(not (project_copy / item['path']).exists() for item in result['files'])
    assert {p: p.read_bytes() for p in project_copy.rglob('*') if p.is_file()} == expected
    assert cleanup.clean_project(project, apply=True)['file_count'] == 0


def test_bindings_removed_before_export_even_if_cleanup_interrupted(project_copy, monkeypatch):
    project = load_project(project_copy)
    for name in cleanup.PREVIEW_BINDINGS:
        _preview(project_copy, name)
    export = _preview(project_copy, 'layout.svg')
    original_unlink = Path.unlink

    def interrupt(path, *args, **kwargs):
        if path == export:
            assert all(not (export.parent / name).exists() for name in cleanup.PREVIEW_BINDINGS)
            raise OSError('simulated cleanup interruption')
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', interrupt)
    with pytest.raises(OSError, match='simulated'):
        cleanup.clean_project(project, apply=True)

    assert export.exists()
    assert not (project_copy / '.pcb-copilot/operation.lock').exists()


@pytest.mark.parametrize('name', ['operation.lock', 'accept.lock', 'recovery-update-incomplete'])
@pytest.mark.parametrize('apply', [False, True])
def test_locks_and_recovery_refuse_cleanup(project_copy, tree_hash, name, apply):
    project = load_project(project_copy)
    export = _preview(project_copy, 'layout.svg')
    retained = project_copy / '.pcb-copilot' / name
    retained.write_text('another operation owns this', encoding='utf-8')
    before = tree_hash(project_copy)

    with pytest.raises(RuntimeError, match='lock|recovery'):
        cleanup.clean_project(project, apply=apply)

    assert tree_hash(project_copy) == before
    assert export.exists()


@pytest.mark.parametrize('level', ['workspace', 'preview', 'file'])
def test_symlink_targets_refused(project_copy, tmp_path, level):
    project = load_project(project_copy)
    outside = tmp_path / 'outside'
    outside.mkdir()
    original = outside / 'layout.svg'
    original.write_bytes(b'outside owner file')
    if level == 'workspace':
        link, target = project_copy / '.pcb-copilot', outside
    elif level == 'preview':
        link, target = project_copy / '.pcb-copilot/preview', outside
    else:
        link, target = project_copy / '.pcb-copilot/preview/layout.svg', original
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=level != 'file')
    except OSError as error:
        pytest.skip(f'symlink creation unavailable: {error}')

    with pytest.raises(ValueError, match='symlink|reparse'):
        cleanup.clean_project(project, apply=True)

    assert original.read_bytes() == b'outside owner file'
    assert link.is_symlink()


def test_windows_reparse_directory_refused(project_copy, monkeypatch):
    project = load_project(project_copy)
    export = _preview(project_copy, 'layout.svg')
    original_lstat = Path.lstat

    def junction(path, *args, **kwargs):
        info = original_lstat(path, *args, **kwargs)
        if path == export.parent:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info

    monkeypatch.setattr(Path, 'lstat', junction)
    with pytest.raises(ValueError, match='reparse'):
        cleanup.clean_project(project, apply=True)

    assert export.exists()


def test_traversal_allowlist_entry_refused(project_copy, monkeypatch, tree_hash):
    project = load_project(project_copy)
    _preview(project_copy, 'layout.svg')
    monkeypatch.setattr(cleanup, 'PREVIEW_ARTIFACTS', ('../../baro-bmp390.kicad_pcb',))
    before = tree_hash(project_copy)

    with pytest.raises(ValueError, match='simple name'):
        cleanup.clean_project(project, apply=True)

    assert tree_hash(project_copy) == before


def test_manifest_input_cannot_be_deleted_even_with_preview_filename(project_copy, tree_hash):
    project = load_project(project_copy)
    declared = _preview(project_copy, 'layout-review.json', b'{"nets": {}}')
    project = replace(project, netmap_path=declared)
    before = tree_hash(project_copy)

    with pytest.raises(ValueError, match='declared project input'):
        cleanup.clean_project(project, apply=True)

    assert tree_hash(project_copy) == before


def test_changed_preview_preserved_during_apply(project_copy, monkeypatch):
    project = load_project(project_copy)
    binding = _preview(project_copy, 'layout-review.json')
    export = _preview(project_copy, 'layout.svg')
    original_unlink = Path.unlink

    def change_export(path, *args, **kwargs):
        result = original_unlink(path, *args, **kwargs)
        if path == binding:
            export.write_bytes(b'new owner preview')
        return result

    monkeypatch.setattr(Path, 'unlink', change_export)
    with pytest.raises(RuntimeError, match='preview changed'):
        cleanup.clean_project(project, apply=True)

    assert export.read_bytes() == b'new owner preview'
    assert not binding.exists()
