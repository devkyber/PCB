import ast
import re
from pathlib import Path

import pytest

CANONICAL = {
    "reading_index": Path("docs/README.md"),
    "purpose": Path("README.md"),
    "workflow": Path("docs/WORKFLOW.md"),
    "architecture": Path("docs/ARCHITECTURE.md"),
    "rules": Path("docs/DESIGN_RULES.md"),
    "limitations": Path("docs/LIMITATIONS.md"),
    "project_format": Path("docs/PROJECT_FORMAT.md"),
    "progress": Path("docs/PROGRESS.md"),
}
LINK_RE = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def test_canonical_docs_exist_and_have_no_placeholder(repo_root):
    for path in CANONICAL.values():
        text = (repo_root / path).read_text(encoding="utf-8")
        assert len(text.strip()) >= 200
        assert "T" + "BD" not in text
        assert "T" + "ODO" not in text


@pytest.mark.parametrize("document", CANONICAL.values(), ids=CANONICAL.keys())
def test_canonical_local_markdown_links_resolve(repo_root, document):
    source = repo_root / document
    text = source.read_text(encoding="utf-8")
    for target in LINK_RE.findall(text):
        path_text = target.split("#", 1)[0]
        if not path_text or "://" in path_text or path_text.startswith("mailto:"):
            continue
        target_path = (source.parent / path_text).resolve()
        if ".pcb-copilot" in target_path.parts:
            # Snapshot IDs are local: another checkout may have different drafts.
            # If this selected draft exists, require all its linked artifacts.
            assert target_path.is_relative_to(repo_root / "projects")
            local_root = next(
                parent for parent in target_path.parents if parent.name == ".pcb-copilot"
            )
            relative_result = target_path.relative_to(local_root).parts
            assert len(relative_result) >= 3 and relative_result[0] == "drafts"
            snapshot = local_root / "drafts" / relative_result[1]
            if not snapshot.exists():
                continue
        assert target_path.exists(), f"{document} links to missing {target}"


@pytest.mark.parametrize("state", ("absent", "other-draft", "missing-file", "complete"))
def test_local_results_link_availability_is_snapshot_specific(tmp_path, state):
    document = Path("docs/PROGRESS.md")
    (tmp_path / "docs").mkdir()
    (tmp_path / document).write_text(
        "[PDF](../projects/board/.pcb-copilot/drafts/selected/preview.pdf)",
        encoding="utf-8",
    )
    drafts = tmp_path / "projects/board/.pcb-copilot/drafts"
    if state == "other-draft":
        (drafts / "new-id").mkdir(parents=True)
    elif state in {"missing-file", "complete"}:
        (drafts / "selected").mkdir(parents=True)
        if state == "complete":
            (drafts / "selected/preview.pdf").touch()
    if state == "missing-file":
        with pytest.raises(AssertionError, match="links to missing"):
            test_canonical_local_markdown_links_resolve(tmp_path, document)
    else:
        test_canonical_local_markdown_links_resolve(tmp_path, document)


def test_canonical_rules_preserve_legacy_ids_and_exact_checker_scope(repo_root):
    legacy = (repo_root / 'migration/legacy-design-rules.md').read_text(encoding='utf-8')
    canonical = (repo_root / 'docs/DESIGN_RULES.md').read_text(encoding='utf-8')
    legacy_ids = set(re.findall(r'^### (\d+\.\d+) ', legacy, re.MULTILINE))
    rows = re.findall(r'^\| `(\d+\.\d+)` \| ([^|]+) \| (Partial|Human) \|$',
                      canonical, re.MULTILINE)
    assert len(rows) == len(legacy_ids), 'preserve each historical rule ID exactly once'
    assert {rule for rule, _topic, _scope in rows} == legacy_ids
    checker = ast.parse((repo_root / 'scripts/check_design_rules.py').read_text(encoding='utf-8'))
    constants = {node.targets[0].id: ast.literal_eval(node.value)
                 for node in checker.body if isinstance(node, ast.Assign)
                 and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id in {'EXECUTABLE_RULES', 'DOC_RULE_COUNT'}}
    assert len(rows) == constants['DOC_RULE_COUNT']
    assert {rule for rule, _topic, scope in rows if scope == 'Partial'} == set(
        constants['EXECUTABLE_RULES'])


def test_workflow_preserves_legacy_entry_points_and_mutation_caveats(repo_root):
    workflow = (repo_root / 'docs/WORKFLOW.md').read_text(encoding='utf-8')
    normalized = ' '.join(workflow.split())
    commands = {
        'uv run python scripts/pipeline.py --status',
        'uv run python scripts/pipeline.py projects/<board> --check',
        'uv run python scripts/run_gates.py --init projects/<board>',
        'uv run pcb-copilot draft-layout projects/baro-bmp390 --intent projects/baro-bmp390/layout-intent.yaml --route human',
    }
    assert commands <= set(workflow.splitlines())
    for required_warning in (
        'The full compatibility pipeline is mutating.',
        '`SCHEMATIC_OWNER` defaults to `generated`',
        'does not protect the PCB',
        '`--check` does not rebuild design files, but it still rewrites check and status reports.',
        'The project directory must already exist.',
        'never overwrites an existing file',
    ):
        assert required_warning in normalized


def test_limitations_describe_current_draft_layout_capability(repo_root):
    limitations = (repo_root / 'docs/LIMITATIONS.md').read_text(encoding='utf-8')
    normalized = ' '.join(limitations.split())
    assert 'draft-only layout' in normalized
    assert 'Plan 5' in normalized and 'pcb_layout_helpers' in normalized
    assert 'Manual constraint' in normalized and 'new proposal' in normalized
    assert 'STEP' in normalized and 'partial' in normalized
    assert 'the new layout, unified review, and release interfaces remain planned' not in normalized
    assert 'Add real-footprint layout intents, measured placement, constraints' not in normalized


def test_progress_is_the_results_entry_point(repo_root):
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "docs/PROGRESS.md" in readme
    progress = (repo_root / "docs/PROGRESS.md").read_text(encoding="utf-8")
    for board in ("baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3"):
        assert f"../projects/{board}/.pcb-copilot/drafts/" in progress
        assert f"../projects/{board}/REFERENCE_REVIEW.md" in progress
    assert progress.count("/preview.pdf)") == 4
    assert progress.count("/preview.svg)") == 4
    assert "not approved" in progress
    assert "local" in progress and "fresh checkout" in progress
    assert "time saved" in progress


def test_project_format_reflects_implemented_layout_intents(repo_root):
    text = (repo_root / "docs/PROJECT_FORMAT.md").read_text(encoding="utf-8")
    assert "layout intents remain planned" not in text
    assert "planned reproducible layout intent" not in text
