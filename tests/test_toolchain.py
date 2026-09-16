import platform
import subprocess

import pytest

from pcb_copilot.toolchain import discover_toolchain


def test_discover_toolchain_uses_shared_kicad_finder(tmp_path, monkeypatch):
    cli = tmp_path / "kicad-cli.exe"
    cli.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)

    paths = discover_toolchain(tmp_path, {})

    assert paths.kicad_cli == cli
    assert paths.freerouting_jars == ()


def test_discover_toolchain_uses_configured_kipython(tmp_path, monkeypatch):
    cli = tmp_path / "kicad-cli.exe"
    kipython = tmp_path / "kipython.exe"
    cli.touch()
    kipython.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)

    paths = discover_toolchain(tmp_path, {"KIPYTHON": str(kipython)})

    assert paths.kipython == kipython.resolve()


def test_configured_kipython_precedes_path_without_probe(tmp_path, monkeypatch):
    cli = tmp_path / "kicad-cli.exe"
    configured = tmp_path / "configured" / "kipython.exe"
    cli.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    monkeypatch.setattr(
        "pcb_copilot.toolchain.shutil.which",
        lambda *_args, **_kwargs: pytest.fail("PATH must not be searched"),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("configured helper must not be probed"),
    )

    paths = discover_toolchain(
        tmp_path,
        {"KIPYTHON": str(configured), "PATH": str(tmp_path / "path")},
    )

    assert paths.kipython == configured.resolve()


def test_path_kipython_precedes_windows_candidate_without_probe(tmp_path, monkeypatch):
    cli = tmp_path / "KiCad 10.0" / "bin" / "kicad-cli.exe"
    path_kipython = tmp_path / "helpers" / "kipython.exe"
    cli.parent.mkdir(parents=True)
    cli.touch()
    path_kipython.parent.mkdir()
    path_kipython.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    calls = []

    def controlled_which(name, *, path=None):
        calls.append((name, path))
        return path_kipython

    monkeypatch.setattr("pcb_copilot.toolchain.shutil.which", controlled_which)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("PATH helper must not be probed"),
    )

    paths = discover_toolchain(tmp_path, {"PATH": str(path_kipython.parent)})

    assert paths.kipython == path_kipython.resolve()
    assert calls == [("kipython", str(path_kipython.parent))]


def test_supplied_environment_controls_kipython_path_lookup(tmp_path, monkeypatch):
    cli = tmp_path / "kicad-cli"
    path_kipython = tmp_path / "isolated helpers" / "kipython"
    supplied_path = str(path_kipython.parent)
    cli.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    calls = []

    def controlled_which(name, *, path=None):
        calls.append((name, path))
        return path_kipython

    monkeypatch.setattr("pcb_copilot.toolchain.shutil.which", controlled_which)

    paths = discover_toolchain(tmp_path, {"PATH": supplied_path})

    assert paths.kipython == path_kipython.resolve()
    assert calls == [("kipython", supplied_path)]


def test_supplied_environment_without_path_does_not_search_process_path(
    tmp_path, monkeypatch
):
    cli = tmp_path / "kicad-cli"
    cli.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        "pcb_copilot.toolchain.shutil.which",
        lambda *_args, **_kwargs: pytest.fail("omitted PATH means no PATH search"),
    )

    assert discover_toolchain(tmp_path, {}).kipython is None


def test_windows_sibling_python_is_used_when_pcbnew_import_succeeds(
    tmp_path, monkeypatch
):
    cli = tmp_path / "Program Files" / "KiCad" / "10.0" / "bin" / "kicad-cli.exe"
    python = cli.with_name("python.exe")
    cli.parent.mkdir(parents=True)
    cli.touch()
    python.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    calls = []

    def successful_probe(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args, 0, stdout=b"ignored", stderr=b"ignored"
        )

    monkeypatch.setattr(subprocess, "run", successful_probe)

    paths = discover_toolchain(tmp_path, {})

    assert paths.kipython == python.resolve()
    assert calls == [
        (
            [str(python), "-I", "-c", "import pcbnew"],
            {"capture_output": True, "check": False, "timeout": 5},
        )
    ]


def test_windows_missing_sibling_python_is_not_probed(tmp_path, monkeypatch):
    cli = tmp_path / "KiCad" / "10.0" / "bin" / "kicad-cli.exe"
    cli.parent.mkdir(parents=True)
    cli.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("missing candidate must not be probed"),
    )

    assert discover_toolchain(tmp_path, {}).kipython is None


@pytest.mark.parametrize("returncode", [1, 7])
def test_windows_sibling_python_is_rejected_when_pcbnew_import_fails(
    tmp_path, monkeypatch, returncode
):
    cli = tmp_path / "KiCad" / "10.0" / "bin" / "kicad-cli.exe"
    python = cli.with_name("python.exe")
    cli.parent.mkdir(parents=True)
    cli.touch()
    python.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **_kwargs: subprocess.CompletedProcess(args, returncode),
    )

    assert discover_toolchain(tmp_path, {}).kipython is None


@pytest.mark.parametrize(
    "failure",
    [OSError("cannot launch"), subprocess.TimeoutExpired(["python.exe"], 5)],
)
def test_windows_sibling_python_probe_failure_is_nonfatal(
    tmp_path, monkeypatch, failure
):
    cli = tmp_path / "KiCad" / "10.0" / "bin" / "kicad-cli.exe"
    python = cli.with_name("python.exe")
    cli.parent.mkdir(parents=True)
    cli.touch()
    python.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    monkeypatch.setattr(platform, "system", lambda: "Windows")

    def failed_probe(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(subprocess, "run", failed_probe)

    paths = discover_toolchain(tmp_path, {})

    assert paths.kicad_cli == cli.resolve()
    assert paths.kipython is None


def test_non_windows_does_not_probe_cli_sibling_python(tmp_path, monkeypatch):
    cli = tmp_path / "kicad-cli"
    cli.touch()
    cli.with_name("python.exe").touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("non-Windows must not probe"),
    )

    assert discover_toolchain(tmp_path, {}).kipython is None
