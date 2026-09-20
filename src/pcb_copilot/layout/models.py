"""Versioned, reviewable PCB layout intent models."""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pcb_copilot.evidence.checks import Finding


class LayoutIntentError(ValueError):
    """Raised when layout intent is incomplete or references unknown design facts."""


class RoutePolicy(str, Enum):
    """Permitted routing automation levels."""

    HUMAN = "human"
    CRITICAL_ONLY = "critical_only"
    CANDIDATE_ALL = "candidate_all"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BoardOutline(_FrozenModel):
    """Rectangular board dimensions in the declared layout coordinate frame."""

    width_mm: float = Field(gt=0, allow_inf_nan=False)
    height_mm: float = Field(gt=0, allow_inf_nan=False)


class PlacementRegion(_FrozenModel):
    """Axis-aligned placement rectangle in board-local design coordinates."""

    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    x_mm: float = Field(ge=0, allow_inf_nan=False)
    y_mm: float = Field(ge=0, allow_inf_nan=False)
    width_mm: float = Field(gt=0, allow_inf_nan=False)
    height_mm: float = Field(gt=0, allow_inf_nan=False)


class PlacementItem(_FrozenModel):
    """Placement intent for a schematic or explicitly PCB-only reference.

    Fixed coordinates locate the footprint anchor, not its geometric center.
    Near-pad relationships name the target pad and may name the source pad so
    later placement checks can measure pad-to-pad distance. A footprint ID is
    lookup input; it is not evidence that the footprint was resolved or approved.
    """

    ref: str = Field(min_length=1, pattern=r"^[A-Za-z#]+[A-Za-z0-9_-]*$")
    region: str = Field(min_length=1)
    footprint: str | None = Field(default=None, min_length=1)
    pcb_only: bool = False
    anchor_x_mm: float | None = Field(default=None, allow_inf_nan=False)
    anchor_y_mm: float | None = Field(default=None, allow_inf_nan=False)
    rotation_deg: float = Field(default=0.0, allow_inf_nan=False)
    near_ref: str | None = Field(default=None, min_length=1)
    near_pin: str | None = Field(default=None, min_length=1)
    source_pin: str | None = Field(default=None, min_length=1)
    max_distance_mm: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @field_validator("footprint")
    @classmethod
    def footprint_is_library_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not re.fullmatch(r"[^\s:/\\]+:[^\s:/\\]+", value):
            raise ValueError("footprint must use Library:Name syntax")
        return value

    @model_validator(mode="after")
    def relationships_are_complete(self) -> PlacementItem:
        if (self.anchor_x_mm is None) != (self.anchor_y_mm is None):
            raise ValueError("anchor_x_mm and anchor_y_mm must be specified together")
        near_values = (self.near_ref, self.near_pin, self.max_distance_mm)
        if any(value is not None for value in near_values) and any(
            value is None for value in near_values
        ):
            raise ValueError(
                "near_ref, near_pin, and max_distance_mm must be specified together"
            )
        if self.source_pin is not None and self.near_ref is None:
            raise ValueError("source_pin requires a near-pad relationship")
        if self.near_ref == self.ref:
            raise ValueError("near_ref must name another placement")
        if (
            self.pcb_only or self.anchor is not None or self.near_ref is not None
        ) and self.footprint is None:
            raise ValueError(
                "geometry-specific placement footprint must use Library:Name syntax"
            )
        return self

    @property
    def anchor(self) -> tuple[float, float] | None:
        if self.anchor_x_mm is None or self.anchor_y_mm is None:
            return None
        return self.anchor_x_mm, self.anchor_y_mm


