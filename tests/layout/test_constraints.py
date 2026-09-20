"""Synthetic arithmetic fixtures and native draft-only constraint regressions."""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict

import pytest
from kicad_claude.adapters import dsn_keepouts, kicad_python
from kicad_claude.adapters import project_settings as ps

from pcb_copilot.drafts import publish_draft
from pcb_copilot.layout.constraints import (
    apply_constraints,
    calculate_current_width,
    calculate_microstrip_width,
)
from pcb_copilot.layout.models import LayoutIntent
from pcb_copilot.state import accepted_file_hashes


def intent(fixture, **changes):
    data = fixture.intent.model_dump(mode="json")
    data.update(changes)
    return LayoutIntent.model_validate(data)


@pytest.fixture
def draft(sensor_layout_draft):
    fixture = sensor_layout_draft
    publish_draft(fixture.record, lambda root: None)
    fixture.pcb = fixture.record.root / fixture.project.pcb_path.name
    return fixture


def native(pcb, kipython, code):
    result = subprocess.run(
        [
            str(kipython),
            "-I",
            "-c",
            "import pcbnew,json,sys\nb=pcbnew.LoadBoard(sys.argv[1])\n" + code,
            str(pcb),
        ],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


RULES = """
print(json.dumps({str(name): {'name': str(net.GetNetClassSlow().GetName()),
 'width': pcbnew.ToMM(net.GetNetClassSlow().GetTrackWidth()),
 'clearance': pcbnew.ToMM(net.GetNetClassSlow().GetClearance()),
 'via': pcbnew.ToMM(net.GetNetClassSlow().GetViaDiameter()),
 'drill': pcbnew.ToMM(net.GetNetClassSlow().GetViaDrill())}
 for name,net in b.GetNetsByName().items() if name}))
"""


def test_ipc2221_synthetic_fixture():
    # KiCad 10.0.6 TWCalculateWidth; nominal 1 oz = 0.035 mm, not measured copper.
    assert calculate_current_width(1, 10, 1, "external") == pytest.approx(
        0.30038652083330486
    )
    assert calculate_current_width(1, 10, 1, "internal") == pytest.approx(
        0.7814374629086279
    )


def test_ti_synthetic_microstrip_fixture():
    # SPRABI2D p95 Eq10; independent fixture, not a GNSS board stackup.
    assert calculate_microstrip_width(50, 0.254, 4, 0.03556) == pytest.approx(
        0.45432289646296536
    )


@pytest.mark.parametrize("value", [0, -1, math.inf, math.nan])
def test_physical_inputs_must_be_finite_positive(value):
    for index in range(3):
        args = [1, 10, 1, "external"]
        args[index] = value
        with pytest.raises(ValueError):
            calculate_current_width(*args)
    for index in range(4):
        args = [50, 0.254, 4, 0.03556]
        args[index] = value
        with pytest.raises(ValueError):
            calculate_microstrip_width(*args)


def test_unsupported_formula_domains_are_rejected():
    with pytest.raises(ValueError):
        calculate_current_width(1, 10, 1, "unknown")
    for args in [
        (49, 0.254, 4, 0.035),
        (101, 0.254, 4, 0.035),
        (50, 0.254, 1, 0.035),
        (100, 0.001, 4, 1),
    ]:
        with pytest.raises(ValueError):
            calculate_microstrip_width(*args)


def test_native_effective_rules_zones_and_accepted_protection(draft, kipython):
    before = accepted_file_hashes(draft.project)
    accepted_pro = draft.project.pcb_path.with_suffix(".kicad_pro").read_bytes()
    baseline = native(draft.pcb, kipython, RULES)
    report = apply_constraints(
        draft.pcb,
        intent(
            draft,
            net_classes=[
                {
                    "name": "Supply",
                    "nets": ["+3V3"],
                    "width_mm": 0.7,
                    "clearance_mm": 0.4,
                }
            ],
            zones=[
                {
                    "net": "GND",
                    "layers": ["B.Cu"],
                    "region": "sensor",
                    "clearance_mm": 0.3,
                }
            ],
        ),
    )
    assert not [f for f in report.findings if f.severity == "block"], report.findings
    effective = native(draft.pcb, kipython, RULES)
    assert report.net_classes["+3V3"] in effective["+3V3"]["name"]
    assert effective["+3V3"]["width"] == pytest.approx(0.7)
    assert effective["+3V3"]["clearance"] == pytest.approx(0.4)
    assert effective["GND"] == baseline["GND"]
    # KiCad 10 ZONE.GetLayerName() incorrectly returns F.Cu for B.Cu zones.
    zones = native(
        draft.pcb,
        kipython,
        "print(json.dumps([(z.GetNetname(),b.GetLayerName(z.GetLayer())) for z in b.Zones() if z.GetZoneName().startswith('Copilot:')]))",
    )
    assert zones == [["GND", "B.Cu"]]
    assert accepted_file_hashes(draft.project) == before
    assert draft.project.pcb_path.with_suffix(".kicad_pro").read_bytes() == accepted_pro
    saved = json.loads((draft.pcb.parent / "constraints-report.json").read_text())
    assert saved == asdict(report)


def test_stricter_existing_rules_and_via_annulus_survive(draft, kipython):
    report = apply_constraints(
        draft.pcb,
        intent(
            draft,
            net_classes=[
                {
                    "name": "Supply",
                    "nets": ["+3V3"],
                    "width_mm": 0.15,
                    "clearance_mm": 0.1,
                    "via_diameter_mm": 0.7,
                    "via_drill_mm": 0.6,
                }
            ],
        ),
    )
    assert not [f for f in report.findings if f.severity == "block"], report.findings
    rules = native(draft.pcb, kipython, RULES)["+3V3"]
    assert rules["width"] >= 0.3 and rules["clearance"] >= 0.2
    assert rules["drill"] >= 0.6
    assert rules["via"] - rules["drill"] >= 0.3 - 1e-8


def test_calculation_inputs_and_limitations_are_serialized(draft):
    report = apply_constraints(
        draft.pcb,
        intent(
            draft,
            critical_nets=[
                {
                    "net": "+3V3",
                    "reason": "synthetic test",
                    "current_a": 1,
                    "duration_s": 0.01,
                    "rise_c": 10,
                    "copper_oz": 1,
                    "layer": "external",
                }
            ],
        ),
    )
    assert report.calculated_widths_mm["+3V3"] == pytest.approx(0.30038652083330486)
    data = json.loads((draft.pcb.parent / "constraints-report.json").read_text())
    assert data["calculations"]["+3V3"]["inputs"]["duration_s"] == 0.01
    assert data["calculations"]["+3V3"]["source"].startswith("https://")
    assert any("pulse" in f.message and "nominal" in f.message for f in report.findings)
    assert not any(
        f.code == "constraints.project_snapshot_unverified" for f in report.findings
    )


def test_legacy_metadata_without_project_snapshot_retains_warning(draft, monkeypatch):
    from pcb_copilot import accept

    metadata_path = draft.pcb.parent / "draft.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    companion = (
        draft.project.pcb_path.with_suffix(".kicad_pro")
        .relative_to(draft.project.root)
        .as_posix()
    )
    metadata["base_files"].pop(companion)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    monkeypatch.setattr(accept, "accepted_file_hashes", lambda project: metadata["base_files"])

    report = apply_constraints(draft.pcb, draft.intent)

    assert any(
        f.code == "constraints.project_snapshot_unverified" for f in report.findings
    )


