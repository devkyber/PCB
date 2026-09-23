"""One source of truth for evidence integrity and coverage checks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from pcb_copilot.evidence.archive import sniff_media_type
from pcb_copilot.evidence.index import EvidenceFormatError, load_evidence_index
from pcb_copilot.evidence.models import EvidenceRecord, EvidenceRole, TrustTier
from pcb_copilot.models import Project


@dataclass(frozen=True)
class Part:
    reference: str
    part_number: str
    requires_datasheet: bool = True
    requires_reference: bool = False
    is_module: bool = False


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    reference: str | None = None
    evidence_id: str | None = None
    severity: Literal["block", "review"] = "block"


TRUSTED_REFERENCE_TIERS = {
    TrustTier.MANUFACTURER_EVM,
    TrustTier.PROVEN_OPEN_HARDWARE,
}


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _records_for_part(
    records: tuple[EvidenceRecord, ...], part: Part
) -> tuple[EvidenceRecord, ...]:
    wanted = _normal(part.part_number)
    return tuple(
        record
        for record in records
        if part.reference.casefold()
        in {reference.casefold() for reference in record.component_refs}
        or any(_normal(number) == wanted for number in record.part_numbers)
    )


def _waived(project: Project, reference: str, scope: str) -> bool:
    from pcb_copilot.deviations import waived

    return waived(project.root, reference, scope)


def _basis_refs(project: Project) -> set[str]:
    path = project.root / "DESIGN_BASIS.md"
    if not path.is_file():
        return set()
    cited = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|") or re.search(
            r"<[^>]+>|\b(?:TBD|TODO)\b", line, re.IGNORECASE
        ):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 7 or set(cells[0]) <= set("-: "):
            continue
        if not cells[5] or not re.match(r"(?i)match|deviate", cells[6]):
            continue
        for token in re.split(r"[,/\s]+", cells[0]):
            match = re.match(r"([A-Za-z]+[0-9]+)(?:\.[A-Za-z0-9]+)?$", token.strip("`*"))
            if match:
                cited.add(match.group(1).casefold())
    return cited


def check_evidence(project: Project, pcb_inventory: list[Part] | tuple[Part, ...]) -> list[Finding]:
    if not project.evidence_index_path.is_file():
        return [Finding("index.missing", "evidence/index.yaml does not exist")]
    try:
        index = load_evidence_index(project.evidence_index_path)
    except EvidenceFormatError as exc:
        return [Finding("index.invalid", str(exc))]

    findings = []
    for record in index.records:
        path = project.evidence_index_path.parent / record.path
        if not record.source_url:
            findings.append(
                Finding(
                    "archive.missing_source_url",
                    "archived evidence has no source URL",
                    evidence_id=record.id,
                )
            )
        if not path.is_file():
            findings.append(
                Finding(
                    "archive.missing_file",
                    f"archived evidence file is missing: {record.path}",
                    evidence_id=record.id,
                )
            )
            continue
        payload = path.read_bytes()
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash.casefold() != record.sha256.casefold():
            findings.append(
                Finding(
                    "archive.hash_mismatch",
                    f"hash mismatch for {record.path}",
                    evidence_id=record.id,
                )
            )
        media_type = sniff_media_type(payload)
        if media_type == "text/html":
            findings.append(
                Finding(
                    "archive.html_payload",
                    f"{record.path} is an HTML login/error page",
                    evidence_id=record.id,
                )
            )
        elif media_type != record.media_type:
            findings.append(
                Finding(
                    "archive.media_type_mismatch",
                    f"{record.path} is {media_type}, indexed as {record.media_type}",
                    evidence_id=record.id,
                )
            )

    basis_refs = _basis_refs(project)
    for part in pcb_inventory:
        records = _records_for_part(index.records, part)
        roles = {role for record in records for role in record.roles}
        if (
            part.requires_datasheet
            and EvidenceRole.DATASHEET not in roles
            and not _waived(project, part.reference, "datasheet")
        ):
            findings.append(
                Finding(
                    "part.missing_datasheet",
                    f"{part.reference} ({part.part_number}) has no datasheet evidence",
                    reference=part.reference,
                )
            )
        if part.requires_reference:
            references = [
                record for record in records if EvidenceRole.REFERENCE_DESIGN in record.roles
            ]
            trusted = [
                record
                for record in references
                if record.trust_tier in TRUSTED_REFERENCE_TIERS
            ]
            if references and not trusted:
                findings.append(
                    Finding(
                        "part.untrusted_reference",
                        f"{part.reference} has only teaching-level reference evidence",
                        reference=part.reference,
                    )
                )
            elif not references and not _waived(project, part.reference, "reference"):
                findings.append(
                    Finding(
                        "part.missing_reference",
                        f"{part.reference} ({part.part_number}) has no reference design",
                        reference=part.reference,
                    )
                )
            if (
                part.reference.casefold() not in basis_refs
                and not _waived(project, part.reference, "basis")
            ):
                findings.append(
                    Finding(
                        "part.missing_basis",
                        f"{part.reference} has no sourced and decided design-basis row",
                        reference=part.reference,
                    )
                )
        if part.is_module and not roles.intersection(
            {EvidenceRole.INTEGRATION_MANUAL, EvidenceRole.MODULE_PINOUT}
        ):
            findings.append(
                Finding(
                    "part.missing_module_document",
                    f"{part.reference} module needs a pinout or integration manual",
                    reference=part.reference,
                )
            )
    return findings
