import json
from dataclasses import dataclass

from pcb_copilot.cli import main
from pcb_copilot.project import load_project
from pcb_copilot.review.commands import (
    render_review_json,
    render_review_markdown,
    review_project,
    write_review_report,
)
from pcb_copilot.review.models import CheckResult, CheckScope

SCOPE = CheckScope(
    proves='fixture executed', does_not_prove='real-board suitability',
    deterministic=True, requires_external_tool=False,
)


@dataclass
class WritingCheck:
    check_id: str = 'writes-report'
    scope: CheckScope = SCOPE

    def run(self, project):
        (project.root / 'erc-report.json').write_text('temporary report', encoding='utf-8')
        return CheckResult(self.check_id, True, 'staged report written', self.scope)


def test_review_runs_checks_in_copy_and_preserves_current_project(project_copy, tree_hash):
    project = load_project(project_copy)
    before = tree_hash(project_copy)

    report = review_project(project, checks=(WritingCheck(),))

    assert report.results[0].passed is True
    assert tree_hash(project_copy) == before
    assert (project_copy / 'erc-report.json').read_text(encoding='utf-8') != 'temporary report'


def test_review_cli_reports_all_registered_checks_without_writing_current_project(
    project_copy, tree_hash, capsys,
):
    before = tree_hash(project_copy)

    code = main(['review', str(project_copy), '--format', 'json'])
    output = json.loads(capsys.readouterr().out)

    assert code == 1  # unresolved human and engineering work is not a green review
    assert len(output['results']) == 10
    assert output['project'] == 'baro-bmp390'
    assert output['blocking'] is True
    assert all(item['scope']['proves'] and item['scope']['does_not_prove']
               for item in output['results'])
    assert tree_hash(project_copy) == before


def test_review_report_can_be_written_only_as_new_local_report(project_copy):
    project = load_project(project_copy)
    report = review_project(project, checks=(WritingCheck(),))
    markdown = render_review_markdown(report)
    output = project.root / '.pcb-copilot' / 'reports' / 'manual.md'

    assert report.schematic_hash in markdown
    assert report.pcb_hash in markdown
    assert 'Does not prove' in markdown
    assert write_review_report(project, output, markdown) == output
    assert output.read_text(encoding='utf-8') == markdown

    try:
        write_review_report(project, output, markdown)
    except FileExistsError:
        pass
    else:
        raise AssertionError('existing report must not be overwritten')

    try:
        write_review_report(project, project.root / 'SIGNOFF.md', markdown)
    except ValueError:
        pass
    else:
        raise AssertionError('review output must not target an authoritative file')


def test_review_json_is_schema_versioned(project_copy):
    report = review_project(load_project(project_copy), checks=(WritingCheck(),))
    document = json.loads(render_review_json(report))

    assert document['schema_version'] == 1
    assert document['schematic_hash'] == report.schematic_hash


def test_review_cli_writes_explicit_markdown_report_without_approval(project_copy):
    output = project_copy / '.pcb-copilot' / 'reports' / 'manual.md'

    code = main(['review', str(project_copy), '--format', 'markdown',
                 '--output', str(output)])

    assert code == 1
    assert output.is_file()
    assert '# Review: baro-bmp390' in output.read_text(encoding='utf-8')
    assert 'signoff — FAIL' in output.read_text(encoding='utf-8')
