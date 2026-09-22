from dataclasses import dataclass
from pathlib import Path
from shutil import copy2

from pcb_copilot.project import load_project
from pcb_copilot.review.fingerprint import schematic_digest
from pcb_copilot.review.models import CheckResult, CheckScope, FindingKind
from pcb_copilot.review.registry import run_checks

SCOPE = CheckScope(
    proves='the fixture condition', does_not_prove='electrical suitability',
    deterministic=True, requires_external_tool=False,
)


@dataclass
class FakeCheck:
    check_id: str
    passed: bool
    calls: list[str]
    scope: CheckScope = SCOPE

    def run(self, _project):
        self.calls.append(self.check_id)
        return CheckResult(self.check_id, self.passed, 'fixture result', self.scope)


@dataclass
class CrashingCheck:
    check_id: str = 'broken'
    scope: CheckScope = SCOPE

    def run(self, _project):
        raise RuntimeError('check crashed')


@dataclass
class MutatingCheck:
    check_id: str = 'mutating'
    scope: CheckScope = SCOPE

    def run(self, project):
        project.schematic_path.write_text('mutated', encoding='utf-8')
        return CheckResult(self.check_id, True, 'fixture result', self.scope)


@dataclass
class AdvisoryCheck:
    check_id: str = 'advisory'
    scope: CheckScope = SCOPE

    def run(self, _project):
        return CheckResult(self.check_id, True, 'structural checks pass', self.scope,
                           advisories=('human page flow may be unclear',))


def test_registry_runs_every_check_after_a_failure(project_copy):
    calls = []
    project = load_project(project_copy)

    report = run_checks(project, [FakeCheck('first', False, calls),
                                  FakeCheck('second', True, calls)])

    assert calls == ['first', 'second']
    assert [result.check_id for result in report.results] == ['first', 'second']
    assert report.blocking is True
    assert report.findings[0].kind == FindingKind.MACHINE_FAILURE


def test_crashed_check_is_blocking_and_does_not_hide_following_checks(project_copy):
    calls = []
    project = load_project(project_copy)

    report = run_checks(project, [CrashingCheck(), FakeCheck('later', True, calls)])

    assert calls == ['later']
    assert report.findings[0].kind == FindingKind.MACHINE_FAILURE
    assert report.findings[0].blocking is True
    assert 'check crashed' in report.findings[0].detail
    assert len(report.results) == 2


def test_report_hashes_identify_input_design_even_if_check_mutates_copy(project_copy):
    project = load_project(project_copy)
    input_hash = schematic_digest(project.schematic_path)

    report = run_checks(project, [MutatingCheck()])

    assert report.schematic_hash == input_hash


def test_schematic_fingerprint_changes_when_hierarchical_child_changes(tmp_path):
    source = Path('projects/tms-v3')
    for schematic in source.glob('*.kicad_sch'):
        copy2(schematic, tmp_path / schematic.name)
    root = tmp_path / 'tms-v3.kicad_sch'
    before = schematic_digest(root)
    child = tmp_path / 'power-and-protection.kicad_sch'
    child.write_bytes(child.read_bytes() + b'\n')

    assert schematic_digest(root) != before


def test_passing_check_can_report_nonblocking_engineering_warning(project_copy):
    report = run_checks(load_project(project_copy), [AdvisoryCheck()])

    assert not report.blocking
    assert report.findings[0].kind == FindingKind.ENGINEERING_WARNING
    assert not report.findings[0].blocking
