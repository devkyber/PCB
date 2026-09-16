"""Portable structural metrics for KiCad schematics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PAGE_CAPACITY = {
    "A5": 12,
    "A4": 25,
    "A3": 50,
    "A2": 100,
    "A1": 200,
    "A0": 400,
    "USLetter": 25,
    "USLegal": 32,
    "USLedger": 50,
}
DEFAULT_CAPACITY = 25


@dataclass(frozen=True)
class SchematicMetrics:
    component_count: int
    power_symbol_count: int
    junction_count: int
    sheet_count: int
    drawn_connection_ratio: float
    title_complete: bool
    paper: str
    page_capacity: int
    label_count: int
    has_title_block: bool
    title: str
    revision: str


def _instances(text: str) -> str:
    start = text.find("(lib_symbols")
    if start < 0:
        return text
    depth = 0
    in_string = False
    for index in range(start, len(text)):
        character = text[index]
        if character == '"' and (index == 0 or text[index - 1] != "\\"):
            in_string = not in_string
        elif not in_string:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return text[index + 1 :]
    return text[start:]


def _sexpr_block(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    depth = 0
    in_string = False
    for index in range(start, len(text)):
        character = text[index]
        if character == '"' and (index == 0 or text[index - 1] != "\\"):
            in_string = not in_string
        elif not in_string:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return text[start:]


def analyse_schematic(path: Path) -> SchematicMetrics:
    text = path.read_text(encoding="utf-8")
    instances = _instances(text)
    identifiers = re.findall(r'\(lib_id "([^"]+)"\)', instances)
    component_count = sum(not item.startswith("power:") for item in identifiers)
    power_count = sum(item.startswith("power:") for item in identifiers)
    junction_count = len(re.findall(r"\(junction\s", text))
    label_count = len(re.findall(r"\((?:global_)?label\s", text))
    hierarchy_count = len(re.findall(r"\(sheet\s*\n\s*\(at ", text))
    paper_match = re.search(r'\(paper "([^"]+)"', text)
    paper = paper_match.group(1) if paper_match else "A4"
    title_block = _sexpr_block(text, "(title_block")
    title_match = re.search(r'\(title "([^"]*)"', title_block)
    revision_match = re.search(r'\(rev "([^"]*)"', title_block)
    title = title_match.group(1) if title_match else ""
    revision = revision_match.group(1) if revision_match else ""
    ratio = (
        min(1.0, junction_count / max(component_count - 1, 1))
        if junction_count
        else 0.0
    )
    return SchematicMetrics(
        component_count=component_count,
        power_symbol_count=power_count,
        junction_count=junction_count,
        sheet_count=1 + hierarchy_count,
        drawn_connection_ratio=ratio,
        title_complete=bool(title_block and title.strip() and revision.strip()),
        paper=paper,
        page_capacity=PAGE_CAPACITY.get(paper, DEFAULT_CAPACITY),
        label_count=label_count,
        has_title_block=bool(title_block),
        title=title,
        revision=revision,
    )
