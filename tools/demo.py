"""Run real first-use commands on an external copy of the saved Rover inputs.

Usage: uv run python tools/demo.py [--full] [--output NEW_DIRECTORY]
The quick demo needs Python dependencies, but does not require KiCad. Full
review needs the native toolchain. No fabrication package or approval is made.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

CLI_ENTRYPOINT = "from pcb_copilot.cli import entrypoint; entrypoint()"
GUARD_MESSAGE = "No successful matching unconsumed preview"


def new_output_directory(requested: Path | None, repository: Path) -> Path:
    """Require a new directory outside the checkout; never reuse owner files."""
    if requested is None:
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if temporary_root == repository.resolve() or temporary_root.is_relative_to(repository.resolve()):
            raise ValueError("temporary directory is inside the repository; select an external --output")
        output = Path(tempfile.mkdtemp(prefix="pcb-copilot-demo-")).resolve()
    else:
        output = requested.expanduser().resolve()
        if output == repository.resolve() or output.is_relative_to(repository.resolve()):
            raise ValueError("demo output must be outside the repository")
        output.mkdir(parents=True, exist_ok=False)
    return output


def snapshot_project(project, output: Path):
    """Copy the pipeline's declared inputs, excluding previews and history."""
    from pcb_copilot.project import load_project
    from pcb_copilot.transaction import copy_inputs, input_hashes

    before = input_hashes(project)
    destination = output / "workspace" / project.root.name
    copy_inputs(project, destination, before)
    snapshot = load_project(destination)
    if input_hashes(snapshot) != before:
        raise RuntimeError("disposable project does not match the saved inputs")
    return snapshot, before


def cad_hashes(inputs: dict) -> dict:
    return {path: digest for path, digest in inputs.items()
            if Path(path).suffix in {".kicad_sch", ".kicad_pcb", ".kicad_pro", ".kicad_dru"}}


def run_command(output: Path, name: str, arguments: list[str], *, timeout: int = 60) -> dict:
    """Capture a real process exit code and its unedited UTF-8 output."""
    logs = output / "logs"
    logs.mkdir(exist_ok=True)
    started = time.monotonic()
    environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    error = None
    exit_code = None
    try:
        result = subprocess.run(
            [sys.executable, "-c", CLI_ENTRYPOINT, *arguments], cwd=output,
            env=environment, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
        stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        stdout = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
        error = f"command exceeded {timeout} seconds; no exit code was observed"
    except OSError as exc:
        stdout, stderr, error = "", "", str(exc)
    stdout_path, stderr_path = logs / f"{name}.stdout.txt", logs / f"{name}.stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return {
        "name": name, "command": ["pcb-copilot", *arguments], "exit_code": exit_code,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": stdout_path.relative_to(output).as_posix(),
        "stderr": stderr_path.relative_to(output).as_posix(), "error": error,
    }


def step_output(output: Path, step: dict, stream: str) -> str:
    return (output / step[stream]).read_text(encoding="utf-8")


