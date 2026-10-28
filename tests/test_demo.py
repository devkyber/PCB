"""The public demo must isolate owner inputs and preserve actual command results."""

import json
from pathlib import Path

import pytest

from pcb_copilot.project import load_project
from pcb_copilot.transaction import input_hashes
from tools import demo


def minimal_source(repository: Path):
    root = repository / "projects" / "rover-pdb"
    root.mkdir(parents=True)
    (root / "project.yaml").write_text(
        "schema_version: 1\nname: rover-pdb\nlifecycle: DRAFT\n"
        "design:\n  schematic: rover-pdb.kicad_sch\n  pcb: rover-pdb.kicad_pcb\n"
        "  netmap: netmap.json\nevidence:\n  index: evidence/index.yaml\n"
        "manufacturing:\n  profile: jlcpcb_2layer_default\n", encoding="utf-8",
    )
    # Parser envelope only; no generated demo circuit or retired board fixture.
    (root / "rover-pdb.kicad_sch").write_text("(kicad_sch (version 20250114))", encoding="utf-8")
    (root / "rover-pdb.kicad_pcb").write_bytes(b"owner PCB bytes")
    (root / "evidence").mkdir()
    (root / "evidence/index.yaml").write_text("schema_version: 1\nrecords: []\n", encoding="utf-8")
    return load_project(root)


def test_output_must_be_new_and_external(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    with pytest.raises(ValueError, match="outside"):
        demo.new_output_directory(repository / "demo", repository)
    existing = tmp_path / "owner-output"
    existing.mkdir()
    note = existing / "owner.txt"
    note.write_bytes(b"keep this")
    with pytest.raises(FileExistsError):
        demo.new_output_directory(existing, repository)
    assert note.read_bytes() == b"keep this"
    monkeypatch.setattr(demo.tempfile, "gettempdir", lambda: str(repository))
    with pytest.raises(ValueError, match="temporary directory is inside"):
        demo.new_output_directory(None, repository)
    assert list(repository.iterdir()) == []


def test_snapshot_copies_declared_inputs_without_owner_history(tmp_path):
    project = minimal_source(tmp_path / "repo")
    (project.root / "owner-notes.txt").write_bytes(b"not a declared input")
    history = project.root / ".pcb-copilot"
    history.mkdir()
    (history / "owner-preview.txt").write_bytes(b"never copy working history")
    before = input_hashes(project)
    snapshot, captured = demo.snapshot_project(project, tmp_path / "outside")
    assert captured == before == input_hashes(project) == input_hashes(snapshot)
    assert not (snapshot.root / "owner-notes.txt").exists()
    assert not (snapshot.root / ".pcb-copilot").exists()
    assert snapshot.pcb_path.read_bytes() == b"owner PCB bytes"


def test_command_records_real_nonzero_process_exit_and_exact_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "CLI_ENTRYPOINT",
                        "import sys; print('real stdout'); print('real stderr', file=sys.stderr); sys.exit(7)")
    result = demo.run_command(tmp_path, "probe", ["status", "workspace/rover-pdb"])
    assert result["exit_code"] == 7
    assert demo.step_output(tmp_path, result, "stdout") == "real stdout\n"
    assert demo.step_output(tmp_path, result, "stderr") == "real stderr\n"
    assert not Path(result["stdout"]).is_absolute()


def fake_commands(output, name, arguments, **kwargs):
    logs = output / "logs"
    logs.mkdir(exist_ok=True)
    stdout = logs / f"{name}.stdout.txt"
    stderr = logs / f"{name}.stderr.txt"
    stdout.write_text(json.dumps({"blocking": True, "results": []}) if name == "review" else "actual output", encoding="utf-8")
    stderr.write_text(demo.GUARD_MESSAGE if name == "missing-preview" else "", encoding="utf-8")
    return {"name": name, "command": ["pcb-copilot", *arguments],
            "exit_code": 2 if name == "missing-preview" else int(name == "review"),
            "stdout": stdout.relative_to(output).as_posix(),
            "stderr": stderr.relative_to(output).as_posix(), "error": None}


def test_full_review_blocker_is_not_reported_as_demo_success(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    project = minimal_source(repository)
    output = tmp_path / "external-run"
    output.mkdir()
    monkeypatch.setattr(demo, "run_command", fake_commands)
    monkeypatch.setattr("pcb_copilot.toolchain.discover_toolchain", lambda *args: object())
    result = demo.execute_demo(repository, output, full=True)
    assert result["exit_code"] == 1
    assert result["source_cad_unchanged"] and result["snapshot_inputs_unchanged"]
    assert result["steps"][2]["exit_code"] == 2
    assert result["steps"][3]["exit_code"] == 1
    assert all(not Path(arg).is_absolute() for step in result["steps"] for arg in step["command"])
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "BLOCKED" in report and "no fabrication release" in report
    assert project.pcb_path.read_bytes() == b"owner PCB bytes"


def test_concurrent_source_edit_fails_preservation_check_without_restoring_it(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    project = minimal_source(repository)
    output = tmp_path / "external-run"
    output.mkdir()

    def concurrent_edit(*args, **kwargs):
        result = fake_commands(*args, **kwargs)
        if result["name"] == "evidence":
            project.pcb_path.write_bytes(b"concurrent owner save")
        return result

    monkeypatch.setattr(demo, "run_command", concurrent_edit)
    result = demo.execute_demo(repository, output, full=False)
    assert result["exit_code"] == 2
    assert not result["source_inputs_unchanged"]
    assert not result["source_cad_unchanged"]
    assert project.pcb_path.read_bytes() == b"concurrent owner save"
