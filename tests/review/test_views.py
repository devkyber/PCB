"""Review artifacts must describe the source/view bytes actually exported."""
import json

import pytest
from kicad_claude.adapters import sch_io

from pcb_copilot.project import load_project
from pcb_copilot.review import views as review


@pytest.mark.slow
def test_native_assembly_plot_hides_fab_values_only_on_its_disposable_copy(project_copy):
    project = load_project(project_copy)
    before = review.source_hashes(project)
    with review.fresh_review_views(project) as bundle:
        assembly = bundle / 'native/assembly-plot.kicad_pcb'
        tree = sch_io.parse_file(assembly)
        values = [field for footprint in sch_io.find_children(tree, 'footprint')
                  for field in sch_io.find_children(footprint, 'property') if field[1] == 'Value']
        assert values
        assert all(sch_io.find_child(field, 'layer')[1] != 'F.Fab' for field in values)
        assert (bundle / 'assembly.svg').is_file()
    assert review.source_hashes(project) == before


@pytest.fixture
def bundle(tmp_path, project_copy):
    project = load_project(project_copy)
    project.pcb_path.write_bytes(b'original PCB')
    project.pcb_path.with_suffix('.kicad_pro').write_bytes(b'original settings')
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
    assert review.validate_bundle(project, exported)['source_hashes'][project.pcb_path.with_suffix('.kicad_dru').name] is None


@pytest.mark.parametrize('suffix', ('.kicad_pcb', '.kicad_pro', '.kicad_dru'))
def test_changed_source_or_new_rules_reject_stale_views(bundle, suffix):
    project, exported = bundle
    project.pcb_path.with_suffix(suffix).write_bytes(b'changed source')
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
    destination = project.root / 'output/review'
    destination.mkdir(parents=True)
    prior = destination / 'assembly.svg'
    prior.write_bytes(b'previous accepted review')
    original_replace = review.replace_bytes
    changed = False

    def replace_and_change_source(path, data):
        nonlocal changed
        original_replace(path, data)
        if not changed:
            changed = True
            project.pcb_path.with_suffix('.kicad_pro').write_bytes(b'owner changed routing settings')

    monkeypatch.setattr(review, 'replace_bytes', replace_and_change_source)
    with pytest.raises(RuntimeError, match='changed during review export'):
        review.publish_views(project, exported)
    assert prior.read_bytes() == b'previous accepted review'
    assert sorted(path.name for path in destination.iterdir()) == ['assembly.svg']


def test_failed_native_export_preserves_previous_bundle(project_copy, monkeypatch):
    project = load_project(project_copy)
    destination = project.root / 'output/review'
    destination.mkdir(parents=True)
    old = destination / 'review-source.json'
    old.write_bytes(b'previous source-bound bundle')

    def fail_export(*_args):
        raise RuntimeError('native export failed')

    monkeypatch.setattr(review, '_export', fail_export)
    with pytest.raises(RuntimeError, match='native export failed'):
        review.export_review_views(project)
    assert old.read_bytes() == b'previous source-bound bundle'
    assert not (project.root / '.pcb-copilot/operation.lock').exists()


@pytest.mark.slow
def test_native_views_work_for_a_non_rover_board_without_changing_cad(project_copy):
    project = load_project(project_copy)
    before = review.source_hashes(project)

    path = review.export_review_views(project)

    manifest = review.validate_bundle(project, path.parent)
    assert review.source_hashes(project) == before
    assert manifest['source_hashes'] == before
    assert 'mirrored' in manifest['view_orientation']['bottom-copper.svg']
    assert all((path.parent / name).read_bytes().lstrip().startswith(b'<?xml')
               for name in review.SVG_NAMES)
