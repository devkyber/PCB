"""Region-bound, measured placement proposals. No routing or acceptance."""

from __future__ import annotations

import copy
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path

from kicad_claude.adapters import sch_io
from kicad_claude.utils.geometry import kicad_to_mcp_xy, mcp_to_kicad_xy

from pcb_copilot.drafts import _project_root, publish_draft
from pcb_copilot.evidence.checks import Finding
from pcb_copilot.layout.footprints import (
    _footprint_data,
    resolve_footprint,
    verify_pin_pad_map,
)
from pcb_copilot.layout.footprints import (
    _layout_helpers as helpers,
)
from pcb_copilot.layout.models import (
    LayoutIntent,
    PlacementItem,
    validate_layout_intent,
)
from pcb_copilot.layout.render import board_pin_nets, native_board, schematic_inventory
from pcb_copilot.layout.research import prepare_layout_research
from pcb_copilot.layout.schematic_links import bind_missing_links
from pcb_copilot.models import DraftKind, DraftRecord, Project
from pcb_copilot.state import canonical_design_hash
from pcb_copilot.toolchain import discover_toolchain


@dataclass(frozen=True)
class Placement:
    """``center`` is the footprint anchor, retained as the public API name.

    Anchor and extents use LayoutIntent's bottom-left, x-right, y-up frame.
    Rotation is native KiCad CCW degrees; an asymmetric header is not centered
    on its anchor. Extents include courtyard, pads and local clearances.
    """

    ref: str
    center: tuple[float, float]
    rotation_deg: float
    extents_mm: tuple[float, float, float, float]


@dataclass(frozen=True)
class PlacementReport:
    placed: dict[str, Placement]
    findings: list[Finding]
    pcb_path: Path


def _board_nets(board: dict, parts: dict | None = None) -> dict:
    return board_pin_nets(board['footprints'], parts)


def _local_embedded(node: list) -> str:
    """Normalize serialized board pad angles into the library-local frame."""
    local = copy.deepcopy(node)
    at = sch_io.find_child(local, "at")
    rotation = float(at[3]) if at is not None and len(at) > 3 else 0
    for pad in sch_io.find_children(local, "pad"):
        at = sch_io.find_child(pad, "at")
        if at is not None:
            angle = float(at[3]) if len(at) > 3 else 0
            at[3:] = [angle - rotation]
    return sch_io.dumps(local)


def _priority(item: PlacementItem) -> tuple:
    if item.anchor is not None and item.near_ref is None:
        return (0, item.ref)
    if item.ref.startswith("U"):
        return (1, item.ref)
    if item.ref.startswith("C") and item.near_ref:
        return (2, item.ref)
    for priority, prefix in enumerate(("C", "Y", "D", "J"), 3):
        if item.ref.startswith(prefix):
            return (priority, item.ref)
    return (7, item.ref)


def _pad_signature(text: str) -> list:
    """Geometry-only signature: ignore net names, UUIDs and library metadata."""
    import sexpdata

    tree = sexpdata.loads(text)
    signatures = []
    for pad in sch_io.find_children(tree, "pad"):
        at = sch_io.find_child(pad, "at")
        size = sch_io.find_child(pad, "size")
        signatures.append(
            (
                str(pad[1]),
                str(pad[3]),
                *(round(float(v), 6) for v in at[1:3]),
                round(float(at[3]) % 360 if len(at) > 3 else 0, 6),
                *(round(float(v), 6) for v in size[1:3]),
            )
        )
    return sorted(signatures)


