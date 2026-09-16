from datetime import datetime, timezone
from pathlib import Path

import pytest

from pcb_copilot.drafts import DraftKind, create_draft
from pcb_copilot.project import load_project
from pcb_copilot.schematic.hierarchy import HierarchyDraft
from pcb_copilot.schematic.io import load_schematic_intent
from pcb_copilot.schematic.render import render_schematic_draft


@pytest.fixture
def fixed_clock():
    return lambda: datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def rendered(project_copy: Path, repo_root: Path, fixed_clock):
    project = load_project(project_copy)
    intent = load_schematic_intent(
        repo_root / "tests/fixtures/schematic/two-block.yaml"
    )
    draft = create_draft(project, DraftKind.SCHEMATIC, fixed_clock)
    return render_schematic_draft(project, intent, draft)


@pytest.fixture
def hierarchical_draft(project_copy: Path, repo_root: Path, fixed_clock) -> HierarchyDraft:
    project = load_project(project_copy)
    intent = load_schematic_intent(
        repo_root / "tests/fixtures/schematic/parent-child.yaml"
    )
    draft = create_draft(project, DraftKind.SCHEMATIC, fixed_clock)
    result = render_schematic_draft(project, intent, draft)
    assert isinstance(result, HierarchyDraft)
    return result