def test_zone_region_uses_board_local_bottom_left_frame(draft, kipython):
    request = intent(
        draft,
        regions=[{"id": "sensor", "x_mm": 1, "y_mm": 2, "width_mm": 3, "height_mm": 4}],
        placements=[{"ref": "C1", "region": "sensor"}],
        zones=[{"net": "GND", "layers": ["B.Cu"], "region": "sensor"}],
    )
    report = apply_constraints(draft.pcb, request)
    assert not [f for f in report.findings if f.severity == "block"]
    points = native(
        draft.pcb,
        kipython,
        """
outline=pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline,False)
box=outline.BBox()
z=next(z for z in b.Zones() if z.GetZoneName().startswith('Copilot:'))
p=z.Outline().COutline(0)
print(json.dumps(sorted([[pcbnew.ToMM(p.CPoint(i).x-box.GetLeft()),pcbnew.ToMM(box.GetBottom()-p.CPoint(i).y)] for i in range(p.PointCount())])))
""",
    )
    assert points == [[1, 2], [1, 6], [4, 2], [4, 6]]


@pytest.mark.parametrize(
    "changes",
    [
        {"zones": [{"net": "MISSING", "layers": ["F.Cu"]}]},
        {"zones": [{"net": "GND", "layers": ["In1.Cu"]}]},
        {"critical_nets": [{"net": "+3V3", "reason": "missing physical inputs"}]},
    ],
)
def test_invalid_intent_leaves_board_and_settings_unchanged(draft, changes):
    paths = [draft.pcb, draft.pcb.with_suffix(".kicad_pro")]
    before = [p.read_bytes() for p in paths]
    report = apply_constraints(draft.pcb, intent(draft, **changes))
    assert any(f.severity == "block" for f in report.findings)
    assert [p.read_bytes() for p in paths] == before
    assert not report.net_classes


