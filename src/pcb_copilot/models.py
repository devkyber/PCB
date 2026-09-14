"""Shared typed models for PCB Copilot."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Lifecycle(str, Enum):
    DRAFT = "DRAFT"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    RELEASED = "RELEASED"


class DesignFiles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schematic: Path
    pcb: Path
    netmap: Path


class EvidenceFiles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: Path


class ManufacturingProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str = Field(min_length=1)


class ProjectManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1, le=1)
    name: str = Field(min_length=1)
    lifecycle: Lifecycle
    design: DesignFiles
    evidence: EvidenceFiles
    manufacturing: ManufacturingProfile
    safety_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Project:
    root: Path
    manifest_path: Path
    manifest: ProjectManifest
    schematic_path: Path
    pcb_path: Path
    netmap_path: Path
    evidence_index_path: Path
