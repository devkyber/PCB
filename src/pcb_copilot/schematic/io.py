"""Deterministic YAML persistence for schematic intents."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from pcb_copilot.schematic.models import IntentValidationError, SchematicIntent


def load_schematic_intent(path: Path) -> SchematicIntent:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        return SchematicIntent.model_validate(document)
    except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
        raise IntentValidationError(f"invalid schematic intent {path}: {exc}") from exc


def save_schematic_intent(intent: SchematicIntent, path: Path) -> None:
    document = intent.model_dump(mode="json")
    document["boundary_nets"] = sorted(intent.boundary_nets)
    for component, source in zip(document["components"], intent.components, strict=True):
        component["pin_inventory"] = sorted(source.pin_inventory)
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
