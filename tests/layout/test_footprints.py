from __future__ import annotations

from pathlib import Path

import pytest

from pcb_copilot.layout.footprints import resolve_footprint, verify_pin_pad_map
from pcb_copilot.layout.models import PlacementItem
from pcb_copilot.models import FootprintCandidate
from pcb_copilot.project import load_project
from tests.board_fixtures import board_source


def test_bmp390_resolves_declared_import_as_real_without_geometry_evidence(
    repo_root: Path,
):
    project = load_project(board_source(repo_root, 'baro-bmp390'))

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


def test_model_and_resolver_accept_safe_interior_spaces(project_copy: Path):
    library = project_copy / "libs/Vendor Parts.pretty"
    library.mkdir(parents=True)
    footprint = library / "Part Name.kicad_mod"
    footprint.write_text(
        '(footprint "Part Name" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "Vendor Parts") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/Vendor Parts.pretty") (options "") '
        '(descr "Real LCSC footprints via easyeda2kicad")))',
        encoding="utf-8",
    )
    lib_id = "Vendor Parts:Part Name"

    assert PlacementItem(ref="U1", region="sensor", footprint=lib_id).footprint == lib_id
    assert resolve_footprint(load_project(project_copy), "U1", lib_id).path == footprint


@pytest.mark.parametrize(
    "lib_id",
    [
        "Vendor/Parts:Part",
        r"Vendor\\Parts:Part",
        "Vendor:../Part",
        "Vendor:Part/Name",
        "Vendor:Part:Name",
        "Vendor:\0Part",
    ],
)
def test_model_and_resolver_reject_the_same_unsafe_ids(project_copy: Path, lib_id: str):
    with pytest.raises(ValueError):
        PlacementItem(ref="U1", region="sensor", footprint=lib_id)
    with pytest.raises(ValueError):
        resolve_footprint(load_project(project_copy), "U1", lib_id)


def test_tms_sod323_resolves_with_silkscreen_polygons(repo_root: Path):
    result = resolve_footprint(
        load_project(board_source(repo_root, 'tms-v3')),
        "D1",
        "jlcpcb:SOD-323_L1.8-W1.3-LS2.5-RD-1",
    )

    assert result.fidelity == "real"
    assert result.extents_mm == pytest.approx((-1.67, -0.65, 1.67, 0.65))
    assert verify_pin_pad_map(result, {"1", "2"}) == []


@pytest.mark.parametrize("last_point", ["(xy 3 4)", "(xy 1e-3 4)", "( xy 3 4)", "(xy nan 4)"])
def test_courtyard_polygons_interleaved_with_other_layers(
    project_copy: Path, last_point: str
):
    library = project_copy / "libs/vendor.pretty"
    library.mkdir(parents=True)
    (library / "Mixed.kicad_mod").write_text(
        '(footprint "Mixed" '
        '(fp_poly (pts (xy -20 -20) (xy 20 -20) (xy 20 20)) (layer "F.SilkS")) '
        '(fp_poly (pts (xy -2 -1) (xy 0 -1) (xy 0 1) (xy -2 1)) (layer "F.CrtYd")) '
        '(fp_poly (pts (xy -30 -30) (xy 30 -30) (xy 30 30)) (layer "F.Fab")) '
        f'(fp_poly (pts (xy 1 2) (xy 3 2) {last_point}) (layer "B.CrtYd")) '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "vendor") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/vendor.pretty") (options "") '
        '(descr "Real LCSC footprints via easyeda2kicad")))',
        encoding="utf-8",
    )

    project = load_project(project_copy)
    if last_point != "(xy 3 4)":
        with pytest.raises(ValueError, match="courtyard"):
            resolve_footprint(project, "U1", "vendor:Mixed")
        return

    result = resolve_footprint(project, "U1", "vendor:Mixed")
    assert result.extents_mm == pytest.approx((-2, -1, 3, 4))
    assert verify_pin_pad_map(result, {"1"}) == []


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


