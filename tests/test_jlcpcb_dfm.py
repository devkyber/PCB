"""The supplier baseline must survive weak or ignored project settings."""

import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from pcb_copilot.jlcpcb import check_jlcpcb
from pcb_copilot.toolchain import discover_toolchain


@pytest.mark.slow
@pytest.mark.parametrize('bad', [False, True])
def test_independent_native_baseline_preserves_sources(repo_root, tmp_path, bad):
    tools = discover_toolchain(repo_root)
    if tools.kipython is None:
        pytest.skip('KiCad Python unavailable')
    template = repo_root / 'templates/jlcpcb-2layer-1oz'
    pcb = tmp_path / 'sample.kicad_pcb'
    for suffix in ('.kicad_pcb', '.kicad_pro'):
        shutil.copy2(template / (template.name + suffix), pcb.with_suffix(suffix))
    settings = json.loads(pcb.with_suffix('.kicad_pro').read_text())
    design = settings['board']['design_settings']
    design['rules']['min_track_width'] = .05
    design['rule_severities']['track_width'] = 'ignore'
    design['rule_severities']['assertion_failure'] = 'ignore'
    pcb.with_suffix('.kicad_pro').write_text(json.dumps(settings))
    pcb.with_suffix('.kicad_dru').write_text('(version 1)\n')
    script = '''import pcbnew, sys
b=pcbnew.LoadBoard(sys.argv[1]); bad=sys.argv[2]=='True'
def pos(x,y): return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
e=pcbnew.PCB_SHAPE(b); e.SetShape(pcbnew.SHAPE_T_RECT)
e.SetStart(pos(10,10)); e.SetEnd(pos(100,100)); e.SetLayer(pcbnew.Edge_Cuts)
e.SetWidth(pcbnew.FromMM(.05)); b.Add(e)
t=pcbnew.PCB_TRACK(b); t.SetStart(pos(20,20)); t.SetEnd(pos(30,20))
t.SetWidth(pcbnew.FromMM(.08 if bad else .25)); t.SetLayer(pcbnew.F_Cu); b.Add(t)
s=pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
s.SetStart(pos(20,30)); s.SetEnd(pos(30,30)); s.SetLayer(pcbnew.F_SilkS)
s.SetWidth(pcbnew.FromMM(.12 if bad else .15)); b.Add(s)
pcbnew.SaveBoard(sys.argv[1],b,True)
'''
    subprocess.run([str(tools.kipython), '-I', '-c', script, str(pcb), str(bad)],
                   check=True, capture_output=True, timeout=30)
    sources = {p: p.read_bytes() for p in tmp_path.glob('sample.*')}
    result = check_jlcpcb(SimpleNamespace(pcb_path=pcb))
    assert result['passed'] is (not bad), result
    if bad:
        assert {'track_width', 'assertion_failure'} <= {e['type'] for e in result['errors']}
    assert {p: p.read_bytes() for p in sources} == sources
