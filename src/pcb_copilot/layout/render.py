"""Native KiCad boundary for isolated placement drafts (never routes a board)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from pcb_copilot.layout.schematic_links import component_paths
from pcb_copilot.toolchain import ToolchainPaths

_NATIVE = r"""
import json, sys
import pcbnew

request = json.load(sys.stdin)
if (not request.get('require_outline', True) or request.get('allow_duplicate_references')) and request.get('output'):
    raise RuntimeError('Repair baseline inspection is read-only')
board = pcbnew.LoadBoard(request['pcb'])
if request.get('output'):
    tracks = board.GetTracks()
    for item in list(tracks):
        board.Remove(item)
    zones = board.Zones()
    for zone in list(zones):
        if not zone.GetIsRuleArea():
            board.Remove(zone)
    for ref, placement in request['placements'].items():
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            path = placement['path']
            from pathlib import Path
            fp = pcbnew.FootprintLoad(str(Path(path).parent), Path(path).stem)
            if fp is None:
                raise RuntimeError('Cannot load footprint for ' + ref)
            fp.SetReference(ref)
            fp.SetFPID(pcbnew.LIB_ID(*placement['lib_id'].split(':', 1)))
            board.Add(fp)
        fp.SetOrientationDegrees(placement['rotation'])
        fp.SetPosition(pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in placement['position'])))
    pcbnew.SaveBoard(request['output'], board, True)

fps = {}
duplicate_references = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref in fps:
        if not request.get('allow_duplicate_references'):
            raise RuntimeError('Duplicate footprint reference ' + ref)
        duplicate_references.append(ref)
        ref = ref + '@' + fp.m_Uuid.AsString()
    fps[ref] = {'uuid': fp.m_Uuid.AsString(), 'lib_id': fp.GetFPIDAsString(), 'value': fp.GetValue(),
        'schematic_path': fp.GetPath().AsString(),
        'lcsc': next((fp.GetFieldText(key).strip() for key in
                     ('LCSC Part', 'LCSC', 'LCSC Part #', 'JLCPCB', 'JLCPCB Part')
                     if fp.HasField(key) and fp.GetFieldText(key).strip()), ''),
        'layer': fp.GetLayerName(),
        'rule_areas': sum(z.GetIsRuleArea() for z in fp.Zones()),
        'pads': [[p.GetNumber(), p.GetNetname()] for p in fp.Pads()]}
outline = pcbnew.SHAPE_POLY_SET()
outline_error = None
bounds = rectangular = None
if not board.GetBoardPolygonOutlines(outline, False) or outline.OutlineCount() == 0:
    outline_error = 'Cannot obtain native board outline'
    if request.get('require_outline', True):
        raise RuntimeError(outline_error)
else:
    box = outline.BBox()
    bounds = [pcbnew.ToMM(v) for v in (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())]
    rectangular = (outline.OutlineCount() == 1 and outline.HoleCount(0) == 0
                   and abs(abs(outline.COutline(0).Area()) - box.GetWidth()*box.GetHeight()) < 1)
print('PCB_COPILOT_RESULT=' + json.dumps({'footprints': fps,
    'duplicate_references': duplicate_references,
    'bounds': bounds, 'rectangular': rectangular, 'outline_error': outline_error,
    'tracks': len(list(board.GetTracks())),
    'zones': sum(not z.GetIsRuleArea() for z in board.Zones()),
    'rule_areas': (sum(z.GetIsRuleArea() for z in board.Zones())
                   + sum(fp['rule_areas'] for fp in fps.values()))}))
