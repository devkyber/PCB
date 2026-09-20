"""Native KiCad boundary for isolated placement drafts (never routes a board)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from pcb_copilot.toolchain import ToolchainPaths

_NATIVE = r"""
import json, sys
import pcbnew

request = json.load(sys.stdin)
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
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref in fps:
        raise RuntimeError('Duplicate footprint reference ' + ref)
    fps[ref] = {'lib_id': fp.GetFPIDAsString(), 'value': fp.GetValue(),
        'layer': fp.GetLayerName(),
        'rule_areas': sum(z.GetIsRuleArea() for z in fp.Zones()),
        'pads': [[p.GetNumber(), p.GetNetname()] for p in fp.Pads()]}
outline = pcbnew.SHAPE_POLY_SET()
if not board.GetBoardPolygonOutlines(outline, False):
    raise RuntimeError('Cannot obtain native board outline')
box = outline.BBox()
print('PCB_COPILOT_RESULT=' + json.dumps({'footprints': fps,
    'bounds': [pcbnew.ToMM(v) for v in (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())],
    'rectangular': (outline.OutlineCount() == 1 and outline.HoleCount(0) == 0
                    and abs(abs(outline.COutline(0).Area()) - box.GetWidth()*box.GetHeight()) < 1),
    'tracks': len(list(board.GetTracks())),
    'zones': sum(not z.GetIsRuleArea() for z in board.Zones()),
    'rule_areas': (sum(z.GetIsRuleArea() for z in board.Zones())
                   + sum(fp['rule_areas'] for fp in fps.values()))}))
"""


def native_board(
    toolchain: ToolchainPaths, pcb: Path, *, output=None, placements=None
) -> dict:
    """Read via pcbnew, optionally move footprints in a caller-owned draft copy."""
    if toolchain.kipython is None:
        raise ValueError("native KiCad Python is required for placement")
    result = subprocess.run(
        [str(toolchain.kipython), "-I", "-c", _NATIVE],
        input=json.dumps(
            {
                "pcb": str(pcb),
                "output": str(output) if output else None,
                "placements": placements or {},
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
    parts. Net normalization matches docs/check_netlist_parity.py: only leading
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
        parts[ref] = {
            "footprint": comp.findtext("footprint") or "",
            "pins": libraries[(source.get("lib"), source.get("part"))],
        }
    nets = {}
    for net in tree.findall("./nets/net"):
        name = (net.get("name") or "").lstrip("/")
        if not name or name.startswith("unconnected-("):
            continue
        members = {
            (node.get("ref"), node.get("pin"))
            for node in net.findall("node")
            if node.get("ref") in parts
        }
        if members:
            nets[name] = members
    return parts, nets
