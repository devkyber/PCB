"""Compose a native-CAD portfolio from current, verified example captures.

uv run --group media python tools/render_examples_gallery.py
This uses recorded native renders, never manufactured-board photographs. The
complete bundle is staged and source-checked before transactional publication.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import imageio_ffmpeg
from check_examples import check_example
from media_publication import publish_bundle
from PIL import Image, ImageDraw
from render_readme_media import (
    AMBER,
    LIME,
    LINE,
    MEDIA,
    MUTED,
    ROOT,
    WHITE,
    base,
    brand,
    digest,
    fit,
    font,
    text,
)

BOARDS = (
    ('usb-c-power', 'USB-C power entry', '5 V sink / independent CC resistors', 'F1 body is not modeled.'),
    ('i2c-sensor', 'I2C temperature sensor', 'MCP9808 / address selection / ALERT', 'Physical fit and bench behavior are open.'),
    ('rs485-interface', 'RS-485 interface', 'THVD1450 / control defaults / termination', 'Short bench link; no isolation or surge qualification.'),
)


def _capture(name: str) -> dict:
    check_example(ROOT, name)
    root = ROOT / 'examples' / name
    manifest = json.loads((root / 'output/SOURCE.json').read_bytes())
    erc = json.loads((root / 'output/erc.json').read_bytes())
    drc = json.loads((root / 'output/drc.json').read_bytes())
    erc_count = sum(len(sheet.get('violations', [])) for sheet in erc['sheets'])
    if not isinstance(drc.get('violations'), list) or not isinstance(drc.get('unconnected_items'), list):
        raise TypeError('gallery requires a completed native DRC report')
    board = Image.open(root / 'output/board-3d.png').convert('RGBA')
    bounds = board.getchannel('A').getbbox()
    if bounds:
        board = board.crop(bounds)
    return {'project': 'examples/' + name, 'source_inputs': manifest['source_inputs'],
            'source_artifacts': {str(p.relative_to(ROOT).as_posix()): digest(p) for p in (
                root / 'output/SOURCE.json', root / 'output/board-3d.png', root / 'output/schematic.png',
                root / 'output/erc.json', root / 'output/drc.json')},
            'board': board, 'schematic': Image.open(root / 'output/schematic.png').convert('RGB'),
            'erc': erc_count, 'drc': len(drc['violations']), 'unconnected': len(drc['unconnected_items'])}


def poster(captures: list[dict]) -> Image.Image:
    canvas = base(1600, 1080)
    draw = ImageDraw.Draw(canvas)
    brand(canvas)
    text(canvas, (64, 112), 'Inspect the whole board.', 65, bold=True)
    text(canvas, (66, 204), 'Three new native KiCad examples, with evidence and open decisions.', 28, MUTED)
    for index, ((_, title, subtitle, limit), captured) in enumerate(zip(BOARDS, captures, strict=True)):
        x = 64 + index * 496
        draw.rounded_rectangle((x, 286, x + 480, 920), radius=9, fill='#182832', outline=LINE)
        text(canvas, (x + 22, 309), title, 28, bold=True)
        text(canvas, (x + 22, 357), subtitle.replace(' / ', '\n', 1), 19, MUTED)
        fit(canvas, captured['board'], (x + 12, 428, 456, 330))
        color = AMBER if captured['drc'] or captured['erc'] else LIME
        text(canvas, (x + 22, 783), f"ERC {captured['erc']} / DRC {captured['drc']} / unrouted {captured['unconnected']}",
             17, color, mono=True)
        words, lines, line = limit.split(), [], ''
        for word in words:
            candidate = (line + ' ' + word).strip()
            if line and draw.textlength(candidate, font=font(17)) > 410:
                lines.append(line)
                line = word
            else:
                line = candidate
        text(canvas, (x + 22, 827), '\n'.join([*lines, line]), 17, MUTED)
        text(canvas, (x + 22, 877), 'Unbuilt DRAFT', 20, WHITE, bold=True)
    draw.line((64, 963, 1536, 963), fill=LINE, width=2)
    text(canvas, (66, 991), 'Recorded native CAD renders. Review and fabrication gates remain open.', 24, MUTED)
    return canvas


def scene(index: int, captured: dict) -> Image.Image:
    canvas = base(1280, 720)
    draw = ImageDraw.Draw(canvas)
    _, title, subtitle, limit = BOARDS[index]
    brand(canvas, 44, 30, 20)
    text(canvas, (44, 94), title, 49, bold=True)
    text(canvas, (46, 165), subtitle, 22, MUTED)
    fit(canvas, captured['board'], (28, 220, 596, 364))
    draw.rounded_rectangle((656, 222, 1236, 595), radius=5, fill='#faf9f2')
    fit(canvas, captured['schematic'], (664, 230, 564, 357))
    text(canvas, (45, 622), f"ERC {captured['erc']} / DRC {captured['drc']} / unrouted {captured['unconnected']}", 19,
         AMBER if captured['drc'] or captured['erc'] else LIME, mono=True)
    text(canvas, (45, 661), 'UNBUILT / NATIVE RENDER / ' + limit, 16, MUTED)
    return canvas


def main() -> None:
    captured = [_capture(board[0]) for board in BOARDS]
    inputs = {item['project']: item['source_inputs'] for item in captured}
    artifacts = {name: value for item in captured for name, value in item['source_artifacts'].items()}

    def source_check():
        for name, *_ in BOARDS:
            check_example(ROOT, name)
        if any(digest(ROOT / name) != expected for name, expected in artifacts.items()):
            raise RuntimeError('example capture changed during gallery rendering')

    with tempfile.TemporaryDirectory(prefix='pcb-examples-gallery-') as directory:
        stage = Path(directory)
        poster(captured).save(stage / 'examples-gallery.png', optimize=True)
        frames = [scene(index, capture) for index, capture in enumerate(captured)]
        gifs = [frame.resize((960, 540), Image.Resampling.LANCZOS).quantize(colors=192) for frame in frames]
        gifs[0].save(stage / 'examples-gallery.gif', save_all=True, append_images=gifs[1:],
                     duration=4000, loop=0, optimize=True, disposal=1)
        writer = imageio_ffmpeg.write_frames(str(stage / 'examples-gallery.mp4'), (1280, 720), fps=24,
                                            codec='libx264', quality=8, ffmpeg_log_level='error',
                                            output_params=['-movflags', '+faststart'])
        writer.send(None)
        try:
            for frame in frames:
                for _ in range(96):
                    writer.send(frame.tobytes())
        finally:
            writer.close()
        outputs = ['examples-gallery.png', 'examples-gallery.gif', 'examples-gallery.mp4']
        manifest = {'schema_version': 1, 'generated_utc': datetime.now(UTC).isoformat(),
                    'source_projects': inputs, 'source_artifacts': artifacts, 'source_cad_unchanged': True,
                    'native_findings': {item['project']: {'erc': item['erc'], 'drc': item['drc'],
                                                        'unconnected': item['unconnected']} for item in captured},
                    'generator_sha256': digest(Path(__file__)),
                    'font_hashes': {p.name: digest(p) for p in sorted((MEDIA / 'fonts').glob('*.ttf'))},
                    'outputs': {name: {'sha256': digest(stage / name), 'bytes': (stage / name).stat().st_size}
                                for name in outputs},
                    'scope': 'Recorded native 3D/schematic captures of unbuilt prototypes; not photographs, '
                             'a screen recording or engineering approval. Native finding counts are retained above; '
                             'engineering and supplier assembly decisions remain in each board review.'}
        (stage / 'examples-manifest.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
        publish_bundle(stage, MEDIA, 'examples-manifest.json', source_check=source_check)
    print(json.dumps({'outputs': manifest['outputs'], 'source_projects': list(inputs)}, indent=2))


if __name__ == '__main__':
    main()
