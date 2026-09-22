"""Run every current-design check, including after failures and crashes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from time import perf_counter
from typing import Protocol

from pcb_copilot.models import Project
from pcb_copilot.review.models import (
    CheckResult,
    CheckScope,
    Finding,
    FindingKind,
    ReviewReport,
)
from pcb_copilot.state import canonical_design_hash


class Check(Protocol):
    check_id: str
    scope: CheckScope

    def run(self, project: Project) -> CheckResult: ...


def run_checks(project: Project, checks: Sequence[Check]) -> ReviewReport:
    """Run all checks and turn exceptions into blocking, scoped findings."""
    results: list[CheckResult] = []
    findings: list[Finding] = []
    for check in checks:
        started = perf_counter()
        try:
            result = check.run(project)
            if result.check_id != check.check_id:
                raise ValueError('check returned the wrong identifier')
        except Exception as exc:  # noqa: BLE001 - a crashed gate must not hide later checks
            result = CheckResult(
                check.check_id, False, f'check crashed: {exc}', check.scope,
                FindingKind.MACHINE_FAILURE,
            )
        result = replace(result, duration_ms=max(0, int((perf_counter() - started) * 1000)))
        results.append(result)
        if not result.passed:
            findings.append(Finding(result.check_id, result.finding_kind,
                                    result.detail, True))
    return ReviewReport(
        project.manifest.name,
        canonical_design_hash(project.schematic_path),
        canonical_design_hash(project.pcb_path),
        tuple(results), tuple(findings), bool(findings),
    )
