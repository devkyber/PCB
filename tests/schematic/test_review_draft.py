import json
import os
import shlex
import subprocess

import pytest

from pcb_copilot.accept import accept_schematic, load_draft
from pcb_copilot.cli import main
from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.models import Lifecycle
from pcb_copilot.project import load_project
from pcb_copilot.schematic.commands import draft_schematic, review_draft
from pcb_copilot.schematic.io import load_schematic_intent, save_schematic_intent
from pcb_copilot.state import effective_lifecycle, file_digest


def _reviewable_draft(project_copy, repo_root, tmp_path):
    project = load_project(project_copy)
    intent = load_schematic_intent(repo_root / 'tests/fixtures/schematic/parent-child.yaml')
    record = load_evidence_index(project.evidence_index_path).records[0]
    components = tuple(component.model_copy(update={
        'pin_map_evidence_id': record.id,
        'evidence_part_number': min(record.part_numbers),
    }) for component in intent.components)
    intent_path = tmp_path / 'intent.yaml'
    save_schematic_intent(intent.model_copy(update={'components': components}), intent_path)
    report = draft_schematic(project, intent_path)
    assert report['exit_code'] == 0, report['findings']
    return project, load_draft(project, report['draft_id']), intent.title


def _move_under_spaced_parent(project_copy, tmp_path):
    destination = tmp_path / "workspace with spaces $operator's" / project_copy.name
    destination.parent.mkdir()
    project_copy.replace(destination)
    return destination


def _expected_review_command(project, draft):
    root = str(project.root)
    if os.name == 'nt':
        quoted_root = "'" + root.replace("'", "''") + "'"
    else:
        quoted_root = shlex.quote(root)
    return f'pcb-copilot review-draft {quoted_root} {draft.id}'


def test_review_preserves_manual_hierarchy_edits_and_refreshes_acceptance(
    project_copy, repo_root, tmp_path,
):
    project_copy = _move_under_spaced_parent(project_copy, tmp_path)
    project, draft, title = _reviewable_draft(project_copy, repo_root, tmp_path)
    accepted_before = {
        path: path.read_bytes()
        for path in (project.schematic_path, project.pcb_path, project.netmap_path)
    }
    prior_report_path = draft.root / 'review.json'
    prior_report = json.loads(prior_report_path.read_text(encoding='utf-8'))
    prior_report['human_review'] = 'approved'
    prior_report_path.write_text(json.dumps(prior_report), encoding='utf-8')
    assert effective_lifecycle(project) == Lifecycle.DRAFT
    edited = {}
    for path in (draft.root / project.schematic_path.name, draft.root / 'sensor.kicad_sch'):
        original = path.read_text(encoding='utf-8')
        changed = original.replace(title, f'{title} reviewed', 1)
        assert changed != original
        path.write_text(changed, encoding='utf-8', newline='\n')
        edited[path] = path.read_bytes()

    with pytest.raises(ValueError, match='review-draft') as error:
        accept_schematic(project, draft)
    assert _expected_review_command(project, draft) in str(error.value)

    report = review_draft(project, draft.id)

    assert report['exit_code'] == 0, report['findings']
    assert report['human_review'] == 'pending'
    assert effective_lifecycle(project) == Lifecycle.DRAFT
    assert report['pdf'] == str(draft.root / 'preview.pdf')
    assert report['erc_report'] == str(draft.root / 'erc.json')
    assert report['metrics'] == str(draft.root / 'metrics.json')
    assert all(path.read_bytes() == payload for path, payload in edited.items())
    assert all(path.read_bytes() == payload for path, payload in accepted_before.items())
    for path in edited:
        relative = path.relative_to(draft.root).as_posix()
        assert report['artifact_hashes'][relative] == file_digest(path)
    assert json.loads((draft.root / 'review.json').read_text(encoding='utf-8')) == report

    accept_schematic(project, draft)
    assert project.schematic_path.read_bytes() == edited[draft.root / project.schematic_path.name]
    assert (project.root / 'sensor.kicad_sch').read_bytes() == edited[draft.root / 'sensor.kicad_sch']


