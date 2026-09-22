"""Review-only diagnostics for serialized power glyph clearance."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from kicad_claude.adapters import sch_editor as ed
from kicad_claude.adapters import sch_io
from kicad_claude.utils.geometry import mcp_to_kicad_xy

from pcb_copilot.drafts import create_draft
from pcb_copilot.evidence.checks import Finding
from pcb_copilot.models import DraftKind
from pcb_copilot.project import load_project
from pcb_copilot.schematic import preview as preview_module
from pcb_copilot.schematic.commands import draft_schematic
from pcb_copilot.schematic.hierarchy import HierarchyDraft
from pcb_copilot.schematic.io import load_schematic_intent
from pcb_copilot.schematic.power import power_clearance_findings
from pcb_copilot.schematic.preview import render_schematic_preview, schematic_files
from pcb_copilot.schematic.render import render_schematic_draft
from pcb_copilot.toolchain import ToolchainPaths


@pytest.fixture(scope='module')
def rendered_boards(tmp_path_factory):
    repo_root = Path(__file__).resolve().parents[2]
    base = tmp_path_factory.mktemp('power-diagnostics')
    rendered = {}
    for board in ('baro-bmp390', 'imu-icm42688', 'gnss-neom9n', 'tms-v3'):
        root = base / board
        shutil.copytree(
            repo_root / 'projects' / board,
            root,
            ignore=shutil.ignore_patterns('.pcb-copilot'),
        )
        project = load_project(root)
        intent = load_schematic_intent(root / 'schematic-intent.yaml')
        output = render_schematic_draft(
            project, intent, create_draft(project, DraftKind.SCHEMATIC)
        )
        schematic = output.root_schematic if isinstance(output, HierarchyDraft) else output
        rendered[board] = {
            'root': schematic,
            'files': {path.name: path for path in schematic_files(schematic)},
        }
    return rendered


def _rendered_tree(rendered_boards, board, filename=None):
    filename = filename or f'{board}.kicad_sch'
    return sch_io.parse_file(rendered_boards[board]['files'][filename])


@pytest.mark.parametrize('board,reference', [
    ('baro-bmp390', 'U1.'),
    ('imu-icm42688', 'U1.'),
    ('gnss-neom9n', 'U2.'),
])
def test_ic_power_spacing_clears_glyph_and_label_clashes(rendered_boards, board, reference):
    tree = _rendered_tree(rendered_boards, board)
    clashes = [finding for finding in power_clearance_findings(tree, f'{board}.kicad_sch')
               if finding.code in {'power-glyph-collision', 'power-text-collision'}
               and f'attached {reference}' in finding.message]
    assert clashes == []


@pytest.mark.parametrize('sheet,reference', [
    ('controller-and-telemetry.kicad_sch', 'J8.'),
    ('external-connectors-and-test.kicad_sch', 'J3.'),
])
def test_tms_connector_power_clears_hierarchical_labels(rendered_boards, sheet, reference):
    tree = _rendered_tree(rendered_boards, 'tms-v3', sheet)
    clashes = [finding for finding in power_clearance_findings(tree, sheet)
               if finding.code == 'power-text-collision'
               and f'attached {reference}' in finding.message]
    assert clashes == []


def test_same_net_power_glyph_pair_is_not_exempt(rendered_boards):
    tree = _rendered_tree(rendered_boards, 'baro-bmp390')
    first_x, _ = ed.get_pin_position(tree, '#PWR108', '1')
    second_x, second_y = ed.get_pin_position(tree, '#PWR109', '1')
    assert first_x != second_x
    ed.move_symbol(tree, '#PWR109', first_x, second_y, 0)
    symbol = ed.find_symbol_by_reference(tree, '#PWR109')
    value = next(prop for prop in ed.find_children(symbol, 'property')
                 if prop[1] == 'Value')
    value[2] = 'GND'

    findings = power_clearance_findings(tree, 'same-net.kicad_sch')

    assert any(finding.code == 'power-glyph-collision'
               and '#PWR108/GND' in finding.message
               and '#PWR109/GND' in finding.message
               for finding in findings)


def test_direct_wired_same_net_non_flag_glyphs_are_not_exempt(rendered_boards):
    tree = _rendered_tree(rendered_boards, 'baro-bmp390')
    refs = ('#PWR108', '#PWR109')
    first_x, _ = ed.get_pin_position(tree, refs[0], '1')
    _, second_y = ed.get_pin_position(tree, refs[1], '1')
    ed.move_symbol(tree, refs[1], first_x, second_y, 0)
    for ref in refs:
        symbol = ed.find_symbol_by_reference(tree, ref)
        value = next(prop for prop in ed.find_children(symbol, 'property')
                     if prop[1] == 'Value')
        value[2] = 'GND'
    page_height = ed.page_height_mm(tree)
    first = mcp_to_kicad_xy(*ed.get_pin_position(tree, refs[0], '1'), page_height)
    second = mcp_to_kicad_xy(*ed.get_pin_position(tree, refs[1], '1'), page_height)
    tree.append([
        sch_io.sym('wire'),
        [sch_io.sym('pts'),
         [sch_io.sym('xy'), *first],
         [sch_io.sym('xy'), *second]],
    ])
    before = deepcopy(tree)

    findings = power_clearance_findings(tree, 'direct-wired-same-net.kicad_sch')

    assert any(finding.code == 'power-glyph-collision'
               and '#PWR108/GND' in finding.message
               and '#PWR109/GND' in finding.message
               for finding in findings)
    assert tree == before


def test_exact_power_attachment_and_own_value_do_not_generate_noise(rendered_boards):
    tree = _rendered_tree(rendered_boards, 'gnss-neom9n')

    findings = power_clearance_findings(tree, 'gnss-neom9n.kicad_sch')

    assert not any('#FLG02' in finding.message and '#PWR122' in finding.message
                   for finding in findings)
    assert not any(
        finding.code == 'power-text-collision'
        and finding.reference is not None
        and f'power Value {finding.reference}' in finding.message
        for finding in findings
    )


def test_clear_single_power_glyph_has_no_collision(rendered_boards):
    tree = _rendered_tree(rendered_boards, 'baro-bmp390')
    for symbol in list(ed.iter_instance_symbols(tree)):
        ref = ed.get_symbol_property(symbol, 'Reference') or ''
        if ref.startswith('#') and ref != '#PWR101':
            tree.remove(symbol)

    findings = power_clearance_findings(tree, 'clear.kicad_sch')

    assert not any(finding.code in {'power-glyph-collision', 'power-text-collision'}
                   for finding in findings)


def test_unsupported_rotation_is_advisory_and_tree_is_unchanged(rendered_boards):
    tree = _rendered_tree(rendered_boards, 'baro-bmp390')
    for symbol in list(ed.iter_instance_symbols(tree)):
        ref = ed.get_symbol_property(symbol, 'Reference') or ''
        if ref.startswith('#') and ref != '#PWR101':
            tree.remove(symbol)
    ed.find_child(ed.find_symbol_by_reference(tree, '#PWR101'), 'at')[3] = 90
    before = deepcopy(tree)

    findings = power_clearance_findings(tree, 'rotated.kicad_sch')

    assert any(finding.code == 'power-clearance-unchecked'
               and finding.reference == '#PWR101'
               and finding.severity == 'review'
               for finding in findings)
    assert not any(finding.code.endswith('-collision') for finding in findings)
    assert tree == before


@pytest.mark.parametrize('axis', ['x', 'y'])
def test_mirrored_power_glyph_is_unchecked_and_tree_is_unchanged(
    rendered_boards, axis
):
    tree = _rendered_tree(rendered_boards, 'baro-bmp390')
    for symbol in list(ed.iter_instance_symbols(tree)):
        ref = ed.get_symbol_property(symbol, 'Reference') or ''
        if ref.startswith('#') and ref != '#PWR101':
            tree.remove(symbol)
    symbol = ed.find_symbol_by_reference(tree, '#PWR101')
    symbol.append([sch_io.sym('mirror'), sch_io.sym(axis)])
    before = deepcopy(tree)

    findings = power_clearance_findings(tree, f'mirrored-{axis}.kicad_sch')

    assert any(finding.code == 'power-clearance-unchecked'
               and finding.reference == '#PWR101'
               and f'mirror {axis}' in finding.message
               for finding in findings)
    assert not any(finding.code.endswith('-collision') for finding in findings)
    assert tree == before


def test_unsupported_glyph_geometry_is_advisory(rendered_boards):
    tree = _rendered_tree(rendered_boards, 'baro-bmp390')
    symbol = ed.find_symbol_by_reference(tree, '#PWR101')
    definition = ed.find_lib_symbol_def(tree, ed.find_child(symbol, 'lib_id')[1])
    ed.find_children(definition, 'symbol')[0].append([sch_io.sym('arc')])

    findings = power_clearance_findings(tree, 'unsupported.kicad_sch')

    assert any(finding.code == 'power-clearance-unchecked'
               and finding.reference == '#PWR101'
               and 'arc' in finding.message
               for finding in findings)


def test_findings_are_stable_unique_and_read_only(rendered_boards):
    tree = _rendered_tree(rendered_boards, 'baro-bmp390')
    before = deepcopy(tree)

    first = power_clearance_findings(tree, 'baro-bmp390.kicad_sch')
    second = power_clearance_findings(tree, 'baro-bmp390.kicad_sch')

    assert first == second
    assert len(first) == len({(item.code, item.message, item.reference)
                              for item in first})
    assert tree == before


def test_preview_diagnostic_hook_is_not_skipped(
    rendered_boards, tmp_path, monkeypatch
):
    injected = Finding(
        'power-clearance-fault-injection',
        'checker hook reached',
        severity='review',
    )
    monkeypatch.setattr(
        preview_module,
        'power_clearance_findings_for_file',
        lambda _path: (injected,),
    )

    result = render_schematic_preview(
        ToolchainPaths(tmp_path / 'missing-kicad-cli', None, ()),
        rendered_boards['baro-bmp390']['root'],
        tmp_path / 'fault-injection-preview',
    )

    assert injected in result.findings


@pytest.mark.slow
def test_power_clearance_review_is_persisted_for_generated_bmp(repo_root, tmp_path):
    root = tmp_path / 'baro-bmp390'
    shutil.copytree(
        repo_root / 'projects' / 'baro-bmp390',
        root,
        ignore=shutil.ignore_patterns('.pcb-copilot'),
    )
    project = load_project(root)

    report = draft_schematic(project, root / 'schematic-intent.yaml')
    persisted = json.loads((root / '.pcb-copilot' / 'drafts' / report['draft_id']
                            / 'review.json').read_text(encoding='utf-8'))

    assert not any(finding['code'] == 'power-glyph-collision'
                   for finding in report['findings'])
    assert persisted['findings'] == report['findings']
