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
    return json.dumps({'schema_version': 1, **asdict(report)}, indent=2,
                      ensure_ascii=False, sort_keys=True)


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


def render_review_markdown(report: ReviewReport) -> str:
    lines = [
        f'# Review: {report.project}', '',
        f'- Schematic SHA-256 (root and referenced sheets): `{report.schematic_hash}`',
        f'- PCB SHA-256: `{report.pcb_hash}`',
        f'- Result: **{"BLOCKED" if report.blocking else "no registered blocker"}**',
        '',
    ]
    for result in report.results:
        lines.extend([
            f'## {result.check_id} — {"PASS" if result.passed else "FAIL"}', '',
            result.detail.strip(), '',
            f'- Proves: {result.scope.proves}',
            f'- Does not prove: {result.scope.does_not_prove}',
            f'- Deterministic: {"yes" if result.scope.deterministic else "no"}',
            f'- External tool: {"yes" if result.scope.requires_external_tool else "no"}',
        ])
        lines.extend(f'- Advisory: {warning}' for warning in result.advisories)
        lines.append('')
    return '\n'.join(lines)


def write_review_report(project: Project, output: Path, rendered: str) -> Path:
    """Create a new local report; never overwrite design or prior review data."""
    reports = (project.root / '.pcb-copilot' / 'reports').resolve()
    target = output.resolve()
    if (not reports.is_relative_to(project.root.resolve())
            or not target.is_relative_to(reports)
            or target.suffix not in {'.json', '.md'}):
        raise ValueError('review output must be a .json or .md file under .pcb-copilot/reports')
    reports.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as stream:
        stream.write(rendered + ('\n' if not rendered.endswith('\n') else ''))
    return target
