"""A failed encoder must never partially refresh the public README assets.

Native exports are stubbed here; this tests publication orchestration, not CAD.
"""

import importlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

Image = pytest.importorskip('PIL.Image')
pytest.importorskip('imageio_ffmpeg')


@pytest.fixture
def renderers(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    rover = importlib.import_module('render_readme_media')
    gpio = importlib.import_module('render_example_media')
    media = tmp_path / 'published'
    media.mkdir()
    project = SimpleNamespace(root=tmp_path / 'source', pcb_path=tmp_path / 'source/board.kicad_pcb')
    hashes = {'board.kicad_pcb': 'a' * 64}
    board = Image.new('RGBA', (32, 32), (30, 80, 40, 255))
    sheets = [('sheet.svg', board.convert('RGB'))]
    for module in (rover, gpio):
        monkeypatch.setattr(module, 'MEDIA', media)
        monkeypatch.setattr(module, 'load_project', lambda _: project)
        monkeypatch.setattr(module, 'capture', lambda *a: (board, board, sheets, hashes))
        monkeypatch.setattr(module, 'repository_binding', lambda *a: {})
        monkeypatch.setattr(module, 'discover_toolchain', lambda _: SimpleNamespace(kicad_cli=Path('stub-cli')))
        monkeypatch.setattr(module, 'assert_current', lambda *a: None)
    monkeypatch.setattr(rover, 'input_hashes', lambda _: hashes)
    monkeypatch.setattr(rover, 'hero', lambda *a, **k: board)
    monkeypatch.setattr(rover, 'gallery', lambda *a: board)
    monkeypatch.setattr(rover, 'sheet_contact', lambda *a: board)
    monkeypatch.setattr(rover, 'scene', lambda *a: board.convert('RGB'))
    monkeypatch.setattr(rover, 'demo_data', lambda _: {'source_input_hashes': hashes})
    monkeypatch.setattr(gpio, 'showcase', lambda *a: board)
    monkeypatch.setattr(gpio, 'turntable_frame', lambda *a: board.convert('RGB'))

    def native_frame(cli, work, arguments, commands):
        board.save(Path(arguments[arguments.index('-o') + 1]))

    monkeypatch.setattr(gpio, 'run_native', native_frame)
    monkeypatch.setattr(rover.subprocess, 'check_output', lambda *a, **k: 'stub-native-version')
    return rover, gpio, media, hashes


@pytest.mark.parametrize('which', ['rover', 'gpio'])
def test_encoding_failure_preserves_every_published_byte(renderers, tmp_path, monkeypatch, which):
    rover, gpio, media, _ = renderers
    names = ['hero.png', 'social-preview.png', 'native-cad.png', 'rover-3d.png',
             'workflow.gif', 'workflow.mp4', 'demo-results.json', 'manifest.json',
             'gpio-demo.png', 'gpio-3d.png', 'gpio-turntable.gif', 'gpio-turntable.mp4',
             'example-manifest.json', 'unrelated.txt']
    originals = {name: ('original ' + name).encode() for name in names}
    for name, payload in originals.items():
        (media / name).write_bytes(payload)

    def broken_encoder(*args, **kwargs):
        raise RuntimeError('injected encoder failure')

    monkeypatch.setattr(rover.imageio_ffmpeg, 'write_frames', broken_encoder)
    work = tmp_path / 'new-work'
    with pytest.raises(RuntimeError, match='injected encoder failure'):
        if which == 'rover':
            monkeypatch.setattr(sys, 'argv', ['render', '--demo', 'unused.json', '--work-dir', str(work)])
            rover.main()
        else:
            work.mkdir()
            gpio.render(work, 12)
    assert {p.name: p.read_bytes() for p in media.iterdir()} == originals
    assert list((work / 'assets').glob('*.png')), 'partial generation happened only in staging'


def test_rover_source_changed_after_transcript_validation_stops_before_assets(renderers, tmp_path, monkeypatch):
    rover, _, media, _ = renderers
    board = Image.new('RGBA', (8, 8))
    monkeypatch.setattr(rover, 'capture', lambda *a: (board, board, [], {'board.kicad_pcb': 'b' * 64}))
    monkeypatch.setattr(sys, 'argv', ['render', '--demo', 'unused.json', '--work-dir', str(tmp_path / 'work')])
    with pytest.raises(RuntimeError, match='project changed'):
        rover.main()
    assert not list(media.iterdir())


@pytest.mark.parametrize('which', ['rover', 'gpio'])
def test_source_check_runs_after_encoding_and_rolls_back(renderers, tmp_path, monkeypatch, which):
    rover, gpio, media, _ = renderers
    original = b'previous published image'
    target = 'hero.png' if which == 'rover' else 'gpio-demo.png'
    (media / target).write_bytes(original)
    calls = []

    def fake_writer(path, *args, **kwargs):
        Path(path).write_bytes(b'encoded video')
        calls.append('encoded')
        while True:
            yield

    def check(*args):
        calls.append('source-check')
        # GPIO has an earlier check immediately after native frame capture.
        if 'encoded' in calls and (media / target).read_bytes() != original:
            raise RuntimeError('source changed during publication')

    module = rover if which == 'rover' else gpio
    monkeypatch.setattr(module, 'assert_current', check)
    monkeypatch.setattr(rover.imageio_ffmpeg, 'write_frames', fake_writer)
    work = tmp_path / 'work'
    with pytest.raises(RuntimeError, match='source changed during publication'):
        if which == 'rover':
            monkeypatch.setattr(sys, 'argv', ['render', '--demo', 'unused.json', '--work-dir', str(work)])
            rover.main()
        else:
            work.mkdir()
            gpio.render(work, 12)
    assert calls[-1] == 'source-check' and 'encoded' in calls
    assert {p.name: p.read_bytes() for p in media.iterdir()} == {target: original}


@pytest.mark.parametrize('fault', ['preservation', 'log-content', 'interface', 'exit'])
def test_evaluation_graphic_rejects_unsupported_claims(tmp_path, monkeypatch, fault):
    tools_path = Path(__file__).resolve().parents[1] / 'tools'
    monkeypatch.syspath_prepend(str(tools_path))
    renderer = importlib.import_module('render_evaluation_media')
    source = tools_path.parent / 'docs/evaluation/2026-10-29'
    packet = tmp_path / 'packet'
    packet.mkdir()
    shutil.copyfile(source / 'evaluation.json', packet / 'evaluation.json')
    shutil.copytree(source / 'logs', packet / 'logs')
    path = packet / 'evaluation.json'
    record = json.loads(path.read_bytes())
    assert len(renderer.read_record(path)[1]) == 19
    if fault == 'preservation':
        record['source_inputs_unchanged'] = False
    elif fault == 'log-content':
        (packet / record['cases'][0]['actual']['stdout']).write_bytes(b'no recorded diagnostic')
    elif fault == 'interface':
        record['cases'][0]['actual']['interface'] = 'validator-api'
    else:
        case = next(c for c in record['cases'] if c['name'] == 'evidence-corruption')
        case['actual']['exit_code'] = case['expected']['exit_code'] = 0
    path.write_bytes(json.dumps(record).encode())
    with pytest.raises(ValueError):
        renderer.read_record(path)
