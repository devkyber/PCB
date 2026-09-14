"""Loading and path containment for PCB Copilot projects."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from pcb_copilot.models import Project, ProjectManifest


class ProjectFormatError(ValueError):
    """Raised when a project manifest is invalid or unsafe."""


def _contained_path(root: Path, configured: Path, field_name: str) -> Path:
    candidate = (root / configured).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ProjectFormatError(
            f"{field_name} resolves outside project root: {configured}"
        ) from exc
    return candidate


def load_project(path: Path) -> Project:
    root = path.resolve()
    manifest_path = root / "project.yaml"
    try:
        document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest = ProjectManifest.model_validate(document)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ProjectFormatError(f"invalid project manifest {manifest_path}: {exc}") from exc

    return Project(
        root=root,
        manifest_path=manifest_path,
        manifest=manifest,
        schematic_path=_contained_path(root, manifest.design.schematic, "design.schematic"),
        pcb_path=_contained_path(root, manifest.design.pcb, "design.pcb"),
        netmap_path=_contained_path(root, manifest.design.netmap, "design.netmap"),
        evidence_index_path=_contained_path(root, manifest.evidence.index, "evidence.index"),
    )
