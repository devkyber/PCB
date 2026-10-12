from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import pytest

from tests.board_fixtures import board_source


def center_of(points):
    points = list(points)
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


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


def test_parity_detects_disconnected_parts_and_wrong_values():
    from pcb_copilot.review.checks import compare_physical_parts
    parts = {'R1': {'footprint': 'R:R', 'value': '10k'},
             'C1': {'footprint': 'C:C', 'value': '1u'}}
    footprints = {'R1': {'lib_id': 'R:R', 'value': '100k'}}
    issues = compare_physical_parts(parts, footprints)
    assert any('C1' in item and 'missing' in item for item in issues)
    assert any('R1' in item and 'value' in item for item in issues)


def test_off_axis_pad_extents_enclose_the_rotated_rectangle(pcb_helpers):
    footprint = '(footprint "rotated" (pad "1" smd rect (at 0 0 45) (size 4 2) (layers "F.Cu")))'
    half_extent = (4 * math.cos(math.pi / 4) + 2 * math.sin(math.pi / 4)) / 2
    assert pcb_helpers.get_extents_from_text(footprint) == pytest.approx(
        (-half_extent, -half_extent, half_extent, half_extent)
    )


def test_validator_off_axis_pad_extents_enclose_the_rotated_rectangle(validator):
    block = _footprint("U1", 5.0, 5.0).replace("(at 0 0)", "(at 0 0 45)").replace(
        "(size 2 2)", "(size 4 2)"
    )
    half_extent = (4 * math.cos(math.pi / 4) + 2 * math.sin(math.pi / 4)) / 2
    assert validator._pad_extents(block) == pytest.approx(
        (5 - half_extent, 5 - half_extent, 5 + half_extent, 5 + half_extent)
    )


def test_serialized_native_pad_angle_is_already_absolute(tmp_path, kipython, validator):
    pcb = tmp_path / "rotated.kicad_pcb"
    script = '''
import pcbnew, sys
board = pcbnew.BOARD()
fp = pcbnew.FOOTPRINT(board)
fp.SetReference("U1")
pad = pcbnew.PAD(fp)
pad.SetNumber("1")
pad.SetShape(pcbnew.PAD_SHAPE_RECT)
pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(4), pcbnew.FromMM(2)))
fp.Add(pad)
board.Add(fp)
fp.SetOrientationDegrees(90)
pcbnew.SaveBoard(sys.argv[1], board)
'''
    subprocess.run([str(kipython), "-I", "-c", script, str(pcb)], check=True)
    block = next(validator._iter_footprint_blocks(pcb.read_text()))
    assert validator._pad_extents(block) == pytest.approx((-1, -2, 1, 2))


def test_shelf_pack_preserves_pin_one_anchor_and_pad_union(pcb_helpers, header_mod):
    text = header_mod.read_text()
    positions = pcb_helpers.shelf_pack([("J1", text)], 0, 0, 15, 15)
    assert positions["J1"] == pytest.approx((2.27, 2.27))
    pad_only = '(footprint "pad" (pad "1" smd rect (at 3 0) (size 4 2)))'
    assert pcb_helpers.shelf_pack([("U1", pad_only)], 0, 0, 15, 15)["U1"] == (0, 2)


def test_pad_and_footprint_clearance_are_included(pcb_helpers):
    text = '''(footprint "FID" (clearance 0.2)
      (pad "1" smd circle (at 0 0) (size 1 1) (clearance 1.5)))'''
    assert pcb_helpers.get_extents_from_text(text) == (-2, -2, 2, 2)


@pytest.mark.parametrize("board_name", ["baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3"])
@pytest.mark.slow
def test_accepted_board_layout_metrics_match_baseline(
    repo_root: Path, capture_layout_metrics_fn, board_name: str
):
    baseline = json.loads(
        (repo_root / "tests/fixtures/baseline/layout_metrics.json").read_text(encoding="utf-8")
    )
    pcb = board_source(repo_root, board_name) / f"{board_name}.kicad_pcb"
    assert capture_layout_metrics_fn(pcb) == baseline[board_name]
