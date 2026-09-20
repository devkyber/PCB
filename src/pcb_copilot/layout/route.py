"""Optional, draft-only candidate routing orchestration.

Routing is never an acceptance operation.  Every attempt starts from the same
published layout draft, runs in its own directory, and remains there for human
comparison.  A selected attempt is only the best measured candidate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pcb_copilot.layout.models import RoutePolicy
from pcb_copilot.models import DraftKind, DraftRecord, Project
from pcb_copilot.project import load_project
from pcb_copilot.state import canonical_design_hash
from pcb_copilot.toolchain import ToolchainPaths, discover_toolchain

UNKNOWN_METRIC = -1


@dataclass(frozen=True)
class RouteAttempt:
    index: int
    pcb_path: Path
    drc_errors: int
    unconnected: int
    commands: tuple[str, ...]


@dataclass(frozen=True)
class RouteReport:
    attempts: tuple[RouteAttempt, ...]
    selected: int | None
    drc_errors: int
    unconnected: int
    limitations: tuple[str, ...]


class RouteBackendError(RuntimeError):
    """A candidate tool failed after zero or more recorded commands."""

    def __init__(self, message: str, commands: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.commands = tuple(commands)


_ROUTE_CHILD = r"""
import json,sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import subprocess
from kicad_claude.adapters import dsn_keepouts, route_pipeline

command_trace = []
operation_stack = []
original_run = subprocess.run
def traced_run(command, *args, **kwargs):
    argv = ([str(value) for value in command]
            if not isinstance(command, str) else [command])
    command_trace.append({
        'operation': operation_stack[-1] if operation_stack else 'pipeline.unknown',
        'argv': argv,
        'cwd': str(kwargs.get('cwd')) if kwargs.get('cwd') is not None else None,
    })
    return original_run(command, *args, **kwargs)
subprocess.run = traced_run

def wrap(owner, name, operation):
    original = getattr(owner, name)
    def traced(*args, **kwargs):
        operation_stack.append(operation() if callable(operation) else operation)
        try:
            return original(*args, **kwargs)
        finally:
            operation_stack.pop()
    setattr(owner, name, traced)

wrap(route_pipeline.kicad_python, 'export_dsn', 'pipeline.export_dsn')
wrap(dsn_keepouts, 'collect', 'pipeline.inspect_keepouts')
wrap(route_pipeline.kicad_python, 'import_ses', 'pipeline.import_ses')
wrap(route_pipeline.kicad_python, 'fill_zones', 'pipeline.fill_zones')
wrap(route_pipeline.kicad_python, 'bond_ground', 'pipeline.bond_ground')

drc_count = [0]
def drc_operation():
    drc_count[0] += 1
    return 'pipeline.drc.' + str(drc_count[0])
wrap(route_pipeline.kicad_cli, 'run_drc', drc_operation)

captured = {}
original = route_pipeline.freerouting.route
def route(*args, **kwargs):
    operation_stack.append('pipeline.freerouting')
    try:
        result = original(*args, **kwargs)
        captured.update(result)
        return result
    finally:
        operation_stack.pop()
route_pipeline.freerouting.route = route
try:
    result = route_pipeline.route_board(
        Path(sys.argv[2]), passes=int(sys.argv[3]), timeout_seconds=900.0, backup=False
    )
except Exception as exc:
    result = {'_pipeline_error': type(exc).__name__ + ': ' + str(exc)}
result['_router_details'] = captured
result['_command_trace'] = command_trace
print('PCB_COPILOT_ROUTE_RESULT=' + json.dumps(result))
"""

_POUR_LAYERS_CHILD = r"""
import json,pcbnew,sys
board=pcbnew.LoadBoard(sys.argv[1])
layers=sorted({str(board.GetLayerName(zone.GetLayer())) for zone in board.Zones()
               if not zone.GetIsRuleArea() and str(zone.GetNetname()) == 'GND'})
