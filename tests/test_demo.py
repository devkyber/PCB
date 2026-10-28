"""The public demo must isolate owner inputs and preserve actual command results."""

import json
from pathlib import Path

import pytest

from pcb_copilot.project import load_project
from pcb_copilot.transaction import input_hashes
from tools import demo


def minimal_source(repository: Path, project_path: Path = demo.DEFAULT_PROJECT):
    root = repository / project_path
    root.mkdir(parents=True)
    name = root.name
    (root / "project.yaml").write_text(
        f"schema_version: 1\nname: {name}\nlifecycle: DRAFT\n"
        f"design:\n  schematic: {name}.kicad_sch\n  pcb: {name}.kicad_pcb\n"
        "  netmap: netmap.json\nevidence:\n  index: evidence/index.yaml\n"
        "manufacturing:\n  profile: jlcpcb_2layer_default\n", encoding="utf-8",
    )
    # Parser envelope only; no generated demo circuit or retired board fixture.
    (root / f"{name}.kicad_sch").write_text("(kicad_sch (version 20250114))", encoding="utf-8")
    (root / f"{name}.kicad_pcb").write_bytes(b"owner PCB bytes")
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
    review = {'project': Path(arguments[1]).name, 'blocking': True,
              'results': [{'check_id': 'signoff', 'passed': False}]}
    content = (json.dumps(review) if name == 'review' else
               '3 evidence record(s) verified\nMACHINE FAILURES: none\n' if name == 'evidence'
               else 'actual output')
    stdout.write_text(content, encoding="utf-8")
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


def test_default_quick_demo_selects_small_example_without_requiring_kicad(tmp_path, monkeypatch):
    repository = tmp_path / 'repo'
    project = minimal_source(repository)
    output = tmp_path / 'run'
    output.mkdir()
    monkeypatch.setattr(demo, 'run_command', fake_commands)
    monkeypatch.setattr('pcb_copilot.toolchain.discover_toolchain',
                        lambda *_args: pytest.fail('quick mode must not require native discovery'))
    result = demo.execute_demo(repository, output, full=False)
    assert result['exit_code'] == 0
    assert result['source_project'] == 'examples/gpio-indicator'
    assert result['snapshot_project'] == 'workspace/gpio-indicator'
    assert result['source_inputs_unchanged'] and result['snapshot_inputs_unchanged']
    report = (output / 'report.md').read_text()
    assert '[workspace](workspace/gpio-indicator/)' in report
    assert 'workspace/rover-pdb' not in report
    assert 'were **not run**' in report
    assert project.pcb_path.read_bytes() == b'owner PCB bytes'


def test_explicit_rover_project_keeps_its_own_report_paths(tmp_path, monkeypatch):
    repository = tmp_path / 'repo'
    project = minimal_source(repository, Path('projects/rover-pdb'))
    output = tmp_path / 'run'
    output.mkdir()
    monkeypatch.setattr(demo, 'run_command', fake_commands)
    result = demo.execute_demo(repository, output, full=False, project_path=Path('projects/rover-pdb'))
    assert result['exit_code'] == 0
    assert result['source_project'] == 'projects/rover-pdb'
    assert result['snapshot_project'] == 'workspace/rover-pdb'
    assert '[workspace](workspace/rover-pdb/)' in (output / 'report.md').read_text()
    assert project.pcb_path.read_bytes() == b'owner PCB bytes'


@pytest.mark.parametrize('requested', ['tests/fixtures/boards/tms-v3',
                                      'examples/../tests/fixtures/boards/tms-v3',
                                      '../outside', '.', 'templates/project'])
def test_project_selection_rejects_fixtures_and_non_project_roots(tmp_path, requested):
    repository = tmp_path / 'repo'
    repository.mkdir()
    with pytest.raises(ValueError, match='examples/ or projects/'):
        demo.select_project(repository, Path(requested))
    assert list(repository.iterdir()) == []


def test_fixture_alias_cannot_bypass_resolved_project_selection(tmp_path):
    repository = tmp_path / 'repo'
    fixture = repository / 'tests/fixtures/boards/frozen'
    fixture.mkdir(parents=True)
    examples = repository / 'examples'
    examples.mkdir()
    alias = examples / 'alias'
    try:
        alias.symlink_to(fixture, target_is_directory=True)
    except OSError:
        pytest.skip('directory symlinks unavailable on this host')
    with pytest.raises(ValueError, match='frozen fixtures'):
        demo.select_project(repository, Path('examples/alias'))


