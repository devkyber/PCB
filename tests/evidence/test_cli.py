import json

from pcb_copilot.cli import main
from pcb_copilot.evidence.index import load_evidence_index


def test_research_verify_is_read_only(project_copy, tree_hash, capsys):
    before = tree_hash(project_copy)
    count = len(load_evidence_index(project_copy / "evidence" / "index.yaml").records)

    result = main(["research", str(project_copy), "--verify"])

    assert result == 0
    assert tree_hash(project_copy) == before
    output = capsys.readouterr().out
    assert "MACHINE FAILURES: none" in output
    assert f"{count} evidence record(s) verified" in output


def test_full_schematic_part_audit_is_read_only_and_counts_native_parts(
    project_copy, tree_hash, capsys
):
    before = tree_hash(project_copy)
    result = main(["research", str(project_copy), "--verify-schematic-parts"])
    output = capsys.readouterr().out
    assert result in (0, 1)
    assert 'physical schematic parts' in output
    assert tree_hash(project_copy) == before


def test_reference_search_plan_is_explicitly_not_live_search(project_copy, tree_hash, capsys):
    before = tree_hash(project_copy)
    assert main(["research", str(project_copy), "--search-plan", "BMP390"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "queries_only_not_searched"
    assert tree_hash(project_copy) == before


def test_reference_pair_cli_is_read_only(project_copy, tree_hash, capsys):
    records = load_evidence_index(project_copy / "evidence" / "index.yaml").records
    schematic = next(r for r in records if r.path.endswith('.sch'))
    board = next(r for r in records if r.path.endswith('.brd'))
    before = tree_hash(project_copy)
    assert main(["research", str(project_copy), "--inspect-reference", schematic.id, board.id]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['mismatches'] == []
    assert result['compared_pad_count'] > 0
    assert len(result['provenance']) == 2
    assert result['review_required']
    assert tree_hash(project_copy) == before


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