def propose_placement(
    project: Project, intent: LayoutIntent, draft: DraftRecord
) -> PlacementReport:
    """Produce an isolated draft using authoritative CAD, never accepted writes.

    The search is deterministic and conservative (AABB envelopes, 0.25 mm grid).
    Infeasibility is a blocking finding, not proof that no geometric solution
    exists. Any blocking finding leaves all accepted placements intact in the
    draft; no partially applied layout can pretend to preserve constraints.
    """
    if (
        draft.kind != DraftKind.LAYOUT
        or draft.project != project.manifest.name
        or _project_root(draft) != project.root.resolve()
    ):
        raise ValueError("layout draft does not belong to this project")
    if draft.base_pcb_hash != canonical_design_hash(
        project.pcb_path
    ) or draft.base_schematic_hash != canonical_design_hash(project.schematic_path):
        raise ValueError("stale draft: accepted design changed")
    toolchain = discover_toolchain(project.root)
    pcb_path = draft.root / project.pcb_path.relative_to(project.root)
    findings = list(intent.unresolved_decisions)
    research = prepare_layout_research(project)
    findings.extend(research.findings)
    placed: dict[str, Placement] = {}
    operations: dict[str, dict] = {}
    board = native_board(toolchain, project.pcb_path)
    parts, nets = schematic_inventory(toolchain, project.schematic_path)
    try:
        validate_layout_intent(intent, set(parts), set(nets))
    except ValueError as exc:
        findings.append(Finding("placement.intent_invalid", str(exc)))
    if _board_nets(board, parts) != nets:
        findings.append(
            Finding(
                "placement.parity", "Accepted schematic/PCB pin-net assignments differ"
            )
        )
    extra = set(board["footprints"]) - {p.ref for p in intent.placements}
    if extra:
        findings.append(
            Finding(
                "placement.intent_invalid",
                "Missing board placement intent: " + ", ".join(sorted(extra)),
            )
        )
    x0, y0, x1, y1 = board["bounds"]
    if not board["rectangular"]:
        findings.append(
            Finding(
                "placement.outline_unsupported",
                "Placement currently requires one rectangular outline without cutouts",
            )
        )
    if not (
        math.isclose(x1 - x0, intent.outline.width_mm, abs_tol=0.01)
        and math.isclose(y1 - y0, intent.outline.height_mm, abs_tol=0.01)
    ):
        findings.append(
            Finding(
                "placement.outline_mismatch",
                "Intent outline differs from accepted board; outline edits require a separate proposal",
            )
        )
    if board["rule_areas"]:
        findings.append(
            Finding(
                "placement.rule_areas",
                "Native rule areas need explicit placement constraint support",
            )
        )
        for ref, footprint in board["footprints"].items():
            if footprint["rule_areas"]:
                findings.append(
                    Finding(
                        "placement.rule_areas",
                        f"{ref}: accepted footprint contains unsupported placement/routing rule areas",
                        reference=ref,
                    )
                )

    # One established boundary conversion. Board-local origin is its bottom-left.
    def to_native(x, y):
        return mcp_to_kicad_xy(x0 + x, y, page_height_mm=y1)

    def to_design(x, y):
        x, y = kicad_to_mcp_xy(x, y, page_height_mm=y1)
        return x - x0, y

    tree = sch_io.parse_file(project.pcb_path)
    embedded = {}
    for node in sch_io.find_children(tree, "footprint"):
        ref = next(
            (
                str(p[2])
                for p in sch_io.find_children(node, "property")
                if str(p[1]) == "Reference"
            ),
            None,
        )
        if ref is None:
            ref = next(
                (
                    str(p[2])
                    for p in sch_io.find_children(node, "fp_text")
                    if str(p[1]) == "reference"
                ),
                None,
            )
        embedded[ref] = node
    geometry = {}
    for item in intent.placements:
        try:
            accepted = board["footprints"].get(item.ref)
            identity = parts.get(item.ref, {}).get("footprint")
            lib_id = item.footprint or identity
            if (item.pcb_only and item.ref in parts) or (
                identity and lib_id != identity
            ):
                raise ValueError(
                    "identity_mismatch: footprint/PCB-only intent differs from accepted schematic"
                )
            if accepted and accepted["lib_id"] != lib_id:
                raise ValueError(
                    "identity_mismatch: footprint differs from accepted PCB"
                )
            if not accepted and not item.pcb_only:
                raise ValueError(
                    "identity_mismatch: physical part is missing from accepted PCB"
                )
            candidate = resolve_footprint(project, item.ref, lib_id or "")
            candidate_tree = sch_io.parse_file(candidate.path)
            if any(
                sch_io.find_child(zone, "keepout") is not None
                for zone in sch_io.find_children(candidate_tree, "zone")
            ):
                findings.append(
                    Finding(
                        "placement.rule_areas",
                        f"{item.ref}: resolved footprint contains unsupported placement/routing rule areas",
                        reference=item.ref,
                    )
                )
                continue
            if item.ref in parts:
                expected_pins = parts[item.ref]["pins"]
                actual_pins = {pin for pin, _ in accepted["pads"] if pin}
                if not expected_pins <= actual_pins:
                    raise ValueError("accepted PCB is missing schematic pins")
                # Existing netless mounting pads (e.g. JST MP) are physical
                # geometry, not extra electrical symbol pins. Verify those too.
                errors = verify_pin_pad_map(candidate, expected_pins | actual_pins)
                if errors:
                    raise ValueError("; ".join(f.message for f in errors))
            elif candidate.fidelity == "placeholder":
                raise ValueError("placeholder footprint cannot be placed")
            text = candidate.path.read_text(encoding="utf-8")
            if accepted:
                if accepted["layer"] != "F.Cu":
                    raise ValueError(
                        "back-side footprints require explicit mirrored geometry support"
                    )
                text = _local_embedded(embedded[item.ref])
                # Validate actual embedded geometry as strictly as the resolved
                # library. Preserve its board-specific clearance overrides.
                with tempfile.TemporaryDirectory(
                    prefix="pcb-layout-geometry-"
                ) as directory:
                    path = Path(directory) / "embedded.kicad_mod"
                    path.write_text(text, encoding="utf-8")
                    _footprint_data(path)
                source_text = candidate.path.read_text(encoding="utf-8")
                if (
                    _pad_signature(text) != _pad_signature(source_text)
                    or helpers.get_extents_from_text(text) != candidate.extents_mm
                ):
                    findings.append(
                        Finding(
                            "placement.instance_differs",
                            f"{item.ref}: embedded geometry/local clearances differ from resolved library; measured and preserved the accepted instance",
                            reference=item.ref,
                            severity="review",
                        )
                    )
            geometry[item.ref] = (text, candidate)
        except (OSError, ValueError, KeyError) as exc:
            code = (
                "placement.identity_mismatch"
                if "identity_mismatch" in str(exc)
                else "placement.footprint"
            )
            findings.append(Finding(code, f"{item.ref}: {exc}", reference=item.ref))
    tracker = helpers.PlacementTracker(board_mm=(x0, y0, x1, y1))
    regions = {r.id: r for r in intent.regions}
    pending = sorted(intent.placements, key=_priority)
    while pending:
        ready = [p for p in pending if p.near_ref is None or p.near_ref in placed]
        if not ready:
            for item in pending:
                findings.append(
                    Finding(
                        "placement.dependency",
                        f"{item.ref}: unresolved or cyclic dependency on {item.near_ref}",
                        reference=item.ref,
                    )
                )
            break
        item = ready[0]
        pending.remove(item)
        if item.ref not in geometry:
            continue
        text, candidate = geometry[item.ref]
        region = regions[item.region]
        low = to_native(region.x_mm, region.y_mm + region.height_mm)
        high = to_native(region.x_mm + region.width_mm, region.y_mm)
        offset = helpers.board_aabb(
            helpers.get_extents_from_text(text), 0, 0, item.rotation_deg
        )
        bounds = (
            max(low[0], x0 + 0.3),
            max(low[1], y0 + 0.3),
            min(high[0], x1 - 0.3),
            min(high[1], y1 - 0.3),
        )
        target = None
        sources = [(0.0, 0.0)]
        if item.near_ref:
            target_item = next(p for p in intent.placements if p.ref == item.near_ref)
            target_pads = helpers.local_pad_positions(geometry[item.near_ref][0])
            source_pads = helpers.local_pad_positions(text)
            if item.near_pin not in target_pads or (
                item.source_pin and item.source_pin not in source_pads
            ):
                findings.append(
                    Finding(
                        "placement.pad_missing",
                        f"{item.ref}: cannot measure {item.source_pin or 'source pads'} to {item.near_ref}.{item.near_pin}",
                        reference=item.ref,
                    )
                )
                continue
            # Without an explicit source pin, choose only pads on the target net.
            source_names = (
                [item.source_pin]
                if item.source_pin
                else [
                    pin
                    for net, members in nets.items()
                    if (item.near_ref, item.near_pin) in members
                    for ref, pin in members
                    if ref == item.ref and pin in source_pads
                ]
            )
            if item.source_pin and not any(
                (item.near_ref, item.near_pin) in members
                and (item.ref, item.source_pin) in members
                for members in nets.values()
            ):
                findings.append(
                    Finding(
                        "placement.pad_net_mismatch",
                        f"{item.ref}.{item.source_pin} and {item.near_ref}.{item.near_pin} are not on the same accepted net",
                        reference=item.ref,
                    )
                )
                continue
            if not source_names:
                findings.append(
                    Finding(
                        "placement.pad_missing",
                        f"{item.ref}: no source pad on {item.near_ref}.{item.near_pin}'s accepted net",
                        reference=item.ref,
                    )
                )
                continue
            sources = [
                helpers._rotate_local(*source_pads[p], item.rotation_deg)
                for p in source_names
            ]
            delta = helpers._rotate_local(
                *target_pads[item.near_pin], target_item.rotation_deg
            )
            anchor = to_native(*placed[item.near_ref].center)
            target = (anchor[0] + delta[0], anchor[1] + delta[1])
        if item.anchor is not None:
            positions = [to_native(*item.anchor)]
        elif target is not None:
            # Pad-to-pad search, with deterministic center-distance tie breaking.
            positions = []
            reach = item.max_distance_mm
            for step in range(1, math.ceil(reach / 0.1) + 1):
                radius = min(reach, step * 0.1)
                for angle in range(0, 360, 15):
                    for sx, sy in sources:
                        a = math.radians(angle)
                        positions.append(
                            (
                                target[0] + radius * math.cos(a) - sx,
                                target[1] + radius * math.sin(a) - sy,
                            )
                        )
            positions.sort(key=lambda p: (math.dist(p, target), p))
        else:
            # shelf_pack supplies the measured anchor seed. The native-frame
            # rectangle represents the already rotated union, without recentering.
            envelope = f'(footprint "envelope" (fp_rect (start {offset[0]:.9f} {offset[1]:.9f}) (end {offset[2]:.9f} {offset[3]:.9f}) (layer "F.CrtYd")))'
            seed = helpers.shelf_pack(
                [(item.ref, envelope)],
                bounds[0],
                bounds[1],
                bounds[2] - bounds[0],
                bounds[3] - bounds[1],
                margin_mm=0,
            )[item.ref]
            positions = [
                (seed[0] + ix * 0.25, seed[1] + iy * 0.25)
                for iy in range(
                    max(0, math.floor((bounds[3] - offset[3] - seed[1]) / 0.25) + 1)
                )
                for ix in range(
                    max(0, math.floor((bounds[2] - offset[2] - seed[0]) / 0.25) + 1)
                )
            ]
        conflicts = set()
        for px, py in positions:
            if (
                target is not None
                and min(math.dist((px + sx, py + sy), target) for sx, sy in sources)
                > item.max_distance_mm + 1e-8
            ):
                continue
            box = (px + offset[0], py + offset[1], px + offset[2], py + offset[3])
            if any(
                (
                    box[0] < bounds[0] - 1e-8,
                    box[1] < bounds[1] - 1e-8,
                    box[2] > bounds[2] + 1e-8,
                    box[3] > bounds[3] + 1e-8,
                )
            ):
                continue
            collision = [
                ref
                for ref, b in tracker.occupied()
                if box[0] - 0.25 < b[2]
                and box[2] + 0.25 > b[0]
                and box[1] - 0.25 < b[3]
                and box[3] + 0.25 > b[1]
            ]
            if collision:
                conflicts.update(collision)
                continue
            try:
                actual = tracker.place(item.ref, text, px, py, item.rotation_deg)
            except (helpers.CourtyardCollisionError, helpers.OffBoardError):
                continue
            left, top = to_design(actual[0], actual[1])
            right, bottom = to_design(actual[2], actual[3])
            placed[item.ref] = Placement(
                item.ref,
                to_design(px, py),
                item.rotation_deg,
                (left, bottom, right, top),
            )
            operations[item.ref] = {
                "position": (px, py),
                "rotation": item.rotation_deg,
                "path": str(candidate.path),
                "lib_id": candidate.lib_id,
            }
            break
        else:
            findings.append(
                Finding(
                    "placement.infeasible",
                    f"{item.ref}: no legal placement in region {item.region}; conflicting refs: {', '.join(sorted(conflicts)) or 'none (region/edge/distance limits)'}",
                    reference=item.ref,
                )
            )
    if any(f.severity == "block" for f in findings):
        placed.clear()
        operations.clear()
        findings.append(
            Finding(
                "placement.not_applied",
                "Blocking findings: draft retains accepted footprint positions",
                severity="review",
            )
        )
    if board["tracks"] or board["zones"]:
        findings.append(
            Finding(
                "placement.copper_removed",
                f"Removed obsolete copper from draft: {board['tracks']} tracks/vias and {board['zones']} zones; routing remains human-controlled",
                severity="review",
            )
        )

    def writer(root: Path):
        # publish_draft copies standard inputs; custom manifest names must also
        # be present at their declared relative paths in the isolated workspace.
        import shutil

        research.write(root)
        for source in (project.pcb_path, project.schematic_path):
            destination = root / source.relative_to(project.root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        output = root / project.pcb_path.relative_to(project.root)
        native_board(toolchain, output, output=output, placements=operations)
        result = native_board(toolchain, output)
        if _board_nets(result) != _board_nets(board):
            raise ValueError("draft PCB parity changed during native placement")
        if _board_nets(result, parts) == nets:
            try:
                linked = bind_missing_links(output, parts, result['footprints'])
                if linked:
                    findings.append(Finding('placement.schematic_links_added',
                        'Bound missing schematic IDs in the draft: ' + ', '.join(linked), severity='review'))
            except ValueError as exc:
                findings.append(Finding('placement.schematic_links', str(exc)))

    publish_draft(draft, writer)
    return PlacementReport(placed, findings, pcb_path)
