"""Full-content fingerprints for the exact design inspected by review."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pcb_copilot.schematic.preview import schematic_files


def schematic_digest(root: Path) -> str:
    """Hash the root schematic and every referenced child, including filenames."""
    digest = hashlib.sha256()
    base = root.parent.resolve()
    for path in sorted(schematic_files(root), key=lambda item: item.relative_to(base).as_posix()):
        name = path.relative_to(base).as_posix().encode('utf-8')
        content = path.read_bytes()
        digest.update(len(name).to_bytes(8, 'big'))
        digest.update(name)
        digest.update(len(content).to_bytes(8, 'big'))
        digest.update(content)
    return digest.hexdigest()


def pcb_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
