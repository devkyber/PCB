from __future__ import annotations

import json
import math
import subprocess
from dataclasses import replace

import pytest
from kicad_claude.adapters import sch_io

from pcb_copilot.drafts import create_draft
from pcb_copilot.layout.models import LayoutIntent
from pcb_copilot.layout.place import propose_placement
from pcb_copilot.models import DraftKind
from pcb_copilot.state import accepted_file_hashes
from pcb_copilot.toolchain import discover_toolchain


def distance(left, right):
    return math.dist(left, right)


def native(pcb_path, code):
    toolchain = discover_toolchain(pcb_path.parent)
    result = subprocess.run(
        [
            str(toolchain.kipython),
            "-I",
            "-c",
            "import pcbnew,json,sys\nb=pcbnew.LoadBoard(sys.argv[1])\n" + code,
            str(pcb_path),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def pad_position(pcb_path, ref, pin):
    return native(
        pcb_path,
        f"""
outline = pcbnew.SHAPE_POLY_SET()
assert b.GetBoardPolygonOutlines(outline, False)
box = outline.BBox()
p = next(p for p in b.FindFootprintByReference({ref!r}).Pads() if p.GetNumber() == {pin!r}).GetPosition()
print(json.dumps([pcbnew.ToMM(p.x-box.GetLeft()), pcbnew.ToMM(box.GetBottom()-p.y)]))
""",
    )


def changed(fixture, ref, **changes):
    data = fixture.intent.model_dump(mode="json")
    next(item for item in data["placements"] if item["ref"] == ref).update(changes)
    fixture.intent = LayoutIntent.model_validate(data)
    return fixture


def propose(fixture):
    return propose_placement(fixture.project, fixture.intent, fixture.record)


def test_decoupler_is_measured_from_its_supply_pad(sensor_layout_draft):
    report = propose(sensor_layout_draft)
    assert not [f for f in report.findings if f.severity == "block"], report.findings
    assert (
        distance(report.placed["C1"].center, pad_position(report.pcb_path, "U1", "10"))
        <= 2
    )
    assert (
        distance(
            pad_position(report.pcb_path, "C1", "1"),
            pad_position(report.pcb_path, "U1", "10"),
        )
        <= 2
    )
    assert report.placed["U1"].center == (9, 12)


def test_draft_preserves_accepted_inputs_parity_and_removes_copper(
    sensor_layout_draft, validator
):
    before = accepted_file_hashes(sensor_layout_draft.project)
    report = propose(sensor_layout_draft)
    assert accepted_file_hashes(sensor_layout_draft.project) == before
    assert report.pcb_path.is_relative_to(sensor_layout_draft.record.root)
    assert (
        report.pcb_path.with_suffix(".kicad_sch").read_bytes()
        == sensor_layout_draft.project.schematic_path.read_bytes()
    )
    measure = "print(json.dumps({'nets': sorted((fp.GetReference(), p.GetNumber(), p.GetNetname()) for fp in b.GetFootprints() for p in fp.Pads()), 'tracks':len(list(b.GetTracks())), 'zones':len(list(b.Zones()))}))"
    old, new = (
        native(sensor_layout_draft.project.pcb_path, measure),
        native(report.pcb_path, measure),
    )
    assert old["nets"] == new["nets"]
    assert new["tracks"] == new["zones"] == 0
    assert any(f.code == "placement.copper_removed" for f in report.findings)
    text = report.pcb_path.read_text(encoding="utf-8")
    assert validator.check_pads_inside_board(text)[0] == "PASS"
    assert validator.check_courtyard_overlap(text)[0] == "PASS"


def test_too_small_region_names_conflicting_refs(sensor_layout_draft):
    changed(sensor_layout_draft, "C1", anchor_x_mm=9, anchor_y_mm=12)
    report = propose(sensor_layout_draft)
    assert "C1" not in report.placed
    assert any("C1" in f.message and "U1" in f.message for f in report.findings)


def test_fiducial_pad_clearance_is_in_placement_envelope(sensor_layout_draft):
    tree = sch_io.parse_file(sensor_layout_draft.project.pcb_path)
    for fp in sch_io.find_children(tree, "footprint"):
        if any(
            str(p[1]) == "Reference" and p[2] == "FID1"
            for p in sch_io.find_children(fp, "property")
        ):
            pad = sch_io.find_children(fp, "pad")[0]
            sch_io.find_child(pad, "clearance")[1] = 1.5
    sch_io.write_file(sensor_layout_draft.project.pcb_path, tree)
    sensor_layout_draft.record = create_draft(
        sensor_layout_draft.project, DraftKind.LAYOUT
    )
    changed(sensor_layout_draft, "FID1", anchor_x_mm=15.5)
    report = propose(sensor_layout_draft)
    assert report.placed, report.findings
    fid = report.placed["FID1"]
    assert fid.extents_mm == pytest.approx((13.5, 21.2, 17.5, 25.2))


def test_rotated_header_is_on_board(sensor_layout_draft):
    data = sensor_layout_draft.intent.model_dump(mode="json")
    data["placements"].append(
        {
            "ref": "J2",
            "region": "sensor",
            "pcb_only": True,
            "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
            "rotation_deg": 90,
        }
    )
    sensor_layout_draft.intent = LayoutIntent.model_validate(data)
    report = propose(sensor_layout_draft)
    assert "J2" in report.placed, report.findings
    for pin in ("1", "4"):
        x, y = pad_position(report.pcb_path, "J2", pin)
        assert 0.3 <= x <= 17.7 and 0.3 <= y <= 25.7
    a, b = (
        pad_position(report.pcb_path, "J2", "1"),
        pad_position(report.pcb_path, "J2", "4"),
    )
    assert b[0] - a[0] == pytest.approx(7.62)
    assert b[1] == pytest.approx(a[1])


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"near_pin": "99"}, "placement.pad_missing"),
        ({"source_pin": "99"}, "placement.pad_missing"),
        ({"max_distance_mm": 0.1}, "placement.infeasible"),
        (
            {"footprint": "Capacitor_SMD:C_0603_1608Metric"},
            "placement.identity_mismatch",
        ),
        ({"source_pin": "2"}, "placement.pad_net_mismatch"),
    ],
)
def test_invalid_constraints_are_named_findings(sensor_layout_draft, changes, code):
    report = propose(changed(sensor_layout_draft, "C1", **changes))
    assert any(f.code == code and f.reference == "C1" for f in report.findings), (
        report.findings
    )


