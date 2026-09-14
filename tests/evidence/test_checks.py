import hashlib
import importlib
import shutil
import sys
from datetime import date

from pcb_copilot.evidence.checks import Part, check_evidence
from pcb_copilot.evidence.index import save_evidence_index
from pcb_copilot.evidence.models import (
    EvidenceIndex,
    EvidenceRecord,
    EvidenceRole,
    TrustTier,
)
from pcb_copilot.project import load_project


def _part(*, module: bool = False) -> Part:
    return Part(
        reference="U1",
        part_number="BMP390",
        requires_datasheet=True,
        requires_reference=True,
        is_module=module,
    )


def _write_index(
    project_copy,
    *,
    roles=frozenset({EvidenceRole.DATASHEET, EvidenceRole.REFERENCE_DESIGN}),
    trust=TrustTier.PROVEN_OPEN_HARDWARE,
):
    evidence = project_copy / "evidence"
    shutil.rmtree(evidence, ignore_errors=True)
    source = evidence / "files" / "BMP390.pdf"
    source.parent.mkdir(parents=True)
    payload = b"%PDF-1.7\nchecker fixture"
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    record = EvidenceRecord(
        id=f"sha256:{digest}",
        manufacturer="Bosch",
        part_numbers={"BMP390"},
        title="BMP390 evidence",
        revision="1.7",
        source_url="https://example.test/BMP390.pdf",
        retrieved_on=date(2026, 9, 14),
        path="files/BMP390.pdf",
        sha256=digest,
        media_type="application/pdf",
        roles=roles,
        trust_tier=trust,
        component_refs={"U1"},
    )
    save_evidence_index(EvidenceIndex(schema_version=1, records=[record]), evidence / "index.yaml")
    return source


def _codes(project_copy, parts=None):
    project = load_project(project_copy)
    return {finding.code for finding in check_evidence(project, parts or [_part()])}


def test_complete_evidence_has_no_findings(project_copy):
    _write_index(project_copy)
    assert _codes(project_copy) == set()


def test_missing_archived_file_is_reported(project_copy):
    source = _write_index(project_copy)
    source.unlink()
    assert "archive.missing_file" in _codes(project_copy)


def test_wrong_hash_and_html_payload_are_reported(project_copy):
    source = _write_index(project_copy)
    source.write_bytes(b"<!doctype html><body>Sign in</body>")
    assert _codes(project_copy) >= {"archive.hash_mismatch", "archive.html_payload"}


def test_missing_source_url_is_reported_as_a_finding(project_copy):
    _write_index(project_copy)
    index_path = project_copy / "evidence" / "index.yaml"
    text = index_path.read_text(encoding="utf-8")
    index_path.write_text(
        text.replace("source_url: https://example.test/BMP390.pdf", "source_url: null"),
        encoding="utf-8",
    )
    assert "archive.missing_source_url" in _codes(project_copy)


def test_roles_do_not_substitute_for_each_other(project_copy):
    _write_index(project_copy, roles=frozenset({EvidenceRole.DATASHEET}))
    assert "part.missing_reference" in _codes(project_copy)

    shutil.rmtree(project_copy / "evidence")
    _write_index(project_copy, roles=frozenset({EvidenceRole.REFERENCE_DESIGN}))
    assert "part.missing_datasheet" in _codes(project_copy)


def test_teaching_reference_is_not_accepted_as_design_evidence(project_copy):
    _write_index(project_copy, trust=TrustTier.TEACHING_REFERENCE)
    assert "part.untrusted_reference" in _codes(project_copy)


def test_module_requires_pinout_or_integration_manual(project_copy):
    _write_index(project_copy)
    assert "part.missing_module_document" in _codes(project_copy, [_part(module=True)])


def test_missing_basis_row_is_reported(project_copy):
    _write_index(project_copy)
    (project_copy / "DESIGN_BASIS.md").write_text("# Design basis\n", encoding="utf-8")
    assert "part.missing_basis" in _codes(project_copy)


def test_numbered_rule_deviation_cannot_waive_missing_reference(project_copy):
    _write_index(project_copy, roles=frozenset({EvidenceRole.DATASHEET}))
    (project_copy / "DEVIATIONS.md").write_text(
        "# Deviations\n\n## Declared\n\nU1.1 | 2.2 | intentional geometry\n",
        encoding="utf-8",
    )
    assert "part.missing_reference" in _codes(project_copy)


def test_legacy_gate_entry_points_consume_unified_index(project_copy, repo_root):
    _write_index(project_copy)
    shutil.rmtree(project_copy / "datasheets", ignore_errors=True)
    shutil.rmtree(project_copy / "reference-designs", ignore_errors=True)
    sys.path.insert(0, str(repo_root / "docs"))
    datasheets = importlib.import_module("check_datasheets")
    research = importlib.import_module("check_research")
    pcb = project_copy / "baro-bmp390.kicad_pcb"

    datasheet_ok, _ = datasheets.check(pcb)
    research_results = research.run(pcb)

    assert datasheet_ok
    assert next(
        item["ok"] for item in research_results if "reference designs" in item["name"]
    )
    assert next(
        item["ok"] for item in research_results if "archive integrity" in item["name"]
    )
