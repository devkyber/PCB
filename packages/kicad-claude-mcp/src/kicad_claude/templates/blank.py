"""Create the native blank schematic used by the intent renderer."""

from __future__ import annotations

import uuid
from importlib import resources
from pathlib import Path
from string import Template


def _load_fixture(name: str) -> str:
    """Read a packaged template fixture as text."""
    return (
        resources.files("kicad_claude.templates").joinpath("blank", name).read_text()
    )


def write_blank_schematic(target_path: Path) -> Path:
    """Write a single blank `.kicad_sch` to `target_path` (no .kicad_pcb / .kicad_pro).

    Useful for creating child schematics in hierarchical projects.
    Raises FileExistsError if the path already exists.
    """
    target_path = Path(target_path)
    if target_path.exists():
        raise FileExistsError(f"{target_path} already exists")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    sch_uuid = str(uuid.uuid4())
    sch_text = Template(_load_fixture("blank.kicad_sch")).substitute(SCH_UUID=sch_uuid)
    target_path.write_text(sch_text)
    return target_path
