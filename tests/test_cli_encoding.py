import io
import sys

import pytest

from pcb_copilot import cli


def test_entrypoint_emits_utf8_even_when_windows_stdout_defaults_to_cp1252(monkeypatch):
    binary = io.BytesIO()
    stream = io.TextIOWrapper(binary, encoding='cp1252')

    def fake_main():
        print('—')
        return 0

    monkeypatch.setattr(cli, 'main', fake_main)
    monkeypatch.setattr(sys, 'stdout', stream)

    with pytest.raises(SystemExit) as stopped:
        cli.entrypoint()

    stream.flush()
    assert stopped.value.code == 0
    assert binary.getvalue().decode('utf-8').replace('\r\n', '\n') == '—\n'
