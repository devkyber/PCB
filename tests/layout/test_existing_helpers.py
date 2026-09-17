from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest


def center_of(points):
    points = list(points)
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


@pytest.mark.parametrize("point", [(0.0, 0.0), (12.7, 25.4), (100.0, 80.0)])
def test_design_kicad_round_trip(coordinate_helpers, point):
    design_to_kicad = coordinate_helpers["design_to_kicad"]
    kicad_to_design = coordinate_helpers["kicad_to_design"]
    assert kicad_to_design(*design_to_kicad(*point)) == pytest.approx(point)


def test_design_coordinates_use_the_existing_mcp_and_kicad_frames(coordinate_helpers):
    assert coordinate_helpers["design_to_mcp"](12.7, 25.4) == pytest.approx((22.7, 84.6))
    assert coordinate_helpers["design_to_kicad"](12.7, 25.4) == pytest.approx((22.7, 125.4))


def test_one_by_n_header_extent_is_measured_from_pin_one(pcb_helpers, header_mod):
    pads = pcb_helpers.local_pad_positions(header_mod.read_text(encoding="utf-8"))
    assert pads["1"] != center_of(pads.values())
    assert pcb_helpers.get_extents_from_file(header_mod) == pytest.approx(
        (-1.27, -1.27, 1.27, 8.89)
    )


def test_extents_union_courtyard_and_pad_geometry(pcb_helpers):
    footprint = """
    (footprint "union"
      (fp_rect (start -0.5 -0.5) (end 0.5 0.5) (layer "F.CrtYd"))
      (pad "1" smd rect (at 2 0) (size 2 1) (layers "F.Cu")))
    """
    assert pcb_helpers.get_extents_from_text(footprint) == pytest.approx((-0.5, -0.5, 3.0, 0.5))


def test_placement_tracker_rotates_offset_extents_and_rejects_overlap(pcb_helpers, header_mod):
    text = header_mod.read_text(encoding="utf-8")
    tracker = pcb_helpers.PlacementTracker(margin_mm=0.0)
    assert tracker.place("J1", text, 20.0, 20.0, 90.0) == pytest.approx(
        (18.73, 18.73, 28.89, 21.27)
    )
    with pytest.raises(pcb_helpers.CourtyardCollisionError):
        tracker.place("J2", text, 22.0, 20.0, 90.0)


def test_placement_tracker_rejects_pads_outside_board(pcb_helpers, header_mod):
    tracker = pcb_helpers.PlacementTracker(
        margin_mm=0.0, board_mm=(0.0, 0.0, 10.0, 10.0), edge_margin_mm=0.0
    )
    with pytest.raises(pcb_helpers.OffBoardError):
        tracker.place("J1", header_mod.read_text(encoding="utf-8"), 1.5, 2.0)


def _footprint(ref: str, x: float, y: float, *, value: str = "PART", lib: str = "Test:Part") -> str:
    return f'''\n\t(footprint "{lib}"
\t\t(layer "F.Cu")
\t\t(at {x} {y})
\t\t(property "Reference" "{ref}")
\t\t(property "Value" "{value}")
\t\t(pad "1" thru_hole circle (at 0 0) (size 2 2) (drill 1) (layers "*.Cu" "*.Mask"))
\t)'''


def _board(*footprints: str) -> str:
    return '''(kicad_pcb
\t(gr_rect (start 0 0) (end 10 10) (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts"))''' + "".join(footprints) + "\n)"


def test_validator_detects_off_board_pads_and_collisions(validator):
    assert validator.check_pads_inside_board(_board(_footprint("J1", 9.5, 5.0)))[0] == "FAIL"
    assert validator.check_courtyard_overlap(
        _board(_footprint("J1", 5.0, 5.0), _footprint("J2", 6.5, 5.0))
    )[0] == "FAIL"


def test_validator_detects_connector_class_mismatch(tmp_path: Path, validator):
    pcb = tmp_path / "candidate.kicad_pcb"
    pcb.write_text(
        _board(_footprint("J1", 5.0, 5.0, value="XT60-ELEC", lib="Connector:PinHeader_1x02")),
        encoding="utf-8",
    )
    (tmp_path / "candidate.kicad_sch").write_text(
        '(kicad_sch (symbol (property "Reference" "J1") '
        '(property "Description" "Electronics battery XT60U-F")))',
        encoding="utf-8",
    )
    assert validator.check_connector_class(str(pcb))[0] == "FAIL"


def test_validator_detects_symbol_without_footprint(tmp_path: Path, validator):
    pcb = tmp_path / "candidate.kicad_pcb"
    pcb.write_text(_board(_footprint("R1", 5.0, 5.0)), encoding="utf-8")
    (tmp_path / "candidate.kicad_sch").write_text(
        '(kicad_sch (symbol (property "Reference" "R1")) '
        '(symbol (property "Reference" "C1")))',
        encoding="utf-8",
    )
    status, message = validator.check_symbol_footprint_parity(str(pcb))
    assert status == "FAIL"
    assert "C1" in message


def test_drc_freshness_requires_a_newer_clean_report(tmp_path: Path, validator):
    pcb = tmp_path / "candidate.kicad_pcb"
    report = tmp_path / "candidate.drc.json"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    report.write_text(
        json.dumps({"violations": [], "unconnected_items": [], "schematic_parity": []}),
        encoding="utf-8",
    )
    os.utime(report, (1_000, 1_000))
    os.utime(pcb, (2_000, 2_000))
    assert validator.check_drc_freshness(str(pcb))[0] == "FAIL"
    os.utime(report, (3_000, 3_000))
    assert validator.check_drc_freshness(str(pcb))[0] == "PASS"


@pytest.mark.xfail(
    strict=True,
    reason="known bug: helper uses max(width, height)/2 for off-axis pads and can under-bound",
)
def test_off_axis_pad_extents_enclose_the_rotated_rectangle(pcb_helpers):
    footprint = '(footprint "rotated" (pad "1" smd rect (at 0 0 45) (size 4 2) (layers "F.Cu")))'
    half_extent = (4 * math.cos(math.pi / 4) + 2 * math.sin(math.pi / 4)) / 2
    assert pcb_helpers.get_extents_from_text(footprint) == pytest.approx(
        (-half_extent, -half_extent, half_extent, half_extent)
    )


@pytest.mark.xfail(
    strict=True,
    reason="known bug: validator uses max(width, height)/2 for off-axis pads and can under-bound",
)
def test_validator_off_axis_pad_extents_enclose_the_rotated_rectangle(validator):
    block = _footprint("U1", 5.0, 5.0).replace("(at 0 0)", "(at 0 0 45)").replace(
        "(size 2 2)", "(size 4 2)"
    )
    half_extent = (4 * math.cos(math.pi / 4) + 2 * math.sin(math.pi / 4)) / 2
    assert validator._pad_extents(block) == pytest.approx(
        (5 - half_extent, 5 - half_extent, 5 + half_extent, 5 + half_extent)
    )


@pytest.mark.parametrize("board_name", ["baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3"])
def test_accepted_board_layout_metrics_match_baseline(
    repo_root: Path, capture_layout_metrics_fn, board_name: str
):
    baseline = json.loads(
        (repo_root / "tests/fixtures/baseline/layout_metrics.json").read_text(encoding="utf-8")
    )
    pcb = repo_root / "projects" / board_name / f"{board_name}.kicad_pcb"
    assert capture_layout_metrics_fn(pcb) == baseline[board_name]