def test_rf_target_conflict_is_not_silently_widened(draft):
    report = apply_constraints(
        draft.pcb,
        intent(
            draft,
            net_classes=[{"name": "RF", "nets": ["+3V3"], "width_mm": 0.8}],
            critical_nets=[
                {
                    "net": "+3V3",
                    "reason": "synthetic RF fixture",
                    "kind": "rf",
                    "impedance_ohm": 50,
                    "dielectric_height_mm": 0.254,
                    "er": 4,
                    "copper_mm": 0.03556,
                }
            ],
        ),
    )
    assert any(f.code == "constraints.impedance_conflict" for f in report.findings)
    assert not report.net_classes


def test_accepted_board_and_unpublished_draft_are_rejected(sensor_layout_draft):
    f = sensor_layout_draft
    with pytest.raises(ValueError, match="draft"):
        apply_constraints(f.project.pcb_path, f.intent)
    with pytest.raises(ValueError, match="draft"):
        apply_constraints(f.record.root / f.project.pcb_path.name, f.intent)


def test_publish_failure_rolls_back_both_files(draft, monkeypatch):
    from pathlib import Path

    before = {
        p: p.read_bytes() for p in (draft.pcb, draft.pcb.with_suffix(".kicad_pro"))
    }
    original = Path.replace
    failed = False

    def fail_settings_once(self, target):
        nonlocal failed
        if Path(target) == draft.pcb.with_suffix(".kicad_pro") and not failed:
            failed = True
            raise OSError("simulated settings publication failure")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", fail_settings_once)
    with pytest.raises(OSError, match="simulated"):
        apply_constraints(
            draft.pcb,
            intent(
                draft,
                net_classes=[{"name": "Power", "nets": ["+3V3"], "width_mm": 0.7}],
            ),
        )
    assert {p: p.read_bytes() for p in before} == before


DSN = """(pcb test
  (resolution um 10)
  (structure
    (layer F.Cu (type signal))
    (layer In1.Cu (type signal))
    (layer B.Cu (type signal))
    (keepout "existing" (circle F.Cu 100 0 0))
    (rule (width 200) (clearance 127))
  )
)"""


def pad(**changes):
    data = {
        "ref": "FID1",
        "pad": "1",
        "x_nm": 0,
        "y_nm": 0,
        "w_nm": 3000000,
        "h_nm": 4000000,
        "clearance_nm": 1000000,
        "layers": ["In1.Cu"],
        "net": "",
        "shape": "rect",
    }
    data.update(changes)
    return data


def test_dsn_existing_keepout_does_not_hide_rectangular_clearance(tmp_path):
    path = tmp_path / "test.dsn"
    path.write_text(DSN)
    assert dsn_keepouts.inject(path, [pad()]) == 3
    text = path.read_text()
    assert "(circle In1.Cu 7000 0 0)" in text
    assert '(keepout "existing"' in text
    assert dsn_keepouts.inject(path, [pad()]) == 0


def test_dsn_connected_pad_is_not_made_unconnectable(tmp_path):
    path = tmp_path / "test.dsn"
    path.write_text(DSN)
    with pytest.raises(ValueError, match="connected"):
        dsn_keepouts.inject(path, [pad(net="GND")])
    assert path.read_text() == DSN


def test_dsn_typed_clearance_cannot_bypass_netless_pad_envelope(tmp_path):
    path = tmp_path / "typed.dsn"
    path.write_text(
        DSN.replace(
            "(clearance 127)",
            "(clearance 200) (clearance 50 (type smd_smd))",
        )
    )
    # 150 um is below the untyped 200 um, but above the SMD rule's 50 um.
    local = pad(clearance_nm=150000, layers=["F.Cu"])
    assert dsn_keepouts.inject(path, [local]) == 3
    assert "(circle F.Cu 5300 0 0)" in path.read_text()
    first = path.read_bytes()
    assert dsn_keepouts.inject(path, [local]) == 0
    assert path.read_bytes() == first


