from pcb_copilot.cli import main
from pcb_copilot.evidence.index import load_evidence_index


def test_research_verify_is_read_only(project_copy, tree_hash, capsys):
    before = tree_hash(project_copy)

    result = main(["research", str(project_copy), "--verify"])

    assert result == 0
    assert tree_hash(project_copy) == before
    output = capsys.readouterr().out
    assert "MACHINE FAILURES: none" in output
    assert "3 evidence record(s) verified" in output


def test_research_add_uses_injected_downloader_and_indexes_once(
    project_copy, capsys
):
    payload = b"%PDF-1.7\nmanufacturer document"
    calls = []

    def download(url):
        calls.append(url)
        return payload

    result = main(
        [
            "research",
            str(project_copy),
            "--add",
            "BMP390",
            "https://manufacturer.test/bmp390-note.pdf",
            "--role",
            "application_note",
        ],
        downloader=download,
    )

    assert result == 0
    assert calls == ["https://manufacturer.test/bmp390-note.pdf"]
    index = load_evidence_index(project_copy / "evidence" / "index.yaml")
    added = [record for record in index.records if record.source_url == calls[0]]
    assert len(added) == 1
    assert (project_copy / "evidence" / added[0].path).read_bytes() == payload
    assert "ARCHIVED" in capsys.readouterr().out


def test_research_extract_prints_exact_facts_with_file_and_page_citations(
    project_copy, capsys
):
    result = main(["research", str(project_copy), "--extract", "BMP390"])

    assert result == 0
    output = capsys.readouterr().out
    assert "EXTRACTED FACTS" in output
    assert "IC1.VDD connected_net 3.3V" in output
    assert "evidence/files/BMP390_Adafruit_20BMP390.sch:page 1" in output
    assert "REVIEW REQUIRED" in output
    assert "PROPOSED DESIGN_BASIS ROWS" in output
