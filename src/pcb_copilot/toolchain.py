"""Discovery of external programs used by the PCB workflow."""

from __future__ import annotations

import os
import shutil
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

    configured_kipython = environment.get("KIPYTHON")
    found_kipython = configured_kipython or shutil.which("kipython")
    kipython = Path(found_kipython).expanduser().resolve() if found_kipython else None

    third_party = repo_root.resolve() / "tools" / "kicad-claude-mcp" / "third_party"
    freerouting_jars = tuple(
        sorted(path.resolve() for path in third_party.glob("freerouting*.jar"))
    )
    return ToolchainPaths(
        kicad_cli=Path(kicad_cli).resolve(),
        kipython=kipython,
        freerouting_jars=freerouting_jars,
    )
