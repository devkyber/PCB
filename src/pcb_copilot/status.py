"""Read-only project status collection and rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pcb_copilot.models import Lifecycle, Project
from pcb_copilot.state import effective_lifecycle
from pcb_copilot.toolchain import ToolchainDiscoveryError, discover_toolchain


@dataclass(frozen=True)
class ProjectStatus:
    name: str
    lifecycle: Lifecycle
    schematic_path: Path
    pcb_path: Path
    evidence_index_present: bool
    toolchain_available: bool
    kicad_cli: Path | None
    review_hashes: tuple[str, str] | None
    release_hashes: tuple[str, str] | None
    recommended_command: str


def _recorded_hashes(path: Path) -> tuple[str, str] | None:
    try:
        record: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    schematic = record.get("schematic_hash")
    pcb = record.get("pcb_hash")
    if isinstance(schematic, str) and isinstance(pcb, str):
        return schematic, pcb
    return None


def collect_status(project: Project) -> ProjectStatus:
    repo_root = Path(__file__).resolve().parents[2]
    try:
        toolchain = discover_toolchain(repo_root)
    except ToolchainDiscoveryError:
        toolchain = None

    state_dir = project.root / ".pcb-copilot"
    evidence_present = project.evidence_index_path.is_file()
    if not evidence_present:
        recommendation = f"pcb-copilot research {project.root} --verify"
    else:
        recommendation = f"pcb-copilot update-schematic {project.root} --intent schematic-intent.yaml"

    return ProjectStatus(
        name=project.manifest.name,
        lifecycle=effective_lifecycle(project),
        schematic_path=project.schematic_path,
        pcb_path=project.pcb_path,
        evidence_index_present=evidence_present,
        toolchain_available=toolchain is not None,
        kicad_cli=toolchain.kicad_cli if toolchain else None,
        review_hashes=_recorded_hashes(state_dir / "review.json"),
        release_hashes=_recorded_hashes(state_dir / "release.json"),
        recommended_command=recommendation,
    )


def render_status(status: ProjectStatus) -> str:
    toolchain = str(status.kicad_cli) if status.kicad_cli else "missing"
    evidence = "present" if status.evidence_index_present else "missing"
    review = " / ".join(status.review_hashes) if status.review_hashes else "none"
    release = " / ".join(status.release_hashes) if status.release_hashes else "none"
    return "\n".join(
        (
            f"Project: {status.name}",
            f"Lifecycle: {status.lifecycle.value}",
            f"Schematic: {status.schematic_path}",
            f"PCB: {status.pcb_path}",
            f"Evidence index: {evidence}",
            f"Toolchain: {toolchain}",
            f"Last review hashes: {review}",
            f"Last release hashes: {release}",
            f"Next: {status.recommended_command}",
        )
    )