def test_dsn_typed_clearance_cannot_bypass_connected_pad_rejection(tmp_path):
    path = tmp_path / "typed.dsn"
    path.write_text(
        DSN.replace(
            "(clearance 127)",
            "(clearance 200) (clearance 50 (type smd_smd))",
        )
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="connected"):
        # The first pad would generate envelopes; rejecting the second must
        # leave the whole file unchanged, not publish partial protection.
        dsn_keepouts.inject(
            path,
            [
                pad(),
                pad(
                    ref="U1",
                    clearance_nm=150000,
                    layers=["F.Cu"],
                    net="GND",
                ),
            ],
        )
    assert path.read_bytes() == before


@pytest.mark.parametrize("raw", ["garbage", "{}"])
def test_dsn_inspection_failures_are_not_empty_success(raw):
    with pytest.raises(ValueError, match="inspect"):
        dsn_keepouts.collect("unused", lambda *args: raw)


def test_dsn_runner_failure_is_not_empty_success():
    def fail(*args):
        raise RuntimeError("native process failed")

    with pytest.raises(ValueError, match="inspect"):
        dsn_keepouts.collect("unused", fail)


def test_native_footprint_inherited_clearance_is_exported(draft, kipython, monkeypatch):
    # The legacy bridge probes KiCad/10; discovery handles this host's 10.0.
    monkeypatch.setattr(kicad_python, "find_kicad_python", lambda: kipython)
    native(
        draft.pcb,
        kipython,
        """
fp = b.FindFootprintByReference('FID1')
fp.SetLocalClearance(pcbnew.FromMM(1.6))
pcbnew.SaveBoard(sys.argv[1], b, True)
print('{}')
""",
    )
    pads = dsn_keepouts.collect(draft.pcb, kicad_python._run_pcbnew_script)
    fid = next(p for p in pads if p["ref"] == "FID1")
    assert fid["clearance_nm"] == 1600000
    assert fid["layers"] == ["F.Cu"]
    dsn = draft.pcb.with_suffix(".dsn")
    kicad_python.export_dsn(draft.pcb, dsn)
    assert dsn_keepouts.inject(dsn, pads) >= 3
    assert "FID1" in dsn.read_text()


def test_dsn_inspection_failure_is_a_reported_limitation(draft, monkeypatch):
    def fail(*args):
        raise ValueError("cannot inspect pad geometry")

    monkeypatch.setattr(dsn_keepouts, "collect", fail)
    report = apply_constraints(draft.pcb, draft.intent)
    assert any(f.code == "constraints.dsn_limitation" for f in report.findings)


def test_reapplying_constraints_does_not_accumulate_classes_or_change_priorities(draft):
    request = intent(
        draft, net_classes=[{"name": "Supply", "nets": ["+3V3"], "width_mm": 0.7}]
    )
    first = apply_constraints(draft.pcb, request)
    before = draft.pcb.with_suffix(".kicad_pro").read_bytes()
    second = apply_constraints(draft.pcb, request)
    assert first.net_classes == second.net_classes
    assert draft.pcb.with_suffix(".kicad_pro").read_bytes() == before


def test_calculated_and_via_rules_are_stable_on_native_grid(draft):
    request = intent(
        draft,
        net_classes=[
            {
                "name": "Supply",
                "nets": ["+3V3"],
                "width_mm": 0.1,
                "via_diameter_mm": 0.7,
                "via_drill_mm": 0.6,
            }
        ],
        critical_nets=[
            {
                "net": "+3V3",
                "reason": "synthetic repeat test",
                "current_a": 1,
                "duration_s": 0.01,
                "rise_c": 10,
                "copper_oz": 1,
                "layer": "external",
            }
        ],
    )
    first = apply_constraints(draft.pcb, request)
    before = draft.pcb.with_suffix(".kicad_pro").read_bytes()
    second = apply_constraints(draft.pcb, request)
    assert first.net_classes == second.net_classes
    assert draft.pcb.with_suffix(".kicad_pro").read_bytes() == before
    assert (
        second.effective_rules_mm["+3V3"]["width"]
        >= second.calculated_widths_mm["+3V3"]
    )


def test_unrequested_differential_rules_are_inherited(draft, kipython):
    path = draft.pcb.with_suffix(".kicad_pro")
    pro = ps.load_pro(path)
    ps.find_net_class(pro, "Power")["diff_pair_width"] = 0.44
    ps.find_net_class(pro, "Default")["diff_pair_gap"] = 0.35
    ps.save_pro(path, pro)
    report = apply_constraints(
        draft.pcb,
        intent(
            draft, net_classes=[{"name": "Supply", "nets": ["+3V3"], "width_mm": 0.7}]
        ),
    )
    assert report.net_classes
    result = native(
        draft.pcb,
        kipython,
        "c=b.FindNet('+3V3').GetNetClassSlow(); print(json.dumps([pcbnew.ToMM(c.GetDiffPairWidth()),pcbnew.ToMM(c.GetDiffPairGap())]))",
    )
    assert result == pytest.approx([0.44, 0.35])


