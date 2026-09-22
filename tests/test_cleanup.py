"""Guards for the audited documentation cleanup, not a blanket deletion gate."""

MOVED = {
    "docs/tms-v3-pdr.md": "projects/tms-v3/PDR.md",
    "docs/pcb-design-rules.md": "migration/legacy-design-rules.md",
}
REMOVED = {
    "docs/archive/tms-v2-summary.md": "projects/tms-v3/DESIGN_BASIS.md",
    "docs/archive/tms3-design-review.md": "projects/tms-v3/DESIGN_BASIS.md",
    "docs/pcb-design-workflow.md": "docs/WORKFLOW.md",
    "projects/baro-bmp390/EVALUATION.md": "projects/baro-bmp390/DESIGN_BASIS.md",
    "projects/imu-icm42688/EVALUATION.md": "projects/imu-icm42688/DESIGN_BASIS.md",
    "docs/archive/tms-v3-relay-and-adc-explained.md": "projects/tms-v3/PDR.md",
    "docs/archive/README.md": "README.md",
    "docs/README.md": "README.md",
    "docs/PROGRESS.md": "README.md",
    "docs/PROJECT_FORMAT.md": "docs/ARCHITECTURE.md",
}


def test_audited_documentation_targets_have_canonical_destinations(repo_root):
    for old, replacement in (MOVED | REMOVED).items():
        assert not (repo_root / old).exists(), old
        assert (repo_root / replacement).is_file(), replacement
    for replacement in MOVED.values():
        assert "historical" in (repo_root / replacement).read_text(
            encoding="utf-8"
        ).lower()


def test_removed_evaluation_refs_are_not_left_in_active_board_sources(repo_root):
    for board in ("baro-bmp390", "imu-icm42688"):
        for path in (repo_root / "projects" / board).iterdir():
            if path.suffix in {".md", ".py", ".kicad_sch"}:
                assert "EVALUATION.md" not in path.read_text(encoding="utf-8"), path


def test_gnss_evaluation_is_retained_while_design_basis_cites_it(repo_root):
    project = repo_root / "projects/gnss-neom9n"
    assert "EVALUATION.md" in (project / "DESIGN_BASIS.md").read_text(
        encoding="utf-8"
    )
    assert (project / "EVALUATION.md").is_file()


def test_cleanup_does_not_remove_live_legacy_runtime_inputs(repo_root):
    # These are not ready for deletion just because newer APIs are planned.
    for relative in (
        "scripts/pcb_layout_helpers.py", "scripts/schematic_layout_helpers.py",
        "scripts/deviations.py", "scripts/extract_netmap.py", "scripts/pipeline.py",
        ".claude/settings.json", "pyproject.toml", "uv.lock",
    ):
        assert (repo_root / relative).is_file(), relative


def test_superseded_history_is_not_retained_as_duplicate_archives(repo_root):
    for relative in (
        "docs/history/legacy-workflow.md",
        "projects/tms-v3/history/tms-v2-summary.md",
        "projects/tms-v3/history/tms3-design-review.md",
    ):
        assert not (repo_root / relative).exists(), relative


def test_board_shell_shims_to_retired_pipeline_are_removed(repo_root):
    for board in ('baro-bmp390', 'imu-icm42688', 'gnss-neom9n', 'tms-v3'):
        assert not (repo_root / 'projects' / board / 'build.sh').exists()


def test_generated_status_mirrors_are_not_current_files(repo_root):
    assert not (repo_root / 'HUMAN_WORK.md').exists()
    for board in ('baro-bmp390', 'imu-icm42688', 'gnss-neom9n', 'tms-v3'):
        root = repo_root / 'projects' / board
        assert (root / 'SCHEMATIC_OWNER').read_text(encoding='utf-8').strip() == 'human'
        assert not (root / 'STATUS.md').exists()
        assert not (root / 'PIPELINE.json').exists()
