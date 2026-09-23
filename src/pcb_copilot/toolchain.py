"""Discovery of external programs used by the PCB workflow."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kicad_claude.utils.kicad_paths import find_kicad_cli


class ToolchainDiscoveryError(RuntimeError):
    """Raised when a required PCB tool is unavailable."""


@dataclass(frozen=True)
class ToolchainPaths:
    kicad_cli: Path
    kipython: Path | None
    freerouting_jars: tuple[Path, ...]


def discover_toolchain(
    repo_root: Path,
    environ: Mapping[str, str] | None = None,
) -> ToolchainPaths:
    environment = os.environ if environ is None else environ
    kicad_cli = find_kicad_cli()
    if kicad_cli is None:
        raise ToolchainDiscoveryError("kicad-cli was not found")
    resolved_kicad_cli = Path(kicad_cli).resolve()

    configured_kipython = environment.get("KIPYTHON")
    if configured_kipython:
        found_kipython = configured_kipython
    elif environ is None:
        found_kipython = shutil.which("kipython")
    elif "PATH" in environment:
        found_kipython = shutil.which("kipython", path=environment["PATH"])
    else:
        found_kipython = None

    if found_kipython is None and platform.system() == "Windows":
        candidate = resolved_kicad_cli.with_name("python.exe")
        if candidate.is_file():
            try:
                probe = subprocess.run(
                    [str(candidate), "-I", "-c", "import pcbnew"],
                    capture_output=True,
                    check=False,
                    timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            else:
                if probe.returncode == 0:
                    found_kipython = candidate

    kipython = Path(found_kipython).expanduser().resolve() if found_kipython else None

    third_party = repo_root.resolve() / "packages" / "kicad-claude-mcp" / "third_party"
    freerouting_jars = tuple(
        sorted(path.resolve() for path in third_party.glob("freerouting*.jar"))
    )
    return ToolchainPaths(
        kicad_cli=resolved_kicad_cli,
        kipython=kipython,
        freerouting_jars=freerouting_jars,
    )
