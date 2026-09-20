"""Layout draft orchestration, non-regenerating review and human attestation."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from kicad_claude.adapters import sch_io

from pcb_copilot.accept import _replace_bytes, assert_draft_base_current, load_draft
from pcb_copilot.drafts import _project_root, create_draft
from pcb_copilot.layout.constraints import apply_constraints
from pcb_copilot.layout.io import load_layout_intent, save_layout_intent
from pcb_copilot.layout.models import RoutePolicy
from pcb_copilot.layout.place import propose_placement
from pcb_copilot.layout.preview import inspect_layout, render_layout_preview
from pcb_copilot.layout.route import route_candidate
from pcb_copilot.models import DraftKind
from pcb_copilot.state import file_digest
from pcb_copilot.toolchain import discover_toolchain


def _write(path, value):
    _replace_bytes(path, (json.dumps(value, indent=2, default=str) + "\n").encode())


def _zone_constraints(pcb):
    """Compare authored zone boundaries/rules while allowing fill regeneration."""
    signatures = []
    for zone in sch_io.find_children(sch_io.parse_file(pcb), "zone"):
        name = sch_io.find_child(zone, "name")
        if name is not None and str(name[1]).startswith("Copilot:"):
            signatures.append(
                sch_io.dumps(
                    [
                        node
                        for node in zone
                        if isinstance(node, list)
                        and sch_io.head_of(node)
                        in {
                            "name",
                            "net",
                            "net_name",
                            "layer",
                            "layers",
                            "connect_pads",
                            "polygon",
                            "min_thickness",
                        }
                    ]
                )
            )
    return sorted(signatures)


def validate_layout_draft(project, draft):
    if (
        draft.kind != DraftKind.LAYOUT
        or _project_root(draft) != project.root
        or draft != load_draft(project, draft.id)
    ):
        raise ValueError("invalid layout draft root or metadata")
    metadata = json.loads((draft.root / "draft.json").read_text(encoding="utf-8"))
    assert_draft_base_current(project, draft, metadata)
    return metadata


def layout_artifacts(project, draft):
    """Fixed required inputs plus optional outputs; no caller-controlled hash list."""
    from pcb_copilot.schematic.preview import schematic_files

    pcb = draft.root / project.pcb_path.relative_to(project.root)
    sch = draft.root / project.schematic_path.relative_to(project.root)
    paths = [pcb, pcb.with_suffix(".kicad_pro"), *schematic_files(sch)]
    paths += [
        draft.root / name
        for name in (
            "draft.json",
            "layout-intent.yaml",
            "placement-proposal.json",
            "placement-report.json",
            "constraints-report.json",
            "route-report.json",
            "preview.svg",
            "drc.json",
            "export-report.json",
        )
    ]
    paths += [
        p
        for p in (
            draft.root / "preview.step",
            pcb.with_suffix(".kicad_dru"),
            draft.root / "DESIGN_BASIS.md",
            draft.root / "reference-review.json",
        )
        if p.exists()
    ]
    return {p.relative_to(draft.root).as_posix(): file_digest(p) for p in paths}


def draft_layout(project, intent_path: Path, route=None):
    intent = load_layout_intent(intent_path)
    if route is not None:
        intent = intent.model_copy(update={"route_policy": RoutePolicy(route)})
    draft = create_draft(project, DraftKind.LAYOUT)
    placement = propose_placement(project, intent, draft)
    save_layout_intent(intent, draft.root / "layout-intent.yaml")
    _write(draft.root / "placement-proposal.json", asdict(placement))
    constraints = apply_constraints(placement.pcb_path, intent)
    constraint_data = asdict(constraints)
    constraint_data["intent_sha256"] = file_digest(draft.root / "layout-intent.yaml")
    constraint_data["project_sha256"] = file_digest(
        placement.pcb_path.with_suffix(".kicad_pro")
    )
    constraint_data["zone_constraints"] = _zone_constraints(placement.pcb_path)
    _write(draft.root / "constraints-report.json", constraint_data)
    route_report = route_candidate(project, draft, intent.route_policy, 3)
    route_data = asdict(route_report)
    for value in [route_data, *route_data["attempts"]]:
        for key in ("drc_errors", "unconnected"):
            if value[key] == -1:
                value[key] = "unknown"
    if route_report.selected is not None:
        chosen = next(
            a for a in route_report.attempts if a.index == route_report.selected
        )
        if (
            chosen.drc_errors < 0
            or chosen.unconnected < 0
            or not chosen.pcb_path.resolve().is_relative_to(draft.root.resolve())
        ):
            raise ValueError("invalid selected routing candidate")
        # The selected attempt and its settings become the review board. Retain
        # the candidate and pre-route board for comparison and provenance.
        shutil.copy2(placement.pcb_path, draft.root / "pre-route.kicad_pcb")
        shutil.copy2(chosen.pcb_path, placement.pcb_path)
        companion = chosen.pcb_path.with_suffix(".kicad_pro")
        if not companion.is_file():
            raise ValueError("selected route has no companion settings")
        shutil.copy2(companion, placement.pcb_path.with_suffix(".kicad_pro"))
        route_data["selected_pcb_sha256"] = file_digest(placement.pcb_path)
    _write(draft.root / "route-report.json", route_data)
    return review_layout_draft(project, draft.id)


def review_layout_draft(project, draft_id):
    """Recheck current CAD, retain original base, invalidate any prior approval."""
    draft = load_draft(project, draft_id)
    metadata = validate_layout_draft(project, draft)
    pcb = draft.root / project.pcb_path.relative_to(project.root)
    intent_path = draft.root / "layout-intent.yaml"
    intent = load_layout_intent(intent_path)
    toolchain = discover_toolchain(project.root)
    # Remove approval before any work: failed refresh cannot leave valid consent.
    (draft.root / "preview-approval.json").unlink(missing_ok=True)
    inputs = [
        pcb,
        pcb.with_suffix(".kicad_pro"),
        intent_path,
        draft.root / "constraints-report.json",
        draft.root / "placement-proposal.json",
        draft.root / "route-report.json",
    ]
    before = {p: file_digest(p) for p in inputs}
    with tempfile.TemporaryDirectory(prefix=".review-", dir=draft.root) as directory:
        staging = Path(directory)
        placement = inspect_layout(project, intent, pcb, toolchain)
        findings = placement["findings"]
        constraint_data = json.loads(
            (draft.root / "constraints-report.json").read_text(encoding="utf-8")
        )
        findings.extend(constraint_data["findings"])
        if constraint_data.get("intent_sha256") != file_digest(intent_path):
            findings.append(
                {
                    "code": "constraints.intent_changed",
                    "severity": "block",
                    "message": "Constraint intent changed; prepare a new draft to apply and measure its rules",
                }
            )
        if constraint_data.get("project_sha256") != file_digest(
            pcb.with_suffix(".kicad_pro")
        ):
            findings.append(
                {
                    "code": "constraints.current_mismatch",
                    "severity": "block",
                    "message": "Companion rules differ from the measured constraint proposal; prepare a new draft for changed rules",
                }
            )
        if constraint_data.get("zone_constraints") != _zone_constraints(pcb):
            findings.append(
                {
                    "code": "constraints.zones_changed",
                    "severity": "block",
                    "message": "Authored zone boundaries or clearances changed from the applied constraints",
                }
            )
        # Search failures are historical: current geometry is measured above.
        # Research, identity and unsupported-rule provenance remains relevant.
        proposal = json.loads(
            (draft.root / "placement-proposal.json").read_text(encoding="utf-8")
        )
        historical = {
            "placement.infeasible",
            "placement.dependency",
            "placement.not_applied",
        }
        findings.extend(f for f in proposal["findings"] if f["code"] not in historical)
        findings.extend(render_layout_preview(toolchain, pcb, staging))
        assert_draft_base_current(project, draft, metadata)
        if before != {p: file_digest(p) for p in inputs}:
            raise ValueError("draft inputs changed during review; rerun review-draft")
        _write(staging / "placement-report.json", placement)
        for name in (
            "preview.svg",
            "preview.step",
            "drc.json",
            "export-report.json",
            "placement-report.json",
        ):
            source = staging / name
            if source.is_file():
                _replace_bytes(draft.root / name, source.read_bytes())
            else:
                (draft.root / name).unlink(missing_ok=True)
        route_data = json.loads(
            (draft.root / "route-report.json").read_text(encoding="utf-8")
        )
        report = {
            "schema_version": 1,
            "draft_id": draft.id,
            "kind": "layout",
            "pcb": str(pcb),
            "plot": str(draft.root / "preview.svg")
            if (draft.root / "preview.svg").exists()
            else None,
            "step": str(draft.root / "preview.step")
            if (draft.root / "preview.step").exists()
            else None,
            "drc_report": str(draft.root / "drc.json"),
            "route": route_data,
            "findings": findings,
            "machine_failures": [f for f in findings if f["severity"] == "block"],
            "engineering_warnings": [f for f in findings if f["severity"] == "review"],
            "human_review": "pending",
            "exit_code": int(any(f["severity"] == "block" for f in findings)),
            "artifact_hashes": layout_artifacts(project, draft),
        }
        _write(draft.root / "review.json", report)
    return report


def checked_layout_review(project, draft):
    validate_layout_draft(project, draft)
    report = json.loads((draft.root / "review.json").read_text(encoding="utf-8"))
    hashes = layout_artifacts(project, draft)
    if None in hashes.values() or report.get("artifact_hashes") != hashes:
        raise ValueError("review artifacts changed or missing; run review-draft")
    if report.get("exit_code") != 0 or any(
        f["severity"] == "block" for f in report["findings"]
    ):
        raise ValueError("layout draft has blocking review findings")
    return report


def approve_layout_preview(project, draft_id, reviewer, *, confirm_preview=False):
    """Record the human operator's attestation; this is not automated approval."""
    if not confirm_preview or not reviewer.strip():
        raise ValueError(
            "human reviewer and explicit preview confirmation are required"
        )
    draft = load_draft(project, draft_id)
    report = checked_layout_review(project, draft)
    approval = {
        "draft_id": draft.id,
        "reviewer": reviewer.strip(),
        "confirmed_preview": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "review_sha256": file_digest(draft.root / "review.json"),
        "artifact_hashes": report["artifact_hashes"],
    }
    _write(draft.root / "preview-approval.json", approval)
    return approval
