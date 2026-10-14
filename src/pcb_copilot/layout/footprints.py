"""Resolve footprint files and verify the geometry used for layout."""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any

import sexpdata
from kicad_claude.adapters import sch_io
from kicad_claude.utils.kicad_paths import find_footprint_lib_dirs

from pcb_copilot.evidence.checks import Finding
from pcb_copilot.layout import geometry as _layout_helpers
from pcb_copilot.layout.footprint_provenance import (
    DRAWING_DERIVED_DESCRIPTION,
    drawing_receipt,
)
from pcb_copilot.layout.lib_ids import split_footprint_lib_id
from pcb_copilot.models import FootprintCandidate, Project

_REAL_LOCAL_DESCRIPTIONS = {
    "real lcsc footprints via easyeda2kicad",
}
_PLACEHOLDER_LOCAL_DESCRIPTIONS = {
    "generated placeholder footprints",
}


def _value(node: list[Any], head: str) -> str | None:
    child = sch_io.find_child(node, head)
    if child is None or len(child) < 2:
        return None
    return str(child[1])


def _library_entry(project: Project, library: str) -> tuple[str, str] | None:
    table_path = project.root / "fp-lib-table"
    if not table_path.is_file():
        return None
    try:
        table = sch_io.parse_file(table_path)
    except Exception as exc:  # sexpdata exposes several parse exception types
        raise ValueError(f"malformed explicit footprint table {table_path}: {exc}") from exc
    if sch_io.head_of(table) != "fp_lib_table":
        raise ValueError(f"malformed explicit footprint table {table_path}")

    matches: list[tuple[str, str]] = []
    for entry in sch_io.find_children(table, "lib"):
        if _value(entry, "name") != library:
            continue
        uri = _value(entry, "uri")
        if not uri:
            raise ValueError(
                f"explicit footprint library {library!r} has no URI in {table_path}"
            )
        matches.append((uri, _value(entry, "descr") or ""))
    if len(matches) > 1:
        raise ValueError(f"explicit footprint library {library!r} is declared more than once")
    return matches[0] if matches else None


def _expand_table_uri(
    project: Project, library: str, uri: str
) -> tuple[Path, str]:
    variables = re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", uri)
    expanded = uri
    source_bits: list[str] = []
    for variable in variables:
        if variable == "KIPRJMOD":
            replacement = str(project.root)
            source_bits.append("KIPRJMOD")
        elif variable in os.environ:
            replacement = os.environ[variable]
            source_bits.append(f"{variable} override")
        elif re.fullmatch(r"KICAD\d+_FOOTPRINT_DIR", variable):
            suffix = uri.split(f"${{{variable}}}", 1)[1].lstrip("/\\")
            for root in find_footprint_lib_dirs():
                candidate = (root / suffix).resolve()
                if candidate.is_dir():
                    return candidate, f"{variable} version alias via {root}"
            raise ValueError(
                f"explicit footprint library {library!r} cannot resolve unset {variable}"
            )
        else:
            raise ValueError(
                f"explicit footprint library {library!r} uses unset variable {variable}"
            )
        expanded = expanded.replace(f"${{{variable}}}", replacement)
    if "${" in expanded:
        raise ValueError(f"explicit footprint library {library!r} has malformed URI {uri!r}")
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = project.root / path
    return path.resolve(), ", ".join(source_bits) or "literal URI"


def _contained_footprint(directory: Path, footprint: str) -> Path:
    declared = directory.resolve()
    path = (declared / f"{footprint}.kicad_mod").resolve()
    if path.parent != declared:
        raise ValueError(f"footprint {footprint!r} escapes declared library {declared}")
    return path


def _resolve_path(
    project: Project, library: str, footprint: str
) -> tuple[Path, str, str]:
    entry = _library_entry(project, library)
    if entry is not None:
        uri, description = entry
        directory, expansion = _expand_table_uri(project, library, uri)
        path = _contained_footprint(directory, footprint)
        if not path.is_file():
            raise ValueError(
                f"explicit footprint library {library!r} entry does not exist: {path}"
            )
        source = f"project fp-lib-table ({expansion})"
        if description:
            source += f": {description}"
        return path, source, description

    local_libraries = sorted(
        path for path in project.root.rglob(f"{library}.pretty") if path.is_dir()
    )
    if local_libraries:
        raise ValueError(
            f"project-local footprint library {local_libraries[0]} is not registered "
            "in fp-lib-table"
        )

    for root in find_footprint_lib_dirs():
        path = _contained_footprint(root / f"{library}.pretty", footprint)
        if path.is_file():
            return path, f"configured KiCad library: {root}", ""
    raise ValueError(f"footprint {library}:{footprint} could not be resolved")


def _finite_number(value: Any, detail: str) -> float:
    try:
        number = float(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"malformed {detail}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite {detail}")
    return number


