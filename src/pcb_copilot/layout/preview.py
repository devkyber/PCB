"""Current-board validation and KiCad review exports; never mutates CAD."""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict
from pathlib import Path

from kicad_claude.adapters import sch_io
from kicad_claude.utils.geometry import kicad_to_mcp_xy

from pcb_copilot.evidence.checks import Finding
from pcb_copilot.layout.footprints import _layout_helpers as helpers
from pcb_copilot.layout.footprints import resolve_footprint
from pcb_copilot.layout.models import validate_layout_intent
from pcb_copilot.layout.place import _board_nets, _local_embedded
from pcb_copilot.layout.render import native_board, schematic_inventory


def inspect_layout(project, intent, pcb, toolchain):
    """Measure actual geometry after human edits without re-running placement."""
    findings = list(intent.unresolved_decisions)
    board = native_board(toolchain, pcb)
    parts, nets = schematic_inventory(toolchain, project.schematic_path)
    try:
        validate_layout_intent(intent, set(parts), set(nets))
    except ValueError as exc:
        findings.append(Finding("layout.intent", str(exc)))
    if _board_nets(board) != nets:
        findings.append(
            Finding(
                "layout.parity", "Schematic/PCB qualified pin-net assignments differ"
            )
        )
    intended = {item.ref: item for item in intent.placements}
    if set(board["footprints"]) != set(intended):
        findings.append(
            Finding("layout.inventory", "PCB references differ from intent inventory")
        )
    x0, y0, x1, y1 = board["bounds"]
    if not board["rectangular"] or not (
        math.isclose(x1 - x0, intent.outline.width_mm, abs_tol=0.01)
        and math.isclose(y1 - y0, intent.outline.height_mm, abs_tol=0.01)
    ):
        findings.append(
            Finding(
                "layout.outline",
                "Current outline does not match supported rectangular intent",
            )
        )
    if board["rule_areas"]:
        findings.append(
            Finding(
                "layout.rule_areas",
                "Native rule areas require explicit constraint support",
            )
        )
    regions = {r.id: r for r in intent.regions}
    # Native save rounds to nanometres. Do not report floating point dust at
    # the exact 0.3 mm edge margin as an off-board component.
    tracker = helpers.PlacementTracker(
        board_mm=(x0, y0, x1, y1), edge_margin_mm=0.3 - 1e-6
    )
    measured, pads = {}, {}
    for fp in sch_io.find_children(sch_io.parse_file(pcb), "footprint"):
        properties = {
            str(p[1]): str(p[2]) for p in sch_io.find_children(fp, "property")
        }
        ref = properties.get("Reference")
        if ref is None:
            ref = next(
                (
                    str(p[2])
                    for p in sch_io.find_children(fp, "fp_text")
                    if str(p[1]) == "reference"
                ),
                "",
            )
        item = intended.get(ref)
        if item is None:
            continue
        try:
            actual = board["footprints"][ref]
            candidate = resolve_footprint(project, ref, actual["lib_id"])
            if candidate.fidelity == "placeholder":
                raise ValueError("placeholder footprint")
            identity = parts.get(ref, {}).get("footprint")
            if (
                (item.pcb_only and ref in parts)
                or (identity and identity != actual["lib_id"])
                or (item.footprint and item.footprint != actual["lib_id"])
            ):
                raise ValueError("footprint identity differs from schematic/intent")
            if ref in parts and not parts[ref]["pins"] <= {
                p for p, _ in actual["pads"]
            }:
                raise ValueError("physical PCB is missing schematic pins")
            if actual["layer"] != "F.Cu":
                raise ValueError(
                    "back-side geometry requires mirrored constraint support"
                )
            at = sch_io.find_child(fp, "at")
            px, py = float(at[1]), float(at[2])
            angle = float(at[3]) if len(at) > 3 else 0
            text = _local_embedded(fp)
            box = tracker.place(ref, text, px, py, angle)
            left, top = kicad_to_mcp_xy(box[0], box[1], page_height_mm=y1)
            right, bottom = kicad_to_mcp_xy(box[2], box[3], page_height_mm=y1)
            r = regions[item.region]
            if (
                left - x0 < r.x_mm - 1e-6
                or right - x0 > r.x_mm + r.width_mm + 1e-6
                or bottom < r.y_mm - 1e-6
                or top > r.y_mm + r.height_mm + 1e-6
            ):
                raise ValueError("footprint envelope lies outside assigned region")
            x, y = kicad_to_mcp_xy(px, py, page_height_mm=y1)
            if item.anchor and math.dist((x - x0, y), item.anchor) > 0.001:
                raise ValueError("footprint moved away from required anchor")
            if not math.isclose((angle - item.rotation_deg) % 360, 0, abs_tol=0.001):
                raise ValueError("footprint rotation differs from intent")
            measured[ref] = {
                "anchor": [x - x0, y],
                "rotation_deg": angle,
                "extents_mm": [left - x0, bottom, right - x0, top],
            }
            pads[ref] = {
                pin: (px + delta[0], py + delta[1])
                for pin, local in helpers.local_pad_positions(text).items()
                for delta in [helpers._rotate_local(*local, angle)]
            }
        except (
            ValueError,
            OSError,
            KeyError,
            helpers.CourtyardCollisionError,
            helpers.OffBoardError,
        ) as exc:
            findings.append(Finding("layout.geometry", f"{ref}: {exc}", reference=ref))
    for item in intent.placements:
        if item.near_ref:
            source_pins = (
                [item.source_pin]
                if item.source_pin
                else [
                    pin
                    for members in nets.values()
                    if (item.near_ref, item.near_pin) in members
                    for ref, pin in members
                    if ref == item.ref
                ]
            )
            try:
                target = pads[item.near_ref][item.near_pin]
                if not source_pins or any(
                    not any(
                        (item.ref, pin) in members
                        and (item.near_ref, item.near_pin) in members
                        for members in nets.values()
                    )
                    for pin in source_pins
                ):
                    raise ValueError(
                        "near-pad relationship does not share the accepted net"
                    )
                if (
                    min(math.dist(pads[item.ref][pin], target) for pin in source_pins)
                    > item.max_distance_mm + 1e-6
                ):
                    raise ValueError("pad-to-pad maximum distance exceeded")
            except (KeyError, ValueError) as exc:
                findings.append(
                    Finding("layout.near_pad", f"{item.ref}: {exc}", reference=item.ref)
                )
    return {"measured": measured, "findings": [asdict(f) for f in findings]}