def test_missing_unconnected_physical_part_is_not_ignored(sensor_layout_draft):
    data = sensor_layout_draft.intent.model_dump(mode="json")
    data["placements"] = [p for p in data["placements"] if p["ref"] != "H1"]
    sensor_layout_draft.intent = LayoutIntent.model_validate(data)
    report = propose(sensor_layout_draft)
    assert any("missing placement intent: H1" in f.message for f in report.findings)


def test_unsafe_or_stale_draft_is_rejected(sensor_layout_draft):
    fixture = sensor_layout_draft
    with pytest.raises(ValueError, match="draft"):
        propose_placement(
            fixture.project,
            fixture.intent,
            replace(fixture.record, root=fixture.project.root),
        )
    with pytest.raises(ValueError, match="stale"):
        propose_placement(
            fixture.project,
            fixture.intent,
            replace(fixture.record, base_pcb_hash="0" * 64),
        )


def test_near_dependency_cycle_is_a_named_blocker(sensor_layout_draft):
    changed(
        sensor_layout_draft,
        "U1",
        near_ref="C1",
        near_pin="1",
        source_pin="10",
        max_distance_mm=2,
    )
    report = propose(sensor_layout_draft)
    assert any(
        f.code == "placement.dependency" and f.reference == "C1"
        for f in report.findings
    )
    assert report.placed == {}


