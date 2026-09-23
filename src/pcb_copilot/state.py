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




def canonical_design_hash(path: Path) -> str:
    if not path.is_file():
        return "-"
    canonical = UUID_RE.sub(b"UUID", path.read_bytes())
    return hashlib.sha256(canonical).hexdigest()[:12]


def file_digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def accepted_file_hashes(project: Project) -> dict[str, str | None]:
    from pcb_copilot.schematic.preview import schematic_files

    files = list(schematic_files(project.schematic_path))
    files.extend([project.pcb_path, project.netmap_path, project.manifest_path,
                  project.pcb_path.with_suffix('.kicad_pro'),
                  project.pcb_path.with_suffix('.kicad_dru')])
    return {p.relative_to(project.root).as_posix(): file_digest(p) for p in files}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None




def effective_lifecycle(project: Project) -> Lifecycle:
    from pcb_copilot.transaction import contained, input_hashes

    state_dir = project.root / ".pcb-copilot"
    release = _read_json(state_dir / "release.json")
    try:
        if (release and release.get('schema_version') == 2
                and release.get('lifecycle') == Lifecycle.RELEASED.value
                and release.get('inputs') == input_hashes(project)):
            from pcb_copilot.release import output_hashes

            output = contained(project.root, project.root / release['output'])
            manifest = output / 'SOURCE.json'
            if file_digest(manifest) == release.get('manifest_sha256'):
                document = json.loads(manifest.read_text(encoding='utf-8'))
                if (document['inputs'] == release['inputs']
                        and document['outputs'] == output_hashes(output)):
                    return Lifecycle.RELEASED
    except (KeyError, OSError, ValueError, TypeError):
        pass
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
