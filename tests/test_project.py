from pathlib import Path

import pytest

from pcb_copilot.models import Lifecycle
from pcb_copilot.project import ProjectFormatError, load_project


def test_load_existing_flat_project(repo_root):
    project = load_project(repo_root / "projects" / "baro-bmp390")
    assert project.manifest.name == "baro-bmp390"
    assert project.schematic_path.name == "baro-bmp390.kicad_sch"
    assert project.pcb_path.name == "baro-bmp390.kicad_pcb"
    assert project.manifest.lifecycle == Lifecycle.DRAFT


def test_manifest_rejects_path_escape(tmp_path):
    (tmp_path / "project.yaml").write_text(
        """schema_version: 1
name: escape-test
lifecycle: DRAFT
design:
  schematic: ../outside.kicad_sch
  pcb: board.kicad_pcb
  netmap: netmap.json
evidence:
  index: evidence/index.yaml
manufacturing:
  profile: jlcpcb_2layer_default
safety_tags: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ProjectFormatError, match="outside project root"):
        load_project(tmp_path)


@pytest.mark.parametrize(
    "board_name",
    ["baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3"],
)
def test_all_existing_board_manifests_resolve_accepted_designs(repo_root, board_name):
    project = load_project(repo_root / "projects" / board_name)
    assert project.schematic_path.is_file()
    assert project.pcb_path.is_file()
    assert project.netmap_path.is_file()


def test_tms_manifest_identifies_high_consequence_design(repo_root):
    project = load_project(repo_root / "projects" / "tms-v3")
    assert set(project.manifest.safety_tags) == {"pyrotechnic", "high_current"}


def test_manifest_paths_are_absolute_after_loading(repo_root):
    project = load_project(repo_root / "projects" / "gnss-neom9n")
    paths: tuple[Path, ...] = (
        project.schematic_path,
        project.pcb_path,
        project.netmap_path,
        project.evidence_index_path,
    )
    assert all(path.is_absolute() for path in paths)
