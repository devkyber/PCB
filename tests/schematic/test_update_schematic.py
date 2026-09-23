import json

import pytest
import yaml

from pcb_copilot.cli import main


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


def test_apply_updates_current_schematic_and_clears_candidate(project_copy, capsys):
    schematic = project_copy / 'baro-bmp390.kicad_sch'
    pcb = project_copy / 'baro-bmp390.kicad_pcb'
    old_schematic = schematic.read_bytes()
    old_pcb = pcb.read_bytes()
    owner_marker = project_copy / 'SCHEMATIC_OWNER'
    owner_marker.unlink(missing_ok=True)

    code = main(['update-schematic', str(project_copy), '--intent',
                 str(project_copy / 'schematic-intent.yaml'), '--apply'])
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result['applied'] is True
    assert result['lifecycle'] == 'DRAFT'
    assert schematic.read_bytes() != old_schematic
    assert pcb.read_bytes() == old_pcb
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
                 str(project_copy / 'schematic-intent.yaml'), '--apply'])
    result = json.loads(capsys.readouterr().out)

    assert code == 1
    assert result['applied'] is False
    assert schematic.read_bytes() == before
    assert any(finding['code'] == 'board-parity' for finding in result['findings'])


def test_reconcile_option_keeps_already_matching_board(project_copy, capsys):
    board = project_copy / 'baro-bmp390.kicad_pcb'
    before = board.read_bytes()

    code = main(['update-schematic', str(project_copy), '--intent',
                 str(project_copy / 'schematic-intent.yaml'),
                 '--reconcile-board-names', '--apply'])
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result['applied'] is True
    assert result['renamed_nets'] == 0
    assert board.read_bytes() == before


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
