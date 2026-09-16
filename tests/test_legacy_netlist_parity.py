import os
import stat
import subprocess
import sys
from pathlib import Path


def test_parity_script_bootstraps_repository_sources_without_site_packages(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    cli_dir = tmp_path / "cli"
    cli_dir.mkdir()
    cli_name = "kicad-cli.exe" if os.name == "nt" else "kicad-cli"
    cli = cli_dir / cli_name
    cli.touch()
    if os.name != "nt":
        cli.chmod(cli.stat().st_mode | stat.S_IXUSR)

    environment = os.environ.copy()
    environment.pop("KIPYTHON", None)
    environment["PATH"] = str(cli_dir)
    environment["ProgramFiles"] = str(tmp_path / "missing-program-files")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(repo / "docs" / "check_netlist_parity.py"),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2, result.stderr
    assert "Usage:  kipython check_netlist_parity.py" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr
