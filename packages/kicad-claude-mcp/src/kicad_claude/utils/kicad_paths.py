"""Locate KiCAD library and binary paths across OS and KiCAD versions.

KiCAD exports env vars `KICAD{N}_SYMBOL_DIR` / `KICAD{N}_FOOTPRINT_DIR` only
inside its own GUI/scripting environment; outside (where this MCP server
runs), we fall back to platform defaults.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
from pathlib import Path

# Versions to probe, newest first
_KICAD_VERSIONS = ("10", "9", "8", "7")


def _windows_kicad_root() -> Path:
    return Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "KiCad"


def _windows_install_dirs() -> list[Path]:
    root = _windows_kicad_root()
    if not root.is_dir():
        return []

    def version_key(path: Path) -> tuple[int, ...]:
        numbers = tuple(int(part) for part in re.findall(r"\d+", path.name))
        return numbers or (-1,)

    return sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=version_key,
        reverse=True,
    )


def _platform_default_symbol_dirs() -> list[Path]:
    """Default install locations for `.kicad_sym` libraries by OS."""
    sys_name = platform.system()
    if sys_name == "Darwin":
        return [
            Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"),
        ]
    if sys_name == "Linux":
        return [Path("/usr/share/kicad/symbols")]
    if sys_name == "Windows":
        return [
            install_dir / "share" / "kicad" / "symbols"
            for install_dir in _windows_install_dirs()
        ]
    return []


def _platform_default_footprint_dirs() -> list[Path]:
    sys_name = platform.system()
    if sys_name == "Darwin":
        return [
            Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"),
        ]
    if sys_name == "Linux":
        return [Path("/usr/share/kicad/footprints")]
    if sys_name == "Windows":
        return [
            install_dir / "share" / "kicad" / "footprints"
            for install_dir in _windows_install_dirs()
        ]
    return []


def _from_env(prefix: str) -> list[Path]:
    """Collect paths from `KICAD_LIBRARY_PATH` (custom) and KICAD{N}_{prefix}."""
    out: list[Path] = []
    custom = os.environ.get("KICAD_LIBRARY_PATH")
    if custom:
        out.extend(Path(p) for p in custom.split(os.pathsep) if p)
    for v in _KICAD_VERSIONS:
        env = os.environ.get(f"KICAD{v}_{prefix}")
        if env:
            out.append(Path(env))
    return out


def find_symbol_lib_dirs(extra: list[Path] | None = None) -> list[Path]:
    """Return existing directories that may contain `.kicad_sym` files.

    Search order: explicit `extra` arg → env vars → platform defaults.
    Filtered to existing directories. Duplicates removed (first wins).
    """
    candidates: list[Path] = []
    if extra:
        candidates.extend(extra)
    candidates.extend(_from_env("SYMBOL_DIR"))
    candidates.extend(_platform_default_symbol_dirs())
    return _dedup_existing(candidates)


def find_footprint_lib_dirs(extra: list[Path] | None = None) -> list[Path]:
    """Return existing directories that may contain `*.pretty/` libraries."""
    candidates: list[Path] = []
    if extra:
        candidates.extend(extra)
    candidates.extend(_from_env("FOOTPRINT_DIR"))
    candidates.extend(_platform_default_footprint_dirs())
    return _dedup_existing(candidates)


def _dedup_existing(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        rp = p.expanduser().resolve()
        if rp in seen or not rp.is_dir():
            continue
        seen.add(rp)
        out.append(rp)
    return out


def find_kicad_cli() -> Path | None:
    """Return path to `kicad-cli`, or None if unavailable.

    Checks PATH first, then platform install locations.
    """
    found = shutil.which("kicad-cli")
    if found:
        return Path(found)
    if platform.system() == "Darwin":
        candidate = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
        if candidate.is_file():
            return candidate
    if platform.system() == "Windows":
        for install_dir in _windows_install_dirs():
            candidate = install_dir / "bin" / "kicad-cli.exe"
            if candidate.is_file():
                return candidate
    return None
