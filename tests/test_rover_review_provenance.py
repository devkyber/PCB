"""Review artifacts must describe the source/view bytes actually exported."""
import importlib.util
import json
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'projects/rover-pdb/layout/render_assembly.py'
spec = importlib.util.spec_from_file_location('rover_review_exports', MODULE)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


@pytest.fixture
def bundle(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'rover-pdb.kicad_pcb').write_bytes(b'original PCB')
    (project / 'rover-pdb.kicad_pro').write_bytes(b'original settings')
    exported = tmp_path / 'bundle'
    exported.mkdir()
    for name in review.SVG_NAMES:
        (exported / name).write_text(f'<svg>{name}</svg>')
    manifest = {
        'source_hashes': review.source_hashes(project),
        'svg_hashes': {name: review.sha256(exported / name) for name in review.SVG_NAMES},
    }
    (exported / 'review-source.json').write_text(json.dumps(manifest))
    return project, exported


def test_current_source_and_views_validate(bundle):
    project, exported = bundle
    assert review.validate_bundle(project, exported)['source_hashes']['rover-pdb.kicad_dru'] is None


@pytest.mark.parametrize('name', review.SOURCE_NAMES)
def test_changed_source_or_new_rules_reject_stale_views(bundle, name):
    project, exported = bundle
    (project / name).write_bytes(b'changed source')
    with pytest.raises(RuntimeError, match='changed during review export'):
        review.validate_bundle(project, exported)


def test_svg_from_another_export_is_rejected(bundle):
    project, exported = bundle
    (exported / 'top-copper.svg').write_bytes(b'old copper view')
    with pytest.raises(RuntimeError, match='Review SVG changed'):
        review.validate_bundle(project, exported)


def test_missing_view_is_rejected(bundle):
    project, exported = bundle
    (exported / 'bottom-copper.svg').unlink()
    with pytest.raises(RuntimeError, match='Review SVG changed or is missing'):
        review.validate_bundle(project, exported)


def test_source_change_during_publication_restores_previous_outputs(bundle, monkeypatch):
    project, exported = bundle
    destination = project / 'output/review'
    destination.mkdir(parents=True)
    prior = destination / 'assembly.svg'
    prior.write_bytes(b'previous accepted review')
    original_replace = review._replace_bytes
    changed = False

    def replace_and_change_source(path, data):
        nonlocal changed
        original_replace(path, data)
        if not changed:
            changed = True
            (project / 'rover-pdb.kicad_pro').write_bytes(b'owner changed routing settings')

    monkeypatch.setattr(review, '_replace_bytes', replace_and_change_source)
    with pytest.raises(RuntimeError, match='changed during review export'):
        review.publish_views(project, exported)
    assert prior.read_bytes() == b'previous accepted review'
    assert sorted(path.name for path in destination.iterdir()) == ['assembly.svg']
