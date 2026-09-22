"""Review the current design without allowing legacy checks to mutate it."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.project import load_project
from pcb_copilot.review.legacy import legacy_checks
from pcb_copilot.review.models import ReviewReport
from pcb_copilot.review.registry import Check, run_checks


def review_project(project: Project, checks: Sequence[Check] | None = None) -> ReviewReport:
    """Run all checks on a disposable byte copy of the current project."""
    selected = tuple(legacy_checks() if checks is None else checks)
    with tempfile.TemporaryDirectory(prefix='pcb-copilot-review-') as temporary:
        staged_root = Path(temporary) / project.root.name
        shutil.copytree(
            project.root, staged_root,
            ignore=shutil.ignore_patterns('.pcb-copilot', 'fabrication',
                                          '__pycache__', '.history', '.backups'),
        )
        return run_checks(load_project(staged_root), selected)


def render_review_json(report: ReviewReport) -> str:
    return json.dumps(asdict(report), indent=2, ensure_ascii=False)


def render_review_text(report: ReviewReport) -> str:
    lines = [f'Review: {report.project}',
             f'Schematic: {report.schematic_hash[:12]}  PCB: {report.pcb_hash[:12]}']
    for result in report.results:
        lines.append(f'[{"PASS" if result.passed else "FAIL"}] {result.check_id}: {result.detail}')
        lines.append(f'  proves: {result.scope.proves}')
        lines.append(f'  does not prove: {result.scope.does_not_prove}')
        lines.extend(f'  advisory: {warning}' for warning in result.advisories)
    lines.append('RESULT: BLOCKED' if report.blocking else 'RESULT: no registered blocker')
    return '\n'.join(lines)
