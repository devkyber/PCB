"""Create and verify a portable, offline handover from saved native CAD.

The HTML is an inspection aid. It creates no design decision, applies no edit,
and grants no fabrication approval. Existing output directories are never reused.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import pymupdf

from pcb_copilot import __version__
from pcb_copilot.models import Project
from pcb_copilot.project import load_project
from pcb_copilot.review.commands import render_review_json, review_project
from pcb_copilot.review.fingerprint import pcb_digest, schematic_digest
from pcb_copilot.review.report_html import render_report
from pcb_copilot.review.views import SVG_NAMES, fresh_review_views
from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import assert_current, copy_inputs, input_hashes

SCOPE = ('Source-bound native views and scoped review findings for inspection. '
         'An offline snapshot, not an approval, a fabrication package, or proof of hardware behavior.')


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(document: dict) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def _plain_path(path: Path) -> Path:
    absolute = path.expanduser().absolute()
    for part in (*reversed(absolute.parents), absolute):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'report paths must not contain symlinks or reparse points: {part}')
    return absolute.resolve()


def _run(arguments: list[str], cwd: Path) -> str:
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, encoding='utf-8',
                            errors='replace', timeout=240, check=False)
    if result.returncode:
        raise RuntimeError(f'native report export failed: {result.stderr or result.stdout}')
    return result.stdout.strip()


def _raster(payload: bytes, kind: str, *, page: int = 0) -> bytes:
    with pymupdf.open(stream=payload, filetype=kind) as document:
        sheet = document[page]
        scale = 2200 / max(sheet.rect.width, sheet.rect.height)
        return sheet.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')


def capture_native(project: Project, work: Path) -> tuple[dict[str, bytes], list[dict], dict]:
    """Export every schematic page and fresh assembly/copper views from a copy."""
    tools = discover_toolchain(project.root)
    version = _run([str(tools.kicad_cli), 'version'], work)
    pdf = work / 'schematic.pdf'
    _run([str(tools.kicad_cli), 'sch', 'export', 'pdf', '--output', str(pdf),
          str(project.schematic_path)], work)
    payload = pdf.read_bytes()
    with pymupdf.open(stream=payload, filetype='pdf') as document:
        count = document.page_count
    if count < len(schematic_files(project.schematic_path)):
        raise RuntimeError('native PDF omits a declared schematic sheet')
    files, images = {'schematic.pdf': payload}, []

    def image(name, title, category, orientation, data):
        files[name] = data
        images.append({'id': Path(name).stem, 'title': title, 'kind': category,
                       'orientation': orientation,
                       'data_uri': 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')})

    for number in range(count):
        image(f'schematic-{number + 1:03}.png', f'Schematic / page {number + 1} of {count}',
              'schematic', 'Native KiCad PDF page', _raster(payload, 'pdf', page=number))
    with fresh_review_views(project) as views:
        for name in SVG_NAMES:
            bottom = name == 'bottom-copper.svg'
            image(Path(name).with_suffix('.png').name, Path(name).stem.replace('-', ' ').capitalize(),
                  'assembly' if name == 'assembly.svg' else 'copper',
                  'Underside; mirrored relative to top' if bottom else 'Viewed from top',
                  _raster((views / name).read_bytes(), 'svg'))
    return files, images, {'kicad_version': version}


def _publish(destination: Path, files: dict[str, bytes], source_check) -> None:
    """Reserve a new folder and create only new files, with the manifest last.

    A handled failure removes only this operation's unchanged files. Concurrent
    owner files/edits are retained, with an explicit incomplete-output location.
    An interrupted process is recognizable by a missing or invalid manifest.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    identity = destination.stat()
    written = []

    def unchanged_directory():
        current = _plain_path(destination).stat()
        if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
            raise RuntimeError('report output directory changed during publication')

    try:
        source_check()
        for name, payload in files.items():
            unchanged_directory()
            with (destination / name).open('xb') as stream:
                written.append(name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        source_check()
        unchanged_directory()
        if {p.name for p in destination.iterdir()} != set(files):
            raise RuntimeError('concurrent files appeared in the report directory')
        for name, payload in files.items():
            if _plain_path(destination / name).read_bytes() != payload:
                raise RuntimeError(f'report output changed during publication: {name}')
    except BaseException as failure:
        retained = False
        for name in reversed(written):
            try:
                unchanged_directory()
                path = _plain_path(destination / name)
                if path.read_bytes() != files[name]:
                    retained = True
                    continue
                path.unlink()
            except (OSError, ValueError, RuntimeError):
                retained = True
        try:
            unchanged_directory()
            destination.rmdir()
        except (OSError, ValueError, RuntimeError):
            retained = True
        if retained:
            raise RuntimeError(f'report publication incomplete; concurrent/partial files retained at {destination}') from failure
        raise


def create_report(project: Project, output: Path) -> dict:
    destination = _plain_path(output)
    if destination == project.root or destination.is_relative_to(project.root):
        raise ValueError('report output must be a new directory outside the source project')
    if destination.exists():
        raise FileExistsError(f'report output already exists: {destination}')
    expected = input_hashes(project)
    with tempfile.TemporaryDirectory(prefix='pcb-handover-') as temporary:
        work = Path(temporary).resolve()
        if work.is_relative_to(project.root):
            raise ValueError('report temporary storage must be outside the source project')
        copy_inputs(project, work / project.root.name, expected)
        snapshot = load_project(work / project.root.name)
        report = review_project(snapshot)
        if (report.schematic_hash != schematic_digest(snapshot.schematic_path)
                or report.pcb_hash != pcb_digest(snapshot.pcb_path)):
            raise RuntimeError('review does not describe the captured report sources')
        files, images, tools = capture_native(snapshot, work)
        assert_current(snapshot, expected)
        assert_current(project, expected)
        document = {'schema_version': 1, 'generated_utc': datetime.now(UTC).isoformat(),
                    'pcb_copilot_version': __version__, 'project': {'name': report.project},
                    'review': json.loads(render_review_json(report)), 'source_inputs': expected,
                    'schematic_pdf_uri': 'data:application/pdf;base64,' + base64.b64encode(files['schematic.pdf']).decode('ascii'),
                    'source_inputs_unchanged': True, 'toolchain': tools,
                    'schematic_files': [p.relative_to(project.root).as_posix()
                                        for p in schematic_files(project.schematic_path)], 'scope': SCOPE}
        files.update({'review.json': _json(document['review']), 'source.json': _json(document),
                      'index.html': render_report(document, images).encode('utf-8')})
        manifest = {'schema_version': 1, 'purpose': 'human-review-handover',
                    'project': report.project, 'generated_utc': document['generated_utc'],
                    'source_inputs': expected, 'source_inputs_unchanged': True,
                    'review_blocking': report.blocking,
                    'outputs': {name: {'sha256': _hash(data), 'bytes': len(data)}
                                for name, data in files.items()}, 'scope': SCOPE}
        files['manifest.json'] = _json(manifest)
        _publish(destination, files, lambda: assert_current(project, expected))
    return {'output': str(destination), 'index': str(destination / 'index.html'),
            'review_blocking': report.blocking, 'source_inputs_unchanged': True,
            'schematic_pages': sum(view['kind'] == 'schematic' for view in images),
            'native_views': len(images), 'exit_code': int(report.blocking)}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate report JSON key: {key}')
        result[key] = value
    return result


class _HtmlSnapshot(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.payloads = []
        self.parts = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'script' and attributes.get('id') == 'report-data':
            if attributes.get('type') != 'application/json':
                raise ValueError('HTML snapshot payload must be inert JSON')
            self.active = True
            self.parts = []
        if tag == 'img' and attributes.get('src'):
            self.images.append(attributes['src'])

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.payloads.append(''.join(self.parts))
            self.active = False


def _verify_html(root: Path, document: dict, outputs: dict) -> None:
    parsed = _HtmlSnapshot()
    parsed.feed((root / 'index.html').read_text(encoding='utf-8'))
    if len(parsed.payloads) != 1:
        raise ValueError('HTML must contain exactly one recorded snapshot')
    embedded = json.loads(parsed.payloads[0], object_pairs_hook=_object)
    if not isinstance(embedded, dict) or embedded.get('document') != document:
        raise ValueError('HTML snapshot disagrees with the source/review records')
    views = embedded.get('images')
    if (not isinstance(views, list) or len(views) != len(parsed.images)
            or any(not isinstance(view, dict) or not isinstance(view.get('id'), str) for view in views)):
        raise ValueError('HTML native view inventory is incomplete')
    names = [view['id'] + '.png' for view in views]
    if len(set(names)) != len(names) or set(names) != {name for name in outputs if name.endswith('.png')}:
        raise ValueError('HTML native views disagree with the captured PNG inventory')
    for name, uri in zip(names, parsed.images, strict=True):
        prefix = 'data:image/png;base64,'
        if not uri.startswith(prefix):
            raise ValueError('HTML native views must be embedded PNGs')
        if base64.b64decode(uri[len(prefix):], validate=True) != (root / name).read_bytes():
            raise ValueError(f'HTML native image differs from its captured artifact: {name}')
    pdf = document.get('schematic_pdf_uri')
    if pdf:
        prefix = 'data:application/pdf;base64,'
        if not isinstance(pdf, str) or not pdf.startswith(prefix):
            raise ValueError('HTML schematic PDF is invalid')
        if base64.b64decode(pdf[len(prefix):], validate=True) != (root / 'schematic.pdf').read_bytes():
            raise ValueError('HTML schematic PDF differs from the captured vector artifact')


def verify_report(directory: Path, project: Project | None = None) -> dict:
    """Verify packet bytes and, optionally, whether saved project inputs match."""
    root = _plain_path(directory)
    manifest_path = _plain_path(root / 'manifest.json')
    if not manifest_path.is_file() or manifest_path.stat().st_nlink != 1:
        raise ValueError('report manifest is missing or aliased')
    manifest = json.loads(manifest_path.read_bytes(), object_pairs_hook=_object)
    if (not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int
            or manifest['schema_version'] != 1
            or manifest.get('purpose') != 'human-review-handover'
            or manifest.get('source_inputs_unchanged') is not True):
        raise ValueError('not a completed PCB review handover')
    outputs = manifest.get('outputs')
    required = {'index.html', 'review.json', 'source.json', 'schematic.pdf',
                'schematic-001.png', 'assembly.png', 'top-copper.png', 'bottom-copper.png'}
    if not isinstance(outputs, dict) or not required <= outputs.keys():
        raise ValueError('report lacks its required native views or review/source records')
    if {p.name for p in root.iterdir()} != {*outputs, 'manifest.json'}:
        raise ValueError('report contains missing or unlisted files')
    for name, record in outputs.items():
        if (not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', name)
                or not isinstance(record, dict) or type(record.get('bytes')) is not int
                or record['bytes'] < 1 or not re.fullmatch(r'[0-9a-f]{64}', str(record.get('sha256')))):
            raise ValueError('invalid report filename/hash/byte count')
        path = _plain_path(root / name)
        if not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError(f'report output is missing or aliased: {name}')
        payload = path.read_bytes()
        if len(payload) != record['bytes'] or _hash(payload) != record['sha256']:
            raise ValueError(f'report output byte/hash mismatch: {name}')
    document = json.loads((root / 'source.json').read_bytes(), object_pairs_hook=_object)
    review = json.loads((root / 'review.json').read_bytes(), object_pairs_hook=_object)
    if (not isinstance(document, dict) or not isinstance(review, dict)
            or document.get('source_inputs') != manifest.get('source_inputs')
            or not isinstance(manifest.get('source_inputs'), dict) or not manifest['source_inputs']
            or document.get('source_inputs_unchanged') is not True or document.get('review') != review
            or type(review.get('blocking')) is not bool or review['blocking'] != manifest.get('review_blocking')):
        raise ValueError('report source/review records disagree')
    if (not isinstance(manifest.get('project'), str) or not manifest['project']
            or document.get('project') != {'name': manifest['project']} or review.get('project') != manifest['project']):
        raise ValueError('report project identities disagree')
    for name, value in manifest['source_inputs'].items():
        if (not isinstance(name, str) or not name or name.startswith('/') or ':' in name or '\\' in name
                or '..' in name.split('/') or (value is not None and
                    (not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)))):
            raise ValueError('report source input ledger is invalid')
    results, findings = review.get('results'), review.get('findings')
    if (not isinstance(results, list) or not results or not isinstance(findings, list)
            or any(not isinstance(r, dict) or type(r.get('passed')) is not bool for r in results)
            or any(not isinstance(f, dict) or type(f.get('blocking')) is not bool for f in findings)
            or review['blocking'] != (any(not r['passed'] for r in results) or any(f['blocking'] for f in findings))):
        raise ValueError('review findings and blocking state disagree')
    _verify_html(root, document, outputs)
    matches = input_hashes(project) == manifest['source_inputs'] if project else None
    return {'integrity_valid': True, 'project': manifest['project'], 'review_blocking': review['blocking'],
            'current_source_matches': matches, 'verified_outputs': len(outputs),
            'scope': 'Recorded byte identities; not capture authenticity, engineering approval or hardware qualification.',
            'exit_code': int(matches is False)}
