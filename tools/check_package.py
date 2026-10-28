"""Build both workspace wheels and smoke-test an installed copy outside the repo.

Run with ``uv run python tools/check_package.py``. Requires uv and dependency
index access; this checks Python packaging, not KiCad or board qualification.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

PROBE = r'''
import hashlib
import json
import sys
from pathlib import Path

import kicad_claude
import pcb_copilot
from pcb_copilot.jlcpcb import BASELINE_STEM, baseline_bytes

installed = Path(sys.prefix).resolve()
for module in (pcb_copilot, kicad_claude):
    location = Path(module.__file__).resolve()
    assert location.is_relative_to(installed), f"Not an installed wheel: {location}"

expected = json.loads(sys.argv[1])
settings, rules = baseline_bytes()
actual = {
    BASELINE_STEM + ".kicad_pro": hashlib.sha256(settings).hexdigest(),
    BASELINE_STEM + ".kicad_dru": hashlib.sha256(rules).hexdigest(),
}
assert actual == expected, (actual, expected)
assert json.loads(settings)["board"]["design_settings"]["rules"]
assert b"(version 1)" in rules
print("Both installed workspace packages and exact JLCPCB baseline resources verified.")
'''


def run(command: list[str], *, cwd: Path, environ: dict[str, str]) -> None:
    subprocess.run(command, cwd=cwd, env=environ, check=True, timeout=300)


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required to build and install the workspace wheels")
    environ = dict(os.environ)
    # The isolated interpreter and external working directory must not import
    # an editable checkout through inherited Python path configuration.
    environ.pop("PYTHONPATH", None)
    environ.pop("PYTHONHOME", None)
    baseline = repository / "templates" / "jlcpcb-2layer-1oz"
    expected = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            baseline / "jlcpcb-2layer-1oz.kicad_pro",
            baseline / "jlcpcb-2layer-1oz.kicad_dru",
        )
    }
    with tempfile.TemporaryDirectory(prefix="pcb-package-check-") as directory:
        outside = Path(directory).resolve()
        if outside.is_relative_to(repository):
            raise RuntimeError("Package smoke-check temporary directory must be outside the repository")
        wheels = outside / "wheels"
        run([uv, "build", "--all-packages", "--wheel", "--out-dir", str(wheels)],
            cwd=repository, environ=environ)
        artifacts = sorted(wheels.glob("*.whl"))
        packages = {path.name.split("-", 1)[0]: path for path in artifacts}
        if set(packages) != {"pcb_copilot", "kicad_claude_mcp"} or len(artifacts) != 2:
            raise RuntimeError(f"Expected both workspace wheels; found {[p.name for p in artifacts]}")
        with ZipFile(packages["pcb_copilot"]) as archive:
            for name, digest in expected.items():
                source = archive.read(f"pcb_copilot/resources/jlcpcb-2layer-1oz/{name}")
                if hashlib.sha256(source).hexdigest() != digest:
                    raise RuntimeError(f"Wheel baseline differs from canonical template: {name}")
        environment = outside / "installed"
        run([uv, "venv", "--python", sys.executable, str(environment)], cwd=outside, environ=environ)
        binary = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binary / ("python.exe" if os.name == "nt" else "python")
        run([uv, "pip", "install", "--python", str(python), *map(str, artifacts)],
            cwd=outside, environ=environ)
        run([uv, "pip", "check", "--python", str(python)], cwd=outside, environ=environ)
        run([str(python), "-I", "-c", PROBE, json.dumps(expected)], cwd=outside, environ=environ)
        cli = binary / ("pcb-copilot.exe" if os.name == "nt" else "pcb-copilot")
        run([str(cli), "--version"], cwd=outside, environ=environ)
        run([str(cli), "--help"], cwd=outside, environ=environ)
    print("Wheel installation smoke check passed; native KiCad checks were not run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