def test_invalid_cli_project_does_not_create_an_output_directory(tmp_path, monkeypatch, capsys):
    repository = tmp_path / 'repo'
    repository.mkdir()
    monkeypatch.setattr(demo, '__file__', str(repository / 'tools/demo.py'))
    output = tmp_path / 'must-not-be-created'
    assert demo.main(['--project', 'tests/fixtures/boards/frozen', '--output', str(output)]) == 2
    assert not output.exists()
    assert 'frozen fixtures' in capsys.readouterr().err


@pytest.mark.parametrize('crash_code', [1, 2, 7])
def test_evidence_process_failure_is_not_misreported_as_archive_blocker(tmp_path, monkeypatch, crash_code):
    repository = tmp_path / 'repo'
    minimal_source(repository)
    output = tmp_path / 'run'
    output.mkdir()

    def failed_evidence(output, name, arguments, **kwargs):
        result = fake_commands(output, name, arguments, **kwargs)
        if name == 'evidence':
            result['exit_code'] = crash_code
            (output / result['stdout']).write_text('')
            (output / result['stderr']).write_text('dependency or runtime failure')
        return result

    monkeypatch.setattr(demo, 'run_command', failed_evidence)
    result = demo.execute_demo(repository, output, full=False)
    assert result['exit_code'] == 2
    assert 'did not complete' in result['error']
    assert len(result['steps']) == 2
    assert result['source_inputs_unchanged'] and result['snapshot_inputs_unchanged']


def test_archive_blockers_keep_exit_one_and_exact_logs(tmp_path, monkeypatch):
    repository = tmp_path / 'repo'
    minimal_source(repository)
    output = tmp_path / 'run'
    output.mkdir()

    def blocked_evidence(output, name, arguments, **kwargs):
        result = fake_commands(output, name, arguments, **kwargs)
        if name == 'evidence':
            result['exit_code'] = 1
            (output / result['stdout']).write_text('0 evidence record(s) verified\nMACHINE FAILURES:\n- hash mismatch\n')
        return result

    monkeypatch.setattr(demo, 'run_command', blocked_evidence)
    result = demo.execute_demo(repository, output, full=False)
    assert result['exit_code'] == 1
    assert result['steps'][1]['interpretation'] == 'archive verification reported blockers'
    assert 'hash mismatch' in demo.step_output(output, result['steps'][1], 'stdout')


@pytest.mark.parametrize('report,code', [
    ({'project': 'other', 'blocking': False, 'results': [{'check_id': 'erc', 'passed': True}]}, 0),
    ({'project': 'gpio-indicator', 'blocking': False, 'results': []}, 0),
    ({'project': 'gpio-indicator', 'blocking': False, 'results': [{'check_id': 'erc', 'passed': False}]}, 0),
    ({'project': 'gpio-indicator', 'blocking': True, 'results': [{'check_id': 'erc', 'passed': True}]}, 1),
    ({'project': 'gpio-indicator', 'blocking': True, 'results': [{'check_id': 'erc', 'passed': False}]}, 0),
    ({'project': 'gpio-indicator', 'blocking': False, 'results': [
        {'check_id': 'erc', 'passed': True}, {'check_id': 'erc', 'passed': True}]}, 0),
])
def test_incomplete_or_contradictory_native_results_are_rejected(report, code):
    with pytest.raises(ValueError):
        demo.review_document(json.dumps(report), 'gpio-indicator', code)


def test_source_change_between_initial_capture_and_snapshot_is_detected(tmp_path, monkeypatch):
    repository = tmp_path / 'repo'
    project = minimal_source(repository)
    output = tmp_path / 'run'
    output.mkdir()
    real_snapshot = demo.snapshot_project

    def changed_before_copy(project, output):
        project.pcb_path.write_bytes(b'new owner save before copy')
        return real_snapshot(project, output)

    monkeypatch.setattr(demo, 'snapshot_project', changed_before_copy)
    monkeypatch.setattr(demo, 'run_command', lambda *_args, **_kwargs: pytest.fail('commands must not run'))
    result = demo.execute_demo(repository, output, full=False)
    assert result['exit_code'] == 2
    assert not result['source_inputs_unchanged']
    assert not result['source_cad_unchanged']
    assert project.pcb_path.read_bytes() == b'new owner save before copy'
