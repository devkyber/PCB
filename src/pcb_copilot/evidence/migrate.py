"""Deterministic migration from split Markdown archives to one evidence index."""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pcb_copilot.evidence.archive import sniff_media_type
from pcb_copilot.evidence.index import load_evidence_index, save_evidence_index
from pcb_copilot.evidence.models import (
    EvidenceIndex,
    EvidenceRecord,
    EvidenceRole,
    TrustTier,
)
from pcb_copilot.models import Project


class EvidenceMigrationError(ValueError):
    """Raised before mutation when legacy evidence cannot be migrated safely."""


@dataclass(frozen=True)
class MigrationReport:
    records_created: int
    duplicates_merged: int
    records: tuple[EvidenceRecord, ...]
    moves: tuple[str, ...]
    rewrites: tuple[str, ...]
    deletions: tuple[str, ...]


@dataclass(frozen=True)
class _LegacyRow:
    folder: str
    file: Path
    keys: tuple[str, ...]
    source_url: str
    retrieved_on: date


_FILENAME = re.compile(r"^[A-Za-z0-9][\w.+-]*\.[A-Za-z0-9_]{1,12}$")
_REF = re.compile(
    r"^(?:R|C|L|U|J|D|Q|K|Y|SW|BT|TP|FID|H|LED|F|JP)\d{1,3}$",
    re.IGNORECASE,
)
_TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".kicad_pro",
    ".kicad_sch",
    ".kicad_pcb",
}


def _parse_rows(project: Project) -> tuple[_LegacyRow, ...]:
    rows = []
    for folder in ("datasheets", "reference-designs"):
        index_path = project.root / folder / "INDEX.md"
        if not index_path.is_file():
            continue
        for raw in index_path.read_text(encoding="utf-8").splitlines():
            if "->" not in raw or raw.lstrip().startswith("#"):
                continue
            keys_text, remainder = raw.split("->", 1)
            filename, _, metadata = remainder.partition("#")
            filename = filename.strip()
            if not _FILENAME.fullmatch(filename):
                continue
            target = project.root / folder / filename
            if not target.is_file():
                raise EvidenceMigrationError(f"missing legacy evidence file: {target}")
            url_match = re.search(r"https?://[^\s|)]+", metadata)
            if not url_match:
                raise EvidenceMigrationError(f"missing source URL for {target}")
            date_match = re.search(r"(?:fetched|verified live)\s+(\d{4}-\d{2}-\d{2})", metadata)
            if not date_match:
                raise EvidenceMigrationError(f"missing retrieval date for {target}")
            rows.append(
                _LegacyRow(
                    folder=folder,
                    file=target,
                    keys=tuple(key.strip() for key in keys_text.split(",") if key.strip()),
                    source_url=url_match.group(0),
                    retrieved_on=date.fromisoformat(date_match.group(1)),
                )
            )
    if not rows:
        raise EvidenceMigrationError(f"no legacy evidence rows in {project.root}")

    indexed = {row.file.resolve() for row in rows}
    for folder in ("datasheets", "reference-designs"):
        directory = project.root / folder
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.name != "INDEX.md" and path.resolve() not in indexed:
                raise EvidenceMigrationError(f"unindexed legacy evidence file: {path}")
    return tuple(rows)


def _roles(row: _LegacyRow) -> set[EvidenceRole]:
    roles = {
        EvidenceRole.DATASHEET
        if row.folder == "datasheets"
        else EvidenceRole.REFERENCE_DESIGN
    }
    identity = " ".join((*row.keys, row.file.name)).casefold()
    if "integrationmanual" in identity or "integration manual" in identity:
        roles.add(EvidenceRole.INTEGRATION_MANUAL)
    if "teensy" in identity or "xbee" in identity or "pinout" in identity:
        roles.add(EvidenceRole.MODULE_PINOUT)
    return roles


def _trust(rows: list[_LegacyRow]) -> TrustTier:
    references = [row for row in rows if row.folder == "reference-designs"]
    if not references:
        return TrustTier.MANUFACTURER
    if any(
        token in row.source_url.casefold()
        for row in references
        for token in ("github.com", "githubusercontent.com", "adafruit", "sparkfun")
    ):
        return TrustTier.PROVEN_OPEN_HARDWARE
    return TrustTier.MANUFACTURER_EVM


