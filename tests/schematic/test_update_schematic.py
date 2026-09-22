import json

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
