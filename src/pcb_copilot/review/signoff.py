"""Project-specific human decisions bound to exact current design bytes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

import yaml

from pcb_copilot.models import Project
from pcb_copilot.review.fingerprint import pcb_digest, schematic_digest
from pcb_copilot.review.models import CheckResult, CheckScope, FindingKind


@dataclass(frozen=True)
class ReviewItem:
    id: str
    prompt: str
    rationale: str
    evidence_refs: tuple[str, ...]
    safety_tags: tuple[str, ...]


@dataclass(frozen=True)
class ReviewProfile:
    items: tuple[ReviewItem, ...]


@dataclass(frozen=True)
class SignoffRecord:
    item_id: str
    reviewer: str
    signed_on: date
    decision: Literal['accepted', 'rejected']
    note: str
    schematic_hash: str
    pcb_hash: str
    profile_hash: str


SCOPE = CheckScope(
    proves='named, dated, project-specific decisions match the exact current design and review profile',
    does_not_prove='the reviewer inspected correctly, measured hardware, or made a safe decision',
    deterministic=True,
    requires_external_tool=False,
)


def profile_digest(root: Path) -> str:
    return hashlib.sha256((root / 'review-profile.yaml').read_bytes()).hexdigest()


def load_review_profile(root: Path) -> ReviewProfile:
    document = yaml.safe_load((root / 'review-profile.yaml').read_text(encoding='utf-8'))
    if not isinstance(document, dict) or document.get('schema_version') != 1:
        raise ValueError('invalid review-profile.yaml schema')
    raw_items = document.get('items')
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError('review profile has no items')
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise TypeError('review profile item is not a mapping')
        item = ReviewItem(
            id=str(raw['id']), prompt=str(raw['prompt']),
            rationale=str(raw['rationale']),
            evidence_refs=tuple(raw.get('evidence_refs', ())),
            safety_tags=tuple(raw.get('safety_tags', ())),
        )
        if not item.id or not item.prompt or not item.rationale:
            raise ValueError('review profile has an empty required field')
        items.append(item)
    if len({item.id for item in items}) != len(items):
        raise ValueError('review profile has duplicate item IDs')
    return ReviewProfile(tuple(items))


def prepare_signoff(project: Project) -> Path:
    """Create an unsigned, current-hash template without replacing decisions."""
    profile = load_review_profile(project.root)
    schematic = schematic_digest(project.schematic_path)
    pcb = pcb_digest(project.pcb_path)
    profile_hash = profile_digest(project.root)
    document = {
        'schema_version': 1,
        'records': [
            {
                'item_id': item.id, 'prompt': item.prompt,
                'reviewer': '', 'signed_on': '', 'decision': '', 'note': '',
                'schematic_hash': schematic, 'pcb_hash': pcb,
                'profile_hash': profile_hash,
            }
            for item in profile.items
        ],
    }
    path = project.root / 'review-signoff.yaml'
    rendered = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    with path.open('x', encoding='utf-8') as output:
        output.write(rendered)
    return path


def _load_records(root: Path) -> tuple[SignoffRecord, ...]:
    path = root / 'review-signoff.yaml'
    if not path.exists():
        return ()
    document = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or document.get('schema_version') != 1:
        raise ValueError('invalid review-signoff.yaml schema')
    records = []
    for raw in document.get('records', []):
        if not isinstance(raw, dict):
            raise TypeError('sign-off record is not a mapping')
        if not any(str(raw.get(key, '')).strip() for key in (
            'reviewer', 'signed_on', 'decision', 'note',
        )):
            continue
        signed_on = date.fromisoformat(str(raw['signed_on']))
        if signed_on > datetime.now(UTC).date() + timedelta(days=1):
            raise ValueError('future-dated sign-off is invalid')
        decision = raw['decision']
        if decision not in {'accepted', 'rejected'}:
            raise ValueError('sign-off decision must be accepted or rejected')
        record = SignoffRecord(
            item_id=str(raw['item_id']), reviewer=str(raw['reviewer']).strip(),
            signed_on=signed_on, decision=decision, note=str(raw['note']).strip(),
            schematic_hash=str(raw['schematic_hash']), pcb_hash=str(raw['pcb_hash']),
            profile_hash=str(raw['profile_hash']),
        )
        if not record.reviewer or not record.note:
            raise ValueError('sign-off reviewer and note are required')
        records.append(record)
    if len({record.item_id for record in records}) != len(records):
        raise ValueError('duplicate sign-off decisions for an item')
    return tuple(records)


@dataclass(frozen=True)
class SignoffCheck:
    check_id: str = 'signoff'
    scope: CheckScope = SCOPE

    def run(self, project: Project) -> CheckResult:
        profile = load_review_profile(project.root)
        records = {record.item_id: record for record in _load_records(project.root)}
        unknown = sorted(set(records) - {item.id for item in profile.items})
        if unknown:
            raise ValueError(f'sign-off records have unknown items: {", ".join(unknown)}')
        schematic = schematic_digest(project.schematic_path)
        pcb = pcb_digest(project.pcb_path)
        profile_hash = profile_digest(project.root)
        open_items = []
        for item in profile.items:
            record = records.get(item.id)
            if record is None:
                open_items.append(f'{item.id} unsigned')
            elif record.decision == 'rejected':
                open_items.append(f'{item.id} rejected')
            elif (record.schematic_hash, record.pcb_hash, record.profile_hash) != (
                schematic, pcb, profile_hash,
            ):
                open_items.append(f'{item.id} stale')
        detail = (f'{len(profile.items) - len(open_items)}/{len(profile.items)} current decisions'
                  + (': ' + '; '.join(open_items) if open_items else ''))
        return CheckResult(self.check_id, not open_items, detail, self.scope,
                           FindingKind.HUMAN_DECISION)