def test_existing_broad_pattern_and_board_minima_are_preserved(draft, kipython):
    path = draft.pcb.with_suffix(".kicad_pro")
    pro = ps.load_pro(path)
    pro["net_settings"]["netclass_patterns"][0]["pattern"] = "*"
    pro["board"]["design_settings"]["rules"]["min_track_width"] = 0.5
    ps.save_pro(path, pro)
    old = native(draft.pcb, kipython, RULES)
    report = apply_constraints(
        draft.pcb,
        intent(
            draft, net_classes=[{"name": "Supply", "nets": ["+3V3"], "width_mm": 0.2}]
        ),
    )
    assert report.net_classes
    new = native(draft.pcb, kipython, RULES)
    assert new["+3V3"]["width"] == pytest.approx(0.5)
    assert new["GND"] == old["GND"]
    assert (
        ps.load_pro(path)["board"]["design_settings"]["rules"]["min_track_width"] == 0.5
    )


def test_literal_wildcard_net_does_not_broaden_assignment(draft, kipython):
    native(
        draft.pcb,
        kipython,
        "b.FindNet('+3V3').SetNetname('V*'); pcbnew.SaveBoard(sys.argv[1],b,True); print('{}')",
    )
    before = draft.pcb.with_suffix(".kicad_pro").read_bytes()
    report = apply_constraints(
        draft.pcb,
        intent(
            draft, net_classes=[{"name": "Supply", "nets": ["V*"], "width_mm": 0.7}]
        ),
    )
    assert any(
        "wildcard" in f.message and f.severity == "block" for f in report.findings
    )
    assert not report.net_classes
    assert draft.pcb.with_suffix(".kicad_pro").read_bytes() == before


def test_missing_companion_is_not_sourced_from_accepted_settings(draft):
    draft.pcb.with_suffix(".kicad_pro").unlink()
    report = apply_constraints(draft.pcb, draft.intent)
    assert any(
        "companion" in f.message and f.severity == "block" for f in report.findings
    )
    assert not draft.pcb.with_suffix(".kicad_pro").exists()


@pytest.mark.parametrize(
    "dsn",
    [
        DSN.replace("resolution um", "resolution mil"),
        DSN.replace("(clearance 127)", "(unsupported 127)"),
    ],
)
def test_unsupported_dsn_dialect_is_not_silent(dsn, tmp_path):
    path = tmp_path / "test.dsn"
    path.write_text(dsn)
    with pytest.raises(ValueError, match="inspect"):
        dsn_keepouts.inject(path, [pad()])
    assert path.read_text() == dsn


def test_network_rule_cannot_substitute_for_missing_structure_rule(tmp_path):
    path = tmp_path / "test.dsn"
    text = DSN.replace("(rule (width 200) (clearance 127))", "")
    text = text[:-1] + "  (network\n    (rule (width 200) (clearance 127))\n  )\n)"
    path.write_text(text)
    with pytest.raises(ValueError, match="inspect"):
        dsn_keepouts.inject(path, [pad()])
    assert path.read_text() == text


def test_native_connected_override_survives_but_export_is_explicitly_unsupported(
    draft, kipython, monkeypatch
):
    monkeypatch.setattr(kicad_python, "find_kicad_python", lambda: kipython)
    native(
        draft.pcb,
        kipython,
        "fp=b.FindFootprintByReference('C1'); next(iter(fp.Pads())).SetLocalClearance(pcbnew.FromMM(.9)); pcbnew.SaveBoard(sys.argv[1],b,True); print('{}')",
    )
    report = apply_constraints(
        draft.pcb, intent(draft, zones=[{"net": "GND", "layers": ["B.Cu"]}])
    )
    assert any("Connected-pad" in f.message for f in report.findings)
    pads = dsn_keepouts.collect(draft.pcb, kicad_python._run_pcbnew_script)
    assert any(p["ref"] == "C1" and p["clearance_nm"] == 900000 for p in pads)
    dsn = draft.pcb.with_suffix(".dsn")
    kicad_python.export_dsn(draft.pcb, dsn)
    with pytest.raises(ValueError, match="connected"):
        dsn_keepouts.inject(dsn, pads)
