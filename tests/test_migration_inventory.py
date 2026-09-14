import subprocess
from pathlib import PurePosixPath

import pytest

from pcb_copilot.migration import (
    AmbiguousInventoryRule,
    InventoryRule,
    capture_board,
    classify_path,
    legacy_project_paths,
    load_inventory,
)


def test_every_tracked_path_has_one_inventory_rule(repo_root):
    rules = load_inventory(repo_root / "migration" / "inventory.yaml")
    tracked = subprocess.check_output(
        ["git", "ls-files"], cwd=repo_root, text=True, encoding="utf-8"
    ).splitlines()
    for name in tracked:
        assert classify_path(PurePosixPath(name), rules).rationale


def test_equal_specificity_matches_are_rejected():
    rules = (
        InventoryRule(pattern="docs/*.py", action="KEEP", rationale="first"),
        InventoryRule(pattern="docs/*.py", action="REFACTOR", rationale="second"),
    )
    with pytest.raises(AmbiguousInventoryRule, match="docs/pipeline.py"):
        classify_path(PurePosixPath("docs/pipeline.py"), rules)


def test_capture_board_is_deterministic_and_complete(repo_root):
    project = legacy_project_paths(repo_root / "projects" / "baro-bmp390")

    first = capture_board(project)
    second = capture_board(project)

    assert first == second
    assert len(first["schematic_hash"]) == 12
    assert len(first["pcb_hash"]) == 12
    assert "U1" in first["schematic_refs"]
    assert "U1" in first["pcb_refs"]
    assert first["netmap"]["U1"]["2"] == "I2C_SCL"
    assert "U1.2" in first["pcb_nets"]["I2C_SCL"]
