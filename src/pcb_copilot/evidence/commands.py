"""Human-facing research operations built on the evidence primitives."""

from __future__ import annotations

import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from pcb_copilot.evidence.archive import archive_document
from pcb_copilot.evidence.checks import check_evidence
from pcb_copilot.evidence.extract import extract_eagle_connections
from pcb_copilot.evidence.facts import EvidenceFact
from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.evidence.models import EvidenceRole, TrustTier
from pcb_copilot.evidence.references import inspect_eagle_pair
from pcb_copilot.models import Project

Downloader = Callable[[str], bytes]


@dataclass(frozen=True)
class ResearchResult:
    headline: str
    machine_failures: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()
    review_required: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    proposed_rows: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        return 1 if self.machine_failures or self.conflicts else 0


def download_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "pcb-copilot/0.1 evidence-archiver"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def verify_evidence(project: Project) -> ResearchResult:
    findings = check_evidence(project, ())
    failures = tuple(f"{item.code}: {item.message}" for item in findings)
    count = 0
    if not failures:
        count = len(load_evidence_index(project.evidence_index_path).records)
    return ResearchResult(
        headline=f"{count} evidence record(s) verified",
        machine_failures=failures,
        review_required=(
            "Archive integrity does not prove circuit completeness or engineering correctness.",
        ),
    )


def verify_schematic_evidence(project: Project) -> ResearchResult:
    """Require actual selected-part identity coverage, also for passives."""
    from pcb_copilot.evidence.schematic_inventory import schematic_parts

    parts = schematic_parts(project, include_passives=True)
    findings = check_evidence(project, ())
    failures = [f'{item.code}: {item.message}' for item in findings]
    index = load_evidence_index(project.evidence_index_path)
    required = [part for part in parts if part.requires_datasheet or part.is_module]
    for part in required:
        records = [record for record in index.records if any(
            _normal(number) == _normal(part.part_number) for number in record.part_numbers)]
        roles = {role for record in records for role in record.roles}
        if part.requires_datasheet and EvidenceRole.DATASHEET not in roles:
            failures.append(f'{part.reference} ({part.part_number}): selected-part datasheet missing; '
                            'a reference-only association is insufficient')
        if part.is_module and not roles.intersection(
            {EvidenceRole.MODULE_PINOUT, EvidenceRole.INTEGRATION_MANUAL}
        ):
            failures.append(f'{part.reference} ({part.part_number}): selected module pinout/manual missing')
    return ResearchResult(
        headline=f'{len(parts)} physical schematic parts; {len(required)} require selected-part evidence',
        machine_failures=tuple(failures),
        review_required=(('Coverage and archive identity do not verify pin interpretation, component values, '
                          'circuit performance or physical fit.'),),
    )


def add_evidence(
    project: Project,
    part_number: str,
    url: str,
    role: EvidenceRole,
    *,
    downloader: Downloader = download_url,
    trust_tier: TrustTier = TrustTier.MANUFACTURER,
) -> ResearchResult:
    payload = downloader(url)
    record = archive_document(
        project,
        part_number,
        url,
        {role},
        payload,
        datetime.now(timezone.utc).date(),
        trust_tier=trust_tier,
    )
    return ResearchResult(
        headline=f"ARCHIVED {record.id} as evidence/{record.path}",
        review_required=(
            "Confirm the document identity, revision, role, and applicability before citing it.",
        ),
    )


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def inspect_reference_pair(project: Project, schematic_id: str, board_id: str) -> dict:
    """Inspect two indexed sources only after checking their archived bytes."""
    index = load_evidence_index(project.evidence_index_path)
    selected = []
    for evidence_id in (schematic_id, board_id):
        record = next((r for r in index.records if r.id == evidence_id), None)
        if record is None or EvidenceRole.REFERENCE_DESIGN not in record.roles:
            raise ValueError(f'{evidence_id} is not an indexed reference design')
        selected.append(record)
    failures = [f for f in check_evidence(project, ())
                if f.evidence_id in {schematic_id, board_id}]
    if failures:
        raise ValueError('; '.join(f.message for f in failures))
    schematic, board = selected
    if not {_normal(p) for p in schematic.part_numbers}.intersection(
        _normal(p) for p in board.part_numbers
    ):
        raise ValueError('reference pair has no common indexed part identity')
    result = inspect_eagle_pair(project.evidence_index_path.parent / schematic.path,
                                project.evidence_index_path.parent / board.path)
    result['provenance'] = [r.model_dump(mode='json') for r in selected]
    return result


def _conflicts(facts: list[tuple[EvidenceFact, str]]) -> tuple[str, ...]:
    grouped: dict[tuple[str, str], set[str]] = {}
    for fact, _citation in facts:
        grouped.setdefault((fact.subject, fact.predicate), set()).add(fact.value)
    return tuple(
        f"{subject} {predicate}: {', '.join(sorted(values))}"
        for (subject, predicate), values in sorted(grouped.items())
        if len(values) > 1
    )


def extract_evidence(project: Project, part_number: str) -> ResearchResult:
    try:
        index = load_evidence_index(project.evidence_index_path)
    except ValueError as exc:
        return ResearchResult(
            headline=f"No facts extracted for {part_number}",
            machine_failures=(str(exc),),
        )

    wanted = _normal(part_number)
    records = tuple(
        record
        for record in index.records
        if any(_normal(number) == wanted for number in record.part_numbers)
    )
    if not records:
        return ResearchResult(
            headline=f"No facts extracted for {part_number}",
            machine_failures=(f"no indexed evidence matches {part_number}",),
        )

    extracted: list[tuple[EvidenceFact, str]] = []
    review = []
    failures = []
    for record in records:
        source = project.evidence_index_path.parent / record.path
        citation_root = f"evidence/{record.path}"
        if record.media_type == "application/vnd.eagle+xml" and source.suffix.lower() == ".sch":
            try:
                facts = extract_eagle_connections(source, part_number)
            except (OSError, ValueError) as exc:
                failures.append(f"{citation_root}: {exc}")
                continue
            for fact in facts:
                pages = ",".join(str(page) for page in fact.pages) or "n/a"
                extracted.append((fact, f"{citation_root}:page {pages}"))
        else:
            review.append(
                f"{citation_root}: {record.media_type} requires human visual/text review"
            )

    rendered_facts = tuple(
        f"{fact.subject} {fact.predicate} {fact.value}"
        f"{(' ' + fact.unit) if fact.unit else ''} [{citation}]"
        for fact, citation in extracted
    )
    proposed = tuple(
        f"| {fact.subject} | {part_number} | {fact.predicate} | <ours> | "
        f"{fact.value} | {citation} | <Match / Deviate: reason> |"
        for fact, citation in extracted
        if fact.predicate == "connected_net"
    )
    return ResearchResult(
        headline=f"{len(extracted)} cited fact(s) extracted for {part_number}",
        machine_failures=tuple(failures),
        facts=rendered_facts,
        review_required=tuple(review),
        conflicts=_conflicts(extracted),
        proposed_rows=proposed,
    )


def render_research_result(result: ResearchResult) -> str:
    sections = [result.headline]
    for title, items in (
        ("MACHINE FAILURES", result.machine_failures),
        ("EXTRACTED FACTS", result.facts),
        ("REVIEW REQUIRED", result.review_required),
        ("CONFLICTS", result.conflicts),
        ("PROPOSED DESIGN_BASIS ROWS", result.proposed_rows),
    ):
        sections.append(f"\n{title}:" + ("\n- " + "\n- ".join(items) if items else " none"))
    return "\n".join(sections)
