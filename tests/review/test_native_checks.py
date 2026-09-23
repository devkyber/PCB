import json
from types import SimpleNamespace

import pytest

from pcb_copilot.review import checks


@pytest.mark.parametrize('exit_code,report', [
    (1, {'violations': [], 'unconnected_items': []}),
    (0, {}),
    (0, {'violations': [], 'unconnected_items': 'invalid'}),
])
def test_drc_refuses_failed_or_malformed_output(tmp_path, monkeypatch, exit_code, report):
    board = tmp_path / 'board.kicad_pcb'
    board.write_text('(kicad_pcb)')
    output = tmp_path / 'drc.json'
    output.write_text(json.dumps({'violations': [], 'unconnected_items': []}))

    def run(command, **kwargs):
        assert not output.exists(), 'a stale report must be removed before the tool runs'
        output.write_text(json.dumps(report))
        return SimpleNamespace(returncode=exit_code, stdout='', stderr='tool failure')

    monkeypatch.setattr(checks, '_run', run)
    monkeypatch.setattr(checks, '_toolchain', lambda: SimpleNamespace(kicad_cli='kicad-cli'))
    with pytest.raises((RuntimeError, ValueError)):
        checks.drc_once(board, output)


def test_drc_missing_report_does_not_reuse_stale_result(tmp_path, monkeypatch):
    output = tmp_path / 'drc.json'
    output.write_text(json.dumps({'violations': [], 'unconnected_items': []}))
    monkeypatch.setattr(checks, '_run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='', stderr=''))
    monkeypatch.setattr(checks, '_toolchain', lambda: SimpleNamespace(kicad_cli='kicad-cli'))
    with pytest.raises(RuntimeError, match='report'):
        checks.drc_once(tmp_path / 'board.kicad_pcb', output)


def test_all_checks_are_available_without_discovering_native_tools(monkeypatch):
    monkeypatch.setattr(checks, '_toolchain', lambda: pytest.fail('eager tool discovery'))
    assert {check.check_id for check in checks.current_checks()} == {
        'research', 'datasheets', 'erc', 'schematic_ownership', 'schematic_quality',
        'netlist_parity', 'placement', 'design_rules', 'drc', 'signoff',
    }
