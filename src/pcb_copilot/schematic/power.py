"""Power spacing hints and serialized preview-clearance diagnostics."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from itertools import combinations, pairwise
from pathlib import Path

from kicad_claude.adapters import sch_editor, sch_io
from kicad_claude.utils.geometry import kicad_to_mcp_xy

from pcb_copilot.evidence.checks import Finding
from pcb_copilot.schematic.fields import (
    symbol_outline_points,
    text_field_envelope,
    visible_text_envelope,
)
from pcb_copilot.schematic.wiring import VisualObstacle

_SCRIPTS = Path(__file__).resolve().parents[3] / 'scripts'
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from schematic_layout_helpers import (
    DEFAULT_STUB_MM,
    GRID_MM,
    pin_exit_orientation_for_symbol,
)


def power_stub_length(
    ed, tree: list, ref: str, pin: str, origin: tuple[float, float]
) -> float | None:
    """Stagger horizontal-column stubs over four rows on the KiCad grid.

    This is a spacing hint, not a glyph collision solver. Pass the result to
    LabelPlacer.auto so its existing crossing checks still govern the wire.
    One/two-pin parts and vertical exits retain the normal power stub policy.
    Nonadjacent glyphs and nearby signal text/wires still need visual review.
    """
    positions = [tuple(item['position_mm']) for item in ed.list_pins_for_symbol(tree, ref)]
    if len(positions) <= 2:
        return None
    x, y = ed.get_pin_position(tree, ref, pin)
    direction = pin_exit_orientation_for_symbol(x, y, *origin, positions)
    if direction not in {'left', 'right'}:
        return None
    column = sorted({round(py, 3) for px, py in positions if abs(px - x) < 0.05})
    if len(column) < 2:
        return None
    rank = column.index(round(y, 3))
    # Alternating two lengths leaves pins two rows apart at the same x. On
    # compact ICs their stock power glyphs can touch even though the pins do
    # not. Four staggered lengths separate those glyphs without a long rail.
    stagger_steps = (0, 8, 4, 12)
    return round(DEFAULT_STUB_MM + stagger_steps[rank % 4] * GRID_MM, 3)


@dataclass(frozen=True)
class _PowerGlyph:
    ref: str
    net: str
    box: VisualObstacle
    pin: tuple[float, float]
    attachment: str | None

    @property
    def identity(self) -> str:
        suffix = f' attached {self.attachment}' if self.attachment else ''
        return f'{self.ref}/{self.net}{suffix}'


@dataclass(frozen=True)
class _VisibleText:
    owner: str
    text: str
    box: VisualObstacle
    power_ref: str | None = None

    @property
    def identity(self) -> str:
        return f'{self.owner} {self.text!r}'


def _overlaps(first: VisualObstacle, second: VisualObstacle) -> bool:
    return not (
        first.x_max < second.x_min
        or second.x_max < first.x_min
        or first.y_max < second.y_min
        or second.y_max < first.y_min
    )


def _box_text(box: VisualObstacle) -> str:
    return (f'({box.x_min:.3f},{box.y_min:.3f})-'
            f'({box.x_max:.3f},{box.y_max:.3f})')


def _intersection_text(first: VisualObstacle, second: VisualObstacle) -> str:
    return (
        f'({max(first.x_min, second.x_min):.3f},'
        f'{max(first.y_min, second.y_min):.3f})-'
        f'({min(first.x_max, second.x_max):.3f},'
        f'{min(first.y_max, second.y_max):.3f})'
    )


def _attachment_map(ed, tree: list) -> dict[tuple[float, float], str]:
    result: dict[tuple[float, float], str] = {}
    for symbol in ed.iter_instance_symbols(tree):
        ref = ed.get_symbol_property(symbol, 'Reference') or ''
        lib_id = ed.find_child(symbol, 'lib_id')
        if not ref or (lib_id is not None and str(lib_id[1]).startswith('power:')):
            continue
        for pin in ed.list_pins_for_symbol(tree, ref):
            point = tuple(round(float(value), 3) for value in pin['position_mm'])
            result[point] = f'{ref}.{pin["number"]}'
    return result


def _wire_attachments(ed, tree: list) -> dict[tuple[float, float], str]:
    page_height = ed.page_height_mm(tree)
    component_pins = _attachment_map(ed, tree)
    result = {}
    for wire in ed.find_children(tree, 'wire'):
        points = [
            tuple(round(value, 3) for value in kicad_to_mcp_xy(
                float(point[1]), float(point[2]), page_height
            ))
            for point in ed.find_child(wire, 'pts')[1:]
        ]
        for point in points:
            for other in points:
                if other != point and other in component_pins:
                    result[point] = component_pins[other]
    return result


def _direct_wire_pairs(ed, tree: list) -> set[frozenset[tuple[float, float]]]:
    """Return exact serialized wire endpoint pairs, without net-wide inference."""
    page_height = ed.page_height_mm(tree)
    result = set()
    for wire in ed.find_children(tree, 'wire'):
        points = [
            tuple(round(value, 3) for value in kicad_to_mcp_xy(
                float(point[1]), float(point[2]), page_height
            ))
            for point in ed.find_child(wire, 'pts')[1:]
        ]
        result.update(frozenset((first, second)) for first, second in pairwise(points))
    return result


def _power_glyphs(ed, tree: list, sheet: str):
    page_height = ed.page_height_mm(tree)
    attachments = _wire_attachments(ed, tree)
    glyphs = []
    advisories = []
    for symbol in ed.iter_instance_symbols(tree):
        ref = ed.get_symbol_property(symbol, 'Reference') or ''
        lib_id = ed.find_child(symbol, 'lib_id')
        if lib_id is None or not str(lib_id[1]).startswith('power:'):
            continue
        at = ed.find_child(symbol, 'at')
        mirror = ed.find_child(symbol, 'mirror')
        rotation = float(at[3]) % 360 if at is not None and len(at) > 3 else 0.0
        if mirror is not None:
            axis = str(mirror[1]) if len(mirror) > 1 else 'unknown'
            advisories.append(Finding(
                'power-clearance-unchecked',
                f'{sheet}: {ref or lib_id[1]} uses unsupported mirror {axis}; '
                'clearance was not checked',
                ref or None,
                severity='review',
            ))
            continue
        if at is None or abs(rotation) > 1e-6:
            advisories.append(Finding(
                'power-clearance-unchecked',
                f'{sheet}: {ref or lib_id[1]} has unsupported power-glyph '
                f'position/rotation {rotation:g}; clearance was not checked',
                ref or None,
                severity='review',
            ))
            continue
        definition = ed.find_lib_symbol_def(tree, lib_id[1])
        unsupported = []
        if definition is not None:
            for unit in ed.find_children(definition, 'symbol'):
                unsupported.extend(
                    str(graphic[0]) for graphic in unit[2:]
                    if isinstance(graphic, list) and graphic
                    and str(graphic[0]) not in {'pin', 'rectangle', 'polyline', 'circle'}
                )
        points = list(symbol_outline_points(ed, definition)) if definition is not None else []
        if not points or unsupported:
            detail = ', '.join(sorted(set(unsupported))) or 'no supported outline'
            advisories.append(Finding(
                'power-clearance-unchecked',
                f'{sheet}: {ref or lib_id[1]} uses unsupported power-glyph '
                f'geometry ({detail}); clearance was not checked',
                ref or None,
                severity='review',
            ))
            continue
        x, y = kicad_to_mcp_xy(float(at[1]), float(at[2]), page_height)
        box = VisualObstacle(
            round(x + min(px for px, _py in points), 3),
            round(y + min(py for _px, py in points), 3),
            round(x + max(px for px, _py in points), 3),
            round(y + max(py for _px, py in points), 3),
            'power-glyph', ref,
        )
        pin = tuple(round(value, 3) for value in ed.get_pin_position(tree, ref, '1'))
        glyphs.append(_PowerGlyph(
            ref,
            ed.get_symbol_property(symbol, 'Value') or str(lib_id[1]).split(':')[-1],
            box,
            pin,
            attachments.get(pin),
        ))
    return glyphs, advisories


def _visible_texts(ed, tree: list, glyphs: list[_PowerGlyph], sheet: str):
    page_height = ed.page_height_mm(tree)
    texts = []
    advisories = []
    for node in tree:
        if not (isinstance(node, list) and node
                and str(node[0]) in {'label', 'hierarchical_label'}):
            continue
        kind = str(node[0]).replace('_', ' ')
        at = ed.find_child(node, 'at')
        effects = ed.find_child(node, 'effects')
        if effects is not None and ed.find_child(effects, 'hide') is not None:
            continue
        font = ed.find_child(effects, 'font') if effects is not None else None
        size = ed.find_child(font, 'size') if font is not None else None
        rotation = float(at[3]) % 360 if at is not None and len(at) > 3 else 0.0
        if at is None or size is None or rotation not in {0.0, 180.0}:
            advisories.append(Finding(
                'power-clearance-unchecked',
                f'{sheet}: {kind} {node[1]!r} has unsupported text geometry/'
                f'rotation {rotation:g}; power clearance was not checked',
                severity='review',
            ))
            continue
        x, y = kicad_to_mcp_xy(float(at[1]), float(at[2]), page_height)
        justify = ed.find_child(effects, 'justify')
        texts.append(_VisibleText(
            kind,
            str(node[1]),
            visible_text_envelope(
                str(node[1]), x, y, float(size[1]), float(size[2]),
                justification=justify[1:] if justify is not None else (),
                kind=kind,
                owner=str(node[1]),
            ),
        ))
    for glyph in glyphs:
        try:
            box = text_field_envelope(ed, tree, glyph.ref, 'Value')
        except (KeyError, ValueError) as exc:
            advisories.append(Finding(
                'power-clearance-unchecked',
                f'{sheet}: {glyph.ref} Value text is unsupported ({exc}); '
                'power clearance was not checked',
                glyph.ref,
                severity='review',
            ))
            continue
        if box is not None:
            texts.append(_VisibleText(
                f'power Value {glyph.ref}', glyph.net, box, glyph.ref
            ))
    return texts, advisories


def power_clearance_findings(tree: list, sheet: str) -> tuple[Finding, ...]:
    """Report conservative power glyph clashes in one serialized sheet tree.

    Scope is deliberately limited to power glyph-to-glyph and glyph-to-visible
    power Value/local/hierarchical text. Findings are advisory and never mutate
    placement or electrical data.
    """
    glyphs, advisories = _power_glyphs(sch_editor, tree, sheet)
    texts, text_advisories = _visible_texts(sch_editor, tree, glyphs, sheet)
    direct_connections = _direct_wire_pairs(sch_editor, tree)
    findings = [*advisories, *text_advisories]

    for first, second in combinations(sorted(glyphs, key=lambda item: item.ref), 2):
        exact_attachment = (
            first.pin == second.pin
            or frozenset((first.pin, second.pin)) in direct_connections
        )
        intentional_flag_attachment = (
            exact_attachment
            and ((first.net == 'PWR_FLAG') != (second.net == 'PWR_FLAG'))
        )
        if intentional_flag_attachment or not _overlaps(first.box, second.box):
            continue
        findings.append(Finding(
            'power-glyph-collision',
            f'{sheet}: power glyph {first.identity} {_box_text(first.box)} '
            f'conflicts with power glyph {second.identity} {_box_text(second.box)} '
            f'at {_intersection_text(first.box, second.box)}',
            first.ref,
            severity='review',
        ))

    for glyph in sorted(glyphs, key=lambda item: item.ref):
        for text in sorted(texts, key=lambda item: (item.owner, item.text, item.power_ref or '')):
            if text.power_ref == glyph.ref or not _overlaps(glyph.box, text.box):
                continue
            findings.append(Finding(
                'power-text-collision',
                f'{sheet}: power glyph {glyph.identity} {_box_text(glyph.box)} '
                f'conflicts with {text.identity} {_box_text(text.box)} '
                f'at {_intersection_text(glyph.box, text.box)}',
                glyph.ref,
                severity='review',
            ))

    unique = {(finding.code, finding.message, finding.reference or ''): finding
              for finding in findings}
    return tuple(unique[key] for key in sorted(unique))


def power_clearance_findings_for_file(path: Path) -> tuple[Finding, ...]:
    """Parse one emitted schematic and return read-only clearance findings."""
    return power_clearance_findings(sch_io.parse_file(path), path.name)