def test_region_boundary_never_silently_relocates(sensor_layout_draft):
    data = sensor_layout_draft.intent.model_dump(mode="json")
    data["regions"] = [
        {"id": "sensor", "x_mm": 0, "y_mm": 0, "width_mm": 18, "height_mm": 25.5},
        {"id": "small", "x_mm": 0, "y_mm": 25.5, "width_mm": 18, "height_mm": 0.5},
    ]
    next(p for p in data["placements"] if p["ref"] == "R1")["region"] = "small"
    sensor_layout_draft.intent = LayoutIntent.model_validate(data)
    report = propose(sensor_layout_draft)
    assert any(
        f.code == "placement.infeasible" and "R1" in f.message and "small" in f.message
        for f in report.findings
    )
    assert report.placed == {}


def test_native_render_rotates_non_square_pad_and_reports_its_envelope(
    sensor_layout_draft,
):
    changed(sensor_layout_draft, "C3", rotation_deg=37)
    report = propose(sensor_layout_draft)
    assert report.placed, report.findings
    observed = native(
        report.pcb_path,
        """
fp = b.FindFootprintByReference('C3')
pads = list(fp.Pads())
print(json.dumps({'angle':fp.GetOrientationDegrees(), 'pads':[p.GetOrientationDegrees() for p in pads]}))
""",
    )
    assert observed["angle"] == pytest.approx(37)
    assert observed["pads"] == pytest.approx([37, 37])


def test_modified_instance_geometry_is_preserved_and_measured(sensor_layout_draft):
    tree = sch_io.parse_file(sensor_layout_draft.project.pcb_path)
    for fp in sch_io.find_children(tree, "footprint"):
        if any(
            str(p[1]) == "Reference" and p[2] == "C3"
            for p in sch_io.find_children(fp, "property")
        ):
            sch_io.find_child(fp, "at")[3:] = [90]
            for pad in sch_io.find_children(fp, "pad"):
                sch_io.find_child(pad, "at")[3:] = [0]
                sch_io.find_child(pad, "size")[1:] = [4, 1]
    sch_io.write_file(sensor_layout_draft.project.pcb_path, tree)
    sensor_layout_draft.record = create_draft(
        sensor_layout_draft.project, DraftKind.LAYOUT
    )
    changed(sensor_layout_draft, "C3", rotation_deg=90)
    report = propose(sensor_layout_draft)
    assert report.placed, report.findings
    assert any(
        f.code == "placement.instance_differs" and f.reference == "C3"
        for f in report.findings
    )
    observed = native(
        report.pcb_path,
        """
fp = b.FindFootprintByReference('C3')
outline=pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline,False)
box=outline.BBox()
print(json.dumps([[pcbnew.ToMM(p.GetBoundingBox().GetLeft()-box.GetLeft()),
                  pcbnew.ToMM(box.GetBottom()-p.GetBoundingBox().GetBottom()),
                  pcbnew.ToMM(p.GetBoundingBox().GetRight()-box.GetLeft()),
                  pcbnew.ToMM(box.GetBottom()-p.GetBoundingBox().GetTop()),
                  p.GetOrientationDegrees(), pcbnew.ToMM(p.GetSize().x)] for p in fp.Pads()]))
""",
    )
    bounds = report.placed["C3"].extents_mm
    for left, bottom, right, top, angle, width in observed:
        assert width == 4 and angle == 0
        assert bounds[0] - 1e-6 <= left <= right <= bounds[2] + 1e-6
        assert bounds[1] - 1e-6 <= bottom <= top <= bounds[3] + 1e-6


def test_outline_cutout_is_blocked_instead_of_treated_as_solid_rectangle(
    sensor_layout_draft,
):
    import sexpdata

    tree = sch_io.parse_file(sensor_layout_draft.project.pcb_path)
    tree.append(
        sexpdata.loads(
            "(gr_rect (start 17 184) (end 20 188) "
            '(stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts"))'
        )
    )
    sch_io.write_file(sensor_layout_draft.project.pcb_path, tree)
    sensor_layout_draft.record = create_draft(
        sensor_layout_draft.project, DraftKind.LAYOUT
    )
    report = propose(sensor_layout_draft)
    assert any(f.code == "placement.outline_unsupported" for f in report.findings)
    assert report.placed == {}
