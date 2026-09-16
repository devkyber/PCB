import json
from dataclasses import replace

import pytest

from pcb_copilot.drafts import DraftKind, create_draft, publish_draft
from pcb_copilot.project import load_project
from pcb_copilot.state import canonical_design_hash


def test_draft_id_and_root_are_deterministic(project_copy, fixed_clock):
    project = load_project(project_copy)

    first = create_draft(project, DraftKind.SCHEMATIC, fixed_clock)
    second = create_draft(project, DraftKind.SCHEMATIC, fixed_clock)

    prefix = canonical_design_hash(project.schematic_path)[:8]
    assert first == second
    assert first.id == f"20260914T120000Z-schematic-{prefix}"
    assert first.root == project_copy / ".pcb-copilot" / "drafts" / first.id
    assert not first.root.exists()


def test_failed_writer_leaves_no_published_draft(project_copy, fixed_clock):
    project = load_project(project_copy)
    accepted_before = project.schematic_path.read_bytes()
    record = create_draft(project, DraftKind.SCHEMATIC, fixed_clock)

    def fail(path):
        (path / "partial.kicad_sch").write_text("partial", encoding="utf-8")
        raise RuntimeError("renderer failed")

    with pytest.raises(RuntimeError, match="renderer failed"):
        publish_draft(record, fail)

    assert not record.root.exists()
    assert not record.root.with_name(f".building-{record.id}").exists()
    assert project.schematic_path.read_bytes() == accepted_before


def test_publish_is_atomic_and_records_base_hashes(project_copy, fixed_clock):
    project = load_project(project_copy)
    record = create_draft(project, DraftKind.SCHEMATIC, fixed_clock)

    published = publish_draft(
        record,
        lambda root: (root / "candidate.kicad_sch").write_text(
            "(kicad_sch)", encoding="utf-8"
        ),
    )

    assert published == record.root
    metadata = json.loads((published / "draft.json").read_text(encoding="utf-8"))
    assert metadata["base_schematic_hash"] == canonical_design_hash(
        project.schematic_path
    )
    assert metadata["base_pcb_hash"] == canonical_design_hash(project.pcb_path)
    assert (published / project.schematic_path.name).is_file()
    assert (published / project.pcb_path.name).is_file()


def test_publish_rejects_forged_draft_root(project_copy, fixed_clock):
    record = create_draft(
        load_project(project_copy), DraftKind.SCHEMATIC, fixed_clock
    )
    forged = replace(record, root=project_copy / "outside" / record.id)

    with pytest.raises(ValueError, match="draft root"):
        publish_draft(forged, lambda _root: None)

    assert not forged.root.exists()
