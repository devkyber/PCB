"""Layout workflow integration: accepted safety and actual native CAD checks."""

import json
from pathlib import Path

import pytest

from pcb_copilot.cli import main
from pcb_copilot.state import accepted_file_hashes, file_digest


def test_draft_layout_cli_preserves_accepted_board(
    sensor_layout_draft, repo_root, capsys
):
    fixture = sensor_layout_draft
    before = accepted_file_hashes(fixture.project)
    main(
        [
            "draft-layout",
            str(fixture.project.root),
            "--intent",
            str(repo_root / "tests/fixtures/layout/sensor-layout.yaml"),
            "--route",
            "human",
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert accepted_file_hashes(fixture.project) == before
    assert report["human_review"] == "pending"
    assert report["route"]["unconnected"] == "unknown"
    assert report["plot"] and report["drc_report"]
    assert not report["machine_failures"], report["machine_failures"]


def test_settings_are_in_stale_base_inventory(sensor_layout_draft):
    project = sensor_layout_draft.project
    relative = (
        project.pcb_path.with_suffix(".kicad_pro").relative_to(project.root).as_posix()
    )
    assert accepted_file_hashes(project).get(relative) == file_digest(
        project.root / relative
    )


def test_publish_copies_manifest_paths_and_child_sheets(sensor_layout_draft):
    import yaml

    from pcb_copilot.drafts import create_draft, publish_draft
    from pcb_copilot.models import DraftKind
    from pcb_copilot.project import load_project

    project = sensor_layout_draft.project
    document = yaml.safe_load(project.manifest_path.read_text())
    for key, path in [
        ("pcb", project.pcb_path),
        ("schematic", project.schematic_path),
        ("netmap", project.netmap_path),
    ]:
        target = project.root / "cad" / path.name
        target.parent.mkdir(exist_ok=True)
        path.replace(target)
        document["design"][key] = target.relative_to(project.root).as_posix()
    pro = project.pcb_path.with_suffix(".kicad_pro")
    pro.replace(project.root / "cad" / pro.name)
    project.manifest_path.write_text(yaml.safe_dump(document))
    project = load_project(project.root)
    # A minimal hierarchy dependency is enough for the snapshot traversal;
    # native netlist export is tested independently by layout review.
    import sexpdata
    from kicad_claude.adapters import sch_io

    child = project.schematic_path.parent / "child.kicad_sch"
    child.write_text('(kicad_sch (version 20250114) (generator "eeschema"))')
    tree = sch_io.parse_file(project.schematic_path)
    tree.append(
        sexpdata.loads(
            '(sheet (property "Sheetname" "Child") (property "Sheetfile" "child.kicad_sch"))'
        )
    )
    sch_io.write_file(project.schematic_path, tree)
    draft = create_draft(project, DraftKind.LAYOUT)
    publish_draft(draft, lambda root: None)
    assert (
        draft.root / "cad" / project.pcb_path.name
    ).read_bytes() == project.pcb_path.read_bytes()
    assert (draft.root / "cad" / pro.name).is_file()
    assert (draft.root / "cad/child.kicad_sch").read_bytes() == child.read_bytes()


@pytest.mark.parametrize("changed", ["schematic", "pcb", "settings"])
def test_layout_accept_rejects_stale_inputs(sensor_layout_draft, repo_root, changed):
    from pcb_copilot.accept import StaleDraftError, accept_layout, load_draft
    from pcb_copilot.layout.commands import draft_layout

    fixture = sensor_layout_draft
    report = draft_layout(
        fixture.project, repo_root / "tests/fixtures/layout/sensor-layout.yaml"
    )
    target = {
        "schematic": fixture.project.schematic_path,
        "pcb": fixture.project.pcb_path,
        "settings": fixture.project.pcb_path.with_suffix(".kicad_pro"),
    }[changed]
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(StaleDraftError):
        accept_layout(fixture.project, load_draft(fixture.project, report["draft_id"]))


@pytest.fixture
def reviewed(sensor_layout_draft, repo_root):
    from pcb_copilot.accept import load_draft
    from pcb_copilot.layout.commands import draft_layout

    fixture = sensor_layout_draft
    report = draft_layout(
        fixture.project, repo_root / "tests/fixtures/layout/sensor-layout.yaml"
    )
    return fixture.project, load_draft(fixture.project, report["draft_id"]), report


def test_accept_needs_explicit_approval_and_installs_companion(reviewed):
    from pcb_copilot.accept import accept_layout
    from pcb_copilot.layout.commands import approve_layout_preview

    project, draft, report = reviewed
    assert not report["machine_failures"], report["machine_failures"]
    before = project.schematic_path.read_bytes()
    with pytest.raises(ValueError, match="human preview"):
        accept_layout(project, draft)
    with pytest.raises(ValueError, match="explicit"):
        approve_layout_preview(project, draft.id, "fixture reviewer")
    approve_layout_preview(project, draft.id, "fixture reviewer", confirm_preview=True)
    pcb = draft.root / project.pcb_path.name
    result = accept_layout(project, draft)
    assert project.pcb_path.read_bytes() == pcb.read_bytes()
    assert (
        project.pcb_path.with_suffix(".kicad_pro").read_bytes()
        == pcb.with_suffix(".kicad_pro").read_bytes()
    )
    assert project.schematic_path.read_bytes() == before
    assert result.accepted_hash == file_digest(pcb)


def test_refresh_preserves_manual_copper_and_invalidates_approval(reviewed):
    import sexpdata
    from kicad_claude.adapters import sch_io

    from pcb_copilot.accept import accept_layout
    from pcb_copilot.layout.commands import approve_layout_preview, review_layout_draft

    project, draft, report = reviewed
    approve_layout_preview(project, draft.id, "fixture reviewer", confirm_preview=True)
    pcb = draft.root / project.pcb_path.name
    tree = sch_io.parse_file(pcb)
    tree.append(
        sexpdata.loads(
            '(segment (start 21 194) (end 22 194) (width 0.25) (layer "F.Cu") (net 0) (uuid "10000000-0000-0000-0000-000000000001"))'
        )
    )
    sch_io.write_file(pcb, tree)
    before, metadata = pcb.read_bytes(), (draft.root / "draft.json").read_bytes()
    with pytest.raises(ValueError, match="artifacts changed"):
        accept_layout(project, draft)
    report = review_layout_draft(project, draft.id)
    assert pcb.read_bytes() == before
    assert (draft.root / "draft.json").read_bytes() == metadata
    assert report["human_review"] == "pending"
    assert not (draft.root / "preview-approval.json").exists()


def test_refresh_rejects_dropped_constraints(sensor_layout_draft, tmp_path):
    from pcb_copilot.accept import load_draft
    from pcb_copilot.layout.commands import draft_layout, review_layout_draft
    from pcb_copilot.layout.io import save_layout_intent
    from pcb_copilot.layout.models import LayoutIntent

    fixture = sensor_layout_draft
    data = fixture.intent.model_dump(mode="json")
    data["net_classes"] = [{"name": "Power", "nets": ["+3V3"], "width_mm": 0.4}]
    path = tmp_path / "intent.yaml"
    save_layout_intent(LayoutIntent.model_validate(data), path)
    report = draft_layout(fixture.project, path)
    draft = load_draft(fixture.project, report["draft_id"])
    pro = draft.root / fixture.project.pcb_path.with_suffix(".kicad_pro").name
    pro.write_bytes(fixture.project.pcb_path.with_suffix(".kicad_pro").read_bytes())
    report = review_layout_draft(fixture.project, draft.id)
    assert any(
        f["code"] == "constraints.current_mismatch" for f in report["machine_failures"]
    )


def test_accept_rolls_back_board_and_settings_on_state_failure(reviewed, monkeypatch):
    from pcb_copilot import accept
    from pcb_copilot.layout.commands import approve_layout_preview

    project, draft, _ = reviewed
    approve_layout_preview(project, draft.id, "fixture reviewer", confirm_preview=True)
    before = accepted_file_hashes(project)
    original = accept._replace_bytes

    def fail_state(target, payload):
        if target == project.root / ".pcb-copilot/review.json":
            raise OSError("fixture state failure")
        original(target, payload)

    monkeypatch.setattr(accept, "_replace_bytes", fail_state)
    with pytest.raises(OSError, match="fixture state failure"):
        accept.accept_layout(project, draft)
    assert accepted_file_hashes(project) == before
    assert not (project.root / ".pcb-copilot/accept.lock").exists()


def test_review_classifies_shorts_as_blocking_and_airwires_as_review(tmp_path):
    from types import SimpleNamespace

    # Exercise the real classifier with an offline subprocess boundary.
    from unittest.mock import patch

    from pcb_copilot.layout.preview import render_layout_preview

    def fake_cli(command, **kwargs):
        output = Path(command[command.index("-o") + 1])
        if "drc" in command:
            output.write_text(
                json.dumps(
                    {
                        "violations": [
                            {
                                "type": "shorting_items",
                                "description": "Short",
                                "severity": "error",
                            }
                        ],
                        "unconnected_items": [{}],
                    }
                )
            )
        elif "svg" in command:
            assert "--fit-page-to-board" in command
            assert "--exclude-drawing-sheet" in command
            output.write_text("<svg></svg>")
        else:
            output.write_text("ISO-10303-21; partial")
            return SimpleNamespace(
                returncode=2, stdout="partial STEP", stderr="missing model"
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch("pcb_copilot.layout.preview.subprocess.run", fake_cli):
        findings = render_layout_preview(
            SimpleNamespace(kicad_cli="fake"), tmp_path / "board.kicad_pcb", tmp_path
        )
    assert any(
        f["code"] == "drc.shorting_items" and f["severity"] == "block" for f in findings
    )
    assert any(
        f["code"] == "drc.unconnected" and f["severity"] == "review" for f in findings
    )
    assert (tmp_path / "preview.step").exists()
    assert "missing model" in (tmp_path / "export-report.json").read_text()


def test_refresh_does_not_erase_unresolved_provenance(reviewed):
    from pcb_copilot.layout.commands import review_layout_draft

    project, draft, _ = reviewed
    path = draft.root / "placement-proposal.json"
    proposal = json.loads(path.read_text())
    proposal["findings"] += [
        {
            "code": "placement.infeasible",
            "message": "historical search failure",
            "severity": "block",
        },
        {
            "code": "placement.footprint",
            "message": "unresolved footprint provenance",
            "severity": "block",
        },
    ]
    path.write_text(json.dumps(proposal))
    report = review_layout_draft(project, draft.id)
    assert not any(
        f["code"] == "placement.infeasible" for f in report["machine_failures"]
    )
    assert any(f["code"] == "placement.footprint" for f in report["machine_failures"])


def test_refresh_rejects_removing_intended_zone(sensor_layout_draft, tmp_path):
    from kicad_claude.adapters import sch_io

    from pcb_copilot.accept import load_draft
    from pcb_copilot.layout.commands import draft_layout, review_layout_draft
    from pcb_copilot.layout.io import save_layout_intent
    from pcb_copilot.layout.models import LayoutIntent

    fixture = sensor_layout_draft
    data = fixture.intent.model_dump(mode="json")
    data["zones"] = [{"net": "GND", "layers": ["B.Cu"]}]
    path = tmp_path / "intent.yaml"
    save_layout_intent(LayoutIntent.model_validate(data), path)
    report = draft_layout(fixture.project, path)
    draft = load_draft(fixture.project, report["draft_id"])
    pcb = draft.root / fixture.project.pcb_path.name
    tree = sch_io.parse_file(pcb)
    tree[:] = [
        node
        for node in tree
        if not isinstance(node, list) or sch_io.head_of(node) != "zone"
    ]
    sch_io.write_file(pcb, tree)
    report = review_layout_draft(fixture.project, draft.id)
    assert any(
        f["code"] == "constraints.zones_changed" for f in report["machine_failures"]
    )


def test_selected_route_uses_attempt_index_and_hashes_the_actual_board(
    sensor_layout_draft, repo_root, monkeypatch
):
    import shutil

    from pcb_copilot.layout import commands
    from pcb_copilot.layout.route import RouteAttempt, RouteReport

    chosen_bytes = []

    def offline_candidates(project, draft, policy, attempts):
        pcb = draft.root / project.pcb_path.name
        folder = draft.root / "routing/attempt-8"
        folder.mkdir(parents=True)
        candidate = folder / pcb.name
        candidate.write_bytes(pcb.read_bytes() + b"\n\n")
        chosen_bytes.append(candidate.read_bytes())
        shutil.copy2(pcb.with_suffix(".kicad_pro"), candidate.with_suffix(".kicad_pro"))
        return RouteReport(
            (RouteAttempt(8, candidate, 0, 20, ()),), 8, 0, 20, ("offline fixture",)
        )

    monkeypatch.setattr(commands, "route_candidate", offline_candidates)
    report = commands.draft_layout(
        sensor_layout_draft.project,
        repo_root / "tests/fixtures/layout/sensor-layout.yaml",
        "candidate_all",
    )
    assert Path(report["pcb"]).read_bytes() == chosen_bytes[0]
    assert report["route"]["selected"] == 8
    assert report["artifact_hashes"][Path(report["pcb"]).name] == file_digest(
        Path(report["pcb"])
    )


@pytest.mark.parametrize(
    "artifact",
    [
        "preview.svg",
        "drc.json",
        "placement-report.json",
        "route-report.json",
        "constraints-report.json",
        "baro-bmp390.kicad_pro",
    ],
)
def test_approval_cannot_outlive_artifact_edits(reviewed, artifact):
    from pcb_copilot.accept import accept_layout
    from pcb_copilot.layout.commands import approve_layout_preview

    project, draft, _ = reviewed
    approve_layout_preview(project, draft.id, "fixture reviewer", confirm_preview=True)
    target = draft.root / artifact
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="artifacts changed"):
        accept_layout(project, draft)
