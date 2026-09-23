import json
from pathlib import Path

import pytest

from pcb_copilot.models import Lifecycle, Project
from pcb_copilot.project import load_project
from pcb_copilot.state import (
    UnsafeDraftTarget,
    assert_draft_target_safe,
    canonical_design_hash,
    effective_lifecycle,
)


@pytest.fixture
def released_project(project_copy: Path) -> Project:
    project = load_project(project_copy)
    state_dir = project.root / ".pcb-copilot"
    state_dir.mkdir()
    record = {
        "schema_version": 1,
        "lifecycle": "RELEASED",
        "schematic_hash": canonical_design_hash(project.schematic_path),
        "pcb_hash": canonical_design_hash(project.pcb_path),
    }
    (state_dir / "release.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return project


def test_uuid_only_change_keeps_canonical_hash(tmp_path):
    first = tmp_path / "a.kicad_sch"
    second = tmp_path / "b.kicad_sch"
    first.write_text('(uuid 11111111-1111-4111-8111-111111111111)', encoding="utf-8")
    second.write_text('(uuid 22222222-2222-4222-8222-222222222222)', encoding="utf-8")
    assert canonical_design_hash(first) == canonical_design_hash(second)


def test_legacy_hash_only_release_is_not_approval(released_project):
    assert effective_lifecycle(released_project) == Lifecycle.DRAFT


def test_changed_released_design_returns_to_draft(released_project):
    released_project.schematic_path.write_text("changed", encoding="utf-8")
    assert effective_lifecycle(released_project) == Lifecycle.DRAFT


def test_legacy_hash_only_review_is_not_approval(project_copy):
    project = load_project(project_copy)
    state_dir = project.root / ".pcb-copilot"
    state_dir.mkdir()
    record = {
        "schema_version": 1,
        "lifecycle": "HUMAN_REVIEWED",
        "schematic_hash": canonical_design_hash(project.schematic_path),
        "pcb_hash": canonical_design_hash(project.pcb_path),
    }
    (state_dir / "review.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    assert effective_lifecycle(project) == Lifecycle.DRAFT


def test_record_lifecycle_must_match_record_type(project_copy):
    project = load_project(project_copy)
    state_dir = project.root / ".pcb-copilot"
    state_dir.mkdir()
    record = {
        "schema_version": 1,
        "lifecycle": "DRAFT",
        "schematic_hash": canonical_design_hash(project.schematic_path),
        "pcb_hash": canonical_design_hash(project.pcb_path),
    }
    (state_dir / "release.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    assert effective_lifecycle(project) == Lifecycle.DRAFT


@pytest.mark.parametrize("accepted_name", ["baro-bmp390.kicad_sch", "baro-bmp390.kicad_pcb"])
def test_draft_target_cannot_equal_accepted_design(project_copy, accepted_name):
    project = load_project(project_copy)
    with pytest.raises(UnsafeDraftTarget, match="accepted design"):
        assert_draft_target_safe(project, project.root / accepted_name)


def test_draft_target_must_stay_in_draft_directory(project_copy):
    project = load_project(project_copy)
    with pytest.raises(UnsafeDraftTarget, match="draft workspace"):
        assert_draft_target_safe(project, project.root / "other" / "candidate.kicad_sch")
