"""Bind an update to the saved inputs of its last successful preview."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.transaction import (
    assert_current,
    assert_editors_closed,
    contained,
    input_hashes,
    replace_bytes,
)

_RERUN = 'run preview again against saved current CAD before applying'


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


@dataclass
class UpdateGuard:
    project: Project
    report_path: Path
    expected: dict
    binding: dict
    sources: dict[str, tuple[Path, bytes | None]]

    def stage(self, directory: Path) -> dict[str, Path]:
        """Tools may mutate these copies, never the owner's request files."""
        directory.mkdir(parents=True)
        staged = {}
        for name, (_, payload) in self.sources.items():
            if payload is not None:
                target = contained(directory, directory / name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                staged[name] = target
        return staged

    def check(self, *, apply: bool = False) -> None:
        try:
            assert_current(self.project, self.expected)
        except RuntimeError as error:
            raise RuntimeError(f'{error}; {_RERUN}') from error
        for path, payload in self.sources.values():
            if _read(path) != payload:
                raise RuntimeError(f'update source changed: {path}; {_RERUN}')
        if apply:
            assert_editors_closed(self.project)


def begin_update(project: Project, workspace: Path, kind: str,
                 source_paths: dict[str, Path], options: dict, *, apply: bool) -> UpdateGuard:
    """Call under project_lock; consume any old preview even if this run fails.

    Source paths include absent optional companion files so adding a project or
    rules file after preview cannot silently change the candidate's checks.
    A preview records bytes on disk, not unsaved state in a running CAD editor.
    """
    report_path = contained(project.root, workspace / 'preview' / f'{kind}-review.json')
    try:
        previous = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        previous = None
    replace_bytes(report_path, (json.dumps({
        'applied': False, 'exit_code': 1,
        'findings': [{'severity': 'block', 'code': 'update.incomplete',
                      'message': f'Update not completed; {_RERUN}.'}],
    }, indent=2) + '\n').encode())
    expected = input_hashes(project)
    sources = {name: (path.resolve(), _read(path)) for name, path in source_paths.items()}
    binding = {
        'version': 1, 'project': str(project.root.resolve()), 'inputs': expected,
        'options': options,
        'sources': {name: {'path': str(path), 'sha256': (
            hashlib.sha256(payload).hexdigest() if payload is not None else None)}
                    for name, (path, payload) in sources.items()},
    }
    if apply:
        assert_editors_closed(project)
        findings = previous.get('findings') if isinstance(previous, dict) else None
        if (not isinstance(previous, dict) or previous.get('applied') is not False
                or previous.get('exit_code') != 0
                or not isinstance(findings, list)
                or any(not isinstance(item, dict) or item.get('severity') == 'block' for item in findings)
                or previous.get('preview_binding') != binding):
            raise RuntimeError(f'No successful matching unconsumed preview; {_RERUN}')
    return UpdateGuard(project, report_path, expected, binding, sources)
