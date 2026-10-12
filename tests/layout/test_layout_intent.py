from pathlib import Path

import pytest

from pcb_copilot.evidence.checks import Finding
from pcb_copilot.layout.io import load_layout_intent, save_layout_intent
from pcb_copilot.layout.models import (
    BoardOutline,
    CriticalNetIntent,
    LayoutIntent,
    LayoutIntentError,
    NetClassIntent,
    PlacementItem,
    PlacementRegion,
    RoutePolicy,
    ZoneIntent,
    validate_layout_intent,
)


def minimal_layout_intent(**updates) -> LayoutIntent:
    values = {
        "schema_version": 1,
        "title": "Two-part sensor board",
        "revision": "A",
        "coordinate_frame": "board-origin-bottom-left-x-right-y-up-mm",
        "outline": BoardOutline(width_mm=20.0, height_mm=20.0),
        "regions": (
            PlacementRegion(
                id="sensor", x_mm=0.0, y_mm=0.0, width_mm=10.0, height_mm=20.0
            ),
            PlacementRegion(
                id="support", x_mm=10.0, y_mm=0.0, width_mm=10.0, height_mm=20.0
            ),
        ),
        "placements": (
            PlacementItem(
                ref="U1",
                region="sensor",
                footprint="Package_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm",
            ),
            PlacementItem(
                ref="C1",
                region="support",
                footprint="Capacitor_SMD:C_0603_1608Metric",
                near_ref="U1",
                near_pin="10",
                source_pin="1",
                max_distance_mm=2.0,
            ),
        ),
        "net_classes": (),
        "critical_nets": (),
        "zones": (),
    }
    values.update(updates)
    return LayoutIntent(**values)


def test_layout_intent_requires_every_physical_ref():
    accepted_refs = {"U1", "C1"}
    intent = minimal_layout_intent(
        placements=[PlacementItem(ref="U1", region="sensor")]
    )

    with pytest.raises(LayoutIntentError, match="missing placement intent"):
        validate_layout_intent(intent, accepted_refs)


def test_critical_current_net_requires_all_physical_inputs():
    intent_with_ignition_net = minimal_layout_intent(
        critical_nets=[CriticalNetIntent(net="IGN_FIRE", reason="igniter current")]
    )

    with pytest.raises(LayoutIntentError, match="current_a"):
        validate_layout_intent(intent_with_ignition_net, {"U1", "C1"})

    intent_missing_duration = minimal_layout_intent(
        critical_nets=[
            CriticalNetIntent(
                net="IGN_FIRE",
                reason="igniter current",
                current_a=1.5,
                rise_c=10.0,
                copper_oz=1.0,
                layer="external",
            )
        ]
    )
    with pytest.raises(LayoutIntentError, match="duration_s"):
        validate_layout_intent(intent_missing_duration, {"U1", "C1"})


def test_impedance_net_requires_complete_stackup_inputs():
    intent = minimal_layout_intent(
        critical_nets=[
            CriticalNetIntent(
                net="RF_OUT",
                reason="50 ohm antenna feed",
                kind="rf",
                impedance_ohm=50.0,
            )
        ]
    )

    with pytest.raises(LayoutIntentError, match="dielectric_height_mm"):
        validate_layout_intent(intent, {"U1", "C1"})


def test_complete_impedance_inputs_can_be_validated_against_accepted_net():
    intent = minimal_layout_intent(
        critical_nets=[
            CriticalNetIntent(
                net="RF_OUT",
                reason="50 ohm antenna feed",
                kind="rf",
                impedance_ohm=50.0,
                dielectric_height_mm=0.18,
                er=4.2,
                copper_mm=0.035,
            )
        ]
    )

    validate_layout_intent(intent, {"U1", "C1"}, {"RF_OUT"})


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {
                "kind": "power",
                "current_a": 1.5,
                "duration_s": 0.5,
                "rise_c": 10.0,
                "copper_oz": 1.0,
                "layer": "external",
                "impedance_ohm": 50.0,
            },
            "RF-only",
        ),
        (
            {
                "kind": "rf",
                "impedance_ohm": 50.0,
                "dielectric_height_mm": 0.18,
                "er": 4.2,
                "copper_mm": 0.035,
                "current_a": 1.5,
            },
            "power-only",
        ),
    ],
    ids=["power-with-rf-input", "rf-with-power-input"],
)
def test_critical_net_rejects_inputs_from_another_kind(updates, message):
    with pytest.raises(ValueError, match=message):
        CriticalNetIntent(net="CRITICAL", reason="derived physical rule", **updates)


