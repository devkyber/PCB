import json
import subprocess
from pathlib import Path

import pytest

from pcb_copilot import doctor
from pcb_copilot.cli import main
from pcb_copilot.toolchain import ToolchainDiscoveryError, ToolchainPaths


@pytest.fixture
def tools(monkeypatch, tmp_path):
    paths = ToolchainPaths(tmp_path / 'kicad-cli', tmp_path / 'python', ())
    monkeypatch.setattr(doctor, 'discover_toolchain', lambda _root: paths)
    monkeypatch.setattr(doctor, 'available_jars', list)
    monkeypatch.setattr(doctor, 'find_java', lambda _minimum: None)

    def probe(command, **_kwargs):
        return subprocess.CompletedProcess(command, 0, stdout='10.0.1\n', stderr='')

    monkeypatch.setattr(doctor.subprocess, 'run', probe)
    return paths


def checks(report):
    return {item['id']: item for item in report['checks']}


def test_required_tools_pass_without_optional_router(tools):
    report = doctor.collect_doctor()
    found = checks(report)
    assert report['schema_version'] == 1
    assert report['ready']
    assert found['kicad_cli']['path'] == str(tools.kicad_cli)
    assert found['pcbnew']['path'] == str(tools.kipython)
    assert found['freerouting_jar']['status'] == 'missing'
    assert found['java']['status'] == 'missing'
    assert not found['java']['required']


def test_probes_use_shared_selected_tools_without_loading_projects(tools, monkeypatch, tmp_path):
    calls = []
    monkeypatch.chdir(tmp_path)

    def probe(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout='10.0.1', stderr='')

    monkeypatch.setattr(doctor.subprocess, 'run', probe)
    monkeypatch.setattr('pcb_copilot.cli.load_project',
                        lambda *_args: pytest.fail('doctor must not load a project'))
    assert main(['doctor', '--format', 'json']) == 0
    assert [command for command, _ in calls] == [
        [str(tools.kicad_cli), '--version'],
        [str(tools.kipython), '-I', '-c',
         'import pcbnew; print(pcbnew.GetBuildVersion())'],
    ]
    assert all(kwargs['timeout'] == 10 and not kwargs['check'] for _, kwargs in calls)
    assert list(tmp_path.iterdir()) == []


def test_missing_cli_reports_runtime_not_checked_and_still_checks_optional(tools, monkeypatch):
    def missing(_root):
        raise ToolchainDiscoveryError('kicad-cli was not found')

    monkeypatch.setattr(doctor, 'discover_toolchain', missing)
    report = doctor.collect_doctor()
    found = checks(report)
    assert not report['ready']
    assert found['kicad_cli']['status'] == 'missing'
    assert 'Install KiCad 10' in found['kicad_cli']['guidance']
    assert found['pcbnew']['status'] == 'not_checked'
    assert found['freerouting_jar']['status'] == 'missing'


def test_missing_pcbnew_runtime_blocks_required_readiness(tools, monkeypatch):
    monkeypatch.setattr(doctor, 'discover_toolchain',
                        lambda _root: ToolchainPaths(tools.kicad_cli, None, ()))
    report = doctor.collect_doctor()
    assert not report['ready']
    assert checks(report)['pcbnew']['status'] == 'missing'
    assert 'KIPYTHON' in checks(report)['pcbnew']['guidance']


@pytest.mark.parametrize('problem', ['nonzero', 'timeout', 'launch', 'empty'])
def test_bad_pcbnew_probe_is_actionable_and_does_not_hide_other_checks(tools, monkeypatch, problem):
    def probe(command, **_kwargs):
        if command[1:] == ['--version']:
            return subprocess.CompletedProcess(command, 0, stdout='10.0.1', stderr='')
        if problem == 'timeout':
            raise subprocess.TimeoutExpired(command, 10)
        if problem == 'launch':
            raise OSError('permission denied')
        return subprocess.CompletedProcess(command, 1 if problem == 'nonzero' else 0,
                                           stdout='', stderr='cannot import pcbnew')

    monkeypatch.setattr(doctor.subprocess, 'run', probe)
    report = doctor.collect_doctor()
    found = checks(report)
    assert not report['ready']
    assert found['kicad_cli']['status'] == 'passed'
    assert found['pcbnew']['status'] == 'failed'
    assert found['pcbnew']['guidance']
    assert 'java' in found


