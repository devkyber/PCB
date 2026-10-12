import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pcb_copilot.layout import update as layout_update
from pcb_copilot.preview_publication import LAYOUT_ARTIFACTS, publish_layout_artifacts
from pcb_copilot.project import load_project
from pcb_copilot.schematic import native_candidate
from pcb_copilot.schematic import update as schematic_update
from pcb_copilot.schematic.preview import PreviewResult


def seed_old_artifacts(preview):
    preview.mkdir(parents=True, exist_ok=True)
    for name in LAYOUT_ARTIFACTS:
        (preview / name).write_bytes(b'old board export')
    for name in ('layout-review.json', 'schematic-review.json', 'owner-notes.txt'):
        (preview / name).write_bytes(b'preserve unrelated file')


@pytest.mark.parametrize('current_svg', [False, True])
def test_missing_layout_exports_are_removed_without_clearing_other_files(tmp_path, current_svg):
    preview, output = tmp_path / 'preview', tmp_path / 'output'
    seed_old_artifacts(preview)
    output.mkdir()
    if current_svg:
        (output / 'layout.svg').write_bytes(b'<svg>current</svg>')
    (output / 'layout-drc-0.json').write_bytes(b'{"current": true}')
    (output / 'export-report.json').write_bytes(b'{"step": "failed"}')

    published = publish_layout_artifacts(
        tmp_path, output, preview, additional_artifacts=output.iterdir(),
    )

    assert (preview / 'layout.svg').is_file() == current_svg
    if current_svg:
        assert Path(published['layout.svg']).read_bytes() == b'<svg>current</svg>'
    else:
        assert 'layout.svg' not in published
    assert not (preview / 'layout.step').exists()
    assert not (preview / 'layout-drc-1.json').exists()
    assert not (preview / 'routing-topology.json').exists()
    assert (preview / 'layout-drc-0.json').read_bytes() == b'{"current": true}'
    assert (preview / 'export-report.json').read_bytes() == b'{"step": "failed"}'
    for name in ('layout-review.json', 'schematic-review.json', 'owner-notes.txt'):
        assert (preview / name).read_bytes() == b'preserve unrelated file'


@pytest.mark.parametrize('missing', ['step', 'svg'])
def test_layout_update_never_returns_an_older_failed_export(project_copy, monkeypatch, missing):
    project = load_project(project_copy)
    preview = project.root / '.pcb-copilot/preview'
    seed_old_artifacts(preview)
    before = project.pcb_path.read_bytes()

    def prepare(snapshot, _intent, _candidate, _route, output):
        if missing != 'svg':
            (output / 'layout.svg').write_bytes(b'<svg>current</svg>')
        return snapshot.pcb_path, [{
            'code': 'step.unavailable' if missing == 'step' else 'preview.failed',
            'message': 'export failed',
            'severity': 'review' if missing == 'step' else 'block',
        }], {}

    monkeypatch.setattr(layout_update, '_prepare_candidate', prepare)
    result = layout_update.update_layout(project, candidate=project.pcb_path)

    assert result['exit_code'] == int(missing == 'svg')
    assert not (preview / 'layout.step').exists()
    assert not (preview / 'layout-drc-0.json').exists()
    assert not (preview / 'layout-drc-1.json').exists()
    if missing == 'svg':
        assert result['preview'] is None
        assert not (preview / 'layout.svg').exists()
    else:
        assert Path(result['preview']).read_bytes() == b'<svg>current</svg>'
    assert project.pcb_path.read_bytes() == before


@pytest.mark.parametrize('mode', ['native', 'intent'])
@pytest.mark.parametrize('paired', [False, True])
def test_schematic_update_clears_layout_exports_only_for_a_paired_attempt(
    project_copy, tmp_path, monkeypatch, mode, paired,
):
    project = load_project(project_copy)
    preview = project.root / '.pcb-copilot/preview'
    seed_old_artifacts(preview)
    before = project.schematic_path.read_bytes(), project.pcb_path.read_bytes()

    def schematic_preview(_tools, _schematic, output):
        output.mkdir(parents=True, exist_ok=True)
        for name, payload in (('preview.pdf', b'%PDF current'), ('erc.json', b'{}'),
                              ('metrics.json', b'{}')):
            (output / name).write_bytes(payload)
        return PreviewResult(output / 'preview.pdf', output / 'erc.json', output / 'metrics.json', ())

    def prepare(snapshot, _intent, _candidate, _route, output, *, schematic_change):
        assert schematic_change
        # Both visualization exports failed; current diagnostic reports remain useful.
        (output / 'layout-drc-0.json').write_bytes(b'{"current": true}')
        return snapshot.pcb_path, [{
            'code': 'preview.failed', 'message': 'export failed', 'severity': 'block',
        }], {}

    monkeypatch.setattr(layout_update, '_prepare_candidate', prepare)
    monkeypatch.setattr(layout_update, '_bind_candidate_links', lambda *_: [])
    if mode == 'native':
        monkeypatch.setattr(native_candidate, 'discover_toolchain', lambda _: None)
        monkeypatch.setattr(native_candidate, 'render_schematic_preview', schematic_preview)
        monkeypatch.setattr(native_candidate, 'check_evidence', lambda *_: ())
        monkeypatch.setattr(native_candidate, 'extract', lambda _: {'nets': {}})
        monkeypatch.setattr(native_candidate, 'check_parity', lambda _: (True, 'matched'))
        candidate = tmp_path / project.schematic_path.name
        candidate.write_bytes(before[0])
        result = native_candidate.update_native_schematic(
            project, candidate, pcb_candidate=project.pcb_path if paired else None,
        )
    else:
        def draft(snapshot, _intent):
            root = snapshot.root / '.fixture-draft'
            root.mkdir()
            (root / snapshot.schematic_path.name).write_bytes(snapshot.schematic_path.read_bytes())
            schematic_preview(None, None, root)
            return {'draft_id': 'fixture', 'findings': [], 'exit_code': 0}

        monkeypatch.setattr(schematic_update, 'draft_schematic', draft)
        monkeypatch.setattr(schematic_update, 'load_draft',
                            lambda snapshot, _: SimpleNamespace(root=snapshot.root / '.fixture-draft'))
        monkeypatch.setattr(schematic_update, 'candidate_board_parity', lambda *_: None)
        result = schematic_update.update_schematic(
            project, project.root / 'schematic-intent.yaml', False,
            pcb_candidate=project.pcb_path if paired else None,
        )

    assert result['exit_code'] == int(paired)
    assert Path(result['preview']).read_bytes() == b'%PDF current'
    assert (preview / 'layout-review.json').read_bytes() == b'preserve unrelated file'
    assert (preview / 'owner-notes.txt').read_bytes() == b'preserve unrelated file'
    if paired:
        assert not (preview / 'layout.svg').exists()
        assert not (preview / 'layout.step').exists()
        assert not (preview / 'layout-drc-1.json').exists()
        assert json.loads((preview / 'layout-drc-0.json').read_text()) == {'current': True}
    else:
        for name in LAYOUT_ARTIFACTS:
            assert (preview / name).read_bytes() == b'old board export'
    assert before == (project.schematic_path.read_bytes(), project.pcb_path.read_bytes())
