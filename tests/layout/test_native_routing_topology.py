import subprocess
from types import SimpleNamespace

from pcb_copilot.review.routing_topology import read_geometry


def test_native_contacts_use_rotated_pad_shape_and_copper_layer(tmp_path, kipython):
    pcb = tmp_path / 'contacts.kicad_pcb'
    subprocess.run([str(kipython), '-I', '-c', '''
import pcbnew, sys
b = pcbnew.BOARD()
net = pcbnew.NETINFO_ITEM(b, 'PWM'); b.Add(net)
def vec(x, y): return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
fp = pcbnew.FOOTPRINT(b); fp.SetReference('J1'); b.Add(fp)
p = pcbnew.PAD(fp); p.SetNumber('1'); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
p.SetShape(pcbnew.PAD_SHAPE_RECT); p.SetSize(vec(4, 1)); p.SetPosition(vec(10, 10))
layers = pcbnew.LSET(); layers.AddLayer(pcbnew.F_Cu)
p.SetOrientationDegrees(90); p.SetLayerSet(layers); p.SetNet(net); fp.Add(p)
for start, end, layer in [((10.4, 11), (12, 11), pcbnew.F_Cu),
                          ((11, 10), (12, 10), pcbnew.F_Cu),
                          ((9, 10), (10, 10), pcbnew.B_Cu)]:
    t = pcbnew.PCB_TRACK(b); t.SetStart(vec(*start)); t.SetEnd(vec(*end))
    t.SetWidth(pcbnew.FromMM(.2)); t.SetLayer(layer); t.SetNet(net); b.Add(t)
pcbnew.SaveBoard(sys.argv[1], b, True)
''', str(pcb)], check=True, capture_output=True, text=True, timeout=30)
    saved = pcb.read_bytes()
    geometry = read_geometry(pcb, SimpleNamespace(kipython=kipython))
    assert pcb.read_bytes() == saved
    assert len(geometry['tracks']) == 3
    assert len(geometry['pad_contacts']) == 1
    contact = geometry['pad_contacts'][0]
    assert contact['ref'] == 'J1' and contact['pad'] == '1'
    assert contact['center'] == [10, 10] and contact['layer'] == 'F.Cu'
    hit = next(t for t in geometry['tracks'] if t['start'] == [10.4, 11])
    assert contact['tracks'] == [hit['id']]
