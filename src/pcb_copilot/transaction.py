"""Exact project snapshots and rollback for explicitly requested changes."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.schematic.preview import schematic_files


def contained(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if resolved == root.resolve() or not resolved.is_relative_to(root.resolve()):
        raise ValueError(f'path escapes project: {path}')
    return resolved


def input_hashes(project: Project, *, include_signoff: bool = True) -> dict[str, str | None]:
    """Bind review to CAD, rules, evidence, intent and engineering decisions."""
    paths = set(schematic_files(project.schematic_path))
    paths.update((project.pcb_path, project.pcb_path.with_suffix('.kicad_pro'),
                  project.pcb_path.with_suffix('.kicad_dru'), project.netmap_path,
                  project.manifest_path, project.evidence_index_path))
    paths.update(project.root / name for name in (
        'REQUIREMENTS.md', 'DESIGN_BASIS.md', 'REFERENCE_REVIEW.md', 'DEVIATIONS.md',
        'review-profile.yaml', 'schematic-intent.yaml', 'layout-intent.yaml',
        'sym-lib-table', 'fp-lib-table',
    ))
    if include_signoff:
        paths.add(project.root / 'review-signoff.yaml')
    for directory in (project.evidence_index_path.parent, project.root / 'libs',
                      project.root / 'symbols', project.root / 'footprints'):
        contained(project.root, directory)
        if directory.is_dir():
            paths.update(path for path in directory.rglob('*') if path.is_file())
    hashes = {}
    for path in sorted(paths):
        contained(project.root, path)
        hashes[path.relative_to(project.root).as_posix()] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
    return hashes


def inputs_digest(project: Project) -> str:
    document = json.dumps(input_hashes(project, include_signoff=False), sort_keys=True)
    return hashlib.sha256(document.encode()).hexdigest()


def assert_current(project: Project, expected: dict) -> None:
    if input_hashes(project) != expected:
        raise RuntimeError('project inputs changed during the operation; rerun on the current design')


def copy_inputs(project: Project, destination: Path, expected: dict) -> None:
    destination.mkdir(parents=True)
    for relative, digest in expected.items():
        if digest is not None:
            target = contained(destination, destination / relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(project.root / relative, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f'project input changed while copying: {relative}')
    assert_current(project, expected)


class RecoveryRequired(RuntimeError):
    """A failed rollback has retained its journal and original files."""


@contextmanager
def recovery_directory(project: Project, operation: str):
    workspace = contained(project.root, project.root / '.pcb-copilot')
    workspace.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=f'recovery-{operation}-', dir=workspace))
    try:
        yield directory
    except RecoveryRequired:
        raise
    except BaseException as error:
        if directory.exists():
            raise RecoveryRequired(f'Operation interrupted; inspect recovery data in {directory}: {error}') from error
        raise
    else:
        shutil.rmtree(contained(workspace, directory))


@contextmanager
def project_lock(project: Project):
    workspace = contained(project.root, project.root / '.pcb-copilot')
    workspace.mkdir(exist_ok=True)
    if any(workspace.glob('recovery-*')):
        raise RecoveryRequired(f'Inspect retained recovery files in {workspace} before retrying')
    lock = contained(project.root, workspace / 'operation.lock')
    with lock.open('x', encoding='utf-8') as stream:
        stream.write(str(os.getpid()))
    try:
        yield workspace
    finally:
        if not any(workspace.glob("recovery-*")):
            lock.unlink(missing_ok=True)


def replace_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.transaction-tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def apply_files(project: Project, changes: dict[Path, bytes | None], expected: dict) -> None:
    """Keep originals on disk until every write and input check succeeds."""
    assert_current(project, expected)
    changes = dict(changes)
    changes[project.root / '.pcb-copilot/review.json'] = None
    changes[project.root / '.pcb-copilot/release.json'] = None
    for path in changes:
        contained(project.root, path)
    before = {path: _bytes(path) for path in changes}
    wanted = dict(expected)
    attempted = []

    def check_inputs():
        # Read original paths directly: a replacement root sheet can briefly refer
        # to child sheets that have not been installed yet.
        for relative, digest in wanted.items():
            payload = _bytes(project.root / relative)
            actual = hashlib.sha256(payload).hexdigest() if payload is not None else None
            if actual != digest:
                raise RuntimeError(f'project input changed during update: {relative}')

    with recovery_directory(project, 'update') as recovery:
        journal = []
        for index, (path, payload) in enumerate(before.items()):
            backup = str(index) if payload is not None else None
            if payload is not None:
                replace_bytes(recovery / backup, payload)
            journal.append({'path': path.relative_to(project.root).as_posix(), 'backup': backup})
        replace_bytes(recovery / 'journal.json', json.dumps(journal, indent=2).encode())
        try:
            for path, payload in changes.items():
                check_inputs()
                if _bytes(path) != before[path]:
                    raise RuntimeError(f'concurrent edit preserved: {path}')
                attempted.append(path)
                if payload is None:
                    path.unlink(missing_ok=True)
                else:
                    replace_bytes(path, payload)
                wanted[path.relative_to(project.root).as_posix()] = (
                    hashlib.sha256(payload).hexdigest() if payload is not None else None)
            check_inputs()
            for relative, digest in input_hashes(project).items():
                if relative not in wanted or wanted[relative] != digest:
                    raise RuntimeError(f'project inputs changed during update: {relative}')
        except BaseException:
            failures = []
            for path in reversed(attempted):
                try:
                    current = _bytes(path)
                    if current == before[path]:
                        continue
                    if current != changes[path]:
                        raise RuntimeError(f'concurrent edit preserved: {path}')
                    if before[path] is None:
                        path.unlink(missing_ok=True)
                    else:
                        replace_bytes(path, before[path])
                except BaseException as error:
                    failures.append(str(error) or type(error).__name__)
            if failures:
                raise RecoveryRequired(f'Rollback incomplete; originals and journal: {recovery}; '
                                       + '; '.join(failures)) from None
            shutil.rmtree(contained(project.root, recovery))
            raise
