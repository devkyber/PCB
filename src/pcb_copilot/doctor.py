"""Read-only diagnostics for the toolchain used by the current CLI."""

from __future__ import annotations

import platform
import re
import subprocess
import sys
from pathlib import Path

from kicad_claude.adapters.freerouting import (
    available_jars,
    find_java,
    java_major,
    required_java_major,
)

from pcb_copilot.toolchain import ToolchainDiscoveryError, discover_toolchain

_SCOPE = (
    'Tool discovery, version and isolated pcbnew import probes only. '
    'No projects are opened or changed; CAD checks and routing are not run.'
)
_KICAD_GUIDANCE = (
    'Install KiCad 10 with its command-line tools. Put kicad-cli on PATH if '
    'the existing resolver cannot find your installation.'
)
_PYTHON_GUIDANCE = (
    'Set KIPYTHON to a Python executable that imports KiCad 10 pcbnew with -I, '
    'or provide that interpreter as kipython on PATH. On Windows the resolver '
    'also checks python.exe beside kicad-cli.'
)


def _check(check_id: str, required: bool, status: str, detail: str, *,
           path: Path | str | None = None, version: str | None = None,
           guidance: str | None = None) -> dict:
    return {
        'id': check_id, 'required': required, 'status': status,
        'path': str(path) if path else None, 'version': version,
        'detail': detail, 'guidance': guidance,
    }


def _probe(command: list[str]) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding='utf-8',
            errors='replace', check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f'Probe could not complete: {exc}'
    output = (result.stdout or '').strip()
    if result.returncode:
        detail = (result.stderr or output or 'no diagnostic output').strip()
        return None, f'Probe exited {result.returncode}: {detail[:1000]}'
    if not output:
        return None, 'Probe returned no version.'
    return output, None


def _major(version: str) -> int | None:
    match = re.search(r'\b(\d+)\.\d+(?:\.\d+)?\b', version)
    return int(match.group(1)) if match else None


def _native_checks(repo_root: Path) -> list[dict]:
    try:
        tools = discover_toolchain(repo_root)
    except (ToolchainDiscoveryError, OSError, ValueError) as exc:
        return [
            _check('kicad_cli', True, 'missing', str(exc), guidance=_KICAD_GUIDANCE),
            _check('pcbnew', True, 'not_checked',
                   'The shared toolchain resolver requires kicad-cli first.',
                   guidance=_PYTHON_GUIDANCE),
        ]

    cli_version, error = _probe([str(tools.kicad_cli), '--version'])
    if error:
        cli_check = _check('kicad_cli', True, 'failed', error,
                           path=tools.kicad_cli, guidance=_KICAD_GUIDANCE)
    elif _major(cli_version) != 10:
        cli_check = _check('kicad_cli', True, 'unsupported',
                           'The supported baseline is KiCad 10.x.',
                           path=tools.kicad_cli, version=cli_version,
                           guidance=_KICAD_GUIDANCE)
    else:
        cli_check = _check('kicad_cli', True, 'passed',
                           'kicad-cli --version succeeded; no CAD commands were run.',
                           path=tools.kicad_cli, version=cli_version)

    if tools.kipython is None:
        python_check = _check('pcbnew', True, 'missing',
                              'No pcbnew interpreter was selected by the shared resolver.',
                              guidance=_PYTHON_GUIDANCE)
    else:
        version, error = _probe([
            str(tools.kipython), '-I', '-c',
            'import pcbnew; print(pcbnew.GetBuildVersion())',
        ])
        if error:
            python_check = _check('pcbnew', True, 'failed', error,
                                  path=tools.kipython, guidance=_PYTHON_GUIDANCE)
        elif _major(version) != 10:
            python_check = _check('pcbnew', True, 'unsupported',
                                  'The pipeline needs KiCad 10 pcbnew bindings.',
                                  path=tools.kipython, version=version,
                                  guidance=_PYTHON_GUIDANCE)
        else:
            python_check = _check('pcbnew', True, 'passed',
                                  'Isolated pcbnew import and GetBuildVersion succeeded.',
                                  path=tools.kipython, version=version)
    return [cli_check, python_check]


