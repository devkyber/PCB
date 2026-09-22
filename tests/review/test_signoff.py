from datetime import UTC, datetime

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


def test_barometer_profile_contains_no_irrelevant_xt60_or_module_socket_question(repo_root):
    profile = load_review_profile(repo_root / 'projects/baro-bmp390')

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
