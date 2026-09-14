"""Preservation inventory and immutable board-baseline helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol

import yaml
from kicad_claude.adapters import sch_io
from pydantic import BaseModel, ConfigDict, model_validator

InventoryAction = Literal["KEEP", "REFACTOR", "MERGE", "GENERATED", "DELETE"]
UUID_RE = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


class InventoryError(ValueError):
    """Base error for an invalid or incomplete migration inventory."""


class AmbiguousInventoryRule(InventoryError):
    """Raised when equally specific rules classify the same path."""


class InventoryRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    pattern: str
    action: InventoryAction
    rationale: str
    replacement: str | None = None

    @model_validator(mode="after")
    def require_rationale_and_replacement(self) -> InventoryRule:
        if not self.rationale.strip():
            raise ValueError("inventory rationale must not be empty")
        if self.action in {"DELETE", "MERGE"} and not (
            self.replacement and self.replacement.strip()
        ):
            raise ValueError(f"{self.action} rule requires a replacement")
        return self


class BoardProject(Protocol):
    root: Path
    schematic_path: Path
    pcb_path: Path
    netmap_path: Path


@dataclass(frozen=True)
class LegacyProjectPaths:
    root: Path
    schematic_path: Path
    pcb_path: Path
    netmap_path: Path


def load_inventory(path: Path) -> tuple[InventoryRule, ...]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise InventoryError(f"cannot read inventory {path}: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("rules"), list):
        raise InventoryError("inventory must contain a rules list")
    return tuple(InventoryRule.model_validate(item) for item in document["rules"])


def _matches(path: str, pattern: str) -> bool:
    pieces: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*" and index + 1 < len(pattern) and pattern[index + 1] == "*":
            pieces.append(".*")
            index += 2
        elif char == "*":
            pieces.append("[^/]*")
            index += 1
        elif char == "?":
            pieces.append("[^/]")
            index += 1
        else:
            pieces.append(re.escape(char))
            index += 1
    return re.fullmatch("".join(pieces), path) is not None


def _specificity(pattern: str) -> int:
    return len(pattern.replace("*", "").replace("?", ""))


def classify_path(
    path: PurePosixPath,
    rules: Sequence[InventoryRule],
) -> InventoryRule:
    name = path.as_posix()
    matches = [rule for rule in rules if _matches(name, rule.pattern)]
    if not matches:
        raise InventoryError(f"no inventory rule for {name}")
    best_score = max(_specificity(rule.pattern) for rule in matches)
    best = [rule for rule in matches if _specificity(rule.pattern) == best_score]
    if len(best) != 1:
        patterns = ", ".join(rule.pattern for rule in best)
        raise AmbiguousInventoryRule(f"ambiguous inventory rules for {name}: {patterns}")
    return best[0]


def legacy_project_paths(root: Path) -> LegacyProjectPaths:
    resolved = root.resolve()
    name = resolved.name
    return LegacyProjectPaths(
        root=resolved,
        schematic_path=resolved / f"{name}.kicad_sch",
        pcb_path=resolved / f"{name}.kicad_pcb",
        netmap_path=resolved / "netmap.json",
    )


def _canonical_hash(path: Path) -> str:
    return hashlib.sha256(UUID_RE.sub(b"UUID", path.read_bytes())).hexdigest()[:12]


def _property(node: list, name: str) -> str | None:
    for child in sch_io.find_children(node, "property"):
        if len(child) >= 3 and child[1] == name and isinstance(child[2], str):
            return child[2]
    return None


def _schematic_refs(path: Path) -> list[str]:
    tree = sch_io.parse_file(path)
    refs = {
        ref
        for node in sch_io.find_children(tree, "symbol")
        if (ref := _property(node, "Reference")) and not ref.startswith("#")
    }
    return sorted(refs)


def _pcb_connectivity(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    tree = sch_io.parse_file(path)
    refs: set[str] = set()
    nets: dict[str, set[str]] = {}
    for footprint in sch_io.find_children(tree, "footprint"):
        ref = _property(footprint, "Reference")
        if not ref:
            continue
        refs.add(ref)
        for pad in sch_io.find_children(footprint, "pad"):
            if len(pad) < 2:
                continue
            net_node = sch_io.find_child(pad, "net")
            if not net_node:
                continue
            net_name = next(
                (value for value in reversed(net_node[1:]) if isinstance(value, str)),
                "",
            )
            if net_name:
                nets.setdefault(net_name.lstrip("/"), set()).add(f"{ref}.{pad[1]}")
    return sorted(refs), {
        name: sorted(assignments) for name, assignments in sorted(nets.items())
    }


def capture_board(project: BoardProject) -> dict[str, object]:
    netmap_document = json.loads(project.netmap_path.read_text(encoding="utf-8"))
    pcb_refs, pcb_nets = _pcb_connectivity(project.pcb_path)
    return {
        "schematic_hash": _canonical_hash(project.schematic_path),
        "pcb_hash": _canonical_hash(project.pcb_path),
        "schematic_refs": _schematic_refs(project.schematic_path),
        "pcb_refs": pcb_refs,
        "netmap": netmap_document["nets"],
        "pcb_nets": pcb_nets,
    }