def _validate_pad(node: list[Any]) -> None:
    shape = str(node[3]) if len(node) > 3 else ""
    if shape == "custom":
        raise ValueError("custom pad geometry is not safely supported")
    if shape not in {
        "circle",
        "rect",
        "oval",
        "trapezoid",
        "roundrect",
        "chamfered_rect",
    }:
        raise ValueError(f"unsupported pad shape {shape or '<missing>'}")
    if shape == "trapezoid":
        rect_delta = sch_io.find_child(node, "rect_delta")
        if rect_delta is not None:
            if len(rect_delta) != 3:
                raise ValueError("trapezoid pad rect_delta is not safely supported")
            delta_x = _finite_number(rect_delta[1], "trapezoid pad rect_delta")
            delta_y = _finite_number(rect_delta[2], "trapezoid pad rect_delta")
            if delta_x != 0.0 or delta_y != 0.0:
                raise ValueError("trapezoid pad rect_delta is not safely supported")
    at = sch_io.find_child(node, "at")
    size = sch_io.find_child(node, "size")
    if at is None or len(at) < 3 or size is None or len(size) < 3:
        raise ValueError("pad geometry was not measured")
    _finite_number(at[1], "pad coordinate")
    _finite_number(at[2], "pad coordinate")
    width = _finite_number(size[1], "pad coordinate")
    height = _finite_number(size[2], "pad coordinate")
    if width <= 0.0 or height <= 0.0:
        raise ValueError("pad geometry was not measured")
    if len(at) > 3:
        _finite_number(at[3], "pad rotation")
    if len(_layout_helpers._pad_local_extents(sch_io.dumps(node))) != 1:
        raise ValueError("pad geometry was not measured by the shared extent helper")


def _validate_courtyard_point(point: list[Any]) -> None:
    if len(point) != 3:
        raise ValueError("courtyard geometry was not fully measured")
    _finite_number(point[1], "courtyard coordinate")
    _finite_number(point[2], "courtyard coordinate")


def _validate_courtyard_coordinates(node: list[Any], head: str) -> int:
    coordinate_heads = {
        "fp_line": ("start", "end"),
        "fp_rect": ("start", "end"),
        "fp_circle": ("center", "end"),
    }
    if head in coordinate_heads:
        for coordinate_head in coordinate_heads[head]:
            coordinates = sch_io.find_children(node, coordinate_head)
            if len(coordinates) != 1:
                raise ValueError(f"{head} courtyard geometry was not fully measured")
            _validate_courtyard_point(coordinates[0])
        return 0

    point_sets = sch_io.find_children(node, "pts")
    if len(point_sets) != 1:
        raise ValueError("fp_poly courtyard geometry was not fully measured")
    points = sch_io.find_children(point_sets[0], "xy")
    if not points:
        raise ValueError("fp_poly courtyard geometry was not fully measured")
    for point in points:
        _validate_courtyard_point(point)
    return len(points)


def _validate_raw_polygon_points(block: str, expected: int) -> None:
    points = list(_layout_helpers._iter_top_level_elements(block, "xy"))
    if len(points) != expected:
        raise ValueError("fp_poly courtyard geometry was not fully measured")
    for point in points:
        probe = f'(fp_poly (pts {point}) (layer "F.CrtYd"))'
        if _layout_helpers._courtyard_local_extents(probe) is None:
            raise ValueError("fp_poly courtyard geometry was not fully measured")


def _validate_courtyard(tree: list[Any], text: str) -> None:
    supported = {"fp_line", "fp_rect", "fp_circle", "fp_poly"}
    expected_by_head = {head: 0 for head in supported}
    polygon_point_counts: list[int] = []
    for node in tree[1:]:
        if not isinstance(node, list):
            continue
        head = sch_io.head_of(node)
        if not head or not head.startswith("fp_") or _value(node, "layer") not in {
            "F.CrtYd",
            "B.CrtYd",
        }:
            continue
        if head not in supported:
            raise ValueError(f"unsupported courtyard primitive {head}")
        point_count = _validate_courtyard_coordinates(node, head)
        if head == "fp_poly":
            polygon_point_counts.append(point_count)
        expected_by_head[head] += 1
        if _layout_helpers._courtyard_local_extents(sch_io.dumps(node)) is None:
            raise ValueError(
                f"{head} courtyard geometry was not measured by the shared extent helper"
            )
    for head, expected in expected_by_head.items():
        measured = 0
        for block in _layout_helpers._iter_top_level_elements(text, head):
            if _layout_helpers._courtyard_local_extents(block) is None:
                continue
            if head == "fp_poly":
                if measured >= len(polygon_point_counts):
                    raise ValueError(
                        "fp_poly courtyard geometry was not fully measured"
                    )
                _validate_raw_polygon_points(block, polygon_point_counts[measured])
            measured += 1
        if measured != expected:
            raise ValueError(
                f"{head} courtyard geometry was not measured by the shared extent helper"
            )


