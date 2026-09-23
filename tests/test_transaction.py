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
