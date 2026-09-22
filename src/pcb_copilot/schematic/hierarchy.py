"""Render multi-sheet schematic intents through the tested hierarchy adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.templates.blank import write_blank_schematic

from pcb_copilot.drafts import publish_draft
from pcb_copilot.models import DraftRecord, Project
from pcb_copilot.schematic.models import SchematicIntent


@dataclass(frozen=True)
class HierarchyDraft:
    root_schematic: Path
    child_paths: tuple[Path, ...]


def _schematic_uuid(tree: list) -> str:
    node = sch_io.find_child(tree, "uuid")
    if not node or len(node) < 2 or not isinstance(node[1], str):
        raise ValueError("root schematic has no UUID")
    return node[1]


def render_hierarchy(
    project: Project,
    intent: SchematicIntent,
    draft: DraftRecord,
) -> HierarchyDraft:
    """Publish a root schematic and its child sheets as one transaction."""
    if len(intent.sheets) < 2:
        raise ValueError("hierarchy renderer requires at least two sheets")

    child_paths = tuple(Path(f"{sheet.id}.kicad_sch") for sheet in intent.sheets[1:])

    def writer(root: Path) -> None:
        from pcb_copilot.schematic.render import (
            _helpers,
            _LabelEditor,
            _render_sheet_tree,
            set_title_block,
        )

        root_path = root / project.schematic_path.name
        root_path.unlink(missing_ok=True)
        write_blank_schematic(root_path)
        root_tree = sch_io.parse_file(root_path)
        set_title_block(root_tree, title=intent.title, rev=intent.revision,
                        paper=intent.sheets[0].page, date=draft.created_utc.date().isoformat())
        root_uuid = _schematic_uuid(root_tree)
        page_h = ed.page_height_mm(root_tree)

        block_sheet = {block.id: block.sheet for block in intent.blocks}
        net_sheets: dict[str, set[str]] = {}
        for component in intent.components:
            for connection in component.pins.values():
                if connection.style == "hierarchical":
                    net_sheets.setdefault(connection.net, set()).add(
                        block_sheet[component.block]
                    )

        sheet_nodes: dict[str, list] = {}
        sheet_tops: dict[str, float] = {}
        top = _helpers.snap_mcp_y_to_kicad_grid(page_h - 20, page_h)
        pin_x = _helpers._snap_to_grid(220.0)
        for index, sheet in enumerate(intent.sheets[1:]):
            count = sum(sheet.id in sheets for sheets in net_sheets.values())
            height = max(25.4, (count + 1) * 5.08)
            bottom = top - height
            if bottom < 20 or intent.sheets[0].page == "A5":
                raise ValueError("hierarchy exceeds root page capacity; use a larger root page")
            sheet_tops[sheet.id] = top
            sheet_nodes[sheet.id] = ed.add_sheet_node(
                root_tree,
                sheet_name=sheet.title,
                sheet_filename=f"{sheet.id}.kicad_sch",
                x_mm=pin_x,
                y_mm=bottom,
                width_mm=50.8,
                height_mm=height,
                project_name=project.manifest.name,
            )
            top = bottom - 10.16

        for sheet, relative in zip(intent.sheets[1:], child_paths, strict=True):
            child_path = root / relative
            child_path.unlink(missing_ok=True)
            write_blank_schematic(child_path)
            child_tree = sch_io.parse_file(child_path)
            instance_path = f"/{root_uuid}/{ed.get_sheet_uuid(sheet_nodes[sheet.id])}"
            _render_sheet_tree(
                project,
                intent,
                sheet.id,
                child_tree,
                instance_path=instance_path,
                child_sheet=True,
                render_date=draft.created_utc.date().isoformat(),
            )
            sch_io.write_file(child_path, child_tree)

        _render_sheet_tree(
            project,
            intent,
            intent.sheets[0].id,
            root_tree,
            instance_path=f"/{root_uuid}",
            render_date=draft.created_utc.date().isoformat(),
        )
        for index, sheet in enumerate(intent.sheets[1:]):
            child_nets = sorted(
                net for net, sheets in net_sheets.items() if sheet.id in sheets
            )
            for pin_index, net in enumerate(child_nets):
                pin_y = sheet_tops[sheet.id] - (pin_index + 1) * 5.08
                ed.add_sheet_pin(
                    sheet_nodes[sheet.id],
                    pin_name=net,
                    shape="bidirectional",
                    x_mm=pin_x,
                    y_mm=pin_y,
                    page_h=page_h,
                    orientation="left",
                )
                # Sheet boundaries use named local nets. Separate short stubs
                # avoid overlapping vertical trunks shorting unrelated signals.
                stub = _helpers._snap_to_grid(max(15.24, len(net) * 1.1 + 5.08))
                ed.add_wire(root_tree, pin_x - stub, pin_y, pin_x, pin_y)
                ed.add_wire(root_tree, pin_x - stub, pin_y, pin_x - stub, pin_y + 2.54)
                _LabelEditor().add_label(root_tree, net, pin_x - stub, pin_y + 2.54, 'left')
        sch_io.write_file(root_path, root_tree)

    published = publish_draft(draft, writer)
    return HierarchyDraft(
        root_schematic=published / project.schematic_path.name,
        child_paths=child_paths,
    )
