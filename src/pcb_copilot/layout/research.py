"""Advisory reference preflight and source snapshot for placement drafts.

This consumes existing evidence checks and authoritative narrative records.
It does not search the web, inspect copper visually, or decide applicability.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path

import sexpdata
from kicad_claude.adapters import sch_io

from pcb_copilot.evidence.checks import (
    TRUSTED_REFERENCE_TIERS,
    Finding,
    Part,
    _records_for_part,
    check_evidence,
)
from pcb_copilot.evidence.index import EvidenceFormatError, load_evidence_index
from pcb_copilot.evidence.models import EvidenceRole
from pcb_copilot.models import Project


@dataclass(frozen=True)
class ResearchSnapshot:
    findings: list[Finding]
    files: dict[Path, bytes]
    appendix: str

    def write(self, root: Path) -> None:
        """Write only into the caller's unpublished draft transaction."""
        for relative, payload in self.files.items():
            destination = root / relative
            destination.resolve().relative_to(root.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        basis = self.files.get(Path("DESIGN_BASIS.md"), b"# Draft design basis\n")
        (root / "DESIGN_BASIS.md").write_bytes(basis + self.appendix.encode("utf-8"))


def _native_kind(payload: bytes) -> str:
    """Recognize source content, without interpreting its layout as approved."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        try:
            root = sexpdata.loads(payload.decode("utf-8"))
            head = sch_io.head_of(root)
        except (
            ValueError,
            UnicodeError,
            AssertionError,
            sexpdata.ExpectClosingBracket,
            sexpdata.ExpectNothing,
            sexpdata.ExpectSExp,
        ):
            return "unclassified document"
        return {
            "kicad_pcb": "PCB native source",
            "kicad_sch": "schematic native source",
        }.get(head, "unclassified document")
    if root.tag == "eagle":
        if root.find("drawing/board") is not None:
            return "PCB native source"
        if root.find("drawing/schematic") is not None:
            return "schematic native source"
    return "unclassified document"


def prepare_layout_research(project: Project) -> ResearchSnapshot:
    # Reuse the legacy research inventory's key-part criteria, including its
    # module detection and legacy footprint reference spelling support.
    docs = str(Path(__file__).resolve().parents[3] / "docs")
    if docs not in sys.path:
        sys.path.insert(0, docs)
    legacy = importlib.import_module("check_research")
    inventory = legacy.inventory(project.pcb_path.read_text(encoding="utf-8"))
    parts = [
        Part(
            reference=ref,
            part_number=value,
            requires_datasheet=False,
            requires_reference=True,
            is_module=any(hint in value.lower() for hint in legacy.MODULE_HINTS),
        )
        for ref, value, _pads, _lcsc, key in inventory
        if key
    ]
    try:
        checks = check_evidence(project, parts)
    except (OSError, ValueError) as exc:
        checks = [Finding("check_unavailable", str(exc))]
    findings = [
        replace(f, code=f"layout.research.{f.code}", severity="review") for f in checks
    ]
    bad_ids = {f.evidence_id for f in checks if f.evidence_id}
    files: dict[Path, bytes] = {}

    def snapshot(source: Path, *, evidence_id: str | None = None) -> bytes | None:
        try:
            source.resolve().relative_to(project.root.resolve())
            if evidence_id:
                source.resolve().relative_to(
                    project.evidence_index_path.parent.resolve()
                )
            payload = source.read_bytes()
        except (OSError, ValueError) as exc:
            findings.append(
                Finding(
                    "layout.research.snapshot_unavailable",
                    f"Cannot snapshot {source.name}: {exc}",
                    evidence_id=evidence_id,
                    severity="review",
                )
            )
            return None
        files[source.relative_to(project.root)] = payload
        return payload

    basis = project.root / "DESIGN_BASIS.md"
    if not basis.is_file() or snapshot(basis) is None:
        findings.append(
            Finding(
                "layout.research.basis_missing",
                "No authoritative DESIGN_BASIS.md was available; design choices remain unresolved",
                severity="review",
            )
        )
    review = project.root / "REFERENCE_REVIEW.md"
    has_review = review.is_file() and snapshot(review) is not None
    if not has_review:
        findings.append(
            Finding(
                "layout.research.review_missing",
                "No REFERENCE_REVIEW.md inspection record was available; archived files do not establish copper inspection",
                severity="review",
            )
        )
    index_path = project.evidence_index_path
    if index_path.is_file():
        snapshot(index_path)
    try:
        index = load_evidence_index(index_path)
        records = index.records
    except EvidenceFormatError:
        records = ()  # Existing check_evidence findings carry the exact reason.

    kinds = {}
    source_lines = []
    for record in records:
        payload = snapshot(index_path.parent / record.path, evidence_id=record.id)
        if (
            payload is not None
            and hashlib.sha256(payload).hexdigest() != record.sha256.lower()
        ):
            if record.id not in bad_ids:
                findings.append(
                    Finding(
                        "layout.research.archive.hash_mismatch",
                        f"Snapshot hash mismatch for {record.path}",
                        evidence_id=record.id,
                        severity="review",
                    )
                )
            bad_ids.add(record.id)
        verified = (
            payload is not None
            and record.id not in bad_ids
            and not any(
                f.code in {"index.missing", "index.invalid", "check_unavailable"}
                for f in checks
            )
        )
        is_reference = EvidenceRole.REFERENCE_DESIGN in record.roles
        trusted = record.trust_tier in TRUSTED_REFERENCE_TIERS
        kind = (
            _native_kind(payload)
            if verified and is_reference
            else "unclassified document"
        )
        if verified and is_reference and trusted:
            kinds[record.id] = kind
        if is_reference:
            state = (
                "integrity verified"
                if verified
                else "unverified; excluded from source coverage"
            )
            source_lines.append(
                f"- `{record.id}` — `{index_path.relative_to(project.root).parent / record.path}`: "
                f"{kind}; {state}; trust tier `{record.trust_tier.value}`. "
                f"Source URL: {record.source_url or 'not recorded'}."
            )
    for part in parts:
        available = {
            kinds[r.id] for r in _records_for_part(records, part) if r.id in kinds
        }
        if "PCB native source" not in available:
            unknown = "unclassified document" in available
            findings.append(
                Finding(
                    "layout.research.pcb_source_unconfirmed"
                    if unknown
                    else "layout.research.pcb_source_missing",
                    f"{part.reference} ({part.part_number}): no verified matching native PCB reference identified; "
                    + (
                        "archived documents/PDFs require visual classification and may contain layout references"
                        if unknown
                        else "schematic-only evidence does not establish a PCB layout reference"
                    ),
                    reference=part.reference,
                    severity="review",
                )
            )
    findings.append(
        Finding(
            "layout.research.comparison_required",
            "Compare this proposal with the reference copper/layout and record adopted choices or justified differences; "
            "archive availability does not establish inspection or applicability",
            severity="review",
        )
    )
    lines = [
        "\n\n## Placement research checkpoint (draft only)\n",
        (
            "Existing design-basis content above is carried from the authoritative project record. "
            "No new adopted choices or justified differences were inferred from placement geometry. "
            "Prior Match/Deviate rows describe the accepted design and are not revalidated for this draft.\n"
        ),
        (
            "Research is advisory during drafting; release research requirements remain unchanged. "
            "This preflight checks archive integrity and source type, and does not establish inspection or applicability.\n"
        ),
        (
            "The existing REFERENCE_REVIEW.md was copied unchanged, including its inspection claims and limits. "
            "Its presence is not machine approval of inspection, reference applicability or this proposal.\n"
            if has_review
            else "No reference inspection narrative was available for this draft.\n"
        ),
        "### Indexed reference sources\n",
        "\n".join(source_lines) or "No indexed reference sources could be evaluated.",
        "\n### Open research findings\n",
        *[f"- `{f.code}`: {f.message}" for f in findings],
        "",
    ]
    return ResearchSnapshot(findings, files, "\n".join(lines))
