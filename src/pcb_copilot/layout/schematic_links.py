"""Preserve KiCad forward-annotation identity independently of net names.

Only missing links may be inferred, and only on a caller-owned candidate after
reference, part identity and complete pin-net parity have been checked. A stale
nonempty link is a conflict, never permission to re-link by reference silently.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from kicad_claude.adapters import sch_io
from sexpdata import loads


def component_paths(component) -> list[str]:
    """Use KiCad's exported sheet path plus each unit UUID, without a root prefix.

    Native netlists omit the root-sheet UUID from forward-annotation paths.
    Multi-unit components can legitimately match any of their exported units.
    """
    sheet = component.find('sheetpath')
    raw_sheet = sheet.get('tstamps') if sheet is not None else None
    stamps = (component.findtext('tstamps') or component.findtext('tstamp') or '').split()
    if raw_sheet is None or not raw_sheet.startswith('/') or not stamps:
        raise ValueError(f"{component.get('ref')}: native netlist has no schematic UUID path")
    prefix = [part for part in raw_sheet.split('/') if part]
    try:
        prefix = [str(UUID(part)) for part in prefix]
        stamps = [str(UUID(part)) for part in stamps]
    except ValueError as exc:
        raise ValueError(f"{component.get('ref')}: malformed schematic UUID path") from exc
    return list(dict.fromkeys('/' + '/'.join([*prefix, stamp]) for stamp in stamps))


def compare_schematic_links(parts: dict, footprints: dict) -> list[str]:
    differences = []
    used = {}
    for ref, footprint in sorted(footprints.items()):
        path = footprint.get('schematic_path', '')
        if path:
            if path in used:
                differences.append(f'{ref}: schematic link is also used by {used[path]}')
            used[path] = ref
        if ref not in parts:
            continue
        expected = parts[ref].get('schematic_paths', [])
        if not expected:
            differences.append(f'{ref}: schematic UUID identity is unavailable')
        elif not path:
            differences.append(f'{ref}: missing schematic link; F8 would add a duplicate footprint')
        elif path not in expected:
            differences.append(f'{ref}: schematic link differs from the current symbol; re-link explicitly in KiCad')
    return differences


def _child_spans(text):
    """Locate direct list children without interpreting escaped text as syntax."""
    depth = 0
    quoted = escaped = False
    start = None
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == '(':
            depth += 1
            if depth == 2:
                start = index
        elif char == ')':
            if depth == 2:
                yield start, index + 1
            depth -= 1


def bind_missing_links(pcb: Path, parts: dict, footprints: dict) -> list[str]:
    """Bind verified candidate parts, preserving all non-path CAD objects.

    The caller must establish full physical/pin-net parity first. This function
    also refuses conflicting links and verifies its inventory against the file.
    Mechanical footprints without symbols are left alone.
    """
    conflicts = [message for message in compare_schematic_links(parts, footprints)
                 if ': missing schematic link;' not in message]
    for ref, part in parts.items():
        footprint = footprints.get(ref)
        if footprint is None:
            conflicts.append(f'{ref}: schematic part missing from candidate')
        elif (part['footprint'] != footprint['lib_id']
              or part['value'] != footprint['value']
              or (part.get('lcsc') and part['lcsc'] != footprint.get('lcsc'))):
            conflicts.append(f'{ref}: part identity differs; cannot infer a schematic link')
    if conflicts:
        raise ValueError('\n'.join(conflicts))
    updates = {ref: parts[ref]['schematic_paths'][0] for ref in sorted(parts)
               if ref in footprints and not footprints[ref].get('schematic_path')}
    if not updates:
        return []
    # Preserve every other byte, including native escapes and full precision.
    # Re-serializing a whole board just to add IDs can change unrelated CAD.
    text = pcb.read_bytes().decode('utf-8')
    newline = '\r\n' if '\r\n' in text else '\n'
    edits = []
    found = set()
    for start, end in _child_spans(text):
        block = text[start:end]
        if block[1:].lstrip().split(None, 1)[0] != 'footprint':
            continue
        footprint = loads(block)
        properties = {str(item[1]): str(item[2])
                      for item in sch_io.find_children(footprint, 'property')}
        ref = properties.get('Reference')
        if ref is None:
            ref = next((str(item[2]) for item in sch_io.find_children(footprint, 'fp_text')
                        if str(item[1]) == 'reference'), None)
        if ref not in updates:
            continue
        path = sch_io.find_child(footprint, 'path')
        if ref in found or (path and len(path) > 1 and path[1]):
            raise ValueError(f'{ref}: candidate changed while binding schematic links')
        found.add(ref)
        if path is not None:
            spans = [(a, b) for a, b in _child_spans(block)
                     if str(loads(block[a:b])[0]) == 'path']
            if len(spans) != 1:
                raise ValueError(f'{ref}: ambiguous path metadata in candidate')
            a, b = spans[0]
            edits.append((start + a, start + b, f'(path "{updates[ref]}")'))
        else:
            edits.append((end - 1, end - 1, f'{newline}\t\t(path "{updates[ref]}"){newline}\t'))
    if found != set(updates):
        raise ValueError('candidate footprint inventory changed while binding schematic links')
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    pcb.write_bytes(text.encode('utf-8'))
    return sorted(found)