"""


def native_board(
    toolchain: ToolchainPaths, pcb: Path, *, output=None, placements=None,
    require_outline: bool = True, allow_duplicate_references: bool = False,
) -> dict:
    """Read via pcbnew, optionally move footprints in a caller-owned draft copy.

    A read-only repair baseline may lack an outline, but retains its complete
    inventory. Duplicate references can be retained by UUID only for read-only
    repair baselines. Draft writes and finished candidates remain strict.
    """
    if (not require_outline or allow_duplicate_references) and output is not None:
        raise ValueError('repair baseline inspection is read-only')
    if toolchain.kipython is None:
        raise ValueError("native KiCad Python is required for placement")
    result = subprocess.run(
        [str(toolchain.kipython), "-I", "-c", _NATIVE],
        input=json.dumps(
            {
                "pcb": str(pcb),
                "output": str(output) if output else None,
                "placements": placements or {},
                "require_outline": require_outline,
                "allow_duplicate_references": allow_duplicate_references,
            }
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode:
        raise ValueError(
            f"native PCB operation failed: {result.stderr or result.stdout}"
        )
    return json.loads(
        next(
            line.removeprefix("PCB_COPILOT_RESULT=")
            for line in result.stdout.splitlines()
            if line.startswith("PCB_COPILOT_RESULT=")
        )
    )


def schematic_inventory(
    toolchain: ToolchainPaths, schematic: Path
) -> tuple[dict, dict]:
    """Export physical parts, complete symbol pins and connected nets from KiCad.

    Components come from the native component list, including wholly disconnected
    parts. Net normalization matches pcb_copilot.schematic.netmap: only leading
    slashes are removed; deeper sheet paths remain distinct.
    """
    with tempfile.TemporaryDirectory(prefix="pcb-layout-netlist-") as directory:
        output = Path(directory) / "accepted.xml"
        subprocess.run(
            [
                str(toolchain.kicad_cli),
                "sch",
                "export",
                "netlist",
                "--format",
                "kicadxml",
                "-o",
                str(output),
                str(schematic),
            ],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        tree = ET.parse(output)
    libraries = {
        (part.get("lib"), part.get("part")): {
            pin.get("num") for pin in part.findall("pins/pin")
        }
        for part in tree.findall("./libparts/libpart")
    }
    parts = {}
    for comp in tree.findall("./components/comp"):
        ref = comp.get("ref")
        if not ref or ref.startswith("#"):
            continue
        if any(p.get("name") == "exclude_from_board" for p in comp.findall("property")):
            continue
        source = comp.find("libsource")
        if source is None:
            raise ValueError(f"{ref}: native netlist has no symbol identity")
        if ref in parts:
            raise ValueError(f"duplicate physical symbol reference {ref}")
        parts[ref] = {
            "schematic_paths": component_paths(comp),
            "footprint": comp.findtext("footprint") or "",
            "value": comp.findtext("value") or "",
            "lcsc": next(((field.text or '').strip() for field in comp.findall('fields/field')
                          if field.get('name') in {'LCSC Part', 'LCSC', 'LCSC Part #', 'JLCPCB', 'JLCPCB Part'}
                          and (field.text or '').strip()), ''),
            "pins": libraries[(source.get("lib"), source.get("part"))],
        }
    nets = {}
    for net in tree.findall("./nets/net"):
        name = (net.get("name") or "").lstrip("/")
        if not name:
            continue
        nodes = net.findall('node')
        members = {
            (node.get("ref"), node.get("pin"))
            for node in nodes
            if node.get("ref") in parts
        }
        if (name.startswith('unconnected-(') and len(nodes) == 1 and len(members) == 1
                and 'no_connect' in (nodes[0].get('pintype') or '').split('+')):
            ref, pin = next(iter(members))
            parts[ref].setdefault('no_connects', {})[pin] = name
            continue
        if members:
            nets[name] = members
    return parts, nets


def board_pin_nets(footprints: dict, parts: dict | None = None) -> dict:
    """Normalize only native, explicitly unconnected single-pad nets.

    F8 assigns placeholder net names to X-marked pins. Ignoring every net with
    that prefix could hide a real extra connection: require the exact exported
    name, pin and singleton membership before omitting it from circuit parity.
    Without schematic parts this returns the full board membership unchanged.
    """
    nets = {}
    for ref, footprint in footprints.items():
        for pin, name in footprint['pads']:
            if name:
                nets.setdefault(name.lstrip('/'), set()).add((ref, pin))
    for ref, part in (parts or {}).items():
        for pin, name in part.get('no_connects', {}).items():
            if nets.get(name) == {(ref, pin)}:
                del nets[name]
    return nets
