from __future__ import annotations

import json
import math
import subprocess
from dataclasses import replace
from pathlib import Path

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


_FOOTPRINT_KEEPOUT = """(zone (net 0) (net_name "") (layer "F.Cu")
    (hatch edge 0.5)
    (keepout (tracks allowed) (vias allowed) (pads allowed)
             (copperpour allowed) (footprints not_allowed))
    (polygon (pts (xy -5 -5) (xy 5 -5) (xy 5 5) (xy -5 5))))"""


def test_accepted_footprint_keepout_blocks_placement(sensor_layout_draft):
    import sexpdata

    tree = sch_io.parse_file(sensor_layout_draft.project.pcb_path)
    for fp in sch_io.find_children(tree, "footprint"):
        if any(
            str(p[1]) == "Reference" and p[2] == "U1"
            for p in sch_io.find_children(fp, "property")
        ):
            fp.append(sexpdata.loads(_FOOTPRINT_KEEPOUT))
    sch_io.write_file(sensor_layout_draft.project.pcb_path, tree)
    sensor_layout_draft.record = create_draft(
        sensor_layout_draft.project, DraftKind.LAYOUT
    )
    assert native(
        sensor_layout_draft.project.pcb_path,
        """
fp=b.FindFootprintByReference('U1')
print(json.dumps([sum(z.GetIsRuleArea() for z in b.Zones()),
                  sum(z.GetIsRuleArea() for z in fp.Zones())]))
""",
    ) == [0, 1]
    report = propose(sensor_layout_draft)
    assert any(
        f.code == "placement.rule_areas" and f.reference == "U1"
        for f in report.findings
    )
    assert report.placed == {}
    assert (
        native(
            report.pcb_path,
            "print(json.dumps(sum(z.GetIsRuleArea() for z in b.FindFootprintByReference('U1').Zones())))",
        )
        == 1
    )


def test_new_pcb_only_footprint_keepout_blocks_placement(sensor_layout_draft, tmp_path):
    import sexpdata

    library = tmp_path / "Keepouts.pretty"
    library.mkdir()
    (library / "Antenna.kicad_mod").write_text(
        '(footprint "Antenna" (layer "F.Cu") '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask")) '
        + _FOOTPRINT_KEEPOUT
        + ")",
        encoding="utf-8",
    )
    table = sch_io.parse_file(sensor_layout_draft.project.root / "fp-lib-table")
    table.append(
        [
            sexpdata.Symbol("lib"),
            [sexpdata.Symbol("name"), "Keepouts"],
            [sexpdata.Symbol("type"), "KiCad"],
            [sexpdata.Symbol("uri"), library.as_posix()],
        ]
    )
    sch_io.write_file(sensor_layout_draft.project.root / "fp-lib-table", table)
    data = sensor_layout_draft.intent.model_dump(mode="json")
    data["placements"].append(
        {
            "ref": "AE1",
            "region": "sensor",
            "pcb_only": True,
            "footprint": "Keepouts:Antenna",
        }
    )
    sensor_layout_draft.intent = LayoutIntent.model_validate(data)
    report = propose(sensor_layout_draft)
    assert any(
        f.code == "placement.rule_areas" and f.reference == "AE1"
        for f in report.findings
    )
    assert report.placed == {}
    assert native(
        report.pcb_path, "print(json.dumps(b.FindFootprintByReference('AE1') is None))"
    )


def test_proposal_carries_research_and_authoritative_basis(sensor_layout_draft):
    project = sensor_layout_draft.project
    basis = (project.root / "DESIGN_BASIS.md").read_bytes()
    review = (project.root / "REFERENCE_REVIEW.md").read_bytes()
    evidence = project.evidence_index_path.read_bytes()
    report = propose(sensor_layout_draft)
    assert report.placed, report.findings
    root = report.pcb_path.parent
    assert (root / "DESIGN_BASIS.md").read_bytes().startswith(basis)
    assert (root / "REFERENCE_REVIEW.md").read_bytes() == review
    assert (root / "evidence/index.yaml").read_bytes() == evidence
    assert (project.root / "DESIGN_BASIS.md").read_bytes() == basis
    assert (project.root / "REFERENCE_REVIEW.md").read_bytes() == review
    assert project.evidence_index_path.read_bytes() == evidence
    assert (root / "evidence/files/BMP390_Adafruit_20BMP390.brd").read_bytes() == (
        project.root / "evidence/files/BMP390_Adafruit_20BMP390.brd"
    ).read_bytes()
    text = (root / "DESIGN_BASIS.md").read_text(encoding="utf-8")
    assert "Placement research checkpoint" in text
    assert "No new adopted choices or justified differences" in text
    assert any(
        f.code == "layout.research.comparison_required" and f.severity == "review"
        for f in report.findings
    )


