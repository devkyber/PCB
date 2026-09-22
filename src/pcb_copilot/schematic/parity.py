"""Check candidate schematic connectivity against the current PCB."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.toolchain import discover_toolchain


def candidate_board_parity(project: Project, candidate_root: Path) -> str | None:
    """Return a failure description or ``None`` for exact KiCad netlist parity."""
    repo_root = Path(__file__).resolve().parents[3]
    toolchain = discover_toolchain(repo_root)
    if toolchain.kipython is None:
        return 'KiCad Python with pcbnew is unavailable; board parity cannot be checked'
    checker = repo_root / 'scripts' / 'check_netlist_parity.py'
    pcb = candidate_root / project.pcb_path.relative_to(project.root)
    try:
        run = subprocess.run(
            [str(toolchain.kipython), str(checker), str(pcb)],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f'board parity check failed to run: {exc}'
    if run.returncode:
        return (run.stdout or run.stderr).strip()[:4000] or 'board parity check failed'
    return None
