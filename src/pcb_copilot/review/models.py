"""Typed results that keep machine findings separate from human judgment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FindingKind(str, Enum):
    MACHINE_FAILURE = 'machine_failure'
    ENGINEERING_WARNING = 'engineering_warning'
    HUMAN_DECISION = 'human_decision'


@dataclass(frozen=True)
class CheckScope:
    proves: str
    does_not_prove: str
    deterministic: bool
    requires_external_tool: bool


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    passed: bool
    detail: str
    scope: CheckScope
    finding_kind: FindingKind = FindingKind.MACHINE_FAILURE
    duration_ms: int = 0


@dataclass(frozen=True)
class Finding:
    check_id: str
    kind: FindingKind
    detail: str
    blocking: bool


@dataclass(frozen=True)
class ReviewReport:
    project: str
    schematic_hash: str
    pcb_hash: str
    results: tuple[CheckResult, ...]
    findings: tuple[Finding, ...]
    blocking: bool
