import hashlib
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def project_copy(tmp_path: Path, repo_root: Path) -> Path:
    destination = tmp_path / "baro-bmp390"
    # Local previews, drafts and approvals are not part of the source fixture.
    shutil.copytree(
        repo_root / "projects" / "baro-bmp390", destination,
        ignore=shutil.ignore_patterns(".pcb-copilot"),
    )
    return destination


@pytest.fixture
def tree_hash():
    def calculate(root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

    return calculate
