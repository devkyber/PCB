"""Typed records stored in a project's evidence index."""

from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceRole(str, Enum):
    DATASHEET = "datasheet"
    INTEGRATION_MANUAL = "integration_manual"
    REFERENCE_DESIGN = "reference_design"
    APPLICATION_NOTE = "application_note"
    FOOTPRINT_DRAWING = "footprint_drawing"
    MODULE_PINOUT = "module_pinout"


class TrustTier(str, Enum):
    MANUFACTURER = "manufacturer"
    MANUFACTURER_EVM = "manufacturer_evm"
    PROVEN_OPEN_HARDWARE = "proven_open_hardware"
    TEACHING_REFERENCE = "teaching_reference"


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    manufacturer: str | None = None
    part_numbers: frozenset[str] = Field(min_length=1)
    title: str | None = None
    revision: str | None = None
    source_url: str = Field(min_length=1)
    retrieved_on: date
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=1, pattern=r"^[0-9a-fA-F]+$")
    media_type: str = Field(min_length=1)
    roles: frozenset[EvidenceRole] = Field(min_length=1)
    trust_tier: TrustTier
    component_refs: frozenset[str] = frozenset()

    @field_validator("path")
    @classmethod
    def path_must_be_relative_and_contained(cls, value: str) -> str:
        posix = PurePosixPath(value)
        windows = PureWindowsPath(value)
        if posix.is_absolute() or windows.is_absolute():
            raise ValueError("evidence path must be relative")
        if ".." in posix.parts or ".." in windows.parts:
            raise ValueError("evidence path must not escape its project")
        return posix.as_posix()

    @model_validator(mode="after")
    def identity_matches_hash(self) -> EvidenceRecord:
        expected = f"sha256:{self.sha256.lower()}"
        if self.id.lower() != expected:
            raise ValueError("evidence id must be sha256:<sha256>")
        return self


class EvidenceIndex(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1, le=1)
    records: tuple[EvidenceRecord, ...] = ()

    @model_validator(mode="after")
    def ids_must_be_unique(self) -> EvidenceIndex:
        ids = [record.id for record in self.records]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ValueError("duplicate evidence id: " + ", ".join(duplicates))
        return self

    def for_part(self, part_number: str) -> tuple[EvidenceRecord, ...]:
        wanted = part_number.strip().casefold()
        return tuple(
            record
            for record in self.records
            if any(part.strip().casefold() == wanted for part in record.part_numbers)
        )
