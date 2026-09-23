"""Render one-sheet functional schematic intents into transactional drafts."""

from __future__ import annotations

import copy
import os
import re
import textwrap
import uuid
from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pcb_copilot.schematic.hierarchy import HierarchyDraft

from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.templates.blank import write_blank_schematic
from kicad_claude.utils.geometry import mcp_to_kicad_xy
from kicad_claude.utils.kicad_paths import find_symbol_lib_dirs

from pcb_copilot.drafts import publish_draft
from pcb_copilot.models import DraftRecord, Project
from pcb_copilot.schematic.fields import place_component_fields, text_field_envelope
from pcb_copilot.schematic.models import SchematicIntent, validate_component_pins
from pcb_copilot.schematic.power import power_stub_length
from pcb_copilot.schematic.wiring import (
    PinRef,
    VisualObstacle,
    WireCorridor,
    WireSegment,
    connect_local,
)

from pcb_copilot.schematic import geometry as _helpers
LabelPlacer = _helpers.LabelPlacer
SymbolPlacer = _helpers.SymbolPlacer
set_title_block = _helpers.set_title_block


class _WireEditor:
    def __init__(self, tree):
        self.tree = tree
        self.segments: list[WireSegment] = []
        self.obstacles: list[VisualObstacle] = []
        self.anchors: dict[PinRef, tuple[float, float]] = {}

    def pin_position(self, pin: PinRef) -> tuple[float, float]:
        if pin in self.anchors:
            return self.anchors[pin]
        return ed.get_pin_position(self.tree, pin.ref, pin.pin)

    def add_segment(self, segment: WireSegment) -> None:
        ed.add_wire(
            self.tree,
            segment.start[0],
            segment.start[1],
            segment.end[0],
            segment.end[1],
        )
        self.segments.append(segment)


class _LabelEditor:
    """Reuse the existing clearance/stub logic for hierarchical labels."""

    hierarchical = False

    def __getattr__(self, name):
        return getattr(ed, name)

    def add_label(self, tree, net, x, y, orientation):
        if self.hierarchical:
            node = ed.add_hierarchical_label(
                tree, net_name=net, x_mm=x, y_mm=y,
                shape='bidirectional', orientation=orientation,
            )
        else:
            node = ed.add_label(tree, net, x, y, orientation)
        if orientation == 'left':
            # KiCad normalizes horizontal text upright: 180 degrees alone
            # still grows right with the adapter's default left justification.
            # Keep the electrical anchor and glyph orientation, align text away
            # from the pin, and preserve local labels' vertical justification.
            effects = sch_io.find_child(node, 'effects')
            justify = sch_io.find_child(effects, 'justify')
            justify[1] = sch_io.sym('right')
        return node


@dataclass(frozen=True)
class _RenderedSheet:
    pins_by_net: dict[str, tuple[PinRef, ...]]
    origins: dict[str, tuple[float, float]]


def _symbol_definition(project: Project, qualified: str):
    library, name = qualified.split(":", 1)
    if not library or any(value in library for value in ('/', '\\', '..')):
        raise ValueError('invalid symbol library name')
    library_path = None
    table_path = project.root / 'sym-lib-table'
    if table_path.is_file():
        table = sch_io.parse_file(table_path)
        entries = [entry for entry in sch_io.find_children(table, 'lib')
                   if sch_io.find_child(entry, 'name')[1] == library]
        if len(entries) > 1:
            raise ValueError(f'duplicate symbol library registration: {library}')
        if entries:
            uri = str(sch_io.find_child(entries[0], 'uri')[1])
            uri = uri.replace('${KIPRJMOD}', str(project.root))
            for variable in re.findall(r'\$\{([^}]+)\}', uri):
                replacement = os.environ.get(variable)
                if replacement is None and re.fullmatch(r'KICAD\d+_SYMBOL_DIR', variable):
                    replacement = str(next((p for p in find_symbol_lib_dirs()
                                            if (p / f'{library}.kicad_sym').is_file()), ''))
                if not replacement:
                    raise ValueError(f'unresolved symbol library variable: {variable}')
                uri = uri.replace('${' + variable + '}', replacement)
            library_path = Path(uri)
            if not library_path.is_absolute():
                library_path = project.root / library_path
    if library_path is None:
        library_path = next((p / f'{library}.kicad_sym' for p in find_symbol_lib_dirs()
                             if (p / f'{library}.kicad_sym').is_file()), None)
    if library_path is None or not library_path.is_file():
        raise ValueError(f'symbol library is unavailable: {library}')
    return library, name, ed.fetch_symbol_def(library_path, name)


