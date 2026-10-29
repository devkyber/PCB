import hashlib
import json

import pytest

from pcb_copilot import transaction as tx
from pcb_copilot.project import load_project


def test_interruption_after_write_restores_originals(project_copy, monkeypatch):
    project = load_project(project_copy)
    path = project.pcb_path
    original = path.read_bytes()
    write = tx.replace_bytes

    def interrupt(target, payload):
        write(target, payload)
        if target == path and payload == b'candidate':
            raise KeyboardInterrupt()

    monkeypatch.setattr(tx, 'replace_bytes', interrupt)
    with pytest.raises(KeyboardInterrupt), tx.project_lock(project):
        tx.apply_files(project, {path: b'candidate'}, tx.input_hashes(project))
    assert path.read_bytes() == original
    assert not list((project.root / '.pcb-copilot').glob('recovery-*'))
    assert not (project.root / '.pcb-copilot/operation.lock').exists()


def test_concurrent_edit_is_preserved_and_prior_write_rolled_back(project_copy, monkeypatch):
    project = load_project(project_copy)
    path = project.pcb_path
    other = project.root / 'DEVIATIONS.md'
    original = path.read_bytes()
    write = tx.replace_bytes

    def edit(target, payload):
        write(target, payload)
        if target == path and payload == b'candidate':
            other.write_bytes(b'human edit')

    monkeypatch.setattr(tx, 'replace_bytes', edit)
    with pytest.raises(RuntimeError, match='changed'), tx.project_lock(project):
        tx.apply_files(project, {path: b'candidate', other: b'overwrite'}, tx.input_hashes(project))
    assert path.read_bytes() == original
    assert other.read_bytes() == b'human edit'


def test_failed_rollback_retains_durable_originals_and_lock(project_copy, monkeypatch):
    project = load_project(project_copy)
    path = project.pcb_path
    original = path.read_bytes()
    write = tx.replace_bytes

    def fail(target, payload):
        if target == path:
            if payload == original:
                raise OSError('cannot restore')
            write(target, payload)
            raise KeyboardInterrupt()
        write(target, payload)

    monkeypatch.setattr(tx, 'replace_bytes', fail)
    with pytest.raises(tx.RecoveryRequired, match='Rollback incomplete'), tx.project_lock(project):
        tx.apply_files(project, {path: b'candidate'}, tx.input_hashes(project))
    recovery, = (project.root / '.pcb-copilot').glob('recovery-*')
    journal = json.loads((recovery / 'journal.json').read_text())
    entry = next(item for item in journal if item['path'] == path.name)
    assert (recovery / entry['backup']).read_bytes() == original
    assert (project.root / '.pcb-copilot/operation.lock').exists()
    with pytest.raises(tx.RecoveryRequired), tx.project_lock(project):
        pytest.fail('unrecovered project must remain locked')


def test_new_target_precondition_preserves_owner_file_created_at_commit_entry(project_copy):
    project = load_project(project_copy)
    expected = tx.input_hashes(project)
    target = project.root / 'new-child.kicad_sch'
    target.write_bytes(b'owner created this after preview')
    with pytest.raises(RuntimeError, match='target precondition changed'), tx.project_lock(project):
        tx.apply_files(project, {target: b'candidate child'}, expected, expected_targets={target: None})
    assert target.read_bytes() == b'owner created this after preview'
    assert not list((project.root / '.pcb-copilot').glob('recovery-*'))


def test_target_precondition_checks_captured_bytes_not_an_earlier_read(project_copy, monkeypatch):
    project = load_project(project_copy)
    expected = tx.input_hashes(project)
    target = project.root / 'new-child.kicad_sch'
    read = tx._bytes

    def capture(path):
        if path == target:
            target.write_bytes(b'owner creation at snapshot capture')
        return read(path)

    monkeypatch.setattr(tx, '_bytes', capture)
    with pytest.raises(RuntimeError, match='target precondition changed'), tx.project_lock(project):
        tx.apply_files(project, {target: b'candidate child'}, expected, expected_targets={target: None})
    assert target.read_bytes() == b'owner creation at snapshot capture'


