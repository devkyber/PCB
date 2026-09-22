import ast
import re
from pathlib import Path

import pytest

CANONICAL = (
    Path('README.md'),
    Path('docs/WORKFLOW.md'),
    Path('docs/ARCHITECTURE.md'),
    Path('docs/DESIGN_RULES.md'),
    Path('docs/LIMITATIONS.md'),
)
LINK_RE = re.compile(r'\[[^]]+\]\(([^)]+)\)')
BOARDS = ('baro-bmp390', 'imu-icm42688', 'gnss-neom9n', 'tms-v3')


def test_docs_directory_contains_only_reader_guides(repo_root):
    assert {path.name for path in (repo_root / 'docs').glob('*.md')} == {
        'WORKFLOW.md', 'ARCHITECTURE.md', 'DESIGN_RULES.md', 'LIMITATIONS.md',
    }
    for relative in CANONICAL:
        text = (repo_root / relative).read_text(encoding='utf-8')
        assert len(text.strip()) >= 200
        assert 'T' + 'BD' not in text
        assert 'T' + 'ODO' not in text


@pytest.mark.parametrize('document', CANONICAL)
def test_current_reader_links_resolve(repo_root, document):
    source = repo_root / document
    for target in LINK_RE.findall(source.read_text(encoding='utf-8')):
        path_text = target.split('#', 1)[0]
        if not path_text or '://' in path_text or path_text.startswith('mailto:'):
            continue
        destination = (source.parent / path_text).resolve()
        assert destination.is_relative_to(repo_root)
        assert destination.exists(), f'{document} links to missing {target}'
        assert '.pcb-copilot' not in destination.parts


def test_results_point_to_current_root_kicad_files(repo_root):
    readme = (repo_root / 'README.md').read_text(encoding='utf-8')
    for board in BOARDS:
        for extension in ('kicad_sch', 'kicad_pcb'):
            assert f'projects/{board}/{board}.{extension}' in readme
    assert '.pcb-copilot/drafts/' not in readme
    assert 'No board has' in readme and 'hash-bound human sign-off' in readme


def test_workflow_states_current_command_and_unfinished_boundaries(repo_root):
    workflow = (repo_root / 'docs/WORKFLOW.md').read_text(encoding='utf-8')
    normalized = ' '.join(workflow.split())
    assert 'pcb-copilot update-schematic' in workflow
    assert '--reconcile-board-names' in workflow
    assert 'root `.kicad_sch`' in workflow
    assert 'Do not copy an unrouted proposal over a routed current PCB.' in normalized
    assert 'pcb-copilot review projects/baro-bmp390' in workflow
    assert 'Relevant hash-bound human sign-off and transactional `release`' in normalized
    assert 'disposable repository' in workflow
    for removed in ('pcb-copilot draft-schematic', 'pcb-copilot review-draft',
                    'pcb-copilot accept '):
        assert removed not in workflow


def test_limitations_keep_human_level_and_safety_boundary(repo_root):
    limitations = (repo_root / 'docs/LIMITATIONS.md').read_text(encoding='utf-8')
    normalized = ' '.join(limitations.split())
    assert 'Not reliably or autonomously.' in limitations
    assert 'TMS V3' in limitations and 'Do not fabricate or energize' in normalized
    assert 'update-layout' in limitations and 'not yet implemented' in limitations


def test_canonical_rules_preserve_legacy_ids_and_exact_checker_scope(repo_root):
    legacy = (repo_root / 'migration/legacy-design-rules.md').read_text(encoding='utf-8')
    canonical = (repo_root / 'docs/DESIGN_RULES.md').read_text(encoding='utf-8')
    legacy_ids = set(re.findall(r'^### (\d+\.\d+) ', legacy, re.MULTILINE))
    rows = re.findall(r'^\| `(\d+\.\d+)` \| ([^|]+) \| (Partial|Human) \|$',
                      canonical, re.MULTILINE)
    assert len(rows) == len(legacy_ids)
    assert {rule for rule, _topic, _scope in rows} == legacy_ids
    checker = ast.parse((repo_root / 'scripts/check_design_rules.py').read_text(encoding='utf-8'))
    constants = {node.targets[0].id: ast.literal_eval(node.value)
                 for node in checker.body if isinstance(node, ast.Assign)
                 and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id in {'EXECUTABLE_RULES', 'DOC_RULE_COUNT'}}
    assert len(rows) == constants['DOC_RULE_COUNT']
    assert {rule for rule, _topic, scope in rows if scope == 'Partial'} == set(
        constants['EXECUTABLE_RULES'])