print('PCB_COPILOT_POUR_LAYERS=' + json.dumps(layers))
print('PCB_COPILOT_KICAD_VERSION=' + str(pcbnew.GetBuildVersion()))
"""


def _command_text(command: Sequence[object]) -> str:
    return subprocess.list2cmdline([str(value) for value in command])


def _marker(stdout: str, prefix: str) -> str:
    for line in reversed(stdout.splitlines()):
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise ValueError(f"command output omitted {prefix.rstrip('=')}")


class RouteBackend:
    """Subprocess boundary for the shared routing pipeline and post-processors.

    ``runner`` is constructor-injected so policy and orchestration tests can use
    an offline callable that records exact command vectors.
    """

    def __init__(
        self,
        runner: Callable[..., Any] = subprocess.run,
        *,
        repo_root: Path | None = None,
        toolchain: ToolchainPaths | None = None,
        passes: int = 100,
    ) -> None:
        self.runner = runner
        self.repo_root = (
            Path(repo_root).resolve()
            if repo_root is not None
            else Path(__file__).resolve().parents[3]
        )
        self.toolchain = toolchain or discover_toolchain(self.repo_root)
        if passes < 1:
            raise ValueError("router passes must be at least 1")
        self.passes = passes
        legacy_override = os.environ.get("KICAD_PYTHON")
        self.kipython = (
            Path(legacy_override).expanduser().resolve()
            if legacy_override and Path(legacy_override).is_file()
            else self.toolchain.kipython
        )

    def _run(
        self,
        command: Sequence[object],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> Any:
        result = self.runner(
            [str(value) for value in command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=dict(env) if env is not None else None,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout or "").strip()[-600:]
            raise RuntimeError(
                f"command failed with exit {result.returncode}: "
                f"{_command_text(command)}: {detail}"
            )
        return result

    def run_attempt(
        self, pcb_path: Path
    ) -> tuple[int, int, tuple[str, ...], tuple[str, ...]]:
        if self.kipython is None:
            raise RouteBackendError(
                "native KiCad Python is required for candidate routing; "
                "tool discovery found kicad-cli but no pcbnew-capable interpreter"
            )
        commands: list[str] = []
        limitations: list[str] = []
        legacy_src = self.repo_root / "tools" / "kicad-claude-mcp" / "src"
        route_command = [
            sys.executable,
            "-I",
            "-c",
            _ROUTE_CHILD,
            legacy_src,
            pcb_path,
            self.passes,
        ]
        commands.append(_command_text(route_command))
        child_env = dict(os.environ)
        # A child-only override bridges root KIPYTHON discovery to the legacy
        # adapter's documented KICAD_PYTHON name without mutating this process.
        child_env["KICAD_PYTHON"] = str(self.kipython)
        try:
            routed = self._run(route_command, timeout=960, env=child_env)
            result = json.loads(_marker(routed.stdout, "PCB_COPILOT_ROUTE_RESULT="))
            trace = result.get("_command_trace")
            if not isinstance(trace, list):
                raise TypeError("shared route pipeline omitted its command trace")
            for entry in trace:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("operation"), str)
                    or not isinstance(entry.get("argv"), list)
                ):
                    raise TypeError(
                        "shared route pipeline returned malformed command trace"
                    )
                commands.append(f"{entry['operation']}: {_command_text(entry['argv'])}")
            if result.get("_pipeline_error"):
                raise RuntimeError(
                    f"shared route pipeline failed: {result['_pipeline_error']}"
                )
            details = result.get("_router_details") or {}
            if details:
                limitations.append(
                    "Freerouting "
                    f"{details.get('jar_version', 'unknown')} via "
                    f"{details.get('java', 'unknown Java')}"
                )
                java_command = [details.get("java", "java"), "-version"]
                commands.append(_command_text(java_command))
                java_result = self._run(java_command, timeout=30)
                java_version = (
                    (java_result.stderr or java_result.stdout or "unknown")
                    .strip()
                    .splitlines()[0]
                )
                limitations.append(f"Java runtime: {java_version}")

            layer_command = [
                self.kipython,
                "-I",
                "-c",
                _POUR_LAYERS_CHILD,
                pcb_path,
            ]
            commands.append(_command_text(layer_command))
            layer_result = self._run(layer_command, timeout=60)
            layers = tuple(
                json.loads(_marker(layer_result.stdout, "PCB_COPILOT_POUR_LAYERS="))
            )
            try:
                kicad_version = _marker(
                    layer_result.stdout, "PCB_COPILOT_KICAD_VERSION="
                )
            except ValueError:
                kicad_version = "unknown"
            limitations.append(f"KiCad pcbnew {kicad_version}")

            if len(layers) >= 2:
                stitch_command = [
                    self.kipython,
                    "-I",
                    self.repo_root / "scripts" / "stitch_vias.py",
                    pcb_path,
                ]
                commands.append(_command_text(stitch_command))
                self._run(stitch_command, timeout=300)
            else:
                limitations.append(
                    "Grid stitching skipped: fewer than two native pour layers; "
                    "the shared pipeline's DRC-targeted ground-pad bonding remains distinct"
                )

            annular_command = [
                self.kipython,
                "-I",
                self.repo_root / "scripts" / "fix_via_annular.py",
                pcb_path,
            ]
            commands.append(_command_text(annular_command))
            self._run(annular_command, timeout=120)

            drc_path = pcb_path.with_suffix(".fresh-drc.json")
            drc_command = [
                self.toolchain.kicad_cli,
                "pcb",
                "drc",
                "--format",
                "json",
                "--severity-all",
                "-o",
                drc_path,
                pcb_path,
            ]
            commands.append(_command_text(drc_command))
            self._run(drc_command, timeout=180)
            if not drc_path.is_file():
                raise ValueError("fresh DRC command produced no JSON report")
            drc = json.loads(drc_path.read_text(encoding="utf-8"))
            violations = drc.get("violations")
            unconnected_items = drc.get("unconnected_items")
            if not isinstance(violations, list) or not isinstance(
                unconnected_items, list
            ):
                raise TypeError("fresh DRC JSON omitted measured result lists")
            errors = sum(
                (item.get("severity") or "").lower() == "error"
                for item in violations
                if isinstance(item, dict)
            )
            unconnected = len(unconnected_items)
            if drc.get("kicad_version"):
                limitations.append(
                    f"Fresh DRC reported by KiCad {drc['kicad_version']}"
                )
            return errors, unconnected, tuple(commands), tuple(limitations)
        except (
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
            subprocess.SubprocessError,
        ) as exc:
            raise RouteBackendError(str(exc), commands) from exc


def _default_backend(project: Project) -> RouteBackend:
    del project
    return RouteBackend()


_backend_factory: Callable[[Project], RouteBackend] = _default_backend


def _published_draft_pcb(project: Project, draft: DraftRecord) -> Path:
    from pcb_copilot.accept import load_draft
    from pcb_copilot.drafts import _project_root

    try:
        canonical_project_root = _project_root(draft)
        persisted = load_draft(project, draft.id)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise ValueError(f"draft root/ID is not canonical: {exc}") from exc
    if canonical_project_root.resolve() != project.root.resolve():
        raise ValueError("draft root is not canonical for the requested project")
    if draft != persisted:
        raise ValueError("caller DraftRecord does not match persisted draft metadata")
    if persisted.kind is not DraftKind.LAYOUT:
        raise ValueError("candidate routing requires a published layout draft")
    if persisted.project != project.manifest.name:
        raise ValueError("draft belongs to a different project")
    try:
        relative = project.pcb_path.resolve().relative_to(project.root.resolve())
    except ValueError as exc:
        raise ValueError("project PCB is outside the project root") from exc
    pcb_path = (persisted.root / relative).resolve()
    try:
        pcb_path.relative_to(persisted.root)
    except ValueError as exc:
        raise ValueError("draft PCB resolves outside the draft root") from exc
    if not pcb_path.is_file():
        raise ValueError("candidate routing requires a published layout draft")
    if (
        canonical_design_hash(project.pcb_path) != persisted.base_pcb_hash
        or canonical_design_hash(project.schematic_path)
        != persisted.base_schematic_hash
    ):
        raise ValueError("accepted design changed after this layout draft was created")
    return pcb_path


def _copy_attempt_inputs(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    pcb = destination / source.name
    shutil.copy2(source, pcb)
    for suffix in (".kicad_pro", ".kicad_dru"):
        companion = source.with_suffix(suffix)
        if companion.is_file():
            shutil.copy2(companion, destination / companion.name)
    return pcb


def _write_report(path: Path, report: RouteReport) -> None:
    document = asdict(report)
    for attempt in document["attempts"]:
        attempt["pcb_path"] = str(attempt["pcb_path"])
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def route_candidate(
    project: Project,
    draft: DraftRecord,
    policy: RoutePolicy,
    attempts: int,
) -> RouteReport:
    """Create and score optional routing candidates without touching acceptance.

    ``-1`` is the explicit unknown-metric sentinel when no fresh DRC result is
    available.  It is never interpreted as clean or included in selection.
    """
    return _route_candidate(project, draft, policy, attempts, None)


def _route_candidate(
    project: Project,
    draft: DraftRecord,
    policy: RoutePolicy,
    attempts: int,
    backend: RouteBackend | None,
) -> RouteReport:
    policy = RoutePolicy(policy)
    if policy is RoutePolicy.HUMAN:
        return RouteReport(
            (),
            None,
            UNKNOWN_METRIC,
            UNKNOWN_METRIC,
            ("Human routing policy: no router or post-processor was invoked",),
        )
    if policy is RoutePolicy.CRITICAL_ONLY:
        return RouteReport(
            (),
            None,
            UNKNOWN_METRIC,
            UNKNOWN_METRIC,
            (
                (
                    "Critical-only routing is unsupported by this backend; choose "
                    "human routing or explicitly authorize candidate-all. "
                    "No nets were routed."
                ),
            ),
        )
    if attempts < 1:
        raise ValueError("candidate routing attempts must be at least 1")

    source = _published_draft_pcb(project, draft)
    backend = backend or _backend_factory(project)
    run_root = draft.root / "routing" / f"run-{uuid.uuid4().hex[:12]}"
    run_root.mkdir(parents=True, exist_ok=False)
    route_attempts: list[RouteAttempt] = []
    limitations = [
        "Candidate routing only: selection is not acceptance, sign-off, fabrication approval, or proof of layout quality",
        "Freerouting via_keepout enforcement remains unverified",
        "Pad-local DSN protection is conservative; connected-pad overrides and full typed-rule applicability remain unsupported",
    ]
    for index in range(1, attempts + 1):
        pcb_path = _copy_attempt_inputs(source, run_root / f"attempt-{index:03d}")
        try:
            errors, unconnected, commands, attempt_limits = backend.run_attempt(
                pcb_path
            )
            limitations.extend(attempt_limits)
        except RouteBackendError as exc:
            errors = unconnected = UNKNOWN_METRIC
            commands = exc.commands
            limitations.append(
                f"Attempt {index} failed; DRC and connectivity are unknown: {exc}"
            )
        route_attempts.append(
            RouteAttempt(index, pcb_path, errors, unconnected, tuple(commands))
        )

    measured = [
        item
        for item in route_attempts
        if item.unconnected >= 0 and item.drc_errors >= 0
    ]
    selected_attempt = (
        min(measured, key=lambda item: (item.unconnected, item.drc_errors, item.index))
        if measured
        else None
    )
    report = RouteReport(
        attempts=tuple(route_attempts),
        selected=selected_attempt.index if selected_attempt else None,
        drc_errors=(
            selected_attempt.drc_errors if selected_attempt else UNKNOWN_METRIC
        ),
        unconnected=(
            selected_attempt.unconnected if selected_attempt else UNKNOWN_METRIC
        ),
        limitations=tuple(dict.fromkeys(limitations)),
    )
    _write_report(run_root / "route-report.json", report)
    return report


def _context_for_candidate_path(pcb_path: Path) -> tuple[Project, DraftRecord]:
    pcb_path = pcb_path.expanduser().resolve()
    draft_root = next(
        (
            parent
            for parent in (pcb_path.parent, *pcb_path.parents)
            if (parent / "draft.json").is_file()
        ),
        None,
    )
    if (
        draft_root is None
        or draft_root.parent.name != "drafts"
        or draft_root.parent.parent.name != ".pcb-copilot"
    ):
        raise ValueError(
            "routing wrapper accepts only a published .pcb-copilot/drafts/<id> "
            "board; create/review a layout draft and route that copy"
        )
    project = load_project(draft_root.parent.parent.parent)
    metadata = json.loads((draft_root / "draft.json").read_text(encoding="utf-8"))
    created = datetime.fromisoformat(metadata["created_utc"].replace("Z", "+00:00"))
    record = DraftRecord(
        id=metadata["id"],
        kind=DraftKind(metadata["kind"]),
        project=metadata["project"],
        base_schematic_hash=metadata["base_schematic_hash"],
        base_pcb_hash=metadata["base_pcb_hash"],
        created_utc=created,
        root=draft_root,
    )
    expected = draft_root / project.pcb_path.relative_to(project.root)
    if pcb_path != expected.resolve():
        raise ValueError(
            "routing wrapper input must be the published draft's declared PCB, "
            "not an accepted board or unvalidated arbitrary copy"
        )
    return project, record


def legacy_route_cli(arguments: Sequence[str], *, best_of: bool) -> int:
    """Compatibility implementation for scripts/route_{and_fill,best_of}.py."""
    if not arguments:
        raise ValueError("a published layout-draft .kicad_pcb path is required")
    pcb_path = Path(arguments[0])
    if best_of:
        attempts = int(arguments[1]) if len(arguments) > 1 else 5
        passes = int(arguments[2]) if len(arguments) > 2 else 200
    else:
        attempts = 1
        passes = int(arguments[1]) if len(arguments) > 1 else 50
    if len(arguments) > (3 if best_of else 2):
        raise ValueError("too many routing wrapper arguments")
    project, record = _context_for_candidate_path(pcb_path)
    report = _route_candidate(
        project,
        record,
        RoutePolicy.CANDIDATE_ALL,
        attempts,
        RouteBackend(passes=passes),
    )
    print(
        json.dumps(
            {
                "selected": report.selected,
                "drc_errors": _present_metric(report.drc_errors),
                "unconnected": _present_metric(report.unconnected),
                "limitations": report.limitations,
                "attempts": [
                    {
                        "index": item.index,
                        "pcb_path": str(item.pcb_path),
                        "drc_errors": _present_metric(item.drc_errors),
                        "unconnected": _present_metric(item.unconnected),
                    }
                    for item in report.attempts
                ],
            },
            indent=2,
        )
    )
    return (
        0
        if report.selected is not None
        and report.unconnected == 0
        and report.drc_errors == 0
        else 1
    )


def _present_metric(value: int) -> int | str:
    return "unknown" if value == UNKNOWN_METRIC else value
