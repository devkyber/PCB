"""Shared research-gate inventory with legacy KiCad property compatibility.

Classification deliberately preserves the established research policy: modules
and non-passive parts with at least eight pads need reference designs. This is
a research inventory, not the native authoritative electrical/parity inventory.
"""

from __future__ import annotations

import re

PASSIVE = ("R", "C", "L", "TP", "FID", "H", "LED", "D", "SW", "F", "JP")
MODULE_HINTS = (
    "teensy",
    "xbee",
    "arduino",
    "esp",
    "raspberry",
    "pico",
    "feather",
    "nucleo",
    "module",
    "socket",
)


def _blocks(text: str):
    i = 0
    while True:
        i = text.find('(footprint "', i)
        if i < 0:
            return
        depth, j = 0, i
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield text[i : j + 1]
        i = j


def _prop(block: str, name: str) -> str:
    """Read modern property or legacy fp_text reference/value spelling.

    TMS's XBee socket J9 uses fp_text. Ignoring that spelling hides a physical
    part from reference, design-basis and sourcing checks, not merely a field.
    """
    match = re.search(rf'\(property\s+"{re.escape(name)}"\s+"([^"]*)"', block)
    if match:
        return match.group(1)
    legacy = {"Reference": "reference", "Value": "value"}.get(name)
    if legacy:
        match = re.search(rf'\(fp_text\s+{legacy}\s+"([^"]*)"', block)
        if match:
            return match.group(1)
    return ""


def _lcsc(block: str) -> str:
    for key in ("LCSC", "LCSC Part #", "LCSC Part", "JLCPCB", "JLCPCB Part"):
        value = _prop(block, key)
        if value.strip():
            return value.strip()
    match = re.search(r'"(C\d{4,})"', block)
    return match.group(1) if match else ""


def inventory(pcb_text: str) -> list[tuple[str, str, int, str, bool]]:
    """Return (reference, value, pad count, LCSC number, key-part flag) rows."""
    out = []
    for block in _blocks(pcb_text):
        reference = _prop(block, "Reference")
        if not reference:
            continue
        value = _prop(block, "Value")
        pads = block.count('(pad "')
        base = (re.match(r"[A-Za-z]+", reference) or re.match(r".*", reference)).group(
            0
        )
        is_module = any(hint in value.lower() for hint in MODULE_HINTS)
        is_passive = base in PASSIVE and not is_module
        is_key = is_module or (not is_passive and pads >= 8)
        out.append((reference, value, pads, _lcsc(block), is_key))
    return out
