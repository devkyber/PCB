import hashlib

from pcb_copilot.evidence.extract import (
    extract_eagle_connections,
    render_pdf_pages,
)
from tests.board_fixtures import board_source


def _evidence_path(repo_root, project, legacy, unified):
    old = board_source(repo_root, project) / legacy
    return old if old.exists() else board_source(repo_root, project) / unified


def test_bmp390_eagle_extraction_keeps_source_identity(repo_root):
    source = _evidence_path(
        repo_root,
        "baro-bmp390",
        "reference-designs/BMP390_Adafruit_20BMP390.sch",
        "evidence/files/BMP390_Adafruit_20BMP390.sch",
    )
    expected_id = f"sha256:{hashlib.sha256(source.read_bytes()).hexdigest()}"

    facts = extract_eagle_connections(source, "BMP390")

    assert any(
        fact.subject == "R1"
        and fact.predicate == "component_value"
        and fact.value == "10K"
        for fact in facts
    )
    assert {
        (fact.subject, fact.value)
        for fact in facts
        if fact.predicate == "connected_net"
    } >= {("IC1.VDD", "3.3V"), ("IC1.VDDIO", "3.3V")}
    assert all(fact.evidence_id == expected_id for fact in facts)
    assert all(fact.pages == (1,) and fact.confidence == "exact" for fact in facts)


def test_render_pdf_pages_returns_cited_page_images(repo_root, tmp_path):
    source = _evidence_path(
        repo_root,
        "baro-bmp390",
        "datasheets/BMP390-datasheet.pdf",
        "evidence/files/BMP390-datasheet.pdf",
    )

    rendered = render_pdf_pages(source, [1], tmp_path)

    assert rendered == (tmp_path / "page_1.png",)
    assert rendered[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
