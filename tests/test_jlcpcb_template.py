"""Exercise the actual KiCad rule engine, including silent custom-rule rejection."""

import json
import shutil
import subprocess

import pytest

from pcb_copilot.toolchain import discover_toolchain


@pytest.mark.slow
@pytest.mark.parametrize('bad_geometry', [False, True])
def test_template_rules_with_native_geometry(repo_root, tmp_path, bad_geometry):
    tools = discover_toolchain(repo_root)
    if tools.kipython is None:
        pytest.skip('KiCad Python is unavailable')
    template = repo_root / 'templates' / 'jlcpcb-2layer-1oz'
    board = tmp_path / 'sample.kicad_pcb'
    for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
        shutil.copy2(template / (template.name + suffix), board.with_suffix(suffix))
    script = '''
import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1])
bad = sys.argv[2] == 'True'
def point(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
edge = pcbnew.PCB_SHAPE(b)
edge.SetShape(pcbnew.SHAPE_T_RECT)
edge.SetStart(point(10, 10)); edge.SetEnd(point(100, 100))
edge.SetLayer(pcbnew.Edge_Cuts); edge.SetWidth(pcbnew.FromMM(.05)); b.Add(edge)
silk = pcbnew.PCB_SHAPE(b)
silk.SetShape(pcbnew.SHAPE_T_SEGMENT)
silk.SetStart(point(20, 20)); silk.SetEnd(point(25, 20))
silk.SetLayer(pcbnew.F_SilkS)
silk.SetWidth(pcbnew.FromMM(.12 if bad else .15)); b.Add(silk)
fp = pcbnew.FOOTPRINT(b); fp.SetReference('J1')
fp.SetAttributes(pcbnew.FP_THROUGH_HOLE); b.Add(fp)
fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
for number, x in enumerate([40, 41.2 if bad else 42.0], 1):
    p = pcbnew.PAD(fp); p.SetNumber(str(number))
    p.SetAttribute(pcbnew.PAD_ATTRIB_PTH); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    size = 1.3 if bad else 1.5
    p.SetSize(point(size, size)); p.SetDrillSize(point(.9, .9))
    p.SetLayerSet(pcbnew.PAD.PTHMask()); p.SetPosition(point(x, 40)); fp.Add(p)
p = pcbnew.PAD(fp); p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
diameter = .4 if bad else .5
p.SetSize(point(diameter, diameter)); p.SetDrillSize(point(diameter, diameter))
p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask()); p.SetPosition(point(50, 50)); fp.Add(p)
# A 0.15 mm via ring and 0.30 mm via-hole spacing must NOT receive PTH limits.
for x in [70, 70.6]:
    v = pcbnew.PCB_VIA(b); v.SetPosition(point(x, 70))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetWidth(pcbnew.FromMM(.6)); v.SetDrill(pcbnew.FromMM(.3)); b.Add(v)
pcbnew.SaveBoard(sys.argv[1], b)
'''
    subprocess.run([str(tools.kipython), '-c', script, str(board), str(bad_geometry)],
                   capture_output=True, text=True, check=True, timeout=30)
    output = tmp_path / 'drc.json'
    subprocess.run([str(tools.kicad_cli), 'pcb', 'drc', '--format', 'json',
                    '-o', str(output), str(board)],
                   capture_output=True, text=True, check=True, timeout=60)
    findings = json.loads(output.read_text(encoding='utf-8'))['violations']
    custom = [v for v in findings if "rule 'JLCPCB" in v['description']]
    if bad_geometry:
        expected = {'annular_width', 'hole_to_hole', 'drill_out_of_range', 'assertion_failure'}
        assert expected <= {v['type'] for v in custom}, findings
    else:
        assert not custom, findings
    assert not [v for v in custom for item in v['items']
                if item['description'].startswith('Via')], custom
