"""Content-verified, hash-addressed evidence archival."""

from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pcb_copilot.evidence.index import load_evidence_index, save_evidence_index
from pcb_copilot.evidence.models import (
    EvidenceIndex,
    EvidenceRecord,
    EvidenceRole,
    TrustTier,
)
from pcb_copilot.models import Project


class InvalidEvidencePayload(ValueError):
    """Raised when downloaded bytes are empty, HTML, or mislabelled."""


class EvidenceConflictError(ValueError):
    """Raised when one content identity has conflicting provenance."""


MEDIA_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/vnd.eagle+xml": ".sch",
    "application/x-kicad-schematic": ".kicad_sch",
    "application/x-kicad-pcb": ".kicad_pcb",
    "application/xml": ".xml",
    "text/plain": ".txt",
    "application/octet-stream": ".bin",
}


def sniff_media_type(payload: bytes) -> str:
    if not payload:
        return "application/x-empty"
    head = payload[:4096]
    low = head.lower().lstrip()
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"PK"):
        return "application/zip"
    if b"<html" in low or low.startswith(b"<!doctype html"):
        return "text/html"
    if b"<eagle" in low:
        return "application/vnd.eagle+xml"
    if b"(kicad_sch" in low:
        return "application/x-kicad-schematic"
    if b"(kicad_pcb" in low:
        return "application/x-kicad-pcb"
    if low.startswith(b"<?xml"):
        return "application/xml"
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    return "text/plain"


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return cleaned[:90] or "document"


def _archive_name(part_number: str, url: str, media_type: str, digest: str, payload: bytes) -> str:
    url_name = Path(unquote(urlsplit(url).path)).name
    base = _safe_stem(url_name or "document")
    expected_suffix = MEDIA_EXTENSIONS[media_type]
    if media_type == 'application/vnd.eagle+xml':
        try:
            if ET.fromstring(payload).find('drawing/board') is not None:
                expected_suffix = '.brd'
        except ET.ParseError as exc:
            raise InvalidEvidencePayload('malformed Eagle XML') from exc
    for suffix in (".kicad_sch", ".kicad_pcb", ".pdf", ".zip", ".xml", ".sch", '.brd'):
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)]
            break
    return f"{_safe_stem(part_number)}_{base}_{digest[:12]}{expected_suffix}"


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def archive_document(
    project: Project,
    part_number: str,
    url: str,
    roles: set[EvidenceRole],
    payload: bytes,
    retrieved_on: date,
    *,
    component_refs: set[str] | None = None,
    manufacturer: str | None = None,
    title: str | None = None,
    revision: str | None = None,
    trust_tier: TrustTier = TrustTier.MANUFACTURER,
) -> EvidenceRecord:
    media_type = sniff_media_type(payload)
    if media_type == "application/x-empty":
        raise InvalidEvidencePayload("empty evidence payload")
    if media_type == "text/html":
        raise InvalidEvidencePayload("HTML response is not evidence")
    if urlsplit(url).path.lower().endswith(".pdf") and media_type != "application/pdf":
        raise InvalidEvidencePayload(
            f"source URL claims PDF but payload is {media_type}"
        )

    digest = hashlib.sha256(payload).hexdigest()
    evidence_id = f"sha256:{digest}"
    index_path = project.evidence_index_path
    if index_path.is_file():
        index = load_evidence_index(index_path)
    else:
        index = EvidenceIndex(schema_version=1, records=())

    existing = next((item for item in index.records if item.id == evidence_id), None)
    if existing is not None:
        if existing.source_url and existing.source_url != url:
            raise EvidenceConflictError(
                f"content {evidence_id} already has source URL {existing.source_url}"
            )
        merged = existing.model_copy(
            update={
                "part_numbers": existing.part_numbers | {part_number},
                "roles": existing.roles | roles,
                "component_refs": existing.component_refs | (component_refs or set()),
            }
        )
        archived_path = index_path.parent / merged.path
        created = not archived_path.exists()
        if created:
            _write_bytes_atomic(archived_path, payload)
        try:
            save_evidence_index(
                index.model_copy(
                    update={
                        "records": tuple(
                            merged if item.id == evidence_id else item
                            for item in index.records
                        )
                    }
                ),
                index_path,
            )
        except Exception:
            if created:
                archived_path.unlink(missing_ok=True)
            raise
        return merged

    relative_path = Path("files") / _archive_name(part_number, url, media_type, digest, payload)
    record = EvidenceRecord(
        id=evidence_id,
        manufacturer=manufacturer,
        part_numbers={part_number},
        title=title or Path(unquote(urlsplit(url).path)).name or part_number,
        revision=revision,
        source_url=url,
        retrieved_on=retrieved_on,
        path=relative_path.as_posix(),
        sha256=digest,
        media_type=media_type,
        roles=roles,
        trust_tier=trust_tier,
        component_refs=component_refs or set(),
    )
    archived_path = index_path.parent / relative_path
    _write_bytes_atomic(archived_path, payload)
    try:
        save_evidence_index(
            index.model_copy(update={"records": (*index.records, record)}),
            index_path,
        )
    except Exception:
        archived_path.unlink(missing_ok=True)
        raise
    return record