def test_overlapping_regions_are_rejected():
    with pytest.raises(ValueError, match="overlap"):
        minimal_layout_intent(
            regions=[
                PlacementRegion(
                    id="sensor",
                    x_mm=0.0,
                    y_mm=0.0,
                    width_mm=12.0,
                    height_mm=20.0,
                ),
                PlacementRegion(
                    id="support",
                    x_mm=10.0,
                    y_mm=0.0,
                    width_mm=10.0,
                    height_mm=20.0,
                ),
            ]
        )


@pytest.mark.parametrize(
    "outline",
    [
        {"width_mm": 0.0, "height_mm": 20.0},
        {"width_mm": 20.0, "height_mm": -1.0},
        {"width_mm": float("inf"), "height_mm": 20.0},
    ],
)
def test_invalid_outline_is_rejected(outline):
    with pytest.raises(ValueError):
        BoardOutline(**outline)


def test_regions_must_be_inside_the_outline():
    with pytest.raises(ValueError, match="outside board outline"):
        minimal_layout_intent(
            regions=[
                PlacementRegion(
                    id="sensor",
                    x_mm=0.0,
                    y_mm=0.0,
                    width_mm=10.0,
                    height_mm=20.0,
                ),
                PlacementRegion(
                    id="support",
                    x_mm=10.0,
                    y_mm=0.0,
                    width_mm=11.0,
                    height_mm=20.0,
                ),
            ]
        )


def test_duplicate_placements_are_rejected():
    with pytest.raises(ValueError, match="duplicate placement ref"):
        minimal_layout_intent(
            placements=[
                PlacementItem(ref="U1", region="sensor"),
                PlacementItem(ref="U1", region="support"),
            ]
        )


def test_unknown_refs_require_explicit_pcb_only_placement_and_footprint():
    intent = minimal_layout_intent(
        placements=[
            PlacementItem(ref="U1", region="sensor"),
            PlacementItem(ref="C1", region="support"),
            PlacementItem(ref="H1", region="support"),
        ]
    )
    with pytest.raises(LayoutIntentError, match="unknown placement ref: H1"):
        validate_layout_intent(intent, {"U1", "C1"})

    with pytest.raises(ValueError, match="footprint"):
        PlacementItem(ref="H1", region="support", pcb_only=True)

    valid = intent.model_copy(
        update={
            "placements": intent.placements[:2]
            + (
                PlacementItem(
                    ref="H1",
                    region="support",
                    footprint="MountingHole:MountingHole_3.2mm_M3",
                    pcb_only=True,
                ),
            )
        }
    )
    validate_layout_intent(valid, {"U1", "C1"}, set())


def test_unknown_region_and_near_ref_are_rejected():
    with pytest.raises(ValueError, match="unknown placement region"):
        minimal_layout_intent(
            placements=[
                PlacementItem(ref="U1", region="missing"),
                PlacementItem(ref="C1", region="support"),
            ]
        )

    with pytest.raises(ValueError, match="unknown near_ref"):
        minimal_layout_intent(
            placements=[
                PlacementItem(ref="U1", region="sensor"),
                PlacementItem(
                    ref="C1",
                    region="support",
                    footprint="Capacitor_SMD:C_0603_1608Metric",
                    near_ref="U9",
                    near_pin="10",
                    max_distance_mm=2.0,
                ),
            ]
        )


def test_fixed_coordinates_are_anchor_pairs_in_the_declared_frame():
    placement = PlacementItem(
        ref="U1",
        region="sensor",
        footprint="Package_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm",
        anchor_x_mm=2.0,
        anchor_y_mm=3.0,
        rotation_deg=90.0,
    )
    assert placement.anchor == (2.0, 3.0)

    with pytest.raises(ValueError, match="anchor_x_mm and anchor_y_mm"):
        PlacementItem(ref="U1", region="sensor", anchor_x_mm=2.0)
    with pytest.raises(ValueError):
        PlacementItem(
            ref="U1",
            region="sensor",
            footprint="Package_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm",
            anchor_x_mm=float("nan"),
            anchor_y_mm=3.0,
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"anchor_x_mm": 2.0, "anchor_y_mm": 3.0},
        {"near_ref": "U1", "near_pin": "10", "max_distance_mm": 2.0},
    ],
    ids=["fixed-anchor", "near-pad"],
)
def test_geometry_specific_placement_requires_footprint_id(updates):
    with pytest.raises(ValueError, match="footprint.*Library:Name"):
        PlacementItem(ref="C1", region="support", **updates)