def _render_sheet_tree(
    project: Project,
    intent: SchematicIntent,
    sheet_id: str,
    tree: list,
    *,
    instance_path: str | None = None,
    child_sheet: bool = False,
    render_date: str = '',
) -> _RenderedSheet:
    sheet = next(item for item in intent.sheets if item.id == sheet_id)
    set_title_block(
        tree,
        title=intent.title if not child_sheet else f"{intent.title} — {sheet.title}",
        rev=intent.revision,
        paper=sheet.page,
        date=render_date,
    )
    symbols = SymbolPlacer(ed, tree)
    origins: dict[str, tuple[float, float]] = {}
    blocks = sorted(
        (item for item in intent.blocks if item.sheet == sheet_id),
        key=lambda item: item.flow_order,
    )
    page_width, page_height = symbols._page_size()
    lane_width = (page_width - 40.0) / max(len(blocks), 1)
    corridor_by_block = {}
    passive_groups = []
    definitions = {}

    def place_symbol(
        component,
        x: float,
        y: float,
        ref: str | None = None,
        value: str | None = None,
    ):
        if component.symbol not in definitions:
            definitions[component.symbol] = _symbol_definition(project, component.symbol)
        library, _name, cached_definition = definitions[component.symbol]
        definition = copy.deepcopy(cached_definition)
        reference = ref or component.ref
        instance = ed.add_symbol(
            tree,
            qualified_lib_id=component.symbol,
            reference=reference,
            value=value or component.value,
            x_mm=x,
            y_mm=y,
            rotation=0,
            sym_def_node=definition,
            project_name=project.manifest.name,
            instance_path=instance_path,
            footprint=component.footprint,
            description=(
                f"Intent block {component.block}; evidence "
                f"{component.pin_map_evidence_id}"
            ),
        )
        properties = {str(p[1]): str(p[2]) for p in sch_io.find_children(definition, 'property')
                      if str(p[1]) in {'LCSC Part', 'Manufacturer', 'Manufacturer Part', 'Datasheet'}}
        if component.lcsc:
            inherited = properties.get('LCSC Part')
            if inherited and inherited != component.lcsc:
                raise ValueError(f'{component.ref}: intent LCSC identity differs from its symbol library')
            properties['LCSC Part'] = component.lcsc
        for key, val in properties.items():
            existing = next((p for p in sch_io.find_children(instance, 'property') if p[1] == key), None)
            if existing is not None:
                existing[2] = val
            else:
                prop = copy.deepcopy(next(p for p in sch_io.find_children(instance, 'property')
                                          if p[1] == 'Description'))
                prop[1:3] = [key, val]
                instance.append(prop)
        symbols.register(reference)
        origins[reference] = symbols._origin(reference)
        return library

    for block_index, block in enumerate(blocks):
        left = 20.0 + block_index * lane_width
        right = left + lane_width - 8.0
        heading = '\n'.join(textwrap.wrap(block.title, width=max(12, int(lane_width - 8))))
        tree.append([sch_io.sym('text'), heading,
                     [sch_io.sym('at'), *mcp_to_kicad_xy(left + lane_width / 2, page_height - 18, page_height), 0],
                     [sch_io.sym('effects'), [sch_io.sym('font'), [sch_io.sym('size'), 1.5, 1.5]]],
                     [sch_io.sym('uuid'), str(uuid.uuid4())]])
        corridor_by_block[block.id] = WireCorridor(left - 12, 65, right + 12, page_height - 20)
        rows = []
        for component in [
            item for item in intent.components if item.block == block.id
        ]:
            # Adjacent same-family passives form a compact bank, making local
            # rail connections visible instead of a column of isolated labels.
            if (rows and component.symbol in {'Device:C', 'Device:R'}
                    and rows[-1][0].symbol == component.symbol and len(rows[-1]) < 2):
                rows[-1].append(component)
            else:
                rows.append([component])
        row_top = page_height - 38.0
        for group in rows:
            if len(group) > 1:
                passive_groups.append(group)
            for column, component in enumerate(group):
                x = left + lane_width / 2 + (column - (len(group) - 1) / 2) * 25.4
                place_symbol(component, x, row_top - 8.0)
                validate_component_pins(component, {
                    pin['number'] for pin in ed.list_pins_for_symbol(tree, component.ref)
                })
            boxes = [symbols.bbox(c.ref) for c in group]
            shift = row_top - max(box[3] for box in boxes)
            for component in group:
                x, y = origins[component.ref]
                ed.move_symbol(tree, component.ref, x, y + shift, 0)
                symbols.register(component.ref)
                origins[component.ref] = symbols._origin(component.ref)
            row_bottom = min(symbols.bbox(c.ref)[1] for c in group)
            if row_bottom < 65:
                raise ValueError(f'{block.id}: block exceeds usable page height; split the sheet')
            row_top = row_bottom - 18.0

    label_editor = _LabelEditor()
    labels = LabelPlacer(label_editor, tree, symbols=symbols)
    for component in intent.components:
        if component.ref in origins and component.ref.startswith('#'):
            labels.hide_reference(component.ref)
            labels.hide_property(component.ref, 'Value')
        elif component.ref in origins:
            place_component_fields(ed, tree, symbols, labels, component.ref)
    power_component = next((
        item
        for item in intent.components
        if any(block.id == item.block for block in blocks)
    ), None)

    def place_power(lib_name, sym_name, ref, value, x, y, rot=0, fp="", desc=""):
        assert power_component is not None
        proxy = power_component.model_copy(
            update={
                "ref": ref,
                "value": value,
                "symbol": f"{lib_name}:{sym_name}",
                "footprint": fp or "~",
            }
        )
        place_symbol(proxy, x, y, ref=ref, value=value)

    labels.place_symbol = place_power

    pins_by_block_net: defaultdict[tuple[str, str], list[PinRef]] = defaultdict(list)
    pins_by_net: defaultdict[str, list[PinRef]] = defaultdict(list)
    for component in intent.components:
        if component.block not in {block.id for block in blocks}:
            continue
        origin = origins[component.ref]
        for pin, connection in component.pins.items():
            pin_ref = PinRef(component.ref, pin)
            pins_by_net[connection.net].append(pin_ref)
            if connection.style == "power":
                labels.auto(component.ref, pin, connection.net, *origin,
                            stub_mm=power_stub_length(ed, tree, component.ref, pin, origin))
            else:
                pins_by_block_net[(component.block, connection.net)].append(pin_ref)
                if connection.style in {"label", "hierarchical"}:
                    label_editor.hierarchical = child_sheet and connection.style == 'hierarchical'
                    labels.place(component.ref, pin, connection.net, *origin)
                    label_editor.hierarchical = False
        for no_connect in component.no_connects:
            x, y = ed.get_pin_position(tree, component.ref, no_connect.pin)
            ed.add_no_connect(tree, x, y)

    for (_block_id, net), pins in sorted(pins_by_block_net.items()):
        declared = [c.pins[p.pin].style for p in pins for c in intent.components if c.ref == p.ref]
        if all(style == 'wire' for style in declared):
            pin = pins[0]
            labels.place(pin.ref, pin.pin, net, *origins[pin.ref])

    # Local wires leave each real pin along its safe outward stub first.
    # Routing directly from pin to pin could run through the symbol body.
    stubbed = {(ref, pin) for _a, _b, ref, pin, _net in labels._segments}
    for (_block_id, net), pins in pins_by_block_net.items():
        for pin in pins:
            if (pin.ref, pin.pin) not in stubbed:
                _orientation, segment = labels._choose_stub(
                    pin.ref, pin.pin, net, *origins[pin.ref], None)
                labels._commit_stub(segment, pin.ref, pin.pin, net)

    wire_editor = _WireEditor(tree)
    wire_editor.anchors = {PinRef(ref, pin): b
                          for _a, b, ref, pin, _net in labels._segments}
    wire_editor.segments.extend(
        WireSegment(a, b, net) for a, b, _ref, _pin, net in labels._segments
    )
    wire_editor.obstacles.extend(
        envelope
        for ref in sorted(labels._used_pwr_refs)
        if (envelope := text_field_envelope(ed, tree, ref, 'Value')) is not None
    )
    for component in intent.components:
        if component.ref not in origins:
            continue
        for pin in ed.list_pins_for_symbol(tree, component.ref):
            point = tuple(pin['position_mm'])
            connection = component.pins.get(pin['number'])
            net = connection.net if connection else f'NC:{component.ref}.{pin["number"]}'
            wire_editor.segments.append(WireSegment(point, point, net))
        if not component.ref.startswith('#'):
            box = symbols.bbox(component.ref)
            if box:
                x0, y0, x1, y1 = box
                corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
                wire_editor.segments.extend(WireSegment(a, b, f'body:{component.ref}')
                                            for a, b in pairwise(corners))
    for (block_id, net), pins in sorted(pins_by_block_net.items()):
        if len(pins) < 2:
            continue
        for target in pins[1:]:
            connect_local(
                wire_editor,
                pins[0],
                target,
                corridor_by_block[block_id],
                net=net,
            )
    for group in passive_groups:
        rails: defaultdict[str, list[PinRef]] = defaultdict(list)
        for component in group:
            for pin, connection in component.pins.items():
                if connection.style == 'power':
                    rails[connection.net].append(PinRef(component.ref, pin))
        for net, pins in rails.items():
            for target in pins[1:]:
                connect_local(wire_editor, pins[0], target,
                              corridor_by_block[group[0].block], net=net)
                # Each bank pin branches into its passive, power stub, and rail.
                for pin in (pins[0], target):
                    x, y = wire_editor.pin_position(pin)
                    tree.append([sch_io.sym('junction'),
                                 [sch_io.sym('at'), *mcp_to_kicad_xy(x, y, page_height)],
                                 [sch_io.sym('diameter'), 0], [sch_io.sym('color'), 0, 0, 0, 0],
                                 [sch_io.sym('uuid'), str(uuid.uuid4())]])
    return _RenderedSheet(
        pins_by_net={net: tuple(pins) for net, pins in pins_by_net.items()},
        origins=origins,
    )


def render_schematic_draft(
    project: Project,
    intent: SchematicIntent,
    draft: DraftRecord,
) -> Path | HierarchyDraft:
    if len(intent.sheets) > 1:
        from pcb_copilot.schematic.hierarchy import render_hierarchy

        return render_hierarchy(project, intent, draft)

    def writer(root: Path) -> None:
        schematic = root / project.schematic_path.name
        schematic.unlink(missing_ok=True)
        write_blank_schematic(schematic)
        tree = sch_io.parse_file(schematic)
        _render_sheet_tree(project, intent, intent.sheets[0].id, tree,
                           render_date=draft.created_utc.date().isoformat())
        sch_io.write_file(schematic, tree)

    published = publish_draft(draft, writer)
    return published / project.schematic_path.name
