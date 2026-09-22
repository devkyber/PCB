"""Scoped adapters for checks not yet relocated from scripts/."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.review.models import CheckResult, CheckScope, FindingKind
from pcb_copilot.review.schematic_quality import SchematicQualityCheck
from pcb_copilot.review.signoff import SignoffCheck

_SCOPES = {
    'gate_research': ('indexed source/reference coverage', 'source applicability or completeness'),
    'gate_datasheets': ('required datasheet files are present', 'correct interpretation of every limit'),
    'gate_erc': ('KiCad electrical-rule findings', 'circuit fitness or safe operation'),
    'gate_schematic_ownership': ('netmap agrees with current schematic', 'the circuit is correct'),
    'gate_netlist_parity': ('schematic/PCB pin-net agreement', 'which side holds the correct intent'),
    'gate_placement': ('implemented placement geometry checks', 'assembly or enclosure fit'),
    'gate_design_rules': ('the implemented subset of house design rules', 'all numbered rules'),
    'gate_drc': ('two refilled KiCad DRC runs and unrouted count', 'thermal, RF, or functional behavior'),
}


@dataclass(frozen=True)
class LegacyCheck:
    check_id: str
    scope: CheckScope
    function: Callable[[Path], tuple[bool, str]]
    finding_kind: FindingKind

    def run(self, project: Project) -> CheckResult:
        passed, detail = self.function(project.pcb_path)
        return CheckResult(self.check_id, passed, detail, self.scope,
                           self.finding_kind)


def legacy_checks() -> tuple[LegacyCheck, ...]:
    repo_root = Path(__file__).resolve().parents[3]
    scripts = str(repo_root / 'scripts')
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    gates = importlib.import_module('run_gates').GATES
    checks = []
    for _name, function, kind in gates:
        if function.__name__ == 'gate_schematic_quality':
            checks.append(SchematicQualityCheck())
            continue
        if function.__name__ == 'gate_signoff':
            checks.append(SignoffCheck())
            continue
        proves, does_not_prove = _SCOPES[function.__name__]
        checks.append(LegacyCheck(
            function.__name__.removeprefix('gate_'),
            CheckScope(proves, does_not_prove,
                       deterministic=function.__name__ != 'gate_drc',
                       requires_external_tool=function.__name__ not in {
                           'gate_signoff', 'gate_schematic_ownership',
                           'gate_schematic_quality',
                       }),
            function,
            FindingKind.HUMAN_DECISION if kind == 'HUMAN' else FindingKind.MACHINE_FAILURE,
        ))
    return tuple(checks)