class NetClassIntent(_FrozenModel):
    name: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    nets: tuple[str, ...] = Field(min_length=1)
    width_mm: float = Field(gt=0, allow_inf_nan=False)
    clearance_mm: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    via_diameter_mm: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    via_drill_mm: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @field_validator("nets")
    @classmethod
    def nets_are_nonblank_and_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("net class nets must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("duplicate net in net class")
        return normalized

    @model_validator(mode="after")
    def via_geometry_is_consistent(self) -> NetClassIntent:
        if (self.via_diameter_mm is None) != (self.via_drill_mm is None):
            raise ValueError(
                "via_diameter_mm and via_drill_mm must be specified together"
            )
        if (
            self.via_diameter_mm is not None
            and self.via_drill_mm is not None
            and self.via_drill_mm >= self.via_diameter_mm
        ):
            raise ValueError("via drill must be smaller than via diameter")
        return self


class CriticalNetIntent(_FrozenModel):
    """Inputs from which a later task can derive a physical routing rule."""

    net: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    kind: Literal["power", "rf"] = "power"
    current_a: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    duration_s: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    rise_c: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    copper_oz: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    layer: Literal["external", "internal"] | None = None
    impedance_ohm: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    dielectric_height_mm: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    er: float | None = Field(default=None, gt=1, allow_inf_nan=False)
    copper_mm: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @field_validator("net", "reason")
    @classmethod
    def text_is_substantive(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("critical net and reason must not be blank")
        return value

    @model_validator(mode="after")
    def inputs_match_kind(self) -> CriticalNetIntent:
        power_fields = ("current_a", "duration_s", "rise_c", "copper_oz", "layer")
        rf_fields = ("impedance_ohm", "dielectric_height_mm", "er", "copper_mm")
        if self.kind == "power" and any(
            getattr(self, name) is not None for name in rf_fields
        ):
            raise ValueError("power critical net contains RF-only inputs")
        if self.kind == "rf" and any(
            getattr(self, name) is not None for name in power_fields
        ):
            raise ValueError("RF critical net contains power-only inputs")
        return self


class ZoneIntent(_FrozenModel):
    net: str = Field(min_length=1)
    layers: tuple[str, ...] = Field(min_length=1)
    region: str | None = Field(default=None, min_length=1)
    clearance_mm: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("net")
    @classmethod
    def net_is_substantive(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("zone net must not be blank")
        return value

    @field_validator("layers")
    @classmethod
    def layers_are_nonblank_and_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("zone layers must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("duplicate zone layer")
        return normalized


class LayoutIntent(_FrozenModel):
    """Versioned layout proposal input; it is not PCB acceptance or sign-off."""

    schema_version: Literal[1]
    title: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    coordinate_frame: Literal["board-origin-bottom-left-x-right-y-up-mm"]
    outline: BoardOutline
    regions: tuple[PlacementRegion, ...] = Field(min_length=1)
    placements: tuple[PlacementItem, ...] = Field(min_length=1)
    net_classes: tuple[NetClassIntent, ...] = ()
    critical_nets: tuple[CriticalNetIntent, ...] = ()
    zones: tuple[ZoneIntent, ...] = ()
    route_policy: RoutePolicy = RoutePolicy.HUMAN
    unresolved_decisions: tuple[Finding, ...] = ()

    @model_validator(mode="after")
    def geometry_and_references_are_consistent(self) -> LayoutIntent:
        region_ids = [region.id for region in self.regions]
        duplicates = _duplicates(region_ids)
        if duplicates:
            raise ValueError(f"duplicate placement region: {', '.join(duplicates)}")
        for region in self.regions:
            if (
                region.x_mm + region.width_mm > self.outline.width_mm
                or region.y_mm + region.height_mm > self.outline.height_mm
            ):
                raise ValueError(f"placement region outside board outline: {region.id}")
        for index, left in enumerate(self.regions):
            for right in self.regions[index + 1 :]:
                if _regions_overlap(left, right):
                    raise ValueError(
                        f"placement regions overlap: {left.id}, {right.id}"
                    )

        placement_refs = [placement.ref for placement in self.placements]
        duplicates = _duplicates(placement_refs)
        if duplicates:
            raise ValueError(f"duplicate placement ref: {', '.join(duplicates)}")
        known_regions = set(region_ids)
        regions_by_id = {region.id: region for region in self.regions}
        known_placements = set(placement_refs)
        for placement in self.placements:
            if placement.region not in known_regions:
                raise ValueError(
                    f"unknown placement region {placement.region}: {placement.ref}"
                )
            if placement.anchor is not None:
                anchor_x, anchor_y = placement.anchor
                region = regions_by_id[placement.region]
                if not (
                    region.x_mm <= anchor_x <= region.x_mm + region.width_mm
                    and region.y_mm <= anchor_y <= region.y_mm + region.height_mm
                ):
                    raise ValueError(
                        f"anchor outside placement region {placement.region}: "
                        f"{placement.ref}"
                    )
            if (
                placement.near_ref is not None
                and placement.near_ref not in known_placements
            ):
                raise ValueError(
                    f"unknown near_ref {placement.near_ref}: {placement.ref}"
                )

        class_names = [net_class.name for net_class in self.net_classes]
        duplicates = _duplicates(class_names)
        if duplicates:
            raise ValueError(f"duplicate net class: {', '.join(duplicates)}")
        classified_nets = [net for item in self.net_classes for net in item.nets]
        duplicates = _duplicates(classified_nets)
        if duplicates:
            raise ValueError(
                f"net assigned to multiple classes: {', '.join(duplicates)}"
            )

        critical_nets = [item.net for item in self.critical_nets]
        duplicates = _duplicates(critical_nets)
        if duplicates:
            raise ValueError(f"duplicate critical net: {', '.join(duplicates)}")

        for zone in self.zones:
            if zone.region is not None and zone.region not in known_regions:
                raise ValueError(f"unknown zone region {zone.region}: {zone.net}")
        for finding in self.unresolved_decisions:
            if finding.severity != "review":
                raise ValueError(
                    "unresolved decision findings must have review severity"
                )
        return self


def _duplicates(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def _regions_overlap(left: PlacementRegion, right: PlacementRegion) -> bool:
    return (
        left.x_mm < right.x_mm + right.width_mm
        and right.x_mm < left.x_mm + left.width_mm
        and left.y_mm < right.y_mm + right.height_mm
        and right.y_mm < left.y_mm + left.height_mm
    )


def validate_layout_intent(
    intent: LayoutIntent,
    accepted_refs: set[str] | frozenset[str],
    accepted_nets: set[str] | frozenset[str] | None = None,
) -> None:
    """Validate intent against refs and nets read from accepted CAD.

    ``accepted_nets=None`` means the authoritative net inventory was not supplied,
    so validation fails rather than inferring accepted facts from intent itself.
    """

    placed_schematic_refs = {
        placement.ref for placement in intent.placements if not placement.pcb_only
    }
    missing = sorted(set(accepted_refs) - placed_schematic_refs)
    if missing:
        raise LayoutIntentError(f"missing placement intent: {', '.join(missing)}")
    unknown = sorted(placed_schematic_refs - set(accepted_refs))
    if unknown:
        raise LayoutIntentError(f"unknown placement ref: {', '.join(unknown)}")

    for critical in intent.critical_nets:
        if critical.kind == "power":
            required = ("current_a", "duration_s", "rise_c", "copper_oz", "layer")
        else:
            required = (
                "impedance_ohm",
                "dielectric_height_mm",
                "er",
                "copper_mm",
            )
        missing_inputs = [name for name in required if getattr(critical, name) is None]
        if missing_inputs:
            raise LayoutIntentError(
                f"critical net {critical.net} missing required inputs: "
                + ", ".join(missing_inputs)
            )

    if accepted_nets is None:
        raise LayoutIntentError("accepted net inventory is required for validation")
    known_nets = set(accepted_nets)
    net_class_unknown = sorted(
        {
            net
            for net_class in intent.net_classes
            for net in net_class.nets
            if net not in known_nets
        }
    )
    if net_class_unknown:
        raise LayoutIntentError(
            f"net class references unknown net: {', '.join(net_class_unknown)}"
        )
    critical_unknown = sorted(
        {item.net for item in intent.critical_nets if item.net not in known_nets}
    )
    if critical_unknown:
        raise LayoutIntentError(
            f"critical intent references unknown net: {', '.join(critical_unknown)}"
        )
    zone_unknown = sorted(
        {zone.net for zone in intent.zones if zone.net not in known_nets}
    )
    if zone_unknown:
        raise LayoutIntentError(
            f"zone references unknown net: {', '.join(zone_unknown)}"
        )