def test_review_blocks_schematic_connectivity_that_contradicts_saved_intent(
    project_copy, repo_root, tmp_path,
):
    project, draft, _title = _reviewable_draft(project_copy, repo_root, tmp_path)
    child = draft.root / 'sensor.kicad_sch'
    intent_path = draft.root / 'schematic-intent.yaml'
    original_intent = intent_path.read_bytes()
    changed = child.read_text(encoding='utf-8').replace('DATA_READY', 'BROKEN_DATA')
    assert changed != child.read_text(encoding='utf-8')
    child.write_text(changed, encoding='utf-8', newline='\n')
    edited_child = child.read_bytes()

    report = review_draft(project, draft.id)

    assert report['exit_code'] == 1
    assert any(finding['code'] == 'intent-netlist-mismatch'
               for finding in report['findings'])
    assert child.read_bytes() == edited_child
    assert intent_path.read_bytes() == original_intent
    with pytest.raises(ValueError, match='blocking review findings'):
        accept_schematic(project, draft)


def test_failed_export_replaces_prior_success_and_preserves_cad(
    project_copy, repo_root, tmp_path, monkeypatch,
):
    import pcb_copilot.schematic.preview as preview_module

    project, draft, _title = _reviewable_draft(project_copy, repo_root, tmp_path)
    cad_paths = (draft.root / project.schematic_path.name, draft.root / 'sensor.kicad_sch')
    cad_before = {path: path.read_bytes() for path in cad_paths}

    monkeypatch.setattr(
        preview_module.subprocess,
        'run',
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 23, '', 'injected failure'),
    )
    report = review_draft(project, draft.id)

    assert report['exit_code'] == 1
    assert report['pdf'] is None
    assert not (draft.root / 'preview.pdf').exists()
    assert json.loads((draft.root / 'erc.json').read_text(encoding='utf-8'))['status'] == 'failed'
    assert {finding['code'] for finding in report['findings']} >= {
        'erc-failed', 'preview-failed',
    }
    assert all(path.read_bytes() == payload for path, payload in cad_before.items())
    with pytest.raises(ValueError):
        accept_schematic(project, draft)


def test_review_rejects_invalid_metadata_hierarchy_and_stale_base_before_writes(
    project_copy, repo_root, tmp_path,
):
    project, draft, _title = _reviewable_draft(project_copy, repo_root, tmp_path)
    metadata_path = draft.root / 'draft.json'
    root_path = draft.root / project.schematic_path.name
    metadata_bytes = metadata_path.read_bytes()
    root_bytes = root_path.read_bytes()
    outputs = tuple(draft.root / name for name in (
        'review.json', 'preview.pdf', 'erc.json', 'metrics.json',
    ))
    output_bytes = {path: path.read_bytes() for path in outputs}

    def assert_outputs_unchanged():
        assert {path: path.read_bytes() for path in outputs} == output_bytes

    with pytest.raises(ValueError, match='invalid draft ID'):
        review_draft(project, '../outside')
    assert_outputs_unchanged()

    metadata = json.loads(metadata_bytes)
    metadata['project'] = 'another-project'
    metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
    with pytest.raises(ValueError, match='does not belong'):
        review_draft(project, draft.id)
    assert_outputs_unchanged()
    metadata_path.write_bytes(metadata_bytes)

    metadata = json.loads(metadata_bytes)
    metadata['kind'] = 'layout'
    metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
    with pytest.raises(ValueError, match='schematic drafts'):
        review_draft(project, draft.id)
    assert_outputs_unchanged()
    metadata_path.write_bytes(metadata_bytes)

    traversing = root_path.read_text(encoding='utf-8').replace(
        'sensor.kicad_sch', '../../outside.kicad_sch', 1,
    )
    assert traversing != root_path.read_text(encoding='utf-8')
    root_path.write_text(traversing, encoding='utf-8', newline='\n')
    with pytest.raises(ValueError, match='escapes draft workspace'):
        review_draft(project, draft.id)
    assert_outputs_unchanged()
    root_path.write_bytes(root_bytes)

    with project.schematic_path.open('ab') as stream:
        stream.write(b'\n')
    with pytest.raises(ValueError, match='accepted files changed'):
        review_draft(project, draft.id)
    assert_outputs_unchanged()
    assert metadata_path.read_bytes() == metadata_bytes


