"""Publish current layout exports without retaining failed exports from an older run."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pcb_copilot.transaction import contained, replace_bytes

LAYOUT_ARTIFACTS = ('layout.svg', 'layout.step', 'layout-drc-0.json', 'layout-drc-1.json',
                    'routing-topology.json')


def publish_layout_artifacts(project_root: Path, output: Path, preview: Path, *,
                             additional_artifacts: Iterable[Path] = ()) -> dict[str, str]:
    """Replace known exports, removing only those missing from this layout attempt.

    Other files in the preview directory, including review reports and owner
    notes, remain untouched unless explicitly supplied as current artifacts.
    Call only when a layout was attempted, not for schematic-only updates.
    """
    sources = {name: output / name for name in LAYOUT_ARTIFACTS}
    sources.update((path.name, path) for path in additional_artifacts if path.is_file())
    published = {}
    for name, source in sources.items():
        target = contained(project_root, preview / name)
        if source.is_file():
            replace_bytes(target, source.read_bytes())
            published[name] = str(target)
        elif name in LAYOUT_ARTIFACTS:
            target.unlink(missing_ok=True)
    return published
