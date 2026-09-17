from __future__ import annotations

from pathlib import Path

import pytest

from pcb_copilot.layout.footprints import resolve_footprint, verify_pin_pad_map
from pcb_copilot.models import FootprintCandidate
from pcb_copilot.project import load_project


def test_bmp390_resolves_declared_import_as_real_without_geometry_evidence(
    repo_root: Path,
):
    project = load_project(repo_root / "projects/baro-bmp390")

    result = resolve_footprint(
        project, "U1", "jlcpcb:LGA-10_L2.0-W2.0-P0.50-BL"
    )

    assert result.fidelity == "real"
    assert result.path == (
        project.root
        / "libs/jlcpcb.pretty/LGA-10_L2.0-W2.0-P0.50-BL.kicad_mod"
    )
    assert result.extents_mm == pytest.approx((-1.0, -1.0, 1.0, 1.0))
    assert result.evidence_id is None
    assert verify_pin_pad_map(
        result, {str(number) for number in range(1, 11)}
    ) == []


def test_placeholder_is_blocking(tmp_path: Path):
    footprint = tmp_path / "generic.kicad_mod"
    footprint.write_text("(footprint generic)", encoding="utf-8")
    candidate = FootprintCandidate(
        lib_id="Generated:Generic_3Pin",
        path=footprint,
        source="generated",
        fidelity="placeholder",
        extents_mm=(-1.0, -1.0, 1.0, 1.0),
        evidence_id=None,
    )

    findings = verify_pin_pad_map(candidate, {"1", "2", "3"})

    assert any(
        item.severity == "block" and "placeholder" in item.message
        for item in findings
    )


def test_pin_pad_map_reports_missing_and_unexpected_numbered_pads(tmp_path: Path):
    footprint = tmp_path / "part.kicad_mod"
    footprint.write_text(
        '(footprint "part" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")) '
        '(pad "3" smd rect (at 1 0) (size 1 1) (layers "F.Cu")) '
        '(pad "" np_thru_hole circle (at 2 0) (size 1 1) (drill 1) '
        '(layers "*.Cu" "*.Mask")))',
        encoding="utf-8",
    )
    candidate = FootprintCandidate(
        lib_id="Vendor:Part",
        path=footprint,
        source="project table",
        fidelity="real",
        extents_mm=(-0.5, -0.5, 2.5, 0.5),
        evidence_id=None,
    )

    findings = verify_pin_pad_map(candidate, {"1", "2"})

    assert [item.code for item in findings] == ["footprint.pad_map_mismatch"]
    assert "missing pads: 2" in findings[0].message
    assert "unexpected pads: 3" in findings[0].message
    assert findings[0].reference == "Vendor:Part"


def test_explicit_environment_override_resolves_standard_footprint(
    project_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    library_root = tmp_path / "footprints"
    library = library_root / "Device.pretty"
    library.mkdir(parents=True)
    footprint = library / "Part.kicad_mod"
    footprint.write_text(
        '(footprint "Part" '
        '(pad "1" smd rect (at 0 0 90) (size 2 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "Device") (type "KiCad") '
        '(uri "${KICAD8_FOOTPRINT_DIR}/Device.pretty") '
        '(options "") (descr "")))',
        encoding="utf-8",
    )
    monkeypatch.setenv("KICAD8_FOOTPRINT_DIR", str(library_root))

    result = resolve_footprint(load_project(project_copy), "U1", "Device:Part")

    assert result.path == footprint
    assert result.fidelity == "standard"
    assert result.extents_mm == pytest.approx((-0.5, -1.0, 0.5, 1.0))
    assert "KICAD8_FOOTPRINT_DIR" in result.source


def test_broken_explicit_project_entry_does_not_fall_back(
    project_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    discovered_root = tmp_path / "discovered"
    discovered_lib = discovered_root / "Broken.pretty"
    discovered_lib.mkdir(parents=True)
    (discovered_lib / "Part.kicad_mod").write_text(
        '(footprint "Part" (pad "1" smd rect (at 0 0) (size 1 1)))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "Broken") (type "KiCad") '
        '(uri "${KIPRJMOD}/missing/Broken.pretty") '
        '(options "") (descr "Imported by kicad-claude")))',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pcb_copilot.layout.footprints.find_footprint_lib_dirs",
        lambda: [discovered_root],
    )

    with pytest.raises(ValueError, match="explicit.*Broken.*does not exist"):
        resolve_footprint(load_project(project_copy), "U1", "Broken:Part")


def test_unregistered_project_library_does_not_fall_back_to_same_named_global(
    project_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    local_library = project_copy / "libs/vendor.pretty"
    local_library.mkdir(parents=True)
    (local_library / "Part.kicad_mod").write_text(
        '(footprint "Part" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    global_root = tmp_path / "global"
    global_library = global_root / "vendor.pretty"
    global_library.mkdir(parents=True)
    (global_library / "Part.kicad_mod").write_text(
        '(footprint "Part" '
        '(pad "1" smd rect (at 0 0) (size 2 2) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        "(fp_lib_table (version 7))", encoding="utf-8"
    )
    monkeypatch.setattr(
        "pcb_copilot.layout.footprints.find_footprint_lib_dirs",
        lambda: [global_root],
    )

    with pytest.raises(ValueError, match="project-local.*not registered"):
        resolve_footprint(load_project(project_copy), "U1", "vendor:Part")


def test_resolution_rejects_footprint_without_measurable_geometry(
    project_copy: Path,
):
    library = project_copy / "libs/vendor.pretty"
    library.mkdir(parents=True)
    (library / "Empty.kicad_mod").write_text(
        '(footprint "Empty")', encoding="utf-8"
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "vendor") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/vendor.pretty") '
        '(options "") (descr "Imported by kicad-claude")))',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no courtyard or pad geometry"):
        resolve_footprint(load_project(project_copy), "U1", "vendor:Empty")


def test_resolution_rejects_off_axis_pad_geometry(project_copy: Path):
    library = project_copy / "libs/vendor.pretty"
    library.mkdir(parents=True)
    (library / "Angled.kicad_mod").write_text(
        '(footprint "Angled" '
        '(pad "1" smd rect (at 0 0 45) (size 4 2) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "vendor") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/vendor.pretty") '
        '(options "") (descr "Imported by kicad-claude")))',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="off-axis pad rotation 45"):
        resolve_footprint(load_project(project_copy), "U1", "vendor:Angled")


def test_unknown_project_local_lineage_is_not_called_real(project_copy: Path):
    library = project_copy / "libs/unknown.pretty"
    library.mkdir(parents=True)
    (library / "Part.kicad_mod").write_text(
        '(footprint "Part" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "unknown") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/unknown.pretty") '
        '(options "") (descr "")))',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="has no declared provenance"):
        resolve_footprint(load_project(project_copy), "U1", "unknown:Part")


def test_hand_authored_library_pointer_does_not_verify_each_footprint(repo_root: Path):
    project = load_project(repo_root / "projects/tms-v3")

    with pytest.raises(ValueError, match="has no declared provenance"):
        resolve_footprint(
            project,
            "U7",
            "tms:XBee_THT_20pin_P2.00mm",
        )
