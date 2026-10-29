"""Fresh assembly/copper views for any board, bound to saved native sources."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import contained, project_lock, replace_bytes

SVG_NAMES = ('assembly.svg', 'top-copper.svg', 'bottom-copper.svg')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_names(project: Project) -> tuple[str, ...]:
    return tuple(project.pcb_path.with_suffix(suffix).relative_to(project.root).as_posix()
                 for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'))


def source_hashes(project: Project) -> dict[str, str | None]:
    return {name: sha256(project.root / name) if (project.root / name).is_file() else None
            for name in source_names(project)}


def assert_sources_current(project: Project, expected: dict) -> None:
    if source_hashes(project) != expected:
        raise RuntimeError('PCB or companion settings changed during review export; regenerate all views')


def validate_bundle(project: Project, bundle: Path) -> dict:
    manifest = json.loads((bundle / 'review-source.json').read_text(encoding='utf-8'))
    expected = manifest['source_hashes']
    names = source_names(project)
    if set(expected) != set(names) or not all(expected[name] for name in names[:2]):
        raise RuntimeError('Review bundle lacks the required PCB/settings provenance')
    assert_sources_current(project, expected)
    if set(manifest['svg_hashes']) != set(SVG_NAMES):
        raise RuntimeError('Review bundle must contain exactly the three required native views')
    for name, digest in manifest['svg_hashes'].items():
        if not (bundle / name).is_file() or sha256(bundle / name) != digest:
            raise RuntimeError(f'Review SVG changed or is missing: {name}')
    return manifest


def _run(command: list) -> str:
    result = subprocess.run([str(value) for value in command], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(f'Review export failed: {result.stderr or result.stdout}')
    return result.stdout.strip()


def _export(project: Project, bundle: Path) -> None:
    tools = discover_toolchain(project.root)
    if tools.kipython is None:
        raise RuntimeError('Native KiCad Python is required for assembly views')
    expected = source_hashes(project)
    names = source_names(project)
    if not all(expected[name] for name in names[:2]):
        raise RuntimeError('Saved PCB and companion project settings are required')
    native = bundle / 'native'
    native.mkdir()
    for name, digest in expected.items():
        if digest is None:
            continue
        data = (project.root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError('Source changed while creating the disposable review snapshot')
        target = native / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    board = native / names[0]
    # Only this disposable assembly copy hides duplicate fabrication text.
    assembly = board.with_name('assembly-plot.kicad_pcb')
    _run([tools.kipython, '-I', '-c', '''import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
for fp in b.GetFootprints():
    if fp.Value().GetLayer()==pcbnew.F_Fab:
        fp.Value().SetLayer(pcbnew.Dwgs_User)
    for item in fp.GraphicalItems():
        if isinstance(item,pcbnew.PCB_TEXT) and item.GetLayer()==pcbnew.F_Fab:
            item.SetLayer(pcbnew.Dwgs_User)
pcbnew.SaveBoard(sys.argv[2],b,True)
''', board, assembly])
    shutil.copyfile(native / names[1], assembly.with_suffix('.kicad_pro'))
    for name, layers, source in (
        ('assembly.svg', 'F.Fab,F.SilkS,Edge.Cuts', assembly),
        ('top-copper.svg', 'F.Cu,F.SilkS,Edge.Cuts', board),
        ('bottom-copper.svg', 'B.Cu,B.SilkS,Edge.Cuts', board),
    ):
        command = [tools.kicad_cli, 'pcb', 'export', 'svg', '-l', layers, '--mode-single',
                   '--fit-page-to-board', '--exclude-drawing-sheet', '-o', bundle / name, source]
        if name == 'assembly.svg':
            command += ['--black-and-white', '--sketch-pads-on-fab-layers']
        if name == 'bottom-copper.svg':
            command += ['--mirror']
        _run(command)
        if not (bundle / name).is_file() or not (bundle / name).stat().st_size:
            raise RuntimeError(f'Native SVG export produced no {name}')
    assert_sources_current(project, expected)
    manifest = {
        'schema_version': 1,
        'source_hashes': expected,
        'svg_hashes': {name: sha256(bundle / name) for name in SVG_NAMES},
        'kicad_version': _run([tools.kicad_cli, '--version']),
        'view_orientation': {'assembly.svg': 'top', 'top-copper.svg': 'top',
                             'bottom-copper.svg': 'underside; mirrored relative to top'},
        'scope': 'Fresh native review views; not a DRC, parity or fabrication approval',
    }
    (bundle / 'review-source.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    validate_bundle(project, bundle)


@contextmanager
def fresh_review_views(project: Project):
    with tempfile.TemporaryDirectory(prefix='pcb-review-views-') as temporary:
        bundle = Path(temporary)
        _export(project, bundle)
        yield bundle
        validate_bundle(project, bundle)


def publish_views(project: Project, bundle: Path) -> Path:
    """Publish all views together; a failed attempt restores previous outputs."""
    validate_bundle(project, bundle)
    destination = project.root / 'output/review'
    files = {contained(project.root, destination / name): bundle / name
             for name in (*SVG_NAMES, 'review-source.json')}
    data = {path: source.read_bytes() for path, source in files.items()}
    previous = {path: path.read_bytes() if path.is_file() else None for path in files}
    try:
        validate_bundle(project, bundle)
        for path, contents in data.items():
            replace_bytes(path, contents)
        validate_bundle(project, bundle)
    except BaseException:
        for path, contents in previous.items():
            if contents is None:
                path.unlink(missing_ok=True)
            else:
                replace_bytes(path, contents)
        raise
    return destination / 'review-source.json'


def export_review_views(project: Project) -> Path:
    with project_lock(project), fresh_review_views(project) as bundle:
        return publish_views(project, bundle)
