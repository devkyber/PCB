"""Exact CAD extraction and review-oriented PDF rendering."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

from pcb_copilot.evidence.facts import EvidenceFact


def parse_eagle_schematic(path: str | Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    parts = {}
    for part in root.iter("part"):
        parts[part.get("name")] = {
            "value": part.get("value"),
            "deviceset": part.get("deviceset"),
            "device": part.get("device"),
            "library": part.get("library"),
        }
    nets = {}
    for net in root.iter("net"):
        pins = [f"{pin.get('part')}.{pin.get('pin')}" for pin in net.iter("pinref")]
        if pins:
            nets[net.get("name")] = pins
    return {"parts": parts, "nets": nets}


def find_pins_for_part(parsed: dict, part_name: str) -> dict[str, list[str]]:
    result = {}
    for net_name, pins in parsed["nets"].items():
        matches = [
            pin.split(".", 1)[1]
            for pin in pins
            if pin.startswith(f"{part_name}.")
        ]
        if matches:
            result[net_name] = matches
    return result


def _normal(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def _resolve_part(parsed: dict, requested: str, source: Path) -> str:
    wanted = _normal(requested)
    for reference, info in parsed["parts"].items():
        if wanted in {
            _normal(reference),
            _normal(info.get("value")),
            _normal(info.get("deviceset")),
        }:
            return reference

    # Some reference designs deliberately reuse a pin-compatible predecessor
    # symbol. The Adafruit BMP390 source, for example, labels IC1 as BMP388.
    family_match = re.match(r"[a-z]+", wanted)
    if wanted in _normal(source.stem) and family_match:
        family = family_match.group(0)
        candidates = [
            reference
            for reference, info in parsed["parts"].items()
            if _normal(info.get("value")).startswith(family)
            or _normal(info.get("deviceset")).startswith(family)
        ]
        if len(candidates) == 1:
            return candidates[0]
    raise ValueError(f"part {requested!r} is not uniquely identifiable in {source}")


def extract_eagle_connections(path: Path, part: str) -> tuple[EvidenceFact, ...]:
    source = path.resolve()
    parsed = parse_eagle_schematic(source)
    reference = _resolve_part(parsed, part, source)
    evidence_id = f"sha256:{hashlib.sha256(source.read_bytes()).hexdigest()}"
    facts = []

    for component, info in sorted(parsed["parts"].items()):
        value = info.get("value")
        if value:
            facts.append(
                EvidenceFact(
                    subject=component,
                    predicate="component_value",
                    value=value,
                    unit=None,
                    evidence_id=evidence_id,
                    pages=(1,),
                    confidence="exact",
                )
            )

    for net_name, pins in sorted(find_pins_for_part(parsed, reference).items()):
        for pin in sorted(pins):
            facts.append(
                EvidenceFact(
                    subject=f"{reference}.{pin}",
                    predicate="connected_net",
                    value=net_name,
                    unit=None,
                    evidence_id=evidence_id,
                    pages=(1,),
                    confidence="exact",
                )
            )
    return tuple(facts)


def render_pdf_pages(
    path: Path,
    pages: Sequence[int],
    output_dir: Path,
    zoom: float = 3.0,
) -> tuple[Path, ...]:
    import fitz

    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with fitz.open(path) as document:
        matrix = fitz.Matrix(zoom, zoom)
        for page_number in pages:
            if page_number < 1 or page_number > document.page_count:
                raise ValueError(
                    f"PDF page {page_number} outside 1..{document.page_count}"
                )
            pixmap = document[page_number - 1].get_pixmap(matrix=matrix)
            destination = output_dir / f"page_{page_number}.png"
            pixmap.save(destination)
            written.append(destination)
    return tuple(written)
