"""Deterministic YAML persistence for PCB layout intents."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from pcb_copilot.layout.models import LayoutIntent, LayoutIntentError


def load_layout_intent(path: Path) -> LayoutIntent:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        return LayoutIntent.model_validate(document)
    except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
        raise LayoutIntentError(f"invalid layout intent {path}: {exc}") from exc


def save_layout_intent(intent: LayoutIntent, path: Path) -> None:
    document = intent.model_dump(mode="json")
    serialized = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
