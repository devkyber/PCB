from pathlib import Path

import pytest

from pcb_copilot.schematic.io import load_schematic_intent, save_schematic_intent
from pcb_copilot.schematic.models import (
    ComponentIntent,
    IntentValidationError,
    NoConnectIntent,
    PinConnection,
    SchematicIntent,
    validate_component_pins,
)


def component(**updates):
    values = {
        "ref": "U1",
        "value": "BMP390",
        "symbol": "jlcpcb:BMP390",
        "footprint": "jlcpcb:LGA-10_L2.0-W2.0-P0.50-BL",
        "block": "sensor",
        "evidence_part_number": "BMP390",
        "pin_map_evidence_id": "sha256:" + "a" * 64,
        "pins": {"1": PinConnection(net="+3V3", style="power")},
        "no_connects": (),
    }
    values.update(updates)
    return ComponentIntent(**values)


def test_intent_requires_every_pin_once():
    item = component()

    with pytest.raises(IntentValidationError, match="pin inventory"):
        validate_component_pins(item, expected_pins={str(n) for n in range(1, 11)})


def test_component_rejects_pin_as_connected_and_no_connect():
    with pytest.raises(ValueError, match="declared more than once"):
        component(no_connects=(NoConnectIntent(pin="1", reason="unused"),))


def test_no_connect_requires_reason():
    with pytest.raises(ValueError, match="reason"):
        NoConnectIntent(pin="2", reason="")


@pytest.mark.parametrize("sheet_id", ["Bad Sheet", "../child", "", "sensor.kicad_sch"])
def test_invalid_sheet_ids_fail(sheet_id):
    with pytest.raises(ValueError):
        SchematicIntent.model_validate(
            {
                "schema_version": 1,
                "title": "Test",
                "revision": "A",
                "sheets": [{"id": sheet_id, "title": "Main"}],
                "blocks": [{"id": "sensor", "title": "Sensor", "sheet": sheet_id, "flow_order": 1}],
                "components": [],
            }
        )


def test_duplicate_refs_and_unknown_blocks_fail():
    document = {
        "schema_version": 1,
        "title": "Test",
        "revision": "A",
        "sheets": [{"id": "main", "title": "Main"}],
        "blocks": [{"id": "sensor", "title": "Sensor", "sheet": "main", "flow_order": 1}],
        "components": [component().model_dump(mode="json"), component().model_dump(mode="json")],
    }
    with pytest.raises(ValueError, match="duplicate component ref"):
        SchematicIntent.model_validate(document)

    document["components"] = [component(block="missing").model_dump(mode="json")]
    with pytest.raises(ValueError, match="unknown block"):
        SchematicIntent.model_validate(document)


def test_cross_block_net_requires_boundary_declaration():
    document = {
        "schema_version": 1,
        "title": "Test",
        "revision": "A",
        "sheets": [{"id": "main", "title": "Main"}],
        "blocks": [
            {"id": "source", "title": "Source", "sheet": "main", "flow_order": 1},
            {"id": "sink", "title": "Sink", "sheet": "main", "flow_order": 2},
        ],
        "components": [
            component(ref="U1", block="source", pins={"1": {"net": "DATA", "style": "label"}}).model_dump(mode="json"),
            component(ref="U2", block="sink", pins={"1": {"net": "DATA", "style": "label"}}).model_dump(mode="json"),
        ],
    }
    with pytest.raises(ValueError, match="block-boundary"):
        SchematicIntent.model_validate(document)
    document["boundary_nets"] = ["DATA"]
    assert SchematicIntent.model_validate(document).boundary_nets == frozenset({"DATA"})


def test_template_round_trips_and_is_not_empty(repo_root: Path, tmp_path: Path):
    source = repo_root / "projects/template/schematic-intent.yaml"
    intent = load_schematic_intent(source)
    assert intent.blocks
    assert len(intent.components) >= 2
    destination = tmp_path / "intent.yaml"

    save_schematic_intent(intent, destination)

    assert load_schematic_intent(destination) == intent
    empty = intent.model_copy(update={"blocks": ()})
    save_schematic_intent(empty, destination)
    with pytest.raises(IntentValidationError):
        load_schematic_intent(destination)
