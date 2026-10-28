"""Render a source-bound 1600 x 1000 evaluation graphic from saved actual logs.

Measured Proof: large type carries the observation; restrained cells keep the
three interfaces distinct. Lime marks controls, amber marks expected rejection.
The quiet grid and precise spacing follow the repository's native CAD media.

Run: uv run --group media python tools/render_evaluation_media.py
    --record docs/evaluation/2026-10-29/evaluation.json --output NEW_EXTERNAL.png
This renderer creates one new external PNG; it never updates CAD or the record.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
FONT_ROOT = ROOT / 'docs/media/fonts'
BG, PANEL, LINE = '#101c24', '#182832', '#31444f'
WHITE, MUTED, LIME, AMBER = '#f2f5ed', '#a8bdc7', '#d4f37c', '#f7c47d'
GROUPS = [('cli', 'ACTUAL CLI'), ('validator-api', 'VALIDATOR API'), ('native-cli', 'NATIVE CLI')]
LABELS = {
    'control-evidence': ('Archive control', '3 evidence record(s) verified'),
    'missing-preview': ('Apply without preview', 'No successful matching unconsumed preview'),
    'evidence-corruption': ('Corrupted evidence', 'archive.hash_mismatch'),
    'control-footprints': ('Footprint control', '"accepted": true'),
    'footprint-geometry': ('Edited footprint geometry', 'beyond allowed model URI replacements'),
    'model-corruption': ('Changed STEP bytes', 'provenance hash mismatch'),
    'selected-mpn': ('Selected MPN mismatch', 'does not match the exact selected native MPN'),
    'native-preview-control': ('Native preview control', '"source_mode": "native"'),
    'changed-candidate': ('Candidate bytes changed', 'No successful matching unconsumed preview'),
}
DECLARED = {
    'control-evidence': ('cli', 0), 'missing-preview': ('cli', 2), 'evidence-corruption': ('cli', 1),
    'control-footprints': ('validator-api', 0), 'footprint-geometry': ('validator-api', 1),
    'model-corruption': ('validator-api', 1), 'selected-mpn': ('validator-api', 1),
    'native-preview-control': ('native-cli', 0), 'changed-candidate': ('native-cli', 2),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def face(size: int, *, bold=False, mono=False):
    name = 'JetBrainsMono-Regular.ttf' if mono else f'InstrumentSans-{"Bold" if bold else "Regular"}.ttf'
    return ImageFont.truetype(str(FONT_ROOT / name), size)


def log_path(directory: Path, relative: str) -> Path:
    if not isinstance(relative, str) or '\\' in relative:
        raise ValueError('evaluation log paths must use scoped POSIX paths')
    parts = PurePosixPath(relative)
    if parts.is_absolute() or len(parts.parts) != 2 or parts.parts[0] != 'logs' or '..' in parts.parts:
        raise ValueError('evaluation log must be directly inside the record logs directory')
    path = directory / relative
    if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(directory):
        raise ValueError('evaluation log path is aliased or escapes the record directory')
    return path


def read_record(path: Path) -> tuple[dict, dict[str, str]]:
    path = path.resolve()
    record = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(record, dict):
        raise ValueError('evaluation record must be an object')  # noqa: TRY004 -- Invalid JSON artifact schema, not an API argument type.
    maps = ['source_inputs_before', 'source_inputs_after', 'implementation_before', 'implementation_after']
    if (any(not isinstance(record.get(key), dict) or not record[key] for key in maps)
            or type(record.get('schema_version')) is not int or record['schema_version'] != 1
            or record.get('mode') != 'native' or type(record.get('exit_code')) is not int or record['exit_code'] != 0
            or record.get('source_inputs_unchanged') is not True or record.get('implementation_unchanged') is not True
            or record.get('source_inputs_before') != record.get('source_inputs_after')
            or record.get('implementation_before') != record.get('implementation_after')):
        raise ValueError('evaluation is incomplete or does not preserve its recorded source/implementation inputs')
    cases = record.get('cases', [])
    if (not isinstance(cases, list) or len(cases) != len(LABELS)
            or any(not isinstance(case, dict) or not isinstance(case.get('name'), str) for case in cases)
            or {case['name'] for case in cases} != set(LABELS)):
        raise ValueError('this graphic requires the nine declared evaluation cases')
    sources = {path.name: digest(path)}
    seen_logs = set()
    for case in cases:
        actual, expected = case['actual'], case['expected']
        interface, exit_code = DECLARED[case['name']]
        if (not isinstance(actual, dict) or not isinstance(expected, dict)
                or any(not isinstance(case.get(key), dict) or not case[key] for key in
                       ('inputs_before', 'inputs_after_injection', 'inputs_after_checks'))
                or case.get('outcome') != 'met_expectation' or case.get('checks_preserved_inputs') is not True
                or case.get('inputs_after_injection') != case.get('inputs_after_checks')
                or actual.get('error') is not None or type(actual.get('exit_code')) is not int
                or actual['exit_code'] != exit_code or type(expected.get('exit_code')) is not int
                or expected['exit_code'] != exit_code or actual.get('interface') != interface):
            raise ValueError(f'evaluation case did not meet its declared preserved-input expectation: {case["name"]}')
        logs = []
        for stream in ('stdout', 'stderr'):
            relative = actual[stream]
            if not isinstance(relative, str) or relative.casefold() in seen_logs:
                raise ValueError('evaluation cases alias the same raw log')
            seen_logs.add(relative.casefold())
            raw = log_path(path.parent, relative)
            sources[relative] = digest(raw)
            if actual.get(stream + '_sha256', sources[relative]) != sources[relative]:
                raise ValueError(f'evaluation raw log hash mismatch: {relative}')
            logs.append(raw.read_text(encoding='utf-8'))
        combined = '\n'.join(logs)
        diagnostic = expected.get('diagnostic_contains')
        if not diagnostic or diagnostic not in combined or LABELS[case['name']][1] not in combined:
            raise ValueError(f'evaluation raw diagnostic does not support the recorded outcome: {case["name"]}')
    versions = {case['native_tool_version'] for case in cases if case.get('native_tool_version')}
    if len(versions) != 1 or not record['environment']['platform'].startswith('Windows'):
        raise ValueError('this evaluation graphic needs its declared Windows/native-tool environment')
    duration = record.get('duration_seconds')
    if type(duration) not in {float, int} or not math.isfinite(duration) or duration <= 0:
        raise ValueError('evaluation duration must be a finite observed value')
    record['display_native_version'] = next(iter(versions))
    return record, sources


def render(record: dict, sources: dict) -> Image.Image:
    image = Image.new('RGB', (1600, 1000), BG)
    draw = ImageDraw.Draw(image)
    for x in range(32, 1600, 40):
        for y in range(32, 1000, 40):
            draw.ellipse((x, y, x + 1, y + 1), fill='#263741')

    def text(x, y, value, size=24, color=WHITE, *, bold=False, mono=False):
        font = face(size, bold=bold, mono=mono)
        bounds = draw.multiline_textbbox((x, y), value, font=font, spacing=8)
        if bounds[0] < 0 or bounds[1] < 0 or bounds[2] > image.width or bounds[3] > image.height:
            raise ValueError(f'graphic text exceeds canvas: {value}')
        draw.multiline_text((x, y), value, font=font, fill=color, spacing=8)

    def wrapped(value, font, width):
        lines, line = [], ''
        for word in value.split():
            candidate = (line + ' ' + word).strip()
            if line and draw.textlength(candidate, font=font) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        return '\n'.join([*lines, line])

    draw.rectangle((64, 45, 88, 69), outline=LIME, width=2)
    draw.rectangle((72, 53, 80, 61), fill=LIME)
    text(104, 40, 'PCB COPILOT', 25, bold=True)
    text(1075, 46, 'RECORDED SOFTWARE EVALUATION', 17, MUTED, mono=True)
    cases = record['cases']
    controls = sum(case['actual']['exit_code'] == 0 for case in cases)
    rejected = len(cases) - controls
    text(57, 99, str(len(cases)), 158, LIME, bold=True)
    text(220, 116, 'declared expectations', 61, bold=True)
    text(220, 184, 'observed', 61, bold=True)
    text(224, 275, f'{controls} valid controls / {rejected} invalid requests rejected', 29, MUTED)
    text(64, 329, f'{record["duration_seconds"]:.2f}s  •  Windows  •  KiCad {record["display_native_version"]}  •  one run',
         21, MUTED, mono=True)
    draw.line((64, 376, 1536, 376), fill=LINE, width=2)
    for column, (interface, heading) in enumerate(GROUPS):
        left, top, width = 64 + column * 496, 402, 480
        draw.rounded_rectangle((left, top, left + width, 854), radius=7, fill=PANEL, outline=LINE)
        group = [case for case in cases if case['actual']['interface'] == interface]
        if len(group) > 4:
            raise ValueError('evaluation group exceeds the graphic row capacity')
        text(left + 22, top + 18, heading, 18, LIME, mono=True)
        text(left + 425, top + 18, f'{len(group):02}', 18, MUTED, mono=True)
        draw.line((left + 22, top + 58, left + width - 22, top + 58), fill=LINE)
        for index, case in enumerate(group):
            y = top + 76 + index * 92
            label, excerpt = LABELS[case['name']]
            code = case['actual']['exit_code']
            color = LIME if code == 0 else AMBER
            text(left + 22, y, label, 21, bold=True)
            draw.rounded_rectangle((left + 381, y - 1, left + 458, y + 29), radius=4, outline=LINE, fill=BG)
            text(left + 392, y + 3, f'exit {code}', 15, color, mono=True)
            text(left + 22, y + 33, wrapped(excerpt, face(17, mono=True), width - 44), 17, MUTED, mono=True)
            if index < len(group) - 1:
                draw.line((left + 22, y + 81, left + width - 22, y + 81), fill=LINE)
        if interface == 'native-cli':
            y = 741
            text(left + 22, y, 'REAL PREVIEW → + NEWLINE → REJECT', 16, AMBER, mono=True)
            text(left + 22, y + 33, 'Candidate circuit was unchanged.', 19, MUTED)
            text(left + 22, y + 64, 'Saved inputs stayed intact.', 19, MUTED)
    text(65, 877, f'SOURCE INPUTS UNCHANGED  /  {len(sources) - 1} RAW LOGS HASHED', 17, LIME, mono=True)
    text(64, 916, 'Small software regression. Unbuilt hardware.', 26, bold=True)
    text(64, 955, 'One board, one run. No general accuracy claim or fabrication approval.', 21, MUTED)
    return image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new external PNG; existing files are never overwritten')
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.is_relative_to(ROOT) or output.suffix.lower() != '.png' or output.exists() or args.output.is_symlink():
        parser.error('--output must be a new PNG outside the repository')
    record, sources = read_record(args.record)
    image = render(record, sources)
    metadata = PngImagePlugin.PngInfo()
    provenance = {'record_and_raw_logs': sources, 'generator_sha256': digest(Path(__file__)),
                  'font_hashes': {path.name: digest(path) for path in sorted(FONT_ROOT.glob('*.ttf'))},
                  'scope': 'One saved software regression; no general accuracy or hardware validation claim.'}
    metadata.add_text('evaluation_provenance', json.dumps(provenance, sort_keys=True))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', pnginfo=metadata, optimize=True)
    # Recheck the exact evidence bytes after rendering, before publishing even
    # this single new file. The PNG's metadata retains every raw-log digest.
    for relative, expected in sources.items():
        path = args.record.resolve() if relative == args.record.name else log_path(args.record.resolve().parent, relative)
        if digest(path) != expected:
            raise RuntimeError(f'evaluation evidence changed during rendering: {relative}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(buffer.getvalue())
    print(json.dumps({'output': str(output), 'sha256': digest(output), 'width': 1600, 'height': 1000,
                      'record_and_raw_logs': sources}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