def render_layout_preview(toolchain, pcb: Path, output: Path):
    """Export a 2D plot, fresh DRC and optional STEP with full exporter messages."""
    output.mkdir(parents=True, exist_ok=True)
    findings, logs = [], {}
    plot, drc, step = (
        output / name for name in ("preview.svg", "drc.json", "preview.step")
    )

    def run(kind, args):
        result = subprocess.run(
            [str(toolchain.kicad_cli), *args],
            cwd=pcb.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        logs[kind] = {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if result.returncode:
            raise ValueError(f"{kind} export failed: {result.stderr or result.stdout}")

    try:
        run("drc", ["pcb", "drc", "--format", "json", "-o", str(drc), str(pcb)])
        report = json.loads(drc.read_text(encoding="utf-8"))
        if not all(
            isinstance(report.get(key), list)
            for key in ("violations", "unconnected_items")
        ):
            raise ValueError(
                "DRC did not produce measured violations/unconnected arrays"
            )
        for violation in report["violations"] + report.get("schematic_parity", []):
            findings.append(
                Finding(
                    "drc." + violation.get("type", "violation"),
                    violation.get("description", "DRC finding"),
                    severity="block"
                    if violation.get("severity") == "error"
                    else "review",
                )
            )
        if report["unconnected_items"]:
            findings.append(
                Finding(
                    "drc.unconnected",
                    f"{len(report['unconnected_items'])} unconnected items; routing required before release",
                    severity="review",
                )
            )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        findings.append(Finding("drc.failed", str(exc)))
        drc.write_text(
            json.dumps({"status": "failed", "error": str(exc)}), encoding="utf-8"
        )
    try:
        run(
            "plot",
            [
                "pcb",
                "export",
                "svg",
                "--layers",
                "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts",
                "--mode-single",
                "--fit-page-to-board",
                "--exclude-drawing-sheet",
                "-o",
                str(plot),
                str(pcb),
            ],
        )
        if "<svg" not in plot.read_text(encoding="utf-8"):
            raise ValueError("No SVG plot produced")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        findings.append(Finding("preview.failed", str(exc)))
        plot.unlink(missing_ok=True)
    try:
        run("step", ["pcb", "export", "step", "--force", "-o", str(step), str(pcb)])
        if not step.is_file():
            raise ValueError("No STEP file produced")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        findings.append(Finding("step.unavailable", str(exc), severity="review"))
        # KiCad can return nonzero for unsupported component models while
        # exporting a usable partial STEP. Retain it with the full warning.
        if not step.is_file() or not step.read_bytes().startswith(b"ISO-10303-21;"):
            step.unlink(missing_ok=True)
    findings.append(
        Finding(
            "step.model_review",
            "STEP may be partial or board-only; exporter success does not establish component model completeness or mechanical fit. Inspect exporter logs and KiCad 3D.",
            severity="review",
        )
    )
    (output / "export-report.json").write_text(
        json.dumps(logs, indent=2), encoding="utf-8"
    )
    return [asdict(f) for f in findings]
