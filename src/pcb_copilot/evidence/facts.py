"""Cited facts extracted from archived evidence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str | None = None
    evidence_id: str = Field(min_length=1)
    pages: tuple[int, ...]
    confidence: Literal["exact", "review_required"]