def test_schematic_only_research_reports_missing_pcb_source_as_advisory(
    sensor_layout_draft,
):
    from pcb_copilot.evidence.index import load_evidence_index, save_evidence_index
    from pcb_copilot.evidence.models import EvidenceRole

    path = sensor_layout_draft.project.evidence_index_path
    index = load_evidence_index(path)
    save_evidence_index(
        index.model_copy(
            update={
                "records": tuple(
                    r
                    for r in index.records
                    if EvidenceRole.REFERENCE_DESIGN not in r.roles
                    or r.path.endswith(".sch")
                )
            }
        ),
        path,
    )
    report = propose(sensor_layout_draft)
    assert report.placed, report.findings
    assert any(
        f.code == "layout.research.pcb_source_missing"
        and f.reference == "U1"
        and f.severity == "review"
        for f in report.findings
    )


def test_missing_research_does_not_block_draft_or_invent_decisions(sensor_layout_draft):
    project = sensor_layout_draft.project
    project.evidence_index_path.unlink()
    (project.root / "DESIGN_BASIS.md").unlink()
    (project.root / "REFERENCE_REVIEW.md").unlink()
    report = propose(sensor_layout_draft)
    assert report.placed, report.findings
    expected = {
        "layout.research.index.missing",
        "layout.research.review_missing",
        "layout.research.basis_missing",
    }
    assert expected <= {f.code for f in report.findings if f.severity == "review"}
    text = (report.pcb_path.parent / "DESIGN_BASIS.md").read_text(encoding="utf-8")
    assert "No authoritative DESIGN_BASIS.md was available" in text
    assert "| Match |" not in text


def test_corrupted_board_research_is_not_verified_pcb_coverage(sensor_layout_draft):
    source = (
        sensor_layout_draft.project.root / "evidence/files/BMP390_Adafruit_20BMP390.brd"
    )
    source.write_bytes(source.read_bytes() + b"\n")
    report = propose(sensor_layout_draft)
    assert report.placed, report.findings
    assert any(
        f.code == "layout.research.archive.hash_mismatch" and f.severity == "review"
        for f in report.findings
    )
    # PDFs remain candidates for visual classification; neither prove a PCB
    # inspection nor justify claiming that every PCB reference is absent.
    assert any(
        f.code == "layout.research.pcb_source_unconfirmed" and f.reference == "U1"
        for f in report.findings
    )
    text = (report.pcb_path.parent / "DESIGN_BASIS.md").read_text(encoding="utf-8")
    assert "unverified" in text.lower()


def test_pcb_archive_without_inspection_record_requires_review(sensor_layout_draft):
    (sensor_layout_draft.project.root / "REFERENCE_REVIEW.md").unlink()
    report = propose(sensor_layout_draft)
    assert report.placed, report.findings
    assert any(f.code == "layout.research.review_missing" for f in report.findings)
    assert not any(
        f.code == "layout.research.pcb_source_missing" for f in report.findings
    )
    text = (report.pcb_path.parent / "DESIGN_BASIS.md").read_text(encoding="utf-8")
    assert "does not establish inspection or applicability" in text


@pytest.mark.parametrize("problem", ["untrusted", "nonmatching", "missing"])
def test_research_source_coverage_excludes_unusable_records(
    sensor_layout_draft, problem
):
    from pcb_copilot.evidence.index import load_evidence_index, save_evidence_index
    from pcb_copilot.evidence.models import EvidenceRole, TrustTier
    from pcb_copilot.layout.research import prepare_layout_research

    project = sensor_layout_draft.project
    index = load_evidence_index(project.evidence_index_path)
    records = []
    for record in index.records:
        if EvidenceRole.REFERENCE_DESIGN in record.roles and record.path.endswith(
            ".pdf"
        ):
            continue
        if record.path.endswith(".brd"):
            if problem == "untrusted":
                record = record.model_copy(
                    update={"trust_tier": TrustTier.TEACHING_REFERENCE}
                )
            elif problem == "nonmatching":
                record = record.model_copy(
                    update={
                        "part_numbers": frozenset({"OTHER_IC"}),
                        "component_refs": frozenset(),
                    }
                )
            else:
                (project.evidence_index_path.parent / record.path).unlink()
        records.append(record)
    save_evidence_index(
        index.model_copy(update={"records": tuple(records)}),
        project.evidence_index_path,
    )
    snapshot = prepare_layout_research(project)
    assert any(
        f.code == "layout.research.pcb_source_missing" and f.reference == "U1"
        for f in snapshot.findings
    )


