"""Exercise a small, declared fault set on disposable copies of gpio-indicator.

Run: uv run python tools/evaluate.py [--native] [--output NEW_EXTERNAL_DIRECTORY]
No source CAD, approval, or fabrication package is written. This is a software
regression exercise, not engineering validation or a comparative benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

CLI = 'from pcb_copilot.cli import entrypoint; entrypoint()'
VALIDATOR = '''import json, sys
from pathlib import Path
from pcb_copilot.project import load_project
from pcb_copilot.layout.footprints import resolve_footprint
project = load_project(Path(sys.argv[1]))
try:
    results = [resolve_footprint(project, ref, lib_id) for ref, lib_id in json.loads(sys.argv[2])]
except ValueError as error:
    print(json.dumps({'accepted': False, 'exception': type(error).__name__, 'message': str(error)}))
    sys.exit(1)
print(json.dumps({'accepted': True, 'footprints': len(results), 'fidelities': [r.fidelity for r in results]}))
'''
GUARD_MESSAGE = 'No successful matching unconsumed preview'
NATIVE_SCENARIOS = (
    ('native-preview-control', 'changed-candidate', 'candidate-bytes'),
    ('native-source-preview-control', 'changed-source-schematic', 'source-schematic'),
    ('native-rules-preview-control', 'changed-source-rules', 'source-rules'),
)
NATIVE_CASE_NAMES = tuple(name for control, fault, _kind in NATIVE_SCENARIOS for name in (control, fault))


def new_output_directory(requested: Path | None, repository: Path) -> Path:
    parent = Path(tempfile.gettempdir()).resolve() if requested is None else requested.expanduser().resolve()
    if parent == repository.resolve() or parent.is_relative_to(repository.resolve()):
        raise ValueError('evaluation output must be outside the repository')
    if requested is None:
        return Path(tempfile.mkdtemp(prefix='pcb-copilot-evaluation-', dir=parent)).resolve()
    parent.mkdir(parents=True, exist_ok=False)
    return parent


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _implementation(repository: Path) -> dict:
    paths = [repository / 'tools/evaluate.py']
    for directory in ('src/pcb_copilot', 'packages/kicad-claude-mcp/src'):
        paths.extend((repository / directory).rglob('*.py'))
    return {path.relative_to(repository).as_posix(): _hash(path) for path in sorted(paths)}


def snapshot_project(source, output: Path, name: str, expected: dict):
    from pcb_copilot.project import load_project
    from pcb_copilot.transaction import copy_inputs, input_hashes

    if output.resolve() == source.root.resolve() or output.resolve().is_relative_to(source.root.resolve()):
        raise ValueError('evaluation snapshots must be outside the source project')
    destination = output / 'workspaces' / name / source.root.name
    copy_inputs(source, destination, expected)
    snapshot = load_project(destination)
    if input_hashes(snapshot) != expected:
        raise RuntimeError('disposable snapshot does not match the source input manifest')
    return snapshot


def _targets(project) -> tuple[list[list[str]], dict, list[str]]:
    from kicad_claude.adapters import sch_io

    from pcb_copilot.schematic.preview import schematic_files

    records = json.loads((project.root / 'libs/PROVENANCE.json').read_bytes())['records']
    record = next(item for item in records if not item.get('fabricated_only') and item['models'])
    targets = []
    for path in schematic_files(project.schematic_path):
        for symbol in sch_io.find_children(sch_io.parse_file(path), 'symbol'):
            fields = {str(item[1]): str(item[2]) for item in sch_io.find_children(symbol, 'property')}
            if fields.get('Reference', '').startswith('#') or not fields.get('Footprint'):
                continue
            pair = [fields['Reference'], fields['Footprint']]
            if pair not in targets:
                targets.append(pair)
    selected = next(pair for pair in targets if pair[1] == record['footprint'])
    return targets, record, selected


def inject_fault(project, kind: str) -> dict:
    """Alter only a declared input in this external case's snapshot."""
    from kicad_claude.adapters import sch_io

    from pcb_copilot.evidence.index import load_evidence_index
    from pcb_copilot.schematic.preview import schematic_files
    from pcb_copilot.transaction import contained

    if kind in {'candidate-bytes', 'source-schematic', 'source-rules'}:
        path = project.pcb_path.with_suffix('.kicad_dru') if kind == 'source-rules' else project.schematic_path
        if not path.is_file():
            raise ValueError(f'evaluation requires an existing fault target: {path.name}')
        before = _hash(path)
        path.write_bytes(path.read_bytes() + b'\n')
        return {'kind': kind, 'target': path.relative_to(project.root).as_posix(),
                'before_sha256': before, 'after_sha256': _hash(path),
                'detail': 'One trailing newline was added after a real preview; circuit/rule semantics were not changed.'}
    _, record, selected = _targets(project)
    if kind == 'evidence-corruption':
        source = load_evidence_index(project.evidence_index_path).records[0]
        path = contained(project.root, project.evidence_index_path.parent / source.path)
        path.write_bytes(path.read_bytes() + b'\nEVALUATION CORRUPTION\n')
    elif kind == 'footprint-geometry':
        path = contained(project.root, project.root / record['local_path'])
        payload = path.read_bytes()
        match = re.search(rb'(\(pad\s+"[^"]*"\s+\w+\s+\w+.*?\(size\s+)([-+0-9.]+)', payload, re.DOTALL)
        if match is None:
            raise ValueError('evaluation could not locate a numbered pad size')
        payload = payload[:match.start(2)] + str(float(match[2]) + 0.1).encode() + payload[match.end(2):]
        path.write_bytes(payload)
        # A refreshed local hash must not authorize a geometry change from upstream.
        manifest = project.root / 'libs/PROVENANCE.json'
        data = json.loads(manifest.read_bytes())
        next(item for item in data['records'] if item['local_path'] == record['local_path'])['local_sha256'] = _hash(path)
        manifest.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    elif kind == 'model-corruption':
        path = contained(project.root, project.root / record['models'][0]['path'])
        path.write_bytes(path.read_bytes() + b'\nEVALUATION CORRUPTION\n')
    elif kind == 'selected-mpn':
        changed = []
        for path in schematic_files(project.schematic_path):
            tree = sch_io.parse_file(path)
            for symbol in sch_io.find_children(tree, 'symbol'):
                properties = sch_io.find_children(symbol, 'property')
                fields = {str(item[1]): str(item[2]) for item in properties}
                if fields.get('Reference') == selected[0]:
                    next(item for item in properties if str(item[1]) == 'MPN')[2] = record['mpn'] + '-EVALUATION-FAULT'
                    changed.append(path)
            if path in changed:
                path.write_text(sch_io.dumps(tree), encoding='utf-8')
        if not changed:
            raise ValueError('evaluation could not locate the selected native MPN')
        path = changed[0]
    else:
        raise ValueError(f'unknown evaluation fault: {kind}')
    return {'kind': kind, 'target': path.relative_to(project.root).as_posix(),
            'selected_reference': selected[0], 'selected_footprint': selected[1]}


