from pcb_copilot.cli import main


def test_status_does_not_modify_project(project_copy, tree_hash, capsys):
    before = tree_hash(project_copy)
    assert main(["status", str(project_copy)]) == 0
    assert tree_hash(project_copy) == before
    output = capsys.readouterr().out
    assert "Lifecycle: DRAFT" in output
    assert "baro-bmp390.kicad_sch" in output
    assert "baro-bmp390.kicad_pcb" in output
    assert "Next: pcb-copilot update-schematic" in output
    assert f"--intent {project_copy / 'schematic-intent.yaml'}" in output


def test_status_reports_missing_evidence_index(project_copy, capsys):
    (project_copy / "evidence" / "index.yaml").unlink()

    assert main(["status", str(project_copy)]) == 0
    assert "Evidence index: missing" in capsys.readouterr().out
