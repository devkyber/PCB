"""Small, filesystem-safe validation shared by layout intent and resolution."""

from __future__ import annotations

from pathlib import Path


def _validate_component(value: str, kind: str) -> None:
    if (
        not value
        or value != value.strip()
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or any(ord(character) < 32 for character in value)
        or Path(value).name != value
    ):
        raise ValueError(f"unsafe {kind} name in footprint library id: {value!r}")


def split_footprint_lib_id(value: str) -> tuple[str, str]:
    """Return a safe ``Library:Name`` pair while allowing interior spaces."""
    value = value.strip()
    if value.count(":") != 1:
        raise ValueError("footprint must use Library:Name syntax")
    library, footprint = value.split(":", 1)
    _validate_component(library, "library")
    _validate_component(footprint, "footprint")
    return library, footprint
