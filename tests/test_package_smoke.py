from pcb_copilot import __version__
from pcb_copilot.cli import main


def test_package_and_cli_are_importable(capsys):
    assert __version__ == "0.1.0"
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "pcb-copilot 0.1.0"
