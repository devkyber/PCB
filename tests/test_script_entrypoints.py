"""Compatibility CLI remains usable after moving executable code out of docs."""

import subprocess
import sys


def test_pipeline_status_from_scripts_works_outside_repo(repo_root, tmp_path):
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts/pipeline.py"), "--status"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for board in ("baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3"):
        assert board in result.stdout