def run_process(output: Path, name: str, interface: str, arguments: list[str], *, timeout: int = 60) -> dict:
    logs = output / 'logs'
    logs.mkdir(exist_ok=True)
    code = CLI if interface in {'cli', 'native-cli'} else VALIDATOR
    command = [sys.executable, '-c', code, *arguments]
    started = time.monotonic()
    error, returncode = None, None
    try:
        result = subprocess.run(command, cwd=output, capture_output=True, check=False, timeout=timeout,
                                env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1'))
        stdout, stderr, returncode = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b'', exc.stderr or b''
        error = f'command exceeded {timeout}s; no process exit code observed'
    except OSError as exc:
        stdout, stderr, error = b'', b'', str(exc)
    stdout_path, stderr_path = logs / f'{name}.stdout.txt', logs / f'{name}.stderr.txt'
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    return {'interface': interface, 'arguments': arguments, 'executed_argv': command,
            'exit_code': returncode, 'duration_seconds': round(time.monotonic() - started, 3),
            'stdout': stdout_path.relative_to(output).as_posix(),
            'stderr': stderr_path.relative_to(output).as_posix(), 'error': error}


def classify_result(actual: dict, stdout: str, stderr: str, expected_code: int, diagnostic: str) -> str:
    if actual['error'] is not None or actual['exit_code'] is None:
        return 'harness_error'
    if actual['interface'] == 'validator-api':
        try:
            payload = json.loads(stdout)
            accepted = payload['accepted']
            if type(accepted) is not bool:
                return 'harness_error'
        except (ValueError, KeyError, TypeError):
            return 'harness_error'
        if accepted != (expected_code == 0):
            return 'mismatch'
        if accepted:
            fidelities = payload.get('fidelities')
            if not isinstance(fidelities, list) or not fidelities:
                return 'harness_error'
            if any(item != 'real' for item in fidelities):
                return 'mismatch'
    if actual['exit_code'] != expected_code or diagnostic not in stdout + stderr:
        return 'mismatch'
    if actual['interface'] == 'native-cli' and expected_code == 0:
        try:
            payload = json.loads(stdout)
            if (not isinstance(payload, dict) or type(payload.get('exit_code')) is not int
                    or payload['exit_code'] != 0 or payload.get('applied') is not False
                    or payload.get('source_mode') != 'native'
                    or not isinstance(payload.get('findings'), list)
                    or any(not isinstance(item, dict) or item.get('severity') != 'review'
                           for item in payload['findings'])):
                return 'harness_error'
        except (ValueError, TypeError):
            return 'harness_error'
    return 'met_expectation'


def _case(source, output: Path, name: str, expected: dict, *, interface: str,
          expected_code: int, diagnostic: str, fault: str | None = None,
          project=None, candidate=None, arguments: list[str] | None = None,
          timeout: int = 60) -> tuple[dict, object]:
    from pcb_copilot.transaction import input_hashes

    project = project or snapshot_project(source, output, name, expected)
    before = input_hashes(project)
    candidate_before = input_hashes(candidate) if candidate else None
    if fault == 'candidate-bytes' and candidate is None:
        raise ValueError('candidate-byte fault requires a separate candidate project')
    fault_project = candidate if fault == 'candidate-bytes' else project
    injection = inject_fault(fault_project, fault) if fault else None
    if injection:
        injection['workspace'] = fault_project.root.relative_to(output).as_posix()
    injected = input_hashes(project)
    candidate_injected = input_hashes(candidate) if candidate else None
    if fault and injected == before and candidate_injected == candidate_before:
        raise RuntimeError('fault injection did not change any declared input')
    targets, _, _ = _targets(project)
    relative = project.root.relative_to(output).as_posix()
    if arguments is None:
        if interface == 'validator-api':
            arguments = [relative, json.dumps(targets)]
        elif name == 'missing-preview':
            arguments = ['update-schematic', relative, '--candidate',
                         project.schematic_path.relative_to(output).as_posix(), '--apply']
        else:
            arguments = ['research', relative, '--verify']
    print(f'Evaluating {name} ({interface})...', flush=True)
    actual = run_process(output, name, interface, arguments, timeout=timeout)
    stdout = (output / actual['stdout']).read_text(encoding='utf-8', errors='replace')
    stderr = (output / actual['stderr']).read_text(encoding='utf-8', errors='replace')
    outcome = classify_result(actual, stdout, stderr, expected_code, diagnostic)
    after = input_hashes(project)
    candidate_after = input_hashes(candidate) if candidate else None
    if after != injected or candidate_after != candidate_injected:
        outcome = 'harness_error'
        actual['error'] = 'checks changed declared snapshot or candidate inputs'
    result = {'name': name, 'workspace': relative, 'injection': injection,
              'expected': {'exit_code': expected_code, 'diagnostic_contains': diagnostic},
              'actual': actual, 'outcome': outcome, 'inputs_before': before,
              'inputs_after_injection': injected, 'inputs_after_checks': after,
              'checks_preserved_inputs': after == injected}
    if candidate:
        result.update(candidate=candidate.root.relative_to(output).as_posix(),
                      candidate_inputs_before=candidate_before, candidate_inputs_after_injection=candidate_injected,
                      candidate_inputs_after_checks=candidate_after,
                      checks_preserved_candidate=candidate_after == candidate_injected)
    if injection and 'after_sha256' in injection:
        injection['after_check_sha256'] = _hash(fault_project.root / injection['target'])
    return result, project


def _check_native_control(control: dict, output: Path, expected: dict, project, candidate) -> None:
    """A matching exit/diagnostic alone is insufficient to establish the preview."""
    from pcb_copilot.schematic.preview import schematic_files

    if control['outcome'] != 'met_expectation':
        return
    try:
        preview = json.loads((output / control['actual']['stdout']).read_bytes())
        binding = preview.get('preview_binding') if isinstance(preview, dict) else None
        sources = {'schematic/' + path.relative_to(candidate.schematic_path.parent).as_posix():
                   {'path': str(path.resolve()), 'sha256': _hash(path)}
                   for path in schematic_files(candidate.schematic_path)}
        if (not isinstance(binding, dict) or type(binding.get('version')) is not int or binding['version'] != 1
                or binding.get('inputs') != expected or binding.get('project') != str(project.root.resolve())
                or binding.get('options') != {'mode': 'native', 'paired_pcb': False}
                or binding.get('sources') != sources):
            raise ValueError('native preview did not bind the exact saved snapshot, candidate and options')
    except (OSError, ValueError, TypeError) as exc:
        control['outcome'] = 'harness_error'
        control['actual']['error'] = str(exc)


def _native_cases(source, output: Path, expected: dict) -> list[dict]:
    from pcb_copilot.project import load_project
    from pcb_copilot.toolchain import discover_toolchain
    from pcb_copilot.transaction import copy_inputs

    tools = discover_toolchain(Path(__file__).resolve().parents[1])
    version = subprocess.run([str(tools.kicad_cli), '--version'], capture_output=True,
                             check=False, timeout=10)
    if version.returncode:
        raise RuntimeError('native evaluation could not probe kicad-cli --version')
    if tools.kipython is None:
        raise RuntimeError('native evaluation requires KiCad Python with pcbnew; run pcb-copilot doctor')
    pcbnew = subprocess.run([str(tools.kipython), '-I', '-c',
                            'import pcbnew; print(pcbnew.GetBuildVersion())'],
                           capture_output=True, check=False, timeout=10)
    if pcbnew.returncode:
        raise RuntimeError('native evaluation could not import pcbnew; run pcb-copilot doctor')
    cases = []
    for control_name, fault_name, kind in NATIVE_SCENARIOS:
        project = snapshot_project(source, output, control_name, expected)
        candidate_root = output / 'candidates' / fault_name / source.root.name
        copy_inputs(source, candidate_root, expected)
        candidate = load_project(candidate_root)
        arguments = ['update-schematic', project.root.relative_to(output).as_posix(), '--candidate',
                     candidate.schematic_path.relative_to(output).as_posix()]
        control, _ = _case(source, output, control_name, expected, interface='native-cli',
                           expected_code=0, diagnostic='"source_mode": "native"', project=project,
                           candidate=candidate, arguments=arguments, timeout=300)
        control['native_tool_version'] = version.stdout.decode('utf-8', errors='replace').strip()
        control['native_pcbnew_version'] = pcbnew.stdout.decode('utf-8', errors='replace').strip()
        _check_native_control(control, output, expected, project, candidate)
        cases.append(control)
        if control['outcome'] != 'met_expectation':
            cases.append({'name': fault_name, 'outcome': 'skipped', 'depends_on': control_name,
                          'reason': 'a real successful matching native preview was not obtained'})
            continue
        stale, _ = _case(source, output, fault_name, expected, interface='native-cli',
                         expected_code=2, diagnostic=GUARD_MESSAGE, fault=kind, project=project,
                         candidate=candidate, arguments=[*arguments, '--apply'])
        stale['depends_on'] = control_name
        cases.append(stale)
    return cases


def write_report(output: Path, report: dict) -> None:
    (output / 'evaluation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    lines = ['# PCB Copilot fault evaluation', '',
             f"Run: `{report['started_utc']}` · mode: `{report['mode']}`", '',
             ('This is a small manually selected software regression exercise. '
              'A met expectation is not a design approval or an engineering-quality score.'), '',
             '| Case | Interface | Expected exit | Actual exit | Outcome | Logs |',
             '| --- | --- | ---: | ---: | --- | --- |']
    for case in report['cases']:
        if case['outcome'] == 'skipped':
            lines.append(f"| {case['name']} | not run | — | — | skipped: {case['reason']} | — |")
            continue
        actual = case['actual']
        lines.append(f"| {case['name']} | {actual['interface']} | {case['expected']['exit_code']} | "
                     f"{actual['exit_code']} | {case['outcome']} | "
                     f"[stdout]({actual['stdout']}) · [stderr]({actual['stderr']}) |")
    lines.extend(['', (f"Source inputs unchanged: **{report.get('source_inputs_unchanged', False)}**. "
                       f"Implementation unchanged during run: **{report.get('implementation_unchanged', False)}**."), '',
                  ('Exact commands, input manifests, fault descriptions, environment, durations and outcomes: '
                   '[evaluation.json](evaluation.json). All workspace paths are relative to this report; '
                   'raw logs and executed argv retain their actual paths.'), '',
                  ('The API cases call `pcb_copilot.layout.footprints.resolve_footprint` directly. '
                   'They do not claim the whole CLI review or release ran. Native preview is optional; '
                   'each stale-input case requires its own real successful preview. Candidate and '
                   'snapshot input bytes must survive every check, including rejected applies. '
                   'Preview creation is not human visual review, approval, or fabrication release.'), '',
                  (f"Harness exit: `{report['exit_code']}` (0: enabled expectations met; "
                   '1: observed behavior differs; 2: execution/preservation error).'), ''])
    if report.get('error'):
        lines.extend(['Error: ' + report['error'], ''])
    (output / 'report.md').write_text('\n'.join(lines), encoding='utf-8')


def evaluate(repository: Path, output: Path, *, native: bool = False) -> dict:
    from pcb_copilot import __version__
    from pcb_copilot.project import load_project
    from pcb_copilot.transaction import input_hashes

    if output.resolve() == repository.resolve() or output.resolve().is_relative_to(repository.resolve()):
        raise ValueError('evaluation output must be outside the repository')
    source = load_project(repository / 'examples/gpio-indicator')
    expected, implementation = input_hashes(source), _implementation(repository)
    started = time.monotonic()
    report = {'schema_version': 1, 'started_utc': datetime.now(UTC).isoformat(),
              'mode': 'native' if native else 'quick', 'source_project': 'examples/gpio-indicator',
              'environment': {'python': sys.version, 'platform': platform.platform(),
                              'pcb_copilot_version': __version__},
              'source_inputs_before': expected, 'implementation_before': implementation,
              'cases': [], 'exit_code': 2}
    specifications = [
        ('control-evidence', 'cli', 0, 'evidence record(s) verified', None),
        ('control-footprints', 'validator-api', 0, '"accepted": true', None),
        ('missing-preview', 'cli', 2, GUARD_MESSAGE, None),
        ('evidence-corruption', 'cli', 1, 'archive.hash_mismatch', 'evidence-corruption'),
        ('footprint-geometry', 'validator-api', 1, 'beyond allowed model URI replacements', 'footprint-geometry'),
        ('model-corruption', 'validator-api', 1, 'hash mismatch', 'model-corruption'),
        ('selected-mpn', 'validator-api', 1, 'does not match the exact selected native MPN', 'selected-mpn'),
    ]
    try:
        for name, interface, code, diagnostic, fault in specifications:
            case, _ = _case(source, output, name, expected, interface=interface,
                            expected_code=code, diagnostic=diagnostic, fault=fault)
            report['cases'].append(case)
        if native:
            report['cases'].extend(_native_cases(source, output, expected))
        else:
            report['cases'].extend({'name': name, 'outcome': 'skipped', 'reason': '--native not requested'}
                                   for name in NATIVE_CASE_NAMES)
        outcomes = {case['outcome'] for case in report['cases']}
        report['exit_code'] = 2 if 'harness_error' in outcomes else int('mismatch' in outcomes)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report.update(error=str(exc), exit_code=2)
        if native:
            present = {case['name'] for case in report['cases']}
            report['cases'].extend({'name': name, 'outcome': 'skipped',
                                    'reason': 'native evaluation could not complete; see run error'}
                                   for name in NATIVE_CASE_NAMES if name not in present)
    finally:
        after, current_implementation = input_hashes(source), _implementation(repository)
        report.update(source_inputs_after=after, source_inputs_unchanged=expected == after,
                      implementation_after=current_implementation,
                      implementation_unchanged=implementation == current_implementation,
                      duration_seconds=round(time.monotonic() - started, 3))
        if expected != after or implementation != current_implementation:
            report.update(error='source inputs or implementation changed during evaluation', exit_code=2)
        write_report(output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new external run directory; default: retained OS temporary directory')
    parser.add_argument('--native', action='store_true',
                        help='also test candidate, saved-schematic and saved-rule drift after independent real previews')
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    try:
        output = new_output_directory(args.output, repository)
        report = evaluate(repository, output, native=args.native)
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        print(f'Evaluation could not start: {exc}. Install dependencies with `uv sync`.', file=sys.stderr)
        return 2
    print(f"Report: {output / 'report.md'}\nResults: {output / 'evaluation.json'}\nHarness exit: {report['exit_code']}")
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
