"""Structural checks for every referenced sheet of the current schematic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.review.models import CheckResult, CheckScope
from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.schematic.quality import analyse_schematic

SCOPE = CheckScope(
    proves='all referenced sheets have title/revision and acceptable density',
    does_not_prove='visual readability, electrical correctness, or page-flow quality',
    deterministic=True,
    requires_external_tool=False,
)


def check_schematic_sheets(root: Path) -> CheckResult:
    sheets = schematic_files(root)
    problems: list[str] = []
    advisories: list[str] = []
    for sheet in sheets:
        metrics = analyse_schematic(sheet)
        if not metrics.title_complete:
            problems.append(f'{sheet.name}: title or revision missing')
        if metrics.component_count > metrics.page_capacity:
            problems.append(
                f'{sheet.name}: {metrics.component_count} components exceed '
                f'{metrics.paper} capacity ~{metrics.page_capacity}',
            )
        if metrics.component_count >= 5 and metrics.junction_count == 0:
            advisories.append(
                f'{sheet.name}: {metrics.component_count} components but no wire junctions; '
                'inspect whether labels obscure circuit flow',
            )
    detail = f'{len(sheets)} sheet(s) checked'
    if problems:
        detail += '; ' + '; '.join(problems)
    return CheckResult('schematic_quality', not problems, detail, SCOPE,
                       advisories=tuple(advisories))


@dataclass(frozen=True)
class SchematicQualityCheck:
    check_id: str = 'schematic_quality'
    scope: CheckScope = SCOPE

    def run(self, project: Project) -> CheckResult:
        return check_schematic_sheets(project.schematic_path)
