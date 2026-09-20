import hashlib
import importlib
import shutil
import sys

import pytest

from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.evidence.migrate import (
    EvidenceMigrationError,
    migrate_legacy_evidence,
)
from pcb_copilot.evidence.models import EvidenceRole
from pcb_copilot.project import load_project


def _write_project(root):
    root.mkdir()
    (root / "project.yaml").write_text(
        """schema_version: 1
name: migration-fixture
lifecycle: DRAFT
design:
  schematic: fixture.kicad_sch
  pcb: fixture.kicad_pcb
  netmap: netmap.json
evidence:
  index: evidence/index.yaml
manufacturing:
  profile: test
""",
        encoding="utf-8",
    )
    return root


def _legacy_sensor_project(tmp_path):
    root = _write_project(tmp_path / "migration-fixture")
    datasheets = root / "datasheets"
    references = root / "reference-designs"
    datasheets.mkdir()
    references.mkdir()
    (datasheets / "BMP390.pdf").write_bytes(b"%PDF-1.7\ndatasheet")
    (references / "BMP390.sch").write_bytes(b"<eagle>schematic</eagle>")
    (references / "BMP390.brd").write_bytes(b"<eagle>board</eagle>")
    (datasheets / "INDEX.md").write_text(
        "U1, BMP390 -> BMP390.pdf # https://example.test/BMP390.pdf | fetched 2026-08-25\n",
        encoding="utf-8",
    )
    (references / "INDEX.md").write_text(
        "BMP390 -> BMP390.sch # https://github.com/example/BMP390.sch | fetched 2026-08-25\n"
        "BMP390 -> BMP390.brd # https://github.com/example/BMP390.brd | fetched 2026-08-25\n",
        encoding="utf-8",
    )
    return root


def test_dry_run_does_not_change_project(tmp_path, tree_hash):
    project_root = _legacy_sensor_project(tmp_path)
    before = tree_hash(project_root)

    report = migrate_legacy_evidence(load_project(project_root), dry_run=True)

    assert report.records_created == 3
    assert tree_hash(project_root) == before


def test_tms_duplicate_module_documents_become_multi_role_records(tmp_path, tree_hash):
    destination = _write_project(tmp_path / "tms-v3")
    datasheets = destination / "datasheets"
    references = destination / "reference-designs"
    datasheets.mkdir()
    references.mkdir()
    xbee = b"%PDF-1.7\nxbee"
    teensy = b"%PDF-1.7\nteensy"
    (datasheets / "xbee3_hardware_ref.pdf").write_bytes(xbee)
    (references / "XBee_90001543.pdf").write_bytes(xbee)
    (datasheets / "card11a_rev4_web.pdf").write_bytes(teensy)
    (references / "TEENSY_card11a_rev4_web.pdf").write_bytes(teensy)
    (datasheets / "INDEX.md").write_text(
        "J9, XBEE3 -> xbee3_hardware_ref.pdf # https://vendor.test/xbee.pdf | fetched 2026-08-25\n"
        "J7, TEENSY -> card11a_rev4_web.pdf # https://vendor.test/teensy.pdf | fetched 2026-08-25\n",
        encoding="utf-8",
    )
    (references / "INDEX.md").write_text(
        "J9, XBEE3 -> XBee_90001543.pdf # https://vendor.test/xbee.pdf | fetched 2026-08-25\n"
        "J7, TEENSY -> TEENSY_card11a_rev4_web.pdf # https://vendor.test/teensy.pdf | fetched 2026-08-25\n",
        encoding="utf-8",
    )
    before = tree_hash(destination)

    report = migrate_legacy_evidence(load_project(destination), dry_run=True)

    xbee_hash = hashlib.sha256(xbee).hexdigest()
    teensy_hash = hashlib.sha256(teensy).hexdigest()
    by_hash = {record.sha256: record for record in report.records}
    assert by_hash[xbee_hash].roles >= {
        EvidenceRole.DATASHEET,
        EvidenceRole.REFERENCE_DESIGN,
        EvidenceRole.MODULE_PINOUT,
    }
    assert by_hash[teensy_hash].roles >= {
        EvidenceRole.DATASHEET,
        EvidenceRole.REFERENCE_DESIGN,
        EvidenceRole.MODULE_PINOUT,
    }
    assert report.duplicates_merged == 2
    assert tree_hash(destination) == before


def test_apply_writes_verified_index_then_removes_legacy_archives(tmp_path):
    project_root = _legacy_sensor_project(tmp_path)
    project = load_project(project_root)

    report = migrate_legacy_evidence(project, dry_run=False)

    index = load_evidence_index(project.evidence_index_path)
    assert len(index.records) == report.records_created == 3
    for record in index.records:
        path = project.evidence_index_path.parent / record.path
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record.sha256
    assert not (project_root / "datasheets").exists()
    assert not (project_root / "reference-designs").exists()


def test_missing_legacy_target_aborts_without_changes(tmp_path, tree_hash):
    project_root = _legacy_sensor_project(tmp_path)
    missing = project_root / "datasheets/BMP390.pdf"
    missing.unlink()
    before = tree_hash(project_root)

    with pytest.raises(EvidenceMigrationError, match="missing"):
        migrate_legacy_evidence(load_project(project_root), dry_run=False)

    assert tree_hash(project_root) == before
    assert not (project_root / "evidence").exists()


@pytest.mark.parametrize("board", ["baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3"])
def test_evidence_gate_results_match_before_and_after_migration(
    board, tmp_path, repo_root
):
    destination = tmp_path / board
    shutil.copytree(repo_root / "projects" / board, destination)
    sys.path.insert(0, str(repo_root / "scripts"))
    datasheets = importlib.import_module("check_datasheets")
    research = importlib.import_module("check_research")
    pcb = destination / f"{board}.kicad_pcb"
    if (destination / "datasheets").exists():
        migrate_legacy_evidence(load_project(destination), dry_run=False)

    assert datasheets.check(pcb)[0]
    assert all(item["ok"] for item in research.run(pcb))


def test_migrated_utf8_signoff_is_readable(repo_root):
    sys.path.insert(0, str(repo_root / "scripts"))
    run_gates = importlib.import_module("run_gates")
    pcb = repo_root / "projects/tms-v3/tms-v3.kicad_pcb"

    ok, detail = run_gates.gate_signoff(pcb)

    assert not ok
    assert "signed" in detail


def test_project_template_uses_unified_evidence_layout(repo_root):
    template = repo_root / "projects" / "template"

    assert (template / "evidence" / "index.yaml").is_file()
    assert not (template / "datasheets").exists()
    assert not (template / "reference-designs").exists()
