from datetime import UTC, datetime

import pytest
import yaml

from pcb_copilot.cli import main
from pcb_copilot.project import load_project
from pcb_copilot.review.fingerprint import pcb_digest, schematic_digest
from pcb_copilot.review.signoff import (
    SignoffCheck,
    load_review_profile,
    prepare_signoff,
    profile_digest,
)
from pcb_copilot.transaction import inputs_digest
from tests.board_fixtures import board_source


def test_barometer_profile_contains_no_irrelevant_xt60_or_module_socket_question(repo_root):
    profile = load_review_profile(board_source(repo_root, 'baro-bmp390'))

    assert profile.items
    assert all('XT60' not in item.prompt and 'module socket' not in item.prompt.lower()
               for item in profile.items)
    assert any('port' in item.prompt.lower() for item in profile.items)


def test_complete_current_signoff_passes_but_changed_child_sheet_is_stale(project_copy):
    project = load_project(project_copy)
    profile = load_review_profile(project.root)
    record = {
        'schema_version': 1,
        'records': [
            {
                'item_id': item.id, 'reviewer': 'Fixture Reviewer',
                'signed_on': datetime.now(UTC).date().isoformat(), 'decision': 'accepted',
                'note': 'Fixture-only signed review',
                'schematic_hash': schematic_digest(project.schematic_path),
                'pcb_hash': pcb_digest(project.pcb_path),
                'profile_hash': profile_digest(project.root),
                'inputs_hash': inputs_digest(project),
            }
            for item in profile.items
        ],
    }
    (project.root / 'review-signoff.yaml').write_text(yaml.safe_dump(record), encoding='utf-8')

    assert SignoffCheck().run(project).passed

    project.schematic_path.write_bytes(project.schematic_path.read_bytes() + b'\n')

    result = SignoffCheck().run(project)
    assert not result.passed
    assert 'stale' in result.detail


def test_rejected_item_blocks_even_with_current_hash(project_copy):
    project = load_project(project_copy)
    profile = load_review_profile(project.root)
    (project.root / 'review-signoff.yaml').write_text(yaml.safe_dump({
        'schema_version': 1,
        'records': [{
            'item_id': profile.items[0].id, 'reviewer': 'Fixture Reviewer',
            'signed_on': datetime.now(UTC).date().isoformat(), 'decision': 'rejected',
            'note': 'Fixture rejection',
            'schematic_hash': schematic_digest(project.schematic_path),
            'pcb_hash': pcb_digest(project.pcb_path),
            'profile_hash': profile_digest(project.root),
                'inputs_hash': inputs_digest(project),
        }],
    }), encoding='utf-8')

    result = SignoffCheck().run(project)
    assert not result.passed
    assert 'rejected' in result.detail


def test_prepare_signoff_creates_only_unsigned_hash_bound_template(project_copy):
    project = load_project(project_copy)

    path = prepare_signoff(project)
    document = yaml.safe_load(path.read_text(encoding='utf-8'))

    assert len(document['records']) == len(load_review_profile(project.root).items)
    assert all(not record['reviewer'] and not record['decision']
               for record in document['records'])
    assert all(record['schematic_hash'] == schematic_digest(project.schematic_path)
               for record in document['records'])
    assert not SignoffCheck().run(project).passed
    assert 'unsigned' in SignoffCheck().run(project).detail

    try:
        prepare_signoff(project)
    except FileExistsError:
        pass
    else:
        raise AssertionError('existing sign-off must not be overwritten')


def test_prepare_signoff_cli_never_marks_human_decisions_complete(project_copy):
    assert main(['prepare-signoff', str(project_copy)]) == 0
    result = SignoffCheck().run(load_project(project_copy))

    assert not result.passed
    assert 'unsigned' in result.detail


def test_local_profile_cannot_omit_shared_handover_decisions(project_copy):
    profile_path = project_copy / 'review-profile.yaml'
    profile_path.write_text(yaml.safe_dump({
        'schema_version': 1,
        'items': [{'id': 'local', 'prompt': 'Local inspection', 'rationale': 'Local scope'}],
    }), encoding='utf-8')
    project = load_project(project_copy)
    record = {
        'item_id': 'local', 'reviewer': 'Fixture Reviewer',
        'signed_on': datetime.now(UTC).date().isoformat(), 'decision': 'accepted',
        'note': 'Fixture-only local decision',
        'schematic_hash': schematic_digest(project.schematic_path),
        'pcb_hash': pcb_digest(project.pcb_path),
        'profile_hash': profile_digest(project.root), 'inputs_hash': inputs_digest(project),
    }
    (project_copy / 'review-signoff.yaml').write_text(yaml.safe_dump({
        'schema_version': 1, 'records': [record],
    }), encoding='utf-8')
    result = SignoffCheck().run(project)
    assert not result.passed
    assert 'shared.schematic-readability unsigned' in result.detail
    assert 'shared.layout-handover unsigned' in result.detail


@pytest.mark.parametrize('item_id', ['shared.schematic-readability', 'shared.layout-handover'])
def test_local_profile_cannot_weaken_shared_prompts(project_copy, item_id):
    path = project_copy / 'review-profile.yaml'
    profile = yaml.safe_load(path.read_text(encoding='utf-8'))
    profile['items'].append({'id': item_id, 'prompt': 'Skip inspection', 'rationale': 'Skip'})
    path.write_text(yaml.safe_dump(profile), encoding='utf-8')
    with pytest.raises(ValueError, match='reserved shared'):
        load_review_profile(project_copy)


def test_shared_policy_change_invalidates_existing_decisions(project_copy, monkeypatch):
    from dataclasses import replace

    from pcb_copilot.review import signoff

    project = load_project(project_copy)
    path = prepare_signoff(project)
    document = yaml.safe_load(path.read_text(encoding='utf-8'))
    for record in document['records']:
        record.update(reviewer='Fixture Reviewer', signed_on=datetime.now(UTC).date().isoformat(),
                      decision='accepted', note='Fixture-only complete decision')
    path.write_text(yaml.safe_dump(document), encoding='utf-8')
    assert SignoffCheck().run(project).passed
    original = signoff.COMMON_REVIEW_ITEMS
    monkeypatch.setattr(signoff, 'COMMON_REVIEW_ITEMS', (
        replace(original[0], prompt=original[0].prompt + ' Changed policy.'), *original[1:],
    ))
    result = SignoffCheck().run(project)
    assert not result.passed
    assert 'stale' in result.detail
