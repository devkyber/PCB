"""Transactional workspaces for unaccepted schematic and layout drafts."""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from pcb_copilot.models import DraftKind, DraftRecord, Project
from pcb_copilot.state import canonical_design_hash

_DRAFT_ID = re.compile(r"^\d{8}T\d{6}Z-(?:schematic|layout)-[0-9a-f]{8}$")


def create_draft(
    project: Project,
    kind: DraftKind,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> DraftRecord:
    created = clock()
    if created.tzinfo is None or created.utcoffset() is None:
        raise ValueError("draft clock must return a timezone-aware datetime")
    created = created.astimezone(timezone.utc)
    schematic_hash = canonical_design_hash(project.schematic_path)
    pcb_hash = canonical_design_hash(project.pcb_path)
    base_hash = schematic_hash if kind == DraftKind.SCHEMATIC else pcb_hash
    timestamp = created.strftime("%Y%m%dT%H%M%SZ")
    draft_id = f"{timestamp}-{kind.value}-{base_hash[:8]}"
    root = project.root / ".pcb-copilot" / "drafts" / draft_id
    return DraftRecord(
        id=draft_id,
        kind=kind,
        project=project.manifest.name,
        base_schematic_hash=schematic_hash,
        base_pcb_hash=pcb_hash,
        created_utc=created,
        root=root,
    )


def _project_root(record: DraftRecord) -> Path:
    root = record.root.resolve()
    if not _DRAFT_ID.fullmatch(record.id) or root.name != record.id:
        raise ValueError("invalid draft root or ID")
    project_root = root.parent.parent.parent
    expected = project_root / ".pcb-copilot" / "drafts" / record.id
    if root != expected or project_root.name != record.project:
        raise ValueError("draft root is not contained by its project workspace")
    return project_root


def _copy_inputs(project_root: Path, destination: Path, project_name: str) -> None:
    names = {
        "project.yaml",
        "netmap.json",
        "SCHEMATIC_OWNER",
        "sym-lib-table",
        "fp-lib-table",
        f"{project_name}.kicad_sch",
        f"{project_name}.kicad_pcb",
        f"{project_name}.kicad_pro",
    }
    for name in sorted(names):
        source = project_root / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    for name in ("symbols", "footprints", "jlcpcb"):
        source = project_root / name
        if source.is_dir():
            shutil.copytree(source, destination / name)


def _write_metadata(record: DraftRecord, path: Path) -> None:
    document = {
        "schema_version": 1,
        "id": record.id,
        "kind": record.kind.value,
        "project": record.project,
        "base_schematic_hash": record.base_schematic_hash,
        "base_pcb_hash": record.base_pcb_hash,
        "created_utc": record.created_utc.isoformat().replace("+00:00", "Z"),
    }
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def publish_draft(
    record: DraftRecord,
    writer: Callable[[Path], None],
) -> Path:
    project_root = _project_root(record)
    final_root = record.root.resolve()
    temporary = final_root.with_name(f".building-{record.id}")
    if final_root.exists() or temporary.exists():
        raise FileExistsError(f"draft already exists: {record.id}")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.mkdir()
    try:
        _copy_inputs(project_root, temporary, record.project)
        _write_metadata(record, temporary / "draft.json")
        writer(temporary)
        temporary.replace(final_root)
    except Exception:
        expected_parent = project_root / ".pcb-copilot" / "drafts"
        if temporary.parent == expected_parent and temporary.name == f".building-{record.id}":
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    return final_root
