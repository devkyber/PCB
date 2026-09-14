"""Lifecycle, ownership, and accepted-design protection."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pcb_copilot.models import Lifecycle, Project

UUID_RE = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


class UnsafeDraftTarget(ValueError):
    """Raised before a draft operation could touch an unsafe path."""


class OwnershipError(RuntimeError):
    """Raised when legacy schematic ownership forbids regeneration."""


def canonical_design_hash(path: Path) -> str:
    if not path.is_file():
        return "-"
    canonical = UUID_RE.sub(b"UUID", path.read_bytes())
    return hashlib.sha256(canonical).hexdigest()[:12]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _matches_accepted_design(project: Project, record: dict[str, Any]) -> bool:
    return (
        record.get("schematic_hash") == canonical_design_hash(project.schematic_path)
        and record.get("pcb_hash") == canonical_design_hash(project.pcb_path)
    )


def effective_lifecycle(project: Project) -> Lifecycle:
    state_dir = project.root / ".pcb-copilot"
    release = _read_json(state_dir / "release.json")
    if (
        release
        and release.get("lifecycle") == Lifecycle.RELEASED.value
        and _matches_accepted_design(project, release)
    ):
        return Lifecycle.RELEASED

    review = _read_json(state_dir / "review.json")
    if (
        review
        and review.get("lifecycle") == Lifecycle.HUMAN_REVIEWED.value
        and _matches_accepted_design(project, review)
    ):
        return Lifecycle.HUMAN_REVIEWED

    return Lifecycle.DRAFT


def assert_draft_target_safe(project: Project, target: Path) -> None:
    resolved = target.resolve()
    if resolved in {project.schematic_path.resolve(), project.pcb_path.resolve()}:
        raise UnsafeDraftTarget(f"draft target is an accepted design: {resolved}")

    draft_root = (project.root / ".pcb-copilot" / "drafts").resolve()
    try:
        relative = resolved.relative_to(draft_root)
    except ValueError as exc:
        raise UnsafeDraftTarget(
            f"draft target is outside the draft workspace: {resolved}"
        ) from exc
    if not relative.parts:
        raise UnsafeDraftTarget("draft target must name a file below the draft workspace")


def assert_schematic_regeneration_safe(project: Project) -> None:
    owner_path = project.root / "SCHEMATIC_OWNER"
    try:
        owner = owner_path.read_text(encoding="utf-8").strip().lower()
    except FileNotFoundError:
        owner = "generated"

    if owner == "human":
        raise OwnershipError(f"{project.manifest.name} schematic is human-owned")
    if owner != "generated":
        raise OwnershipError(f"invalid SCHEMATIC_OWNER value: {owner!r}")

    pipeline = _read_json(project.root / "PIPELINE.json")
    recorded_hash = pipeline.get("sch_sha256_12") if pipeline else None
    current_hash = canonical_design_hash(project.schematic_path)
    if recorded_hash is not None and recorded_hash != current_hash:
        raise OwnershipError(
            "generated schematic differs from the last recorded canonical hash"
        )
