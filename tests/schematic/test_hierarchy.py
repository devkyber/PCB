import importlib.util
from pathlib import Path

import pytest
from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io

from pcb_copilot.drafts import DraftKind, create_draft
from pcb_copilot.project import load_project
from pcb_copilot.schematic.hierarchy import HierarchyDraft
from pcb_copilot.schematic.models import SchematicIntent
from pcb_copilot.schematic.render import render_schematic_draft


def _minimal_document(*, sheet_count: int = 2) -> dict:
    sheets = [{"id": "main", "title": "Main", "page": "A4"}]
    blocks = [{"id": "root", "title": "Root", "sheet": "main", "flow_order": 1}]
    if sheet_count == 2:
        sheets.append({"id": "sensor", "title": "Sensor", "page": "A4"})
        blocks.append(
            {"id": "child", "title": "Child", "sheet": "sensor", "flow_order": 1}
        )
    return {
        "schema_version": 1,
        "title": "Hierarchy validation",
        "revision": "T1",
        "sheets": sheets,
        "blocks": blocks,
        "components": [],
        "boundary_nets": ["DATA_READY"],
    }


def _component(ref: str, block: str, net: str = "DATA_READY") -> dict:
    return {
        "ref": ref,
        "value": ref,
        "symbol": "Connector_Generic:Conn_01x01",
        "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x01_P2.54mm_Vertical",
        "block": block,
        "evidence_part_number": f"FIXTURE-{ref}",
        "pin_map_evidence_id": "sha256:" + "a" * 64,
        "pins": {"1": {"net": net, "style": "hierarchical"}},
        "pin_inventory": ["1"],
    }


def _extract(schematic: Path) -> dict:
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "extract_netmap.py"
    spec = importlib.util.spec_from_file_location("extract_netmap", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.extract(schematic)


def test_hierarchical_net_survives_round_trip(hierarchical_draft):
    assert isinstance(hierarchical_draft, HierarchyDraft)
    assert hierarchical_draft.child_paths == (Path("sensor.kicad_sch"),)

    root = sch_io.parse_file(hierarchical_draft.root_schematic)
    root_labels = ed.find_children(root, 'label')
    assert root_labels
    for label in root_labels:
        effects = ed.find_child(label, 'effects')
        assert ed.find_child(effects, 'justify')[1] == sch_io.sym('right')
    sheet = ed.find_sheet_by_filename(root, "sensor.kicad_sch")
    assert sheet is not None
    pins = [node for node in sheet[1:] if sch_io.is_call(node, "pin")]
    assert [pin[1] for pin in pins] == ["DATA_READY"]

    child = sch_io.parse_file(
        hierarchical_draft.root_schematic.parent / hierarchical_draft.child_paths[0]
    )
    labels = [node for node in child[1:] if sch_io.is_call(node, "hierarchical_label")]
    assert [label[1] for label in labels] == ["DATA_READY"]

    symbol = ed.find_symbol_by_reference(child, "U1")
    instances = sch_io.find_child(symbol, "instances")
    project_node = sch_io.find_child(instances, "project")
    path_node = sch_io.find_child(project_node, "path")
    assert len(path_node[1].strip("/").split("/")) == 2

    extracted = _extract(hierarchical_draft.root_schematic)
    assert extracted["nets"]["J1"]["1"] == "DATA_READY"
    assert extracted["nets"]["U1"]["7"] == "DATA_READY"


def test_hierarchical_label_requires_a_matching_parent_connection():
    document = _minimal_document()
    document["components"] = [_component("U1", "child")]
    with pytest.raises(ValueError, match="matching connection on another sheet"):
        SchematicIntent.model_validate(document)


def test_cross_sheet_signal_must_use_hierarchical_style():
    document = _minimal_document()
    root = _component("J1", "root")
    root["pins"]["1"]["style"] = "label"
    document["components"] = [root, _component("U1", "child")]
    with pytest.raises(ValueError, match="must use hierarchical style"):
        SchematicIntent.model_validate(document)


def test_page_capacity_requires_another_sheet():
    document = _minimal_document(sheet_count=1)
    document["components"] = [
        _component(f"J{index}", "root", net=f"N{index}") for index in range(1, 27)
    ]
    document["boundary_nets"] = [f"N{index}" for index in range(1, 27)]
    with pytest.raises(ValueError, match="capacity"):
        SchematicIntent.model_validate(document)


def test_sheet_filenames_are_unique_after_normalization():
    document = _minimal_document()
    document["sheets"].append(
        {"id": "Sensor", "title": "Duplicate filename", "page": "A4"}
    )
    with pytest.raises(ValueError, match="sheet"):
        SchematicIntent.model_validate(document)


def test_sibling_sheets_preserve_distinct_nets_with_empty_root(project_copy, fixed_clock):
    document = _minimal_document()
    document["sheets"].append({"id": "output", "title": "Output", "page": "A4"})
    document["blocks"].append(
        {"id": "output", "title": "Output", "sheet": "output", "flow_order": 1}
    )
    document["boundary_nets"] = ["DATA_READY", "CLOCK"]
    document["components"] = [
        _component("J1", "child"), _component("J2", "output"),
        _component("J3", "child", "CLOCK"), _component("J4", "output", "CLOCK"),
    ]
    project = load_project(project_copy)
    draft = create_draft(project, DraftKind.SCHEMATIC, fixed_clock)
    result = render_schematic_draft(project, SchematicIntent.model_validate(document), draft)
    nets = _extract(result.root_schematic)["nets"]
    assert nets == {
        "J1": {"1": "DATA_READY"}, "J2": {"1": "DATA_READY"},
        "J3": {"1": "CLOCK"}, "J4": {"1": "CLOCK"},
    }
