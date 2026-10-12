import json

import pytest
import yaml
from kicad_claude.adapters import sch_io
from sexpdata import loads

from pcb_copilot.cli import main
from pcb_copilot.project import load_project
from pcb_copilot.schematic.update import update_schematic


def copper_and_footprints(payload):
    """Schematic-only legacy migration may add links, never alter other objects."""
    tree = loads(payload.decode('utf-8'))
    for fp in sch_io.find_children(tree, 'footprint'):
        for path in sch_io.find_children(fp, 'path'):
            fp.remove(path)
    return tree


def test_preview_keeps_root_design_and_exposes_pdf(project_copy, capsys):
    schematic = project_copy / 'baro-bmp390.kicad_sch'
    before = schematic.read_bytes()

    code = main(['update-schematic', str(project_copy), '--intent',
                 str(project_copy / 'schematic-intent.yaml')])
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert schematic.read_bytes() == before
    assert (project_copy / '.pcb-copilot/preview/schematic.pdf').read_bytes().startswith(b'%PDF')
    assert result['applied'] is False
    assert not list((project_copy / '.pcb-copilot/drafts').glob('*'))
    # A drawing-only save has identical connectivity but is still owner CAD.
    schematic.write_bytes(before + b'\n')
    with pytest.raises(SystemExit) as error:
        main(['update-schematic', str(project_copy), '--intent',
              str(project_copy / 'schematic-intent.yaml'), '--apply'])
    assert error.value.code == 2
    assert 'run preview again against saved current CAD' in capsys.readouterr().err
    assert schematic.read_bytes() == before + b'\n'


def test_apply_updates_current_schematic_and_clears_candidate(project_copy, capsys):
    schematic = project_copy / 'baro-bmp390.kicad_sch'
    pcb = project_copy / 'baro-bmp390.kicad_pcb'
    old_schematic = schematic.read_bytes()
    old_pcb = pcb.read_bytes()
    owner_marker = project_copy / 'SCHEMATIC_OWNER'
    owner_marker.unlink(missing_ok=True)

    assert main(['update-schematic', str(project_copy), '--intent',
                 str(project_copy / 'schematic-intent.yaml')]) == 0
    capsys.readouterr()
    code = main(['update-schematic', str(project_copy), '--intent',
                 str(project_copy / 'schematic-intent.yaml'), '--apply'])
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result['applied'] is True
    assert result['lifecycle'] == 'DRAFT'
    assert schematic.read_bytes() != old_schematic
    assert copper_and_footprints(pcb.read_bytes()) == copper_and_footprints(old_pcb)
    assert any(item['code'] == 'layout.schematic_links_added' for item in result['findings'])
    assert not owner_marker.exists()
    assert not list((project_copy / '.pcb-copilot/drafts').glob('*'))
    assert not list((project_copy / '.pcb-copilot/acceptances').glob('*'))


def test_apply_blocks_schematic_pcb_net_mismatch(project_copy, capsys):
    schematic = project_copy / 'baro-bmp390.kicad_sch'
    pcb = project_copy / 'baro-bmp390.kicad_pcb'
    pcb.write_text(pcb.read_text(encoding='utf-8').replace('I2C_SDA', 'BROKEN_NET'),
                   encoding='utf-8')
    before = schematic.read_bytes()

    code = main(['update-schematic', str(project_copy), '--intent',
                 str(project_copy / 'schematic-intent.yaml')])
    result = json.loads(capsys.readouterr().out)

    assert code == 1
    assert result['applied'] is False
    assert schematic.read_bytes() == before
    assert any(finding['code'] == 'board-parity' for finding in result['findings'])
    with pytest.raises(SystemExit):
        main(['update-schematic', str(project_copy), '--intent',
              str(project_copy / 'schematic-intent.yaml'), '--apply'])
    assert schematic.read_bytes() == before


def test_reconcile_option_keeps_already_matching_board(project_copy, capsys):
    board = project_copy / 'baro-bmp390.kicad_pcb'
    before = board.read_bytes()

    assert main(['update-schematic', str(project_copy), '--intent',
                 str(project_copy / 'schematic-intent.yaml'), '--reconcile-board-names']) == 0
    capsys.readouterr()
    code = main(['update-schematic', str(project_copy), '--intent',
                 str(project_copy / 'schematic-intent.yaml'),
                 '--reconcile-board-names', '--apply'])
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result['applied'] is True
    assert result['renamed_nets'] == 0
    assert copper_and_footprints(board.read_bytes()) == copper_and_footprints(before)


@pytest.mark.parametrize('nested', [False, True])
def test_apply_circuit_change_installs_matching_schematic_and_pcb(project_copy, tmp_path, capsys, nested):
    intent = tmp_path / 'changed-intent.yaml'
    intent.write_text((project_copy / 'schematic-intent.yaml').read_text(encoding='utf-8')
                      .replace('I2C_SDA', 'NEW_SDA'), encoding='utf-8')
    candidate = tmp_path / 'changed.kicad_pcb'
    candidate.write_text((project_copy / 'baro-bmp390.kicad_pcb').read_text(encoding='utf-8')
                         .replace('I2C_SDA', 'NEW_SDA'), encoding='utf-8')
    pcb_name = 'baro-bmp390.kicad_pcb'
    if nested:
        (project_copy / 'cad').mkdir()
        for suffix in ('.kicad_pcb', '.kicad_pro'):
            source = project_copy / ('baro-bmp390' + suffix)
            source.rename(project_copy / 'cad' / source.name)
        pcb_name = 'cad/' + pcb_name
        manifest_path = project_copy / 'project.yaml'
        document = yaml.safe_load(manifest_path.read_text(encoding='utf-8'))
        document['design']['pcb'] = pcb_name
        manifest_path.write_text(yaml.safe_dump(document), encoding='utf-8')
    assert main(['update-schematic', str(project_copy), '--intent', str(intent),
                 '--pcb', str(candidate)]) == 0
    capsys.readouterr()
    code = main(['update-schematic', str(project_copy), '--intent', str(intent),
                 '--pcb', str(candidate), '--apply'])
    result = json.loads(capsys.readouterr().out)
    assert code == 0, result['findings']
    assert result['applied']
    for name in ('baro-bmp390.kicad_sch', pcb_name, 'netmap.json',
                 'schematic-intent.yaml'):
        text = (project_copy / name).read_text(encoding='utf-8')
        assert 'NEW_SDA' in text
        assert 'I2C_SDA' not in text


def test_paired_candidate_extension_is_not_silently_rewritten(project_copy, tmp_path):
    project = load_project(project_copy)
    wrong = tmp_path / 'candidate.txt'
    wrong.write_bytes(b'not a board')
    wrong.with_suffix('.kicad_pcb').write_bytes(project.pcb_path.read_bytes())
    with pytest.raises(ValueError, match='existing .kicad_pcb'):
        update_schematic(project, project.root / 'schematic-intent.yaml', False, pcb_candidate=wrong)