def _build_records(rows: tuple[_LegacyRow, ...]) -> tuple[EvidenceRecord, ...]:
    grouped: dict[str, list[_LegacyRow]] = {}
    for row in rows:
        digest = hashlib.sha256(row.file.read_bytes()).hexdigest()
        grouped.setdefault(digest, []).append(row)

    used_names = set()
    records = []
    for digest, group in sorted(grouped.items()):
        urls = {row.source_url for row in group}
        if len(urls) != 1:
            raise EvidenceMigrationError(
                f"identical bytes have conflicting source URLs: {sorted(urls)}"
            )
        media_types = {sniff_media_type(row.file.read_bytes()) for row in group}
        if media_types & {"application/x-empty", "text/html"}:
            raise EvidenceMigrationError(f"invalid payload in {group[0].file}")
        if len(media_types) != 1:
            raise EvidenceMigrationError(f"conflicting media types for sha256:{digest}")
        dates = {row.retrieved_on for row in group}
        if len(dates) != 1:
            raise EvidenceMigrationError(f"conflicting retrieval dates for sha256:{digest}")

        source = min(
            {row.file for row in group},
            key=lambda path: (
                0 if path.parent.name == "datasheets" else 1,
                path.name.casefold(),
            ),
        )
        name = source.name
        if name.casefold() in used_names:
            name = f"{source.stem}_{digest[:12]}{source.suffix}"
        used_names.add(name.casefold())
        keys = {key for row in group for key in row.keys}
        component_refs = {key for key in keys if _REF.fullmatch(key)}
        part_numbers = keys - component_refs
        if not part_numbers:
            part_numbers = {source.stem}
        roles = {role for row in group for role in _roles(row)}
        records.append(
            EvidenceRecord(
                id=f"sha256:{digest}",
                manufacturer=None,
                part_numbers=part_numbers,
                title=source.stem,
                revision=None,
                source_url=urls.pop(),
                retrieved_on=dates.pop(),
                path=f"files/{name}",
                sha256=digest,
                media_type=media_types.pop(),
                roles=roles,
                trust_tier=_trust(group),
                component_refs=component_refs,
            )
        )
    return tuple(records)


def _source_to_record(
    rows: tuple[_LegacyRow, ...], records: tuple[EvidenceRecord, ...]
) -> dict[Path, EvidenceRecord]:
    by_hash = {record.sha256: record for record in records}
    return {
        row.file: by_hash[hashlib.sha256(row.file.read_bytes()).hexdigest()]
        for row in rows
    }


def _planned_rewrites(project: Project, replacements: dict[str, str]) -> tuple[str, ...]:
    changed = []
    for path in sorted(project.root.rglob("*")):
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
            continue
        if "evidence" in path.relative_to(project.root).parts:
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != text:
            changed.append(path.relative_to(project.root).as_posix())
    return tuple(changed)


def _verify_written_index(project: Project) -> None:
    index = load_evidence_index(project.evidence_index_path)
    for record in index.records:
        path = project.evidence_index_path.parent / record.path
        if not path.is_file():
            raise EvidenceMigrationError(f"unwritten evidence target: {path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record.sha256:
            raise EvidenceMigrationError(f"written evidence hash mismatch: {path}")


def migrate_legacy_evidence(
    project: Project, dry_run: bool = True
) -> MigrationReport:
    rows = _parse_rows(project)
    records = _build_records(rows)
    source_records = _source_to_record(rows, records)
    unique_sources = sorted({row.file for row in rows})
    replacements = {
        f"{row.folder}/{row.file.name}": f"evidence/{source_records[row.file].path}"
        for row in rows
    }
    rewrites = _planned_rewrites(project, replacements)
    legacy_dirs = [
        project.root / name
        for name in ("datasheets", "reference-designs")
        if (project.root / name).is_dir()
    ]
    report = MigrationReport(
        records_created=len(records),
        duplicates_merged=len(unique_sources) - len(records),
        records=records,
        moves=tuple(
            f"{path.relative_to(project.root).as_posix()} -> "
            f"evidence/{source_records[path].path}"
            for path in unique_sources
        ),
        rewrites=rewrites,
        deletions=tuple(path.relative_to(project.root).as_posix() for path in legacy_dirs),
    )
    if dry_run:
        return report

    evidence_dir = project.evidence_index_path.parent
    files_dir = evidence_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for source in unique_sources:
        destination = evidence_dir / source_records[source].path
        if not destination.exists():
            shutil.copy2(source, destination)
    save_evidence_index(EvidenceIndex(schema_version=1, records=records), project.evidence_index_path)
    _verify_written_index(project)

    for relative in rewrites:
        path = project.root / relative
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        path.write_text(updated, encoding="utf-8", newline="\n")

    for directory in legacy_dirs:
        resolved = directory.resolve()
        try:
            resolved.relative_to(project.root.resolve())
        except ValueError as exc:
            raise EvidenceMigrationError(f"refusing to delete outside project: {resolved}") from exc
        shutil.rmtree(resolved)
    _verify_written_index(project)
    return report