@pytest.mark.parametrize('version', ['9.0.7', '11.0.0', 'unrecognized'])
def test_unknown_or_unsupported_native_version_does_not_claim_readiness(tools, monkeypatch, version):
    monkeypatch.setattr(doctor.subprocess, 'run', lambda command, **_kwargs:
                        subprocess.CompletedProcess(command, 0, stdout=version, stderr=''))
    report = doctor.collect_doctor()
    assert not report['ready']
    assert checks(report)['kicad_cli']['status'] == 'unsupported'
    assert checks(report)['pcbnew']['status'] == 'unsupported'


def test_older_python_blocks_required_readiness(tools, monkeypatch):
    monkeypatch.setattr(doctor.sys, 'version_info', (3, 10, 0))
    monkeypatch.setattr(doctor.platform, 'python_version', lambda: '3.10.0')
    report = doctor.collect_doctor()
    assert not report['ready']
    assert checks(report)['python']['status'] == 'unsupported'


def test_router_uses_newest_jar_compatible_with_discovered_java(tools, monkeypatch, tmp_path):
    newest, older = tmp_path / 'freerouting-2.3.0.jar', tmp_path / 'freerouting-2.1.0.jar'
    java = tmp_path / 'java'
    monkeypatch.setattr(doctor, 'available_jars', lambda: [((2, 3, 0), newest), ((2, 1, 0), older)])
    monkeypatch.setattr(doctor, 'find_java', lambda minimum: java if minimum <= 21 else None)
    monkeypatch.setattr(doctor, 'java_major', lambda _java: 21)
    report = doctor.collect_doctor()
    found = checks(report)
    assert report['ready']
    assert found['freerouting_jar']['path'] == str(older)
    assert found['freerouting_jar']['version'] == '2.1.0'
    assert found['java']['status'] == 'passed'
    assert 'not executed' in found['freerouting_jar']['detail']


def test_incompatible_java_does_not_fail_native_tools(tools, monkeypatch, tmp_path):
    monkeypatch.setattr(doctor, 'available_jars',
                        lambda: [((2, 3, 0), tmp_path / 'freerouting.jar')])
    monkeypatch.setattr(doctor, 'find_java', lambda _minimum: Path('java'))
    monkeypatch.setattr(doctor, 'java_major', lambda _java: 21)
    report = doctor.collect_doctor()
    assert report['ready']
    assert checks(report)['java']['status'] == 'unsupported'
    assert 'Java 25+' in checks(report)['java']['detail']


def test_optional_discovery_error_does_not_fail_native_tools(tools, monkeypatch):
    def unavailable():
        raise OSError('cannot read JAR directory')

    monkeypatch.setattr(doctor, 'available_jars', unavailable)
    report = doctor.collect_doctor()
    assert report['ready']
    assert checks(report)['freerouting_jar']['status'] == 'failed'
    assert checks(report)['java']['status'] == 'not_checked'


@pytest.mark.parametrize('ready', [True, False])
def test_cli_json_exit_status_and_machine_readable_contract(monkeypatch, capsys, ready):
    report = {'schema_version': 1, 'ready': ready, 'scope': 'probe only', 'checks': []}
    monkeypatch.setattr(doctor, 'collect_doctor', lambda: report)
    assert main(['doctor', '--format', 'json']) == int(not ready)
    assert json.loads(capsys.readouterr().out) == report


def test_cli_text_distinguishes_optional_tools_and_actions(tools, capsys):
    assert main(['doctor']) == 0
    output = capsys.readouterr().out
    assert 'kicad_cli [required]' in output
    assert 'java [optional]' in output
    assert 'Next: For optional autorouting' in output
    assert 'No projects are opened or changed' in output
    assert 'Required probes passed.' in output
