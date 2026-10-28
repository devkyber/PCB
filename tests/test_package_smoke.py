import json

import pytest

from pcb_copilot import __version__, jlcpcb
from pcb_copilot.cli import main


def test_package_and_cli_are_importable(capsys):
    assert __version__ == "0.1.0"
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "pcb-copilot 0.1.0"


def test_checkout_baseline_uses_exact_canonical_template_bytes(repo_root):
    template = repo_root / 'templates' / jlcpcb.BASELINE_STEM
    actual = jlcpcb.baseline_bytes()
    expected = tuple((template / (jlcpcb.BASELINE_STEM + suffix)).read_bytes()
                     for suffix in ('.kicad_pro', '.kicad_dru'))
    assert actual == expected
    assert json.loads(actual[0])['board']['design_settings']['rules']


def test_installed_baseline_reads_resources_without_checkout(tmp_path, monkeypatch):
    package = tmp_path / 'installed-package'
    resources = package / 'resources' / jlcpcb.BASELINE_STEM
    resources.mkdir(parents=True)
    settings = b'{"board": {"design_settings": {"rules": {"min_track_width": 0.1}}}}'
    rules = b'(version 1)\n'
    (resources / (jlcpcb.BASELINE_STEM + '.kicad_pro')).write_bytes(settings)
    (resources / (jlcpcb.BASELINE_STEM + '.kicad_dru')).write_bytes(rules)
    monkeypatch.setattr(jlcpcb, 'files', lambda _name: package)
    assert jlcpcb.baseline_bytes() == (settings, rules)
    # A damaged installed baseline must fail rather than silently switching to
    # a potentially different checkout profile.
    (resources / (jlcpcb.BASELINE_STEM + '.kicad_dru')).unlink()
    with pytest.raises(FileNotFoundError):
        jlcpcb.baseline_bytes()
