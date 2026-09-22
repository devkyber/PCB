"""Compatibility CLI remains usable after moving executable code out of docs."""

import subprocess
import sys

from pcb_copilot.project import load_project


def test_pipeline_status_from_scripts_is_retired(repo_root, tmp_path):
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts/pipeline.py"), "--status"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 2
    assert 'pcb-copilot status' in result.stderr


def test_legacy_pipeline_refuses_build_or_check_without_mutating_project(
    repo_root, project_copy, tree_hash,
):
    project = load_project(project_copy)
    before = tree_hash(project.root)

    result = subprocess.run(
        [sys.executable, str(repo_root / 'scripts/pipeline.py'),
         str(project.root), '--check'],
        cwd=repo_root, capture_output=True, check=False, text=True,
        encoding='utf-8', timeout=90,
    )

    assert result.returncode == 2
    assert 'pcb-copilot review' in result.stderr
    assert tree_hash(project.root) == before


def test_legacy_fabrication_script_refuses_unreviewed_export(
    repo_root, project_copy, tree_hash,
):
    project = load_project(project_copy)
    before = tree_hash(project.root)

    result = subprocess.run(
        [sys.executable, str(repo_root / 'scripts/export_fab.py'),
         str(project.pcb_path)],
        cwd=repo_root, capture_output=True, check=False, text=True,
        encoding='utf-8', errors='replace', timeout=20,
    )

    assert result.returncode == 2
    assert 'release' in result.stderr
    assert tree_hash(project.root) == before
    assert not (project.root / 'fabrication').exists()
