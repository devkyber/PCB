"""Export source-bound assembly and copper views from disposable native CAD.

The historical filename is retained for callers. All three views are always
exported together; accepted CAD is never saved by this module.
"""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

P = Path(__file__).resolve().parents[1]
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
KIPYTHON = CLI.with_name('python.exe')
SVG_NAMES = ('assembly.svg', 'top-copper.svg', 'bottom-copper.svg')
SOURCE_NAMES = ('rover-pdb.kicad_pcb', 'rover-pdb.kicad_pro', 'rover-pdb.kicad_dru')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(project):
    return {name: sha256(project / name) if (project / name).is_file() else None
            for name in SOURCE_NAMES}


def assert_sources_current(project, expected):
    if source_hashes(project) != expected:
        raise RuntimeError('PCB or companion settings changed during review export; regenerate all views')


def validate_bundle(project, bundle):
    manifest = json.loads((bundle / 'review-source.json').read_text(encoding='utf-8'))
    expected = manifest['source_hashes']
    if set(expected) != set(SOURCE_NAMES) or not all(expected[name] for name in SOURCE_NAMES[:2]):
        raise RuntimeError('Review bundle lacks the required PCB/settings provenance')
    assert_sources_current(project, expected)
    if set(manifest['svg_hashes']) != set(SVG_NAMES):
        raise RuntimeError('Review bundle must contain exactly the three required native views')
    for name, digest in manifest['svg_hashes'].items():
        if not (bundle / name).is_file() or sha256(bundle / name) != digest:
            raise RuntimeError(f'Review SVG changed or is missing: {name}')
    return manifest


def _run(command):
    result = subprocess.run([str(value) for value in command], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=180)
    if result.returncode:
        raise RuntimeError(f'Review export failed: {result.stderr or result.stdout}')
    return result.stdout


def _export(project, bundle):
    expected = source_hashes(project)
    if not all(expected[name] for name in SOURCE_NAMES[:2]):
        raise RuntimeError('Accepted PCB and companion project settings are required')
    native = bundle / 'native'
    native.mkdir()
    for name, digest in expected.items():
        if digest is None:
            continue
        data = (project / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError('Source changed while creating the disposable review snapshot')
        (native / name).write_bytes(data)
    board = native / SOURCE_NAMES[0]
    # Only the disposable assembly copy hides duplicate fabrication text.
    assembly = native / 'assembly-plot.kicad_pcb'
    _run([KIPYTHON, '-I', '-c', '''import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
for fp in b.GetFootprints():
    for item in fp.GraphicalItems():
        if isinstance(item,pcbnew.PCB_TEXT) and item.GetLayer()==pcbnew.F_Fab:
            item.SetLayer(pcbnew.Dwgs_User)
pcbnew.SaveBoard(sys.argv[2],b,True)
''', board, assembly])
    shutil.copyfile(native / SOURCE_NAMES[1], assembly.with_suffix('.kicad_pro'))
    for name, layers, source in (
        ('assembly.svg', 'F.Fab,F.SilkS,Edge.Cuts', assembly),
        ('top-copper.svg', 'F.Cu,F.SilkS,Edge.Cuts', board),
        ('bottom-copper.svg', 'B.Cu,B.SilkS,Edge.Cuts', board),
    ):
        command = [CLI, 'pcb', 'export', 'svg', '-l', layers, '--mode-single',
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
        'kicad_version': _run([CLI, '--version']).strip(),
        'view_orientation': {'assembly.svg': 'top', 'top-copper.svg': 'top',
                             'bottom-copper.svg': 'underside; mirrored relative to top'},
        'scope': 'Fresh native review views; not a DRC, parity or fabrication approval',
    }
    (bundle / 'review-source.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    validate_bundle(project, bundle)


@contextmanager
def fresh_review_views(project=P):
    project = Path(project).resolve()
    with tempfile.TemporaryDirectory(prefix='rover-pcb-review-') as temporary:
        bundle = Path(temporary)
        _export(project, bundle)
        yield bundle
        validate_bundle(project, bundle)


def _replace_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.review-', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_views(project, bundle, additional_files=None):
    validate_bundle(project, bundle)
    files = {project / 'output/review' / name: bundle / name
             for name in (*SVG_NAMES, 'review-source.json')}
    files.update(additional_files or {})
    data = {path: source.read_bytes() for path, source in files.items()}
    previous = {path: path.read_bytes() if path.is_file() else None for path in files}
    try:
        validate_bundle(project, bundle)
        for path, contents in data.items():
            _replace_bytes(path, contents)
        validate_bundle(project, bundle)
    except Exception:
        for path, contents in previous.items():
            if contents is None:
                path.unlink(missing_ok=True)
            else:
                _replace_bytes(path, contents)
        raise


if __name__ == '__main__':
    with fresh_review_views() as bundle:
        publish_views(P, bundle)
    print(P / 'output/review/review-source.json')
