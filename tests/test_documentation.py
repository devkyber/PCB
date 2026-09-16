import ast
import re
from pathlib import Path

import pytest

CANONICAL = {
    "purpose": Path("README.md"),
    "workflow": Path("docs/WORKFLOW.md"),
    "architecture": Path("docs/ARCHITECTURE.md"),
    "rules": Path("docs/DESIGN_RULES.md"),
    "limitations": Path("docs/LIMITATIONS.md"),
    "project_format": Path("docs/PROJECT_FORMAT.md"),
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
        assert target_path.exists(), f"{document} links to missing {target}"


def test_canonical_rules_preserve_legacy_ids_and_exact_checker_scope(repo_root):
    legacy = (repo_root / 'docs/pcb-design-rules.md').read_text(encoding='utf-8')
    canonical = (repo_root / 'docs/DESIGN_RULES.md').read_text(encoding='utf-8')
    legacy_ids = set(re.findall(r'^### (\d+\.\d+) ', legacy, re.MULTILINE))
    rows = re.findall(r'^\| `(\d+\.\d+)` \| ([^|]+) \| (Partial|Human) \|$',
                      canonical, re.MULTILINE)
    assert len(rows) == len(legacy_ids), 'preserve each historical rule ID exactly once'
    assert {rule for rule, _topic, _scope in rows} == legacy_ids
    checker = ast.parse((repo_root / 'docs/check_design_rules.py').read_text(encoding='utf-8'))
    constants = {node.targets[0].id: ast.literal_eval(node.value)
                 for node in checker.body if isinstance(node, ast.Assign)
                 and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id in {'EXECUTABLE_RULES', 'DOC_RULE_COUNT'}}
    assert len(rows) == constants['DOC_RULE_COUNT']
    assert {rule for rule, _topic, scope in rows if scope == 'Partial'} == set(
        constants['EXECUTABLE_RULES'])