def _footprint_text_data(
    text: str, source: object
) -> tuple[list[Any], tuple[float, float, float, float]]:
    try:
        tree = sexpdata.loads(text)
    except Exception as exc:  # sexpdata exposes several parse exception types
        raise ValueError(f"malformed footprint {source}: {exc}") from exc
    if sch_io.head_of(tree) != "footprint":
        raise ValueError(f"malformed footprint {source}: root is not footprint")

    pads = sch_io.find_children(tree, "pad")
    for pad in pads:
        _validate_pad(pad)
    for node in [tree, *pads]:
        for clearance in sch_io.find_children(node, "clearance"):
            if len(clearance) != 2:
                raise ValueError("malformed clearance")
            _finite_number(clearance[1], "clearance")
    for block in _layout_helpers._iter_top_level_elements(text, "clearance"):
        if not re.fullmatch(r"\(clearance\s+[-\d.]+\)", block):
            raise ValueError("clearance was not measured by the shared extent helper")
    if len(_layout_helpers._pad_local_extents(text)) != len(pads):
        raise ValueError("pad geometry was not measured by the shared extent helper")
    _validate_courtyard(tree, text)
    extents = _layout_helpers.get_extents_from_text(text)
    if extents is None:
        raise ValueError(f"footprint {source} has no courtyard or pad geometry")
    if not all(math.isfinite(value) for value in extents):
        raise ValueError(f"footprint {source} produced non-finite extents")
    return tree, extents


def _footprint_data(path: Path) -> tuple[list[Any], tuple[float, float, float, float]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"malformed footprint {path}: {exc}") from exc
    return _footprint_text_data(text, path)


def _fidelity(project: Project, path: Path, description: str) -> str:
    try:
        path.relative_to(project.root)
    except ValueError:
        return "standard"
    provenance = " ".join(description.casefold().split())
    if provenance in _PLACEHOLDER_LOCAL_DESCRIPTIONS:
        return "placeholder"
    if provenance in _REAL_LOCAL_DESCRIPTIONS:
        return "real"
    if provenance == DRAWING_DERIVED_DESCRIPTION:
        drawing_receipt(project, path)
        return "real"
    raise ValueError(
        f"project-local footprint {path} has no declared provenance; "
        "it cannot be classified as real"
    )


def resolve_footprint(project: Project, ref: str, lib_id: str) -> FootprintCandidate:
    """Resolve a declared footprint and measure its real local-frame geometry."""
    try:
        library, footprint = split_footprint_lib_id(lib_id)
    except ValueError as exc:
        raise ValueError(
            f"{ref}: invalid footprint library id {lib_id!r}: {exc}"
        ) from exc

    path, source, description = _resolve_path(project, library, footprint)
    _, extents = _footprint_data(path)
    receipt = (drawing_receipt(project, path)
               if ' '.join(description.casefold().split()) == DRAWING_DERIVED_DESCRIPTION else None)
    return FootprintCandidate(
        lib_id=lib_id,
        path=path,
        source=(source + '; hash-bound author derivation, physical fit unqualified' if receipt else source),
        fidelity=_fidelity(project, path, description),
        extents_mm=extents,
        evidence_id=receipt['evidence_ids'][0] if receipt else None,
    )


def verify_pin_pad_map(
    candidate: FootprintCandidate, expected_pins: set[str]
) -> list[Finding]:
    """Return blocking findings for placeholder or mismatched electrical pads."""
    findings: list[Finding] = []
    if candidate.fidelity == "placeholder":
        findings.append(
            Finding(
                "footprint.placeholder",
                f"{candidate.lib_id} is placeholder geometry and cannot be accepted",
                reference=candidate.lib_id,
                evidence_id=candidate.evidence_id,
            )
        )
    try:
        tree, _ = _footprint_data(candidate.path)
    except (OSError, ValueError) as exc:
        findings.append(
            Finding(
                "footprint.geometry_unreadable",
                str(exc),
                reference=candidate.lib_id,
                evidence_id=candidate.evidence_id,
            )
        )
        return findings

    pads = {
        str(pad[1])
        for pad in sch_io.find_children(tree, "pad")
        if len(pad) > 1 and str(pad[1]).strip()
    }
    missing = sorted(expected_pins - pads)
    unexpected = sorted(pads - expected_pins)
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing pads: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected pads: {', '.join(unexpected)}")
        findings.append(
            Finding(
                "footprint.pad_map_mismatch",
                f"{candidate.lib_id} pin/pad mismatch ({'; '.join(details)})",
                reference=candidate.lib_id,
                evidence_id=candidate.evidence_id,
            )
        )
    return findings
