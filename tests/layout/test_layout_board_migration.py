"""Real-board migration contracts; no acceptance or routing is performed."""

import json
import shutil
from pathlib import Path

import pytest

from pcb_copilot.layout.commands import draft_layout
from pcb_copilot.layout.constraints import _native
from pcb_copilot.layout.io import load_layout_intent
from pcb_copilot.layout.models import validate_layout_intent
from pcb_copilot.layout.render import native_board, schematic_inventory
from pcb_copilot.project import load_project
from pcb_copilot.state import accepted_file_hashes
from pcb_copilot.toolchain import discover_toolchain

BOARDS = ["baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3"]
MECHANICS = {
    "baro-bmp390": {"H1": (2.8, 2.8), "H2": (15.2, 2.8), "J1": (9, 21)},
    "imu-icm42688": {"H1": (3, 15), "H2": (21, 10), "J1": (5, 5)},
    "gnss-neom9n": {"H1": (4, 36), "H2": (30, 36), "J2": (31, 29)},
    "tms-v3": {"H1": (4.5, 95.5), "H4": (95.5, 4.5), "J7": (26, 18), "J8": (26, 33.24)},
}
OWNER_CODES = {
    "baro-bmp390": {"owner.standoffs", "owner.supply-performance"},
    "imu-icm42688": {"owner.orientation", "owner.mount-rigidity"},
    "gnss-neom9n": {"owner.rf-stackup", "owner.antenna", "owner.rf-zone-shape"},
    "tms-v3": {
        "owner.igniter-current",
        "owner.xbee-body-fit",
        "owner.reference-source",
        "source.pad-angles",
    },
}


@pytest.mark.parametrize("name", BOARDS)
def test_migration_intent_exists(repo_root, name):
    assert (repo_root / "projects" / name / "layout-intent.yaml").is_file()


@pytest.fixture(params=BOARDS, ids=BOARDS)
def migrated(request, repo_root, kipython):
    project = load_project(repo_root / "projects" / request.param)
    path = project.root / "layout-intent.yaml"
    assert path.is_file(), f"missing migration intent: {request.param}"
    return project, load_layout_intent(path), discover_toolchain(repo_root)


def test_native_inventory_and_mechanics_are_preserved(migrated):
    project, intent, toolchain = migrated
    before = accepted_file_hashes(project)
    board = native_board(toolchain, project.pcb_path)
    parts, nets = schematic_inventory(toolchain, project.schematic_path)
    validate_layout_intent(intent, set(parts), set(nets))
    placed = {p.ref: p for p in intent.placements}
    assert set(placed) == set(board["footprints"])
    assert {p.ref for p in intent.placements if p.pcb_only} == {"FID1", "FID2", "FID3"}
    for ref, fp in board["footprints"].items():
        assert placed[ref].footprint == fp["lib_id"]
        if ref in parts:
            assert placed[ref].footprint == parts[ref]["footprint"]
    for ref, xy in MECHANICS[project.manifest.name].items():
        assert placed[ref].anchor == xy
    assert any(p.anchor is None for p in intent.placements if p.ref.startswith("C"))
    assert any(p.near_ref for p in intent.placements)
    assert len(intent.regions) > 1
    native_rules = _native(project.pcb_path, toolchain.kipython)["nets"]
    intended_rules = {net: cls for cls in intent.net_classes for net in cls.nets}
    assert set(intended_rules) == set(nets)
    for net, cls in intended_rules.items():
        for field, native_field in (
            ("width_mm", "width"),
            ("clearance_mm", "clearance"),
            ("via_diameter_mm", "via"),
            ("via_drill_mm", "drill"),
        ):
            assert getattr(cls, field) == pytest.approx(native_rules[net][native_field])
    assert accepted_file_hashes(project) == before


def test_unknown_owner_inputs_do_not_become_calculated_rules(migrated):
    project, intent, _ = migrated
    assert intent.route_policy.value == "human"
    assert (
        not intent.critical_nets
    )  # no complete current/stackup measurement set exists
    assert OWNER_CODES[project.manifest.name] <= {
        f.code for f in intent.unresolved_decisions
    }
    assert all(f.severity == "review" for f in intent.unresolved_decisions)
    if project.manifest.name == "tms-v3":
        classes = {net: c for c in intent.net_classes for net in c.nets}
        assert classes["IGN_GND"].width_mm == 1.0
        assert classes["GND"].width_mm == 0.254
        assert {z.net for z in intent.zones} == {"GND"}


def test_fresh_human_draft_keeps_complete_native_inventory_and_reports_limits(
    migrated, tmp_path
):
    project, intent, toolchain = migrated
    destination = tmp_path / project.manifest.name
    shutil.copytree(
        project.root, destination, ignore=shutil.ignore_patterns(".pcb-copilot")
    )
    copied = load_project(destination)
    before = accepted_file_hashes(copied)
    report = draft_layout(copied, copied.root / "layout-intent.yaml", "human")
    assert accepted_file_hashes(copied) == before
    assert report["human_review"] == "pending"
    assert report["route"]["attempts"] == []
    assert report["route"]["unconnected"] == "unknown"
    root = Path(report["pcb"]).parent
    assert not (root / "preview-approval.json").exists()
    assert report["plot"] and Path(report["plot"]).is_file()
    assert Path(report["drc_report"]).is_file()
    constraints = json.loads((root / "constraints-report.json").read_text())
    assert "custom_rules_sha256" in constraints
    accepted = native_board(toolchain, copied.pcb_path)
    draft = native_board(toolchain, Path(report["pcb"]))
    assert draft["footprints"] == accepted["footprints"]
    assert OWNER_CODES[project.manifest.name] <= {
        f["code"] for f in report["engineering_warnings"]
    }
    # A geometry failure must stay blocking; a successful report must not hide it.
    assert report["exit_code"] == int(bool(report["machine_failures"]))
    assert (root / "placement-report.json").is_file()
    proposal = json.loads((root / "placement-proposal.json").read_text())
    if project.manifest.name == "baro-bmp390":
        assert not report["machine_failures"], report["machine_failures"]
        assert set(proposal["placed"]) == set(accepted["footprints"])
    if project.manifest.name == "imu-icm42688":
        assert not report["machine_failures"], report["machine_failures"]
        assert set(proposal["placed"]) == set(accepted["footprints"])
    if project.manifest.name == "gnss-neom9n":
        assert not intent.zones  # RF notch cannot be represented as a rectangle.
        assert draft["zones"] == 0
        assert any(f["code"] == "layout.rule_areas" for f in report["machine_failures"])
    if project.manifest.name == "tms-v3":
        assert any(
            f["code"] == "placement.footprint" and f.get("reference") == "J9"
            for f in report["machine_failures"]
        )
