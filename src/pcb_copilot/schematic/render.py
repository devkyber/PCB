"""Render one-sheet functional schematic intents into transactional drafts."""

from __future__ import annotations

import importlib
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pcb_copilot.schematic.hierarchy import HierarchyDraft

from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.templates.blank import write_blank_schematic
from kicad_claude.utils.kicad_paths import find_symbol_lib_dirs

from pcb_copilot.drafts import publish_draft
from pcb_copilot.models import DraftRecord, Project
from pcb_copilot.schematic.models import SchematicIntent
from pcb_copilot.schematic.wiring import (
    PinRef,
    WireCorridor,
    WireSegment,
    connect_local,
)

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs"
if str(DOCS) not in sys.path:
    sys.path.insert(0, str(DOCS))

_helpers = importlib.import_module("schematic_layout_helpers")
LabelPlacer = _helpers.LabelPlacer
SymbolPlacer = _helpers.SymbolPlacer
set_title_block = _helpers.set_title_block


class _WireEditor:
    def __init__(self, tree):
        self.tree = tree
        self.segments: list[WireSegment] = []

    def pin_position(self, pin: PinRef) -> tuple[float, float]:
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


@dataclass(frozen=True)
class _RenderedSheet:
    pins_by_net: dict[str, tuple[PinRef, ...]]
    origins: dict[str, tuple[float, float]]


def _symbol_definition(project: Project, qualified: str):
    library, name = qualified.split(":", 1)
    if library == "jlcpcb":
        library_path = project.root / "libs" / "jlcpcb.kicad_sym"
    else:
        library_path = find_symbol_lib_dirs()[0] / f"{library}.kicad_sym"
    return library, name, ed.fetch_symbol_def(library_path, name)


def _render_sheet_tree(
    project: Project,
    intent: SchematicIntent,
    sheet_id: str,
    tree: list,
    *,
    instance_path: str | None = None,
    child_sheet: bool = False,
) -> _RenderedSheet:
    sheet = next(item for item in intent.sheets if item.id == sheet_id)
    set_title_block(
        tree,
        title=intent.title if not child_sheet else f"{intent.title} — {sheet.title}",
        rev=intent.revision,
        paper=sheet.page,
    )
    symbols = SymbolPlacer(ed, tree)
    origins: dict[str, tuple[float, float]] = {}
    blocks = sorted(
        (item for item in intent.blocks if item.sheet == sheet_id),
        key=lambda item: item.flow_order,
    )
    lane_width = 250.0 / max(len(blocks), 1)
    corridor_by_block = {}
    component_rows: defaultdict[str, int] = defaultdict(int)

    def place_symbol(
        component,
        x: float,
        y: float,
        ref: str | None = None,
        value: str | None = None,
    ):
        library, _name, definition = _symbol_definition(project, component.symbol)
        reference = ref or component.ref
        ed.add_symbol(
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
        origins[reference] = symbols.register(reference) or (x, y)
        return library

    for block_index, block in enumerate(blocks):
        left = 20.0 + block_index * lane_width
        right = left + lane_width - 8.0
        corridor_by_block[block.id] = WireCorridor(left - 12, 20, right + 12, 190)
        for component in [
            item for item in intent.components if item.block == block.id
        ]:
            row = component_rows[block.id]
            component_rows[block.id] += 1
            place_symbol(component, left + lane_width / 2, 45.0 + row * 28.0)

    labels = LabelPlacer(ed, tree, symbols=symbols)
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
                labels.auto(component.ref, pin, connection.net, *origin)
            else:
                pins_by_block_net[(component.block, connection.net)].append(pin_ref)
                if connection.style == "label":
                    labels.place(component.ref, pin, connection.net, *origin)
        for no_connect in component.no_connects:
            x, y = ed.get_pin_position(tree, component.ref, no_connect.pin)
            ed.add_no_connect(tree, x, y)

    wire_editor = _WireEditor(tree)
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
    if child_sheet:
        for net in sorted(
            name
            for name, pins in pins_by_net.items()
            if any(
                component.pins[pin.pin].style == "hierarchical"
                for pin in pins
                for component in intent.components
                if component.ref == pin.ref
            )
        ):
            for pin in pins_by_net[net]:
                x, y = ed.get_pin_position(tree, pin.ref, pin.pin)
                ed.add_hierarchical_label(
                    tree, net_name=net, x_mm=x, y_mm=y, shape="bidirectional",
                )
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
        _render_sheet_tree(project, intent, intent.sheets[0].id, tree)
        sch_io.write_file(schematic, tree)

    published = publish_draft(draft, writer)
    return published / project.schematic_path.name