def write_report(output: Path, transcript: dict) -> None:
    (output / "transcript.json").write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    lines = [
        "# PCB Copilot first-use demo", "",
        f"Source: `{transcript['source_project']}` · mode: `{transcript['mode']}`", "",
        ("Commands ran on the disposable [workspace](workspace/rover-pdb/). "
         "Command paths below are relative to this report. Logs retain the exact process output."), "",
        "| Step | Actual exit code | Result | Logs |",
        "| --- | ---: | --- | --- |",
    ]
    for step in transcript["steps"]:
        result = step.get("interpretation", "command completed" if step["exit_code"] == 0 else "see logs")
        lines.append(f"| {step['name']} | {step['exit_code']} | {result} | "
                     f"[stdout]({step['stdout']}) · [stderr]({step['stderr']}) |")
    lines.extend(["", "## Saved inputs", "",
                  f"- Owner inputs unchanged: **{transcript.get('source_inputs_unchanged', False)}**",
                  f"- Owner CAD unchanged: **{transcript.get('source_cad_unchanged', False)}**",
                  f"- Disposable inputs unchanged: **{transcript.get('snapshot_inputs_unchanged', False)}**",
                  "- Exact per-file SHA-256 values: [transcript.json](transcript.json)", ""])
    review = transcript.get("review")
    if review is not None:
        lines.extend(["## Native review", "",
                      (f"Result: **{'BLOCKED' if review['blocking'] else 'no registered blocker'}**. "
                       "This is a check result, not fabrication approval."), "",
                      "| Check | Result |", "| --- | --- |"])
        lines.extend(f"| `{result['check_id']}` | {'PASS' if result['passed'] else 'FAIL'} |"
                     for result in review["results"])
        lines.extend(["", "Full findings, scope and limitations: [native review JSON](logs/review.stdout.txt).", ""])
    elif transcript["mode"] == "quick":
        lines.extend([("Native ERC/DRC and full board review were **not run**. "
                       "Use `--full` with KiCad installed to run the current registered checks."), ""])
    lines.extend(["## Interpretation", "",
                  ("The missing-preview step requests an apply only inside the disposable copy. "
                   "A rejection demonstrates the real preview prerequisite; it does not demonstrate "
                   "a successful preview, stale-preview detection, parity checking or a completed edit."), "",
                  ("Evidence verification checks archived bytes. It does not establish circuit "
                   "correctness. This demo records no human sign-off and creates no fabrication release."), "",
                  (f"Demo process exit code: `{transcript['exit_code']}`. "
                   "0 means the requested demo completed; 1 means evidence or full-review blockers "
                   "were reported; 2 means the demo could not complete or an invariant failed."), ""])
    if transcript.get("error"):
        lines.extend(["Error: " + transcript["error"], ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def execute_demo(repository: Path, output: Path, *, full: bool) -> dict:
    from pcb_copilot import __version__
    from pcb_copilot.project import load_project
    from pcb_copilot.toolchain import ToolchainDiscoveryError, discover_toolchain
    from pcb_copilot.transaction import input_hashes

    project = load_project(repository / "projects" / "rover-pdb")
    transcript = {
        "schema_version": 1, "started_utc": datetime.now(UTC).isoformat(),
        "pcb_copilot_version": __version__, "source_project": "projects/rover-pdb",
        "mode": "full" if full else "quick", "steps": [], "exit_code": 2,
    }
    snapshot = None
    before = input_hashes(project)
    try:
        snapshot, before = snapshot_project(project, output)
        relative = snapshot.root.relative_to(output).as_posix()
        print(f"Disposable project: {snapshot.root}", flush=True)
        for name, arguments in (
            ("status", ["status", relative]),
            ("evidence", ["research", relative, "--verify"]),
            ("missing-preview", ["update-schematic", relative, "--candidate",
                                 snapshot.schematic_path.relative_to(output).as_posix(), "--apply"]),
        ):
            print(f"Running {name}...", flush=True)
            step = run_command(output, name, arguments)
            transcript["steps"].append(step)
            if step["error"]:
                raise RuntimeError(step["error"])
            if name == "status" and step["exit_code"] != 0:
                raise RuntimeError("status could not run; inspect its logs")
            if name == "missing-preview":
                if step["exit_code"] != 2 or GUARD_MESSAGE not in step_output(output, step, "stderr"):
                    raise RuntimeError("expected missing-preview rejection was not observed")
                step["interpretation"] = "expected rejection; no matching successful preview"
        transcript["exit_code"] = int(transcript["steps"][1]["exit_code"] != 0)
        if full:
            try:
                discover_toolchain(repository)
            except ToolchainDiscoveryError as exc:
                raise RuntimeError(f"full review needs KiCad: {exc}; install KiCad and rerun --full") from exc
            print("Running full native review (may take several minutes)...", flush=True)
            step = run_command(output, "review", ["review", relative, "--format", "json"], timeout=900)
            transcript["steps"].append(step)
            if step["error"] or step["exit_code"] not in {0, 1}:
                raise RuntimeError(step["error"] or "native review could not run; inspect its logs")
            transcript["review"] = json.loads(step_output(output, step, "stdout"))
            if not isinstance(transcript["review"].get("blocking"), bool):
                raise RuntimeError("native review did not return a valid blocking result")
            step["interpretation"] = "review blocked" if transcript["review"]["blocking"] else "no registered blocker"
            transcript["exit_code"] = max(transcript["exit_code"], step["exit_code"])
    except (OSError, ValueError, RuntimeError) as exc:
        transcript.update(error=str(exc), exit_code=2)
    finally:
        after = input_hashes(project)
        snapshot_after = input_hashes(snapshot) if snapshot is not None else None
        transcript.update(
            source_inputs_before=before, source_inputs_after=after,
            source_inputs_unchanged=before == after,
            source_cad_before=cad_hashes(before), source_cad_after=cad_hashes(after),
            source_cad_unchanged=cad_hashes(before) == cad_hashes(after),
            snapshot_inputs_unchanged=snapshot_after == before,
        )
        if before != after or (snapshot is not None and snapshot_after != before):
            transcript.update(error="saved inputs changed during the demo; inspect the hash manifest", exit_code=2)
        write_report(output, transcript)
    return transcript


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new output directory outside the repository (default: temporary directory)")
    parser.add_argument("--full", action="store_true", help="also run native KiCad review; preserve its actual blockers")
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    try:
        output = new_output_directory(args.output, repository)
        transcript = execute_demo(repository, output, full=args.full)
    except ImportError as exc:
        print(f"Demo dependencies unavailable: {exc}. Run `uv sync`, then `uv run python tools/demo.py`.", file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Demo could not start: {exc}", file=sys.stderr)
        return 2
    print(f"Report: {output / 'report.md'}")
    print(f"Transcript: {output / 'transcript.json'}")
    print(f"Demo exit code: {transcript['exit_code']} (no fabrication approval)")
    return transcript["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
