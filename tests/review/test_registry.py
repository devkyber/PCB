from dataclasses import dataclass

from pcb_copilot.project import load_project
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