def test_literal_relative_uri_resolves_from_project_root(
    project_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    library = project_copy / "libs/vendor.pretty"
    library.mkdir(parents=True)
    footprint = library / "Part.kicad_mod"
    footprint.write_text(
        '(footprint "Part" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "vendor") (type "KiCad") '
        '(uri "libs/vendor.pretty") (options "") '
        '(descr "Real LCSC footprints via easyeda2kicad")))',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = resolve_footprint(load_project(project_copy), "U1", "vendor:Part")

    assert result.path == footprint
    assert result.fidelity == "real"


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


def test_footprint_name_cannot_escape_declared_library(project_copy: Path):
    declared = project_copy / "libs/vendor.pretty"
    escaped = project_copy / "libs/Other.pretty"
    declared.mkdir(parents=True)
    escaped.mkdir(parents=True)
    (escaped / "Part.kicad_mod").write_text(
        '(footprint "Part" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "vendor") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/vendor.pretty") (options "") '
        '(descr "Real LCSC footprints via easyeda2kicad")))',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsafe footprint"):
        resolve_footprint(
            load_project(project_copy), "U1", "vendor:../Other.pretty/Part"
        )


def test_symlinked_footprint_cannot_escape_declared_library(project_copy: Path):
    declared = project_copy / "libs/vendor.pretty"
    declared.mkdir(parents=True)
    outside = project_copy / "libs/outside.kicad_mod"
    outside.write_text(
        '(footprint "Outside" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    link = declared / "Part.kicad_mod"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable: {exc}")
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "vendor") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/vendor.pretty") (options "") '
        '(descr "Real LCSC footprints via easyeda2kicad")))',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="escapes declared library"):
        resolve_footprint(load_project(project_copy), "U1", "vendor:Part")


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


def test_resolution_measures_off_axis_pad_geometry(project_copy: Path):
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
        '(options "") (descr "Real LCSC footprints via easyeda2kicad")))',
        encoding="utf-8",
    )

    candidate = resolve_footprint(load_project(project_copy), "U1", "vendor:Angled")
    assert candidate.extents_mm == pytest.approx((-2.121320344, -2.121320344, 2.121320344, 2.121320344))


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            (
                '(fp_arc (start 0 0) (mid 1 1) (end 2 0) (layer "F.CrtYd")) '
                '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))'
            ),
            "unsupported courtyard primitive fp_arc",
        ),
        (
            (
                '(fp_rect (start -1 -1) (end 1 1) (layer "F.CrtYd")) '
                '(pad "1" smd rect (at 0 0) (layers "F.Cu"))'
            ),
            "pad geometry was not measured",
        ),
        (
            (
                '(pad "1" smd custom (at 0 0) (size 1 1) (layers "F.Cu") '
                '(options (clearance outline) (anchor rect)) '
                '(primitives (gr_rect (start -2 -2) (end 2 2) (fill yes))))'
            ),
            "custom pad geometry",
        ),
        (
            '(pad "1" smd mystery (at 0 0) (size 1 1) (layers "F.Cu"))',
            "unsupported pad shape mystery",
        ),
        (
            (
                '(fp_rect (start -1 -1) (end 1 1) (layer "F.CrtYd")) '
                '(pad "1" smd rect (at nan 0) (size 1 1) (layers "F.Cu"))'
            ),
            "non-finite pad coordinate",
        ),
        (
            (
                '(fp_rect (start -1 -1) (end 1 1) (layer "F.CrtYd")) '
                '(pad "1" smd rect (at 1e-3 0) (size 1 1) (layers "F.Cu"))'
            ),
            "pad geometry was not measured",
        ),
        (
            (
                '(fp_poly (pts (xy 0 0) (xy nan 1)) (layer "F.CrtYd")) '
                '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))'
            ),
            "non-finite courtyard coordinate",
        ),
        (
            (
                '(fp_poly (pts (xy 0 0) (xy 1e-3 1)) (layer "F.CrtYd")) '
                '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))'
            ),
            "fp_poly courtyard geometry was not fully measured",
        ),
        (
            (
                '(fp_poly (pts (xy 0 0) ( xy 1e-3 1)) (layer "F.CrtYd")) '
                '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))'
            ),
            "fp_poly courtyard geometry was not fully measured",
        ),
        (
            (
                '(pad "1" smd trapezoid (at 0 0) (size 4 2) '
                '(rect_delta 1 0) (layers "F.Cu"))'
            ),
            "trapezoid pad rect_delta is not safely supported",
        ),
        (
            '(pad "1" smd rect (at 0 0) (size 1 1) (clearance nan) (layers "F.Cu"))',
            "non-finite clearance",
        ),
        (
            '(pad "1" smd rect (at 0 0) (size 1 1) (clearance 1e1) (layers "F.Cu"))',
            "clearance was not measured",
        ),
    ],
)
def test_resolution_rejects_geometry_the_shared_helper_cannot_fully_measure(
    project_copy: Path, body: str, message: str
):
    library = project_copy / "libs/vendor.pretty"
    library.mkdir(parents=True)
    (library / "Unsupported.kicad_mod").write_text(
        f'(footprint "Unsupported" {body})', encoding="utf-8"
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "vendor") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/vendor.pretty") (options "") '
        '(descr "Real LCSC footprints via easyeda2kicad")))',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        resolve_footprint(
            load_project(project_copy), "U1", "vendor:Unsupported"
        )


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


def test_negative_lineage_prose_is_not_promoted_to_real(project_copy: Path):
    library = project_copy / "libs/vendor.pretty"
    library.mkdir(parents=True)
    (library / "Part.kicad_mod").write_text(
        '(footprint "Part" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) '
        '(lib (name "vendor") (type "KiCad") '
        '(uri "${KIPRJMOD}/libs/vendor.pretty") (options "") '
        '(descr "not imported; unfetched draft")))',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="has no declared provenance"):
        resolve_footprint(load_project(project_copy), "U1", "vendor:Part")


def test_external_generic_named_footprint_is_standard(
    project_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "footprints"
    library = root / "Device.pretty"
    library.mkdir(parents=True)
    footprint = library / "Generic_Device.kicad_mod"
    footprint.write_text(
        '(footprint "Generic_Device" '
        '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu")))',
        encoding="utf-8",
    )
    (project_copy / "fp-lib-table").write_text(
        "(fp_lib_table (version 7))", encoding="utf-8"
    )
    monkeypatch.setattr(
        "pcb_copilot.layout.footprints.find_footprint_lib_dirs", lambda: [root]
    )

    result = resolve_footprint(
        load_project(project_copy), "U1", "Device:Generic_Device"
    )

    assert result.fidelity == "standard"


def test_hand_authored_library_pointer_does_not_verify_each_footprint(repo_root: Path):
    project = load_project(board_source(repo_root, 'tms-v3'))

    with pytest.raises(ValueError, match="has no declared provenance"):
        resolve_footprint(
            project,
            "U7",
            "tms:XBee_THT_20pin_P2.00mm",
        )
