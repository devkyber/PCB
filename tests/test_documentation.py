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
