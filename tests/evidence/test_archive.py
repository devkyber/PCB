import importlib
import shutil
import sys
from datetime import date

import pytest

from pcb_copilot.evidence.archive import (
    InvalidEvidencePayload,
    archive_document,
    sniff_media_type,
)
from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.evidence.models import EvidenceRole
from pcb_copilot.project import load_project


def test_archived_eagle_board_keeps_board_extension(project_copy):
    project = load_project(project_copy)
    record = archive_document(
        project, 'FIXTURE', 'https://example.test/reference.brd',
        {EvidenceRole.REFERENCE_DESIGN}, b'<eagle><drawing><board/></drawing></eagle>',
        date(2026, 9, 16),
    )
    assert record.path.endswith('.brd')


def _without_unified_evidence(project_copy):
    shutil.rmtree(project_copy / "evidence", ignore_errors=True)
    return load_project(project_copy)


@pytest.mark.parametrize(
    ("payload", "media_type"),
    [
        (b"%PDF-1.7\nfixture", "application/pdf"),
        (b"<?xml version='1.0'?><eagle><drawing/></eagle>", "application/vnd.eagle+xml"),
        (b"(kicad_sch (version 20250114))", "application/x-kicad-schematic"),
        (b"ordinary engineering notes\n", "text/plain"),
    ],
)
def test_sniff_media_type_uses_payload_not_filename(payload, media_type):
    assert sniff_media_type(payload) == media_type


@pytest.mark.parametrize(
    "payload",
    [
        b"<html><title>Login</title></html>",
        b"<!doctype html><body>Access denied</body>",
    ],
)
def test_archive_rejects_html_named_pdf(project_copy, tree_hash, payload):
    project = _without_unified_evidence(project_copy)
    before = tree_hash(project_copy)

    with pytest.raises(InvalidEvidencePayload, match="HTML"):
        archive_document(
            project,
            "BMP390",
            "https://example.test/BMP390.pdf",
            {EvidenceRole.DATASHEET},
            payload,
            date(2026, 9, 14),
        )

    assert tree_hash(project_copy) == before


def test_pdf_claim_rejects_non_pdf_bytes_without_creating_evidence(project_copy):
    project = _without_unified_evidence(project_copy)

    with pytest.raises(InvalidEvidencePayload, match="claims PDF"):
        archive_document(
            project,
            "BMP390",
            "https://example.test/BMP390.pdf",
            {EvidenceRole.DATASHEET},
            b"plain text instead",
            date(2026, 9, 14),
        )

    assert not (project_copy / "evidence").exists()


def test_archive_writes_hashed_bytes_and_index(project_copy):
    project = _without_unified_evidence(project_copy)
    payload = b"%PDF-1.7\nfixture"

    record = archive_document(
        project,
        "BMP390",
        "https://example.test/BMP390-rev-1.pdf?download=1",
        {EvidenceRole.DATASHEET},
        payload,
        date(2026, 9, 14),
        component_refs={"U1"},
    )

    archived = project_copy / "evidence" / record.path
    assert archived.read_bytes() == payload
    assert archived.name.startswith("BMP390_")
    assert archived.suffix == ".pdf"
    assert record.id == f"sha256:{record.sha256}"
    assert load_evidence_index(project.evidence_index_path).records == (record,)


def test_same_bytes_merge_roles_parts_and_refs_without_duplicate_file(project_copy):
    project = _without_unified_evidence(project_copy)
    payload = b"%PDF-1.7\nshared manual"
    first = archive_document(
        project,
        "XBee 3",
        "https://example.test/xbee.pdf",
        {EvidenceRole.DATASHEET},
        payload,
        date(2026, 9, 14),
        component_refs={"J9"},
    )
    second = archive_document(
        project,
        "XB3-24Z8",
        "https://example.test/xbee.pdf",
        {EvidenceRole.MODULE_PINOUT},
        payload,
        date(2026, 9, 14),
        component_refs={"J10"},
    )

    index = load_evidence_index(project.evidence_index_path)
    assert second.id == first.id
    assert len(index.records) == 1
    assert index.records[0].roles == frozenset(
        {EvidenceRole.DATASHEET, EvidenceRole.MODULE_PINOUT}
    )
    assert index.records[0].part_numbers == frozenset({"XBee 3", "XB3-24Z8"})
    assert index.records[0].component_refs == frozenset({"J9", "J10"})
    assert len(list((project_copy / "evidence" / "files").iterdir())) == 1


def test_legacy_add_command_archives_to_unified_index(
    project_copy, repo_root, monkeypatch
):
    _without_unified_evidence(project_copy)
    sys.path.insert(0, str(repo_root / "scripts"))
    collect = importlib.import_module("collect_references")
    monkeypatch.setattr(collect, "verify_url", lambda _url: (True, "200"))
    monkeypatch.setattr(
        collect,
        "_download_bytes",
        lambda _url: b"%PDF-1.7\ncompatibility fixture",
        raising=False,
    )

    result = collect.cmd_add(
        project_copy,
        "BMP390",
        "https://example.test/BMP390.pdf",
        "datasheet",
        "compatibility test",
    )

    assert result == 0
    index = load_evidence_index(project_copy / "evidence" / "index.yaml")
    assert len(index.records) == 1
    assert index.records[0].roles == frozenset({EvidenceRole.DATASHEET})
