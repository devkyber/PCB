"""Run every current-design check, including after failures and crashes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from time import perf_counter
from typing import Protocol

from pcb_copilot.models import Project
from pcb_copilot.review.fingerprint import pcb_digest, schematic_digest
from pcb_copilot.review.models import (
    CheckResult,
    CheckScope,
    Finding,
    FindingKind,
    ReviewReport,
)


class Check(Protocol):
    check_id: str
    scope: CheckScope

    def run(self, project: Project) -> CheckResult: ...


def run_checks(project: Project, checks: Sequence[Check]) -> ReviewReport:
    """Run all checks and turn exceptions into blocking, scoped findings."""
    schematic_hash = schematic_digest(project.schematic_path)
    pcb_hash = pcb_digest(project.pcb_path)
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
        findings.extend(Finding(result.check_id, FindingKind.ENGINEERING_WARNING,
                                warning, False) for warning in result.advisories)
    return ReviewReport(
        project.manifest.name,
        schematic_hash,
        pcb_hash,
        tuple(results), tuple(findings), any(finding.blocking for finding in findings),
    )
