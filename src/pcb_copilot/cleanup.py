"""Remove only regenerable latest previews, never CAD or retained working history."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.transaction import (
    RecoveryRequired,
    assert_current,
    contained,
    input_hashes,
    project_lock,
)

PREVIEW_BINDINGS = (
    'schematic-review.json', 'layout-review.json', 'routing-settings-review.json',
)
PREVIEW_ARTIFACTS = (
    'layout.svg', 'layout.step', 'layout-drc-0.json', 'layout-drc-1.json',
    'drc.json', 'export-report.json', 'schematic.pdf', 'schematic-erc.json',
    'schematic-metrics.json', 'routing-topology.json',
)


def _plain_path(root: Path, path: Path) -> Path:
    """Reject links/junctions at every component, before following any path."""
    relative = path.relative_to(root)
    if '..' in relative.parts:
        raise ValueError(f'cleanup path escapes project: {path}')
    current = root
    for part in relative.parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise ValueError(f'cleanup refuses symlink or reparse point: {current}')
    contained(root, path)
    return path


def _check_workspace(project: Project, *, locked: bool = False) -> Path:
    workspace = _plain_path(project.root, project.root / '.pcb-copilot')
    preview = _plain_path(project.root, workspace / 'preview')
    for directory in (workspace, preview):
        if directory.exists() and not directory.is_dir():
            raise ValueError(f'cleanup expected a directory: {directory}')
    locks = ('accept.lock',) if locked else ('operation.lock', 'accept.lock')
    for name in locks:
        lock = _plain_path(project.root, workspace / name)
        if lock.exists():
            raise RuntimeError(f'cleanup blocked by active operation lock: {lock}')
    if any(workspace.glob('recovery-*')):
        raise RecoveryRequired(f'Inspect retained recovery files in {workspace} before cleanup')
    return preview


def _plan(project: Project, preview: Path, inputs: dict) -> list[dict]:
    entries = []
    for name in (*PREVIEW_BINDINGS, *PREVIEW_ARTIFACTS):
        if Path(name).name != name:
            raise ValueError(f'cleanup filename must be a simple name: {name}')
        path = _plain_path(project.root, preview / name)
        if not path.exists():
            continue
        if not path.is_file():
            raise ValueError(f'cleanup expected a regular file: {path}')
        relative = path.relative_to(project.root).as_posix()
        if relative in inputs:
            raise ValueError(f'cleanup refuses declared project input: {relative}')
        payload = path.read_bytes()
        entries.append({'path': relative, 'bytes': len(payload),
                        'sha256': hashlib.sha256(payload).hexdigest()})
    return entries


def clean_project(project: Project, apply: bool = False) -> dict:
    """Return a read-only plan, or delete its current allowlisted preview files.

    The returned JSON-compatible dictionary lists relative paths, sizes, hashes,
    total ``file_count``/``bytes`` and ``applied``. Apply rescans while holding the
    project operation lock. Preview authorization reports are deleted first;
    another update must preview again. Unknown files, directories, recovery,
    drafts, acceptance history and fabrication output are never cleanup targets.
    No archive is required: this API only handles reproducible latest exports.
    """
    preview = _check_workspace(project)
    expected = input_hashes(project)
    entries = _plan(project, preview, expected)
    if apply and entries:
        with project_lock(project):
            preview = _check_workspace(project, locked=True)
            assert_current(project, expected)
            entries = _plan(project, preview, expected)
            for entry in entries:
                _check_workspace(project, locked=True)
                path = _plain_path(project.root, project.root / entry['path'])
                if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                    raise RuntimeError(f'preview changed during cleanup: {path}')
                path.unlink()
            assert_current(project, expected)
    return {'project': project.manifest.name, 'applied': apply, 'files': entries,
            'file_count': len(entries), 'bytes': sum(entry['bytes'] for entry in entries)}
