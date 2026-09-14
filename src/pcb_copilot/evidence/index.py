"""Validated, deterministic and atomic evidence-index persistence."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from pcb_copilot.evidence.models import EvidenceIndex, EvidenceRecord


class EvidenceFormatError(ValueError):
    """Raised when an evidence index cannot be parsed or validated."""


def load_evidence_index(path: Path) -> EvidenceIndex:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        return EvidenceIndex.model_validate(document)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise EvidenceFormatError(f"invalid evidence index {path}: {exc}") from exc


def _record_document(record: EvidenceRecord) -> dict:
    return {
        "id": record.id,
        "manufacturer": record.manufacturer,
        "part_numbers": sorted(record.part_numbers, key=str.casefold),
        "title": record.title,
        "revision": record.revision,
        "source_url": record.source_url,
        "retrieved_on": record.retrieved_on.isoformat(),
        "path": record.path,
        "sha256": record.sha256.lower(),
        "media_type": record.media_type,
        "roles": sorted(role.value for role in record.roles),
        "trust_tier": record.trust_tier.value,
        "component_refs": sorted(record.component_refs, key=str.casefold),
    }


def save_evidence_index(index: EvidenceIndex, path: Path) -> None:
    validated = EvidenceIndex.model_validate(index)
    document = {
        "schema_version": validated.schema_version,
        "records": [
            _record_document(record)
            for record in sorted(validated.records, key=lambda item: item.id)
        ],
    }
    serialized = yaml.safe_dump(
        document,
        allow_unicode=True,
        sort_keys=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
