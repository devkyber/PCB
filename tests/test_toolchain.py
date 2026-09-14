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