def _optional_checks() -> list[dict]:
    """Use the routing adapter's discovery and version-dependent Java policy."""
    guidance = ('For optional autorouting, set FREEROUTING_JAR to an existing '
                'Freerouting JAR. Routing is optional for native KiCad candidates.')
    java_guidance = ('For optional autorouting, install a compatible Java runtime '
                     'and use JAVA_BIN or PATH; the routing adapter also supports '
                     'JAVA_25_HOME for JARs requiring Java 25.')
    try:
        jars = available_jars()
        # Follow the adapter's newest-compatible-JAR preference. Verify the
        # reported Java major as JAVA_25_HOME itself is not probed by find_java.
        selected = jars[0] if jars else None
        java = None
        major = None
        for candidate in jars:
            found = find_java(required_java_major(candidate[0]))
            found_major = java_major(found) if found else None
            if found_major is not None and found_major >= required_java_major(candidate[0]):
                selected, java, major = candidate, found, found_major
                break
        if java is None:
            java = find_java(0)
            major = java_major(java) if java else None
    except (OSError, ValueError) as exc:
        return [
            _check('freerouting_jar', False, 'failed', str(exc), guidance=guidance),
            _check('java', False, 'not_checked', 'Optional routing discovery failed.',
                   guidance=java_guidance),
        ]

    need = required_java_major(selected[0]) if selected else 21
    if selected:
        version, jar = selected
        jar_check = _check(
            'freerouting_jar', False, 'passed',
            f'JAR file found; adapter requires Java {need}+. '
            'Version is inferred by the adapter; the JAR was not executed.',
            path=jar, version='.'.join(map(str, version)) if any(version) else None,
        )
    else:
        jar_check = _check('freerouting_jar', False, 'missing',
                           'No Freerouting JAR found by the routing adapter.', guidance=guidance)
    if java is None or major is None:
        java_check = _check('java', False, 'missing',
                            f'No Java runtime with a readable version found (routing needs {need}+).',
                            path=java, guidance=java_guidance)
    elif major < need:
        java_check = _check('java', False, 'unsupported',
                            f'Optional routing needs Java {need}+ for the selected JAR.',
                            path=java, version=str(major), guidance=java_guidance)
    else:
        java_check = _check('java', False, 'passed',
                            f'Java reports major {major}; optional routing requires {need}+.',
                            path=java, version=str(major))
    return [jar_check, java_check]


def collect_doctor() -> dict:
    """Probe dependencies without loading project inputs or modifying CAD."""
    python_ok = sys.version_info[:2] >= (3, 11)
    checks = [_check(
        'python', True, 'passed' if python_ok else 'unsupported',
        'PCB Copilot requires Python 3.11 or newer.',
        path=sys.executable, version=platform.python_version(),
        guidance=None if python_ok else 'Run uv sync with Python 3.11 or newer.',
    )]
    checks.extend(_native_checks(Path(__file__).resolve().parents[2]))
    checks.extend(_optional_checks())
    return {
        'schema_version': 1,
        'ready': all(item['status'] == 'passed' for item in checks if item['required']),
        'scope': _SCOPE,
        'checks': checks,
    }


def render_doctor(report: dict) -> str:
    lines = ['PCB Copilot toolchain diagnostics', report['scope']]
    for check in report['checks']:
        requirement = 'required' if check['required'] else 'optional'
        version = f" ({check['version']})" if check['version'] else ''
        lines.append(f"[{check['status'].upper()}] {check['id']} [{requirement}]{version}")
        if check['path']:
            lines.append(f"  Path: {check['path']}")
        lines.append(f"  {check['detail']}")
        if check['guidance']:
            lines.append(f"  Next: {check['guidance']}")
    lines.append('Required probes passed.' if report['ready']
                 else 'Required probes failed or are missing; follow the guidance above.')
    return '\n'.join(lines)