@pytest.mark.parametrize('timing', ['between_writes', 'publication'])
def test_new_owner_file_is_preserved_and_prior_write_rolled_back(project_copy, monkeypatch, timing):
    project = load_project(project_copy)
    expected = tx.input_hashes(project)
    target = project.root / 'new-child.kicad_sch'
    original = project.pcb_path.read_bytes()
    write, link = tx.replace_bytes, tx.os.link

    def edit_after_write(path, payload):
        write(path, payload)
        if path == project.pcb_path and payload == b'candidate pcb':
            target.write_bytes(b'owner created child')

    def edit_at_publication(source, destination):
        if destination == target:
            target.write_bytes(b'owner created child')
        link(source, destination)

    if timing == 'between_writes':
        monkeypatch.setattr(tx, 'replace_bytes', edit_after_write)
    else:
        monkeypatch.setattr(tx.os, 'link', edit_at_publication)
    with pytest.raises(RuntimeError, match='changed|concurrent edit preserved'), tx.project_lock(project):
        tx.apply_files(project, {project.pcb_path: b'candidate pcb', target: b'candidate child'}, expected,
                       expected_targets={target: None})
    assert target.read_bytes() == b'owner created child'
    assert project.pcb_path.read_bytes() == original
    assert not list((project.root / '.pcb-copilot').glob('recovery-*'))
    assert not target.with_name(target.name + '.transaction-tmp').exists()


def test_explicit_hash_precondition_preserves_untracked_owner_edit(project_copy):
    project = load_project(project_copy)
    target = project.root / 'owner-notes.txt'
    original = b'original notes'
    target.write_bytes(b'owner edited notes')
    with pytest.raises(RuntimeError, match='target precondition changed'), tx.project_lock(project):
        tx.apply_files(project, {target: b'replacement'}, tx.input_hashes(project),
                       expected_targets={target: hashlib.sha256(original).hexdigest()})
    assert target.read_bytes() == b'owner edited notes'


@pytest.mark.parametrize('interrupt', [False, True])
def test_exclusive_new_file_publication_and_rollback(project_copy, monkeypatch, interrupt):
    project = load_project(project_copy)
    target = project.root / 'new-child.kicad_sch'
    expected = tx.input_hashes(project)
    create = tx.create_bytes

    def publish(path, payload):
        create(path, payload)
        if path == target and interrupt:
            raise KeyboardInterrupt()

    monkeypatch.setattr(tx, 'create_bytes', publish)
    if interrupt:
        with pytest.raises(KeyboardInterrupt), tx.project_lock(project):
            tx.apply_files(project, {target: b'complete child'}, expected, expected_targets={target: None})
        assert not target.exists()
    else:
        with tx.project_lock(project):
            tx.apply_files(project, {target: b'complete child'}, expected, expected_targets={target: None})
        assert target.read_bytes() == b'complete child'
    assert not target.with_name(target.name + '.transaction-tmp').exists()


@pytest.mark.parametrize('publish', [tx.replace_bytes, tx.create_bytes])
def test_temporary_file_collision_preserves_other_writer_data(tmp_path, publish):
    target = tmp_path / 'target.kicad_sch'
    temporary = target.with_name(target.name + '.transaction-tmp')
    temporary.write_bytes(b'another writer owns these bytes')
    with pytest.raises(FileExistsError):
        publish(target, b'candidate')
    assert temporary.read_bytes() == b'another writer owns these bytes'
    assert not target.exists()


def test_distinct_schematic_companion_settings_are_snapshotted(project_copy, tmp_path):
    from dataclasses import replace
    from shutil import copyfile

    from pcb_copilot.project import load_project
    from pcb_copilot.transaction import assert_current, copy_inputs, input_hashes

    project = load_project(project_copy)
    schematic = project.root / 'capture.kicad_sch'
    copyfile(project.schematic_path, schematic)
    project = replace(project, schematic_path=schematic)
    settings = schematic.with_suffix('.kicad_pro')
    settings.write_bytes(b'{"erc": {"ignored": []}}')
    expected = input_hashes(project)
    assert expected['capture.kicad_pro']
    copy_inputs(project, tmp_path / 'isolated', expected)
    assert (tmp_path / 'isolated/capture.kicad_pro').read_bytes() == settings.read_bytes()
    settings.write_bytes(b'{"erc": {"ignored": ["new"]}}')
    with pytest.raises(RuntimeError, match='inputs changed'):
        assert_current(project, expected)


def test_operation_workspace_alias_is_rejected_before_any_owner_write(project_copy):
    project = load_project(project_copy)
    owner = project.root / 'owner-notes'
    owner.mkdir()
    note = owner / 'keep.txt'
    note.write_bytes(b'owner')
    try:
        (project.root / '.pcb-copilot').symlink_to(owner, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'directory symlinks unavailable: {exc}')
    with pytest.raises(ValueError, match='symlink or reparse'), tx.project_lock(project):
        pytest.fail('aliased workspace acquired')
    assert list(owner.iterdir()) == [note]
    assert note.read_bytes() == b'owner'