def test_near_pad_target_requires_footprint_id():
    with pytest.raises(ValueError, match="near-pad target U1.*footprint"):
        minimal_layout_intent(
            placements=[
                PlacementItem(ref="U1", region="sensor"),
                PlacementItem(
                    ref="C1",
                    region="support",
                    footprint="Capacitor_SMD:C_0603_1608Metric",
                    near_ref="U1",
                    near_pin="10",
                    source_pin="1",
                    max_distance_mm=2.0,
                ),
            ]
        )


def test_simple_unreferenced_placement_may_defer_footprint_to_accepted_cad():
    placement = PlacementItem(ref="R1", region="sensor")

    assert placement.footprint is None


@pytest.mark.parametrize(
    "footprint",
    [
        " ",
        "C_0603",
        ":C_0603",
        "Capacitor_SMD:",
        "Bad/Lib:C",
        "Lib:C/0603",
        "Lib:C:0603",
    ],
)
def test_footprint_id_must_use_library_name_syntax(footprint):
    with pytest.raises(ValueError, match="Library:Name"):
        PlacementItem(ref="C1", region="support", footprint=footprint)


def test_footprint_id_accepts_safe_interior_spaces():
    placement = PlacementItem(
        ref="C1", region="support", footprint="Vendor Parts:Part Name"
    )

    assert placement.footprint == "Vendor Parts:Part Name"


def test_fixed_anchor_must_be_inside_its_assigned_region():
    with pytest.raises(ValueError, match="anchor outside placement region"):
        minimal_layout_intent(
            placements=[
                PlacementItem(
                    ref="U1",
                    region="sensor",
                    footprint="Package_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm",
                    anchor_x_mm=15.0,
                    anchor_y_mm=5.0,
                ),
                PlacementItem(ref="C1", region="support"),
            ]
        )


def test_net_references_must_exist_in_accepted_schematic():
    intent = minimal_layout_intent(
        net_classes=[
            NetClassIntent(name="signals", nets=["SENSE", "MISSING"], width_mm=0.2)
        ],
        critical_nets=[
            CriticalNetIntent(
                net="IGN_FIRE",
                reason="igniter current",
                current_a=1.5,
                duration_s=0.5,
                rise_c=10.0,
                copper_oz=1.0,
                layer="external",
            )
        ],
    )

    with pytest.raises(LayoutIntentError, match="unknown net.*MISSING"):
        validate_layout_intent(intent, {"U1", "C1"}, {"SENSE", "IGN_FIRE"})


def test_full_validation_requires_authoritative_net_inventory():
    intent = minimal_layout_intent()

    with pytest.raises(LayoutIntentError, match="accepted net inventory"):
        validate_layout_intent(intent, {"U1", "C1"})


def test_zone_net_must_exist_in_accepted_schematic():
    intent = minimal_layout_intent(
        zones=[ZoneIntent(net="MISSING_GND", layers=["F.Cu", "B.Cu"])]
    )

    with pytest.raises(LayoutIntentError, match="zone.*MISSING_GND"):
        validate_layout_intent(intent, {"U1", "C1"}, {"GND"})


def test_route_policy_defaults_to_human():
    intent = minimal_layout_intent()

    assert intent.route_policy is RoutePolicy.HUMAN
    assert {item.value for item in RoutePolicy} == {
        "human",
        "critical_only",
        "candidate_all",
    }


def test_unresolved_owner_decisions_round_trip_as_findings(tmp_path: Path):
    intent = minimal_layout_intent(
        unresolved_decisions=[
            Finding(
                code="layout.rf-stackup-unresolved",
                message="Owner must select the RF stackup before deriving impedance.",
                reference="U1",
                severity="review",
            )
        ]
    )
    destination = tmp_path / "layout-intent.yaml"

    save_layout_intent(intent, destination)

    loaded = load_layout_intent(destination)
    assert loaded == intent
    assert loaded.unresolved_decisions[0].severity == "review"


def test_template_round_trips_and_empty_template_fails(repo_root: Path, tmp_path: Path):
    source = repo_root / "templates/project/layout-intent.yaml"
    intent = load_layout_intent(source)
    assert len(intent.regions) == 2
    assert len(intent.placements) >= 2
    destination = tmp_path / "layout-intent.yaml"

    save_layout_intent(intent, destination)
    assert load_layout_intent(destination) == intent

    empty = intent.model_copy(update={"placements": ()})
    save_layout_intent(empty, destination)
    with pytest.raises(LayoutIntentError):
        load_layout_intent(destination)
