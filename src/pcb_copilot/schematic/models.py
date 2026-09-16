"""Versioned, evidence-backed circuit intent models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IntentValidationError(ValueError):
    """Raised when a schematic intent is incomplete or internally inconsistent."""


class PinConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    net: str = Field(min_length=1)
    style: Literal["wire", "label", "power", "hierarchical"]


class NoConnectIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pin: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def reason_must_be_substantive(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("no-connect reason must not be blank")
        return value.strip()


class ComponentIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str = Field(min_length=1, pattern=r"^[A-Za-z#]+[A-Za-z0-9_-]*$")
    value: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    footprint: str = Field(min_length=1)
    block: str = Field(min_length=1)
    evidence_part_number: str = Field(min_length=1)
    pin_map_evidence_id: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    pins: dict[str, PinConnection]
    no_connects: tuple[NoConnectIntent, ...] = ()
    pin_inventory: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def pins_are_declared_once(self) -> ComponentIntent:
        disconnected = [item.pin for item in self.no_connects]
        duplicates = sorted(set(self.pins).intersection(disconnected))
        if duplicates or len(disconnected) != len(set(disconnected)):
            raise ValueError("component pin declared more than once")
        if self.pin_inventory:
            validate_component_pins(self, set(self.pin_inventory))
        return self


class SheetIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    page: Literal["A5", "A4", "A3", "A2", "A1", "A0"] = "A4"

    @field_validator("id")
    @classmethod
    def valid_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", value):
            raise ValueError("invalid sheet id")
        return value


class BlockIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(min_length=1)
    sheet: str = Field(min_length=1)
    flow_order: int = Field(ge=0)
    placement_hint: Literal["left", "center", "right", "top", "bottom"] | None = None


class SchematicIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    title: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    sheets: tuple[SheetIntent, ...] = Field(min_length=1)
    blocks: tuple[BlockIntent, ...] = Field(min_length=1)
    components: tuple[ComponentIntent, ...] = Field(min_length=1)
    boundary_nets: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def references_are_consistent(self) -> SchematicIntent:
        sheet_ids = [item.id for item in self.sheets]
        block_ids = [item.id for item in self.blocks]
        refs = [item.ref for item in self.components]
        for label, values in (
            ("sheet id", sheet_ids),
            ("block id", block_ids),
            ("component ref", refs),
        ):
            duplicates = sorted({item for item in values if values.count(item) > 1})
            if duplicates:
                raise ValueError(f"duplicate {label}: {', '.join(duplicates)}")
        unknown_sheets = sorted(
            {block.sheet for block in self.blocks} - set(sheet_ids)
        )
        if unknown_sheets:
            raise ValueError(f"unknown sheet: {', '.join(unknown_sheets)}")
        unknown_blocks = sorted(
            {component.block for component in self.components} - set(block_ids)
        )
        if unknown_blocks:
            raise ValueError(f"unknown block: {', '.join(unknown_blocks)}")

        net_blocks: dict[str, set[str]] = {}
        power_nets = set()
        for component in self.components:
            for connection in component.pins.values():
                net_blocks.setdefault(connection.net, set()).add(component.block)
                if connection.style == "power":
                    power_nets.add(connection.net)
        undeclared = sorted(
            net
            for net, blocks in net_blocks.items()
            if len(blocks) > 1
            and net not in self.boundary_nets
            and net not in power_nets
        )
        if undeclared:
            raise ValueError(
                "net crosses a block-boundary without declaration: "
                + ", ".join(undeclared)
            )
        return self


def validate_component_pins(
    component: ComponentIntent, expected_pins: set[str]
) -> None:
    declared = set(component.pins) | {item.pin for item in component.no_connects}
    if declared != expected_pins:
        missing = sorted(expected_pins - declared)
        extra = sorted(declared - expected_pins)
        raise IntentValidationError(
            f"{component.ref} pin inventory mismatch; missing={missing}, extra={extra}"
        )