def test_mid_review_edit_is_not_published_as_a_current_success(
    project_copy, repo_root, tmp_path, monkeypatch,
):
    import pcb_copilot.schematic.preview as preview_module

    project_copy = _move_under_spaced_parent(project_copy, tmp_path)
    project, draft, title = _reviewable_draft(project_copy, repo_root, tmp_path)
    child = draft.root / 'sensor.kicad_sch'
    outputs = tuple(draft.root / name for name in (
        'review.json', 'preview.pdf', 'erc.json', 'metrics.json',
    ))
    output_bytes = {path: path.read_bytes() for path in outputs}
    real_run = preview_module.subprocess.run
    edited = False

    def edit_during_export(*args, **kwargs):
        nonlocal edited
        argv = args[0]
        if not edited and argv[1:4] == ['sch', 'export', 'pdf']:
            text = child.read_text(encoding='utf-8')
            child.write_text(text.replace(title, f'{title} concurrent edit', 1),
                             encoding='utf-8', newline='\n')
            edited = True
        return real_run(*args, **kwargs)

    monkeypatch.setattr(preview_module.subprocess, 'run', edit_during_export)
    with pytest.raises(RuntimeError, match='changed during review') as error:
        review_draft(project, draft.id)

    assert edited
    assert _expected_review_command(project, draft) in str(error.value)
    assert {path: path.read_bytes() for path in outputs} == output_bytes
    assert f'{title} concurrent edit' in child.read_text(encoding='utf-8')
    with pytest.raises(ValueError, match='review-draft'):
        accept_schematic(project, draft)


def test_intent_edit_while_loading_cannot_be_sealed_with_stale_parsed_intent(
    project_copy, repo_root, tmp_path, monkeypatch,
):
    import pcb_copilot.schematic.commands as commands_module

    project, draft, title = _reviewable_draft(project_copy, repo_root, tmp_path)
    intent_path = draft.root / 'schematic-intent.yaml'
    cad_paths = (draft.root / project.schematic_path.name, draft.root / 'sensor.kicad_sch')
    cad_before = {path: path.read_bytes() for path in cad_paths}
    outputs = tuple(draft.root / name for name in (
        'review.json', 'preview.pdf', 'erc.json', 'metrics.json',
    ))
    output_bytes = {path: path.read_bytes() for path in outputs}
    real_load = commands_module.load_schematic_intent

    def edit_after_loading(path):
        intent = real_load(path)
        text = path.read_text(encoding='utf-8')
        path.write_text(text.replace(title, f'{title} concurrent intent edit', 1),
                        encoding='utf-8', newline='\n')
        return intent

    monkeypatch.setattr(commands_module, 'load_schematic_intent', edit_after_loading)
    with pytest.raises(RuntimeError, match='changed during review'):
        review_draft(project, draft.id)

    assert f'{title} concurrent intent edit' in intent_path.read_text(encoding='utf-8')
    assert all(path.read_bytes() == payload for path, payload in cad_before.items())
    assert {path: path.read_bytes() for path in outputs} == output_bytes
    with pytest.raises(ValueError, match='review-draft'):
        accept_schematic(project, draft)


def test_review_draft_cli_returns_report_schema_and_blocking_exit_code(
    project_copy, repo_root, tmp_path, capsys,
):
    project, draft, title = _reviewable_draft(project_copy, repo_root, tmp_path)
    child = draft.root / 'sensor.kicad_sch'
    child.write_text(
        child.read_text(encoding='utf-8').replace(title, f'{title} reviewed', 1),
        encoding='utf-8', newline='\n',
    )

    code = main(['review-draft', str(project.root), draft.id])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert set(report) == {
        'schema_version', 'draft_id', 'schematic', 'pdf', 'erc_report',
        'metrics', 'findings', 'human_review', 'exit_code', 'artifact_hashes',
    }

    child.write_text(
        child.read_text(encoding='utf-8').replace('DATA_READY', 'BROKEN_DATA'),
        encoding='utf-8', newline='\n',
    )
    code = main(['review-draft', str(project.root), draft.id])
    report = json.loads(capsys.readouterr().out)
    assert code == 1 == report['exit_code']
    assert any(finding['code'] == 'intent-netlist-mismatch'
               for finding in report['findings'])