def test_research_snapshot_preserves_manifest_evidence_location(
    sensor_layout_draft, tmp_path
):
    import shutil
    from dataclasses import replace

    from pcb_copilot.layout.research import prepare_layout_research

    project = sensor_layout_draft.project
    nested = project.root / "research/reference-archive"
    shutil.copytree(project.evidence_index_path.parent, nested)
    project = replace(project, evidence_index_path=nested / "index.yaml")
    snapshot = prepare_layout_research(project)
    destination = tmp_path / "draft-snapshot"
    snapshot.write(destination)
    assert (
        destination / "research/reference-archive/index.yaml"
    ).read_bytes() == project.evidence_index_path.read_bytes()
    assert (
        destination / "research/reference-archive/files/BMP390_Adafruit_20BMP390.brd"
    ).is_file()
    assert not (destination / "evidence/index.yaml").exists()


def test_research_snapshot_excludes_payload_symlink_outside_archive(
    sensor_layout_draft, tmp_path
):
    from pcb_copilot.layout.research import prepare_layout_research

    project = sensor_layout_draft.project
    source = project.root / "evidence/files/BMP390_Adafruit_20BMP390.brd"
    outside = tmp_path / "outside.brd"
    outside.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(outside)
    snapshot = prepare_layout_research(project)
    assert Path("evidence/files/BMP390_Adafruit_20BMP390.brd") not in snapshot.files
    assert any(
        f.code == "layout.research.snapshot_unavailable" for f in snapshot.findings
    )


def test_research_snapshot_rechecks_bytes_after_evidence_check(
    sensor_layout_draft, monkeypatch
):
    from pcb_copilot.layout import research

    project = sensor_layout_draft.project
    source = project.root / "evidence/files/BMP390_Adafruit_20BMP390.brd"
    original = research.check_evidence

    def change_after_check(project, parts):
        results = original(project, parts)
        source.write_bytes(source.read_bytes() + b"\n")
        return results

    monkeypatch.setattr(research, "check_evidence", change_after_check)
    snapshot = research.prepare_layout_research(project)
    assert any(
        f.code == "layout.research.archive.hash_mismatch" for f in snapshot.findings
    )
    assert any(
        f.code == "layout.research.pcb_source_unconfirmed" for f in snapshot.findings
    )


def test_malformed_native_reference_remains_advisory(sensor_layout_draft):
    import hashlib

    from pcb_copilot.evidence.archive import sniff_media_type
    from pcb_copilot.evidence.index import load_evidence_index, save_evidence_index
    from pcb_copilot.layout.research import prepare_layout_research

    project = sensor_layout_draft.project
    index = load_evidence_index(project.evidence_index_path)
    payload = b"(kicad_pcb ("
    records = []
    for record in index.records:
        if record.path.endswith(".brd"):
            (project.evidence_index_path.parent / record.path).write_bytes(payload)
            record = record.model_copy(
                update={
                    "id": f"sha256:{hashlib.sha256(payload).hexdigest()}",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "media_type": sniff_media_type(payload),
                }
            )
        records.append(record)
    save_evidence_index(
        index.model_copy(update={"records": tuple(records)}),
        project.evidence_index_path,
    )
    snapshot = prepare_layout_research(project)
    assert any(
        f.code == "layout.research.pcb_source_unconfirmed" and f.severity == "review"
        for f in snapshot.findings
    )
    assert "unclassified document" in snapshot.appendix


def test_research_preflight_from_package_without_checkout_docs(
    project_copy, repo_root, tmp_path
):
    import shutil
    import subprocess
    import sys

    installed = tmp_path / "installed"
    shutil.copytree(repo_root / "src/pcb_copilot", installed / "pcb_copilot")
    # Supply only the two known pre-existing compatibility dependencies. This
    # tests the new research boundary, not full wheel portability.
    compatibility = tmp_path / "compatibility"
    compatibility.mkdir()
    for name in ("pcb_layout_helpers.py", "deviations.py"):
        shutil.copy2(repo_root / "scripts" / name, compatibility / name)
    # Fresh isolated process: no test-loaded check_research or docs path can
    # mask a checkout-only import. Keep installed third-party dependencies.
    script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[3])
from pcb_copilot.layout.research import prepare_layout_research
from pcb_copilot.project import load_project
import pcb_copilot
assert Path(pcb_copilot.__file__).is_relative_to(Path(sys.argv[1]))
snapshot = prepare_layout_research(load_project(Path(sys.argv[2])))
assert any(f.code == 'layout.research.comparison_required' for f in snapshot.findings)
assert not any(f.code == 'layout.research.pcb_source_missing' for f in snapshot.findings)
assert 'PCB native source' in snapshot.appendix
assert 'check_research' not in sys.modules
print('isolated packaged research preflight passed')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            script,
            str(installed),
            str(project_copy),
            str(compatibility),
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
