"""Bridge to KiCAD's bundled Python interpreter for `pcbnew` API access.

KiCAD ships its own Python 3.9 with the `pcbnew` SWIG bindings. The host
Python (this MCP server, 3.10+) cannot import `pcbnew` directly because the
bindings are compiled for KiCAD's exact Python version. Instead we shell out
to KiCAD's Python and run a tiny script.

This is the only way (without IPC API in KiCAD 11) to use KiCAD's native
Specctra DSN export and SES import — `kicad-cli` v10 doesn't expose them.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("kicad-claude.adapters.kicad_python")


class KicadPythonError(RuntimeError):
    """KiCAD's bundled Python failed (not found, returned non-zero, etc.)."""


def find_kicad_python() -> Path | None:
    """Locate KiCAD's bundled Python interpreter.

    Resolution order:
    1. KICAD_PYTHON env override
    2. macOS: /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/.../bin/python3.X
    3. Linux: /usr/lib/kicad/bin/python3 (rare; most distros use system Python)
    4. Windows: %ProgramFiles%\\KiCad\\<ver>\\bin\\python.exe
    """
    override = os.environ.get("KICAD_PYTHON")
    if override and Path(override).is_file():
        return Path(override)

    sys_name = platform.system()
    if sys_name == "Darwin":
        framework = Path("/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions")
        if framework.is_dir():
            # Prefer "Current" symlink, else newest 3.x.
            current = framework / "Current" / "bin" / "python3"
            if current.is_file():
                return current
            for ver_dir in sorted(framework.iterdir(), reverse=True):
                if not ver_dir.is_dir():
                    continue
                p = ver_dir / "bin" / "python3"
                if p.is_file():
                    return p

    if sys_name == "Linux":
        candidate = Path("/usr/lib/kicad/bin/python3")
        if candidate.is_file():
            return candidate
        # Fallback to system python with pcbnew available.
        sys_python = shutil.which("python3")
        if sys_python:
            return Path(sys_python)

    if sys_name == "Windows":
        for ver in ("10", "9", "8"):
            cand = Path(rf"C:\Program Files\KiCad\{ver}\bin\python.exe")
            if cand.is_file():
                return cand

    return None


def _ensure_python() -> Path:
    p = find_kicad_python()
    if p is None:
        raise KicadPythonError(
            "couldn't find KiCAD's bundled Python (no `pcbnew` available). "
            "Set KICAD_PYTHON in .env to override."
        )
    return p


def _run_pcbnew_script(script: str, *args: str, timeout: float = 60.0) -> str:
    """Run `script` against KiCAD's Python; return stdout. Raises on failure."""
    py = _ensure_python()
    try:
        r = subprocess.run(
            [str(py), "-c", script, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise KicadPythonError(f"pcbnew script timed out after {timeout}s") from e
    if r.returncode != 0:
        raise KicadPythonError(
            f"pcbnew script failed (rc={r.returncode}): "
            f"stdout={r.stdout[-300:]} stderr={r.stderr[-300:]}"
        )
    return r.stdout


# --------------------------------------------------------------------------- #
# Public functions
# --------------------------------------------------------------------------- #

_EXPORT_DSN_SCRIPT = """
import sys, os
import pcbnew
pcb_path, dsn_path = sys.argv[1], sys.argv[2]
board = pcbnew.LoadBoard(pcb_path)
if not board:
    print("LoadBoard returned None", file=sys.stderr); sys.exit(1)
ok = pcbnew.ExportSpecctraDSN(board, dsn_path)
print("EXPORT_OK" if ok else "EXPORT_FAIL")
sys.exit(0 if ok else 1)
"""


_IMPORT_SES_SCRIPT = """
import sys, os
import pcbnew
pcb_path, ses_path = sys.argv[1], sys.argv[2]
board = pcbnew.LoadBoard(pcb_path)
if not board:
    print("LoadBoard returned None", file=sys.stderr); sys.exit(1)
ok = pcbnew.ImportSpecctraSES(board, ses_path)
if not ok:
    print("ImportSpecctraSES returned False", file=sys.stderr); sys.exit(1)
saved = pcbnew.SaveBoard(pcb_path, board)
print("IMPORT_OK" if saved else "IMPORT_FAIL")
sys.exit(0 if saved else 1)
"""


def export_dsn(pcb_path: Path, dsn_path: Path, timeout: float = 60.0) -> Path:
    """Export the .kicad_pcb to Specctra DSN at `dsn_path`.

    Uses KiCAD's bundled Python (`pcbnew.ExportSpecctraDSN`).
    """
    pcb_path = Path(pcb_path).expanduser().resolve()
    dsn_path = Path(dsn_path).expanduser().resolve()
    if not pcb_path.is_file():
        raise FileNotFoundError(pcb_path)
    out = _run_pcbnew_script(
        _EXPORT_DSN_SCRIPT, str(pcb_path), str(dsn_path), timeout=timeout
    )
    if not dsn_path.is_file():
        raise KicadPythonError(
            f"DSN file not produced at {dsn_path}; pcbnew said: {out.strip()}"
        )
    return dsn_path


def import_ses(pcb_path: Path, ses_path: Path, timeout: float = 60.0) -> Path:
    """Apply a Freerouting .ses session back into the .kicad_pcb (in-place)."""
    pcb_path = Path(pcb_path).expanduser().resolve()
    ses_path = Path(ses_path).expanduser().resolve()
    if not pcb_path.is_file():
        raise FileNotFoundError(pcb_path)
    if not ses_path.is_file():
        raise FileNotFoundError(ses_path)
    _run_pcbnew_script(
        _IMPORT_SES_SCRIPT, str(pcb_path), str(ses_path), timeout=timeout
    )
    return pcb_path


# --------------------------------------------------------------------------- #
# Apply netlist to PCB (poor man's "Update PCB from Schematic")
# --------------------------------------------------------------------------- #

_APPLY_NETLIST_SCRIPT = r"""
import sys
import json
import xml.etree.ElementTree as ET
import pcbnew

pcb_path = sys.argv[1]
xml_path = sys.argv[2]

# Parse the kicadxml netlist: ref -> {pin -> net_name}
tree = ET.parse(xml_path)
root = tree.getroot()
ref_to_pad_nets = {}
all_nets = set()
for net in root.findall("nets/net"):
    net_name = net.get("name") or ""
    if not net_name:
        continue
    all_nets.add(net_name)
    for node in net.findall("node"):
        ref = node.get("ref")
        pin = node.get("pin")
        if ref and pin:
            ref_to_pad_nets.setdefault(ref, {})[pin] = net_name

# Load the board
board = pcbnew.LoadBoard(pcb_path)

# Make sure every net from the schematic exists on the board.
# `board.FindNet(name)` returns the NETINFO_ITEM or None — that's the
# easiest existence check. SWIG's NETNAMES_MAP isn't a real dict.
added_nets = 0
for net_name in sorted(all_nets):
    if board.FindNet(net_name) is None:
        ni = pcbnew.NETINFO_ITEM(board, net_name)
        board.Add(ni)
        added_nets += 1

# Walk footprints and update pad net assignments
fps = list(board.GetFootprints())
schematic_refs = set(ref_to_pad_nets.keys())
pcb_refs = {fp.GetReference() for fp in fps}
missing_in_pcb = sorted(schematic_refs - pcb_refs)

pad_changes = 0
matched = 0
for fp in fps:
    ref = fp.GetReference()
    if ref not in ref_to_pad_nets:
        continue
    matched += 1
    pad_nets = ref_to_pad_nets[ref]
    for pad in fp.Pads():
        num = pad.GetNumber()
        if num in pad_nets:
            net_obj = board.FindNet(pad_nets[num])
            if net_obj is not None:
                pad.SetNet(net_obj)
                pad_changes += 1

pcbnew.SaveBoard(pcb_path, board)

result = {
    "added_nets": added_nets,
    "matched_footprints": matched,
    "missing_in_pcb": missing_in_pcb,
    "pad_assignments_made": pad_changes,
    "schematic_references": len(schematic_refs),
    "pcb_references": len(pcb_refs),
    "schematic_nets": len(all_nets),
}
print("RESULT_JSON:" + json.dumps(result))
"""


def apply_netlist(pcb_path: Path, netlist_xml_path: Path, timeout: float = 90.0) -> dict:
    """Apply a kicadxml netlist to the PCB: assign nets to pads, add missing nets.

    The netlist must be in `kicadxml` format (use `export_netlist(format="kicadxml")`
    to produce it). Footprints in the schematic that aren't on the PCB are
    listed as `missing_in_pcb` — call `add_footprint` for each, then re-run.
    """
    pcb_path = Path(pcb_path).expanduser().resolve()
    netlist_xml_path = Path(netlist_xml_path).expanduser().resolve()
    if not pcb_path.is_file():
        raise FileNotFoundError(pcb_path)
    if not netlist_xml_path.is_file():
        raise FileNotFoundError(netlist_xml_path)

    out = _run_pcbnew_script(
        _APPLY_NETLIST_SCRIPT, str(pcb_path), str(netlist_xml_path), timeout=timeout
    )
    # Parse the trailing RESULT_JSON: line.
    result_line = next(
        (line for line in reversed(out.splitlines()) if line.startswith("RESULT_JSON:")),
        None,
    )
    if result_line is None:
        raise KicadPythonError(f"apply_netlist script produced no result: {out[-300:]}")
    import json
    return json.loads(result_line[len("RESULT_JSON:"):])


# --------------------------------------------------------------------------- #
# Zone fill + ground bonding
# --------------------------------------------------------------------------- #
#
# Why these live here rather than in a one-off script:
#
# 1. `kicad-cli pcb drc` does NOT fill zones. On a board with a ground pour an
#    unfilled DRC reports every pour-dependent pad as unconnected, which is
#    pure noise. Zones must be filled between routing and DRC, every time.
#
# 2. Autorouting a board with pours fragments those pours: the router carves
#    traces through the copper and leaves islands. An island that no via
#    reaches is a floating piece of copper, and KiCAD reports it as an
#    unconnected GND item. Freerouting will never fix this — it treats the
#    pour as an obstacle, not as a net it owns. Bonding is our job, and it is
#    a mechanical, geometric job, so it belongs in the pipeline rather than in
#    a human's hands.

_FILL_ZONES_SCRIPT = """
import sys
import pcbnew
pcb_path = sys.argv[1]
board = pcbnew.LoadBoard(pcb_path)
ok = pcbnew.ZONE_FILLER(board).Fill(board.Zones())
if not ok:
    print("ZONE_FILLER.Fill returned False", file=sys.stderr); sys.exit(1)
pcbnew.SaveBoard(pcb_path, board)
print("FILL_OK")
"""


_GROUND_BOND_SCRIPT = r"""
import sys, json, math
import pcbnew

IU = 1000000.0
pcb_path, net_name, cfg_json = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = json.loads(cfg_json)

DRILL = float(cfg.get("via_drill_mm", 0.3))
PAD = float(cfg.get("via_pad_mm", 0.6))
CLR = float(cfg.get("clearance_mm", 0.2))
TW = float(cfg.get("trace_width_mm", 0.25))
MAX_ESCAPE = float(cfg.get("max_escape_mm", 2.0))
targets = cfg.get("escape_targets") or []

board = pcbnew.LoadBoard(pcb_path)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())

net = board.FindNet(net_name)
if net is None:
    print("RESULT_JSON:" + json.dumps({"error": "net not found: " + net_name}))
    sys.exit(0)
nc = net.GetNetCode()

R = int((PAD / 2 + CLR) * IU)
MIN_SEP = int((PAD + CLR) * IU)
clr_iu = int(CLR * IU)

layer_zones = {}
for z in board.Zones():
    if z.GetNetname() != net_name:
        continue
    for lid in z.GetLayerSet().Seq():
        layer_zones.setdefault(lid, []).append(z)


def pour(lid):
    sps = pcbnew.SHAPE_POLY_SET()
    for z in layer_zones.get(lid, []):
        src = z.GetFilledPolysList(lid)
        for i in range(src.OutlineCount()):
            sps.AddOutline(src.Outline(i))
    return sps


pours = dict((lid, pour(lid)) for lid in layer_zones)
lids = list(layer_zones)


def circle_in(sps, x, y, r):
    # A via pad fits only if the whole pad footprint plus clearance is inside
    # the pour. Nine sample points is enough for pour geometry, which never
    # has features finer than the fill's own minimum thickness.
    for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r),
                   (int(r * .71), int(r * .71)), (int(-r * .71), int(r * .71)),
                   (int(r * .71), int(-r * .71)), (int(-r * .71), int(-r * .71))):
        if not sps.Contains(pcbnew.VECTOR2I(x + dx, y + dy)):
            return False
    return True


# Pads whose own clearance rule is WIDER than the flat CLR this pass assumes.
# CLR is a constant, and a constant is wrong the moment a footprint overrides
# it: KiCad's stock Fiducial_1mm_Mask3mm carries a 1.1mm local pad clearance
# so no copper creeps near the optical target — 5.5x the 0.2mm assumed here.
# Filling a pour and then dropping a bonding via "inside the pour" is not
# sufficient, because the pour's own knockout is computed from the ZONE's
# clearance, not the pad's. That put two GND vias 1.0mm and 1.58mm from a
# fiducial needing 1.9mm centre-to-centre, for 6 DRC errors on a board that
# was otherwise clean. docs/stitch_vias.py fixed exactly this in its own
# pass; this is the same defect in the bonding pass.
keepaway = []
for _fp in board.GetFootprints():
    for _pad in _fp.Pads():
        try:
            _own = _pad.GetOwnClearance(_pad.GetLayer())
        except Exception:
            _own = 0
        if not _own or _own <= int(CLR * IU):
            continue
        _pp = _pad.GetPosition()
        _sz = max(_pad.GetSize().x, _pad.GetSize().y)
        keepaway.append((_pp.x, _pp.y, int(_sz / 2 + _own + PAD / 2 * IU)))


def clear_of_pads(x, y):
    # True when a via at (x, y) respects every over-clearance pad.
    for px, py, r in keepaway:
        if (x - px) ** 2 + (y - py) ** 2 < r * r:
            return False
    return True


existing = [(t.GetPosition().x, t.GetPosition().y)
            for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]

report = {"islands": {}, "stitch_vias": [], "unstitchable": [],
          "escapes": [], "unescapable": []}


def add_via(x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(x, y))
    v.SetDrill(int(DRILL * IU))
    v.SetWidth(int(PAD * IU))
    v.SetNetCode(nc)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(v)
    existing.append((x, y))
    return v


# --- Pass 1: stitch pour islands to the opposite layer ---------------------- #
# An island that already contains a via is connected to the other layer and
# needs nothing. An island with no via is floating copper.
for lid in lids:
    others = [l for l in lids if l != lid]
    if not others:
        continue
    opp = pours[others[0]]
    src = pours[lid]
    lname = board.GetLayerName(lid)
    report["islands"][lname] = src.OutlineCount()
    for i in range(src.OutlineCount()):
        outline = src.Outline(i)
        one = pcbnew.SHAPE_POLY_SET()
        one.AddOutline(outline)
        if any(one.Contains(pcbnew.VECTOR2I(px, py)) for px, py in existing):
            continue
        bb = outline.BBox()
        cx = (bb.GetLeft() + bb.GetRight()) // 2
        cy = (bb.GetTop() + bb.GetBottom()) // 2
        step = int(0.2 * IU)
        best = None
        y = bb.GetTop()
        while y <= bb.GetBottom():
            x = bb.GetLeft()
            while x <= bb.GetRight():
                if (circle_in(one, x, y, R) and circle_in(opp, x, y, R)
                        and clear_of_pads(x, y)
                        and all((x - px) ** 2 + (y - py) ** 2 >= MIN_SEP ** 2
                                for px, py in existing)):
                    d = (x - cx) ** 2 + (y - cy) ** 2
                    if best is None or d < best[0]:
                        best = (d, x, y)
                x += step
            y += step
        if best is None:
            report["unstitchable"].append({
                "layer": lname, "island": i,
                "area_mm2": round(abs(outline.Area()) / 1e12, 3),
                "near_mm": [round(cx / IU, 2), round(cy / IU, 2)],
            })
            continue
        add_via(best[1], best[2])
        report["stitch_vias"].append({
            "layer": lname,
            "x_mm": round(best[1] / IU, 3), "y_mm": round(best[2] / IU, 3),
        })

# --- Pass 2: escape isolated pads to the opposite-layer pour ---------------- #
# Only attempted within MAX_ESCAPE mm. A longer stub is worse than an honest
# report: it means routing the pad properly, not stapling a wire across the
# board.
if targets:
    obstacles = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() != nc and p.IsOnLayer(pcbnew.F_Cu):
                obstacles.append(p.GetEffectiveShape(pcbnew.F_Cu))
    for t in board.GetTracks():
        if t.GetNetCode() != nc and t.IsOnLayer(pcbnew.F_Cu):
            obstacles.append(t.GetEffectiveShape(pcbnew.F_Cu))
    added_circles = []   # (x, y, radius) for vias we place in this pass

    for tgt in targets:
        ref, padnum = tgt[0], str(tgt[1])
        fp = None
        for f in board.GetFootprints():
            if f.GetReference() == ref:
                fp = f
                break
        pad = None
        if fp is not None:
            for p in fp.Pads():
                if p.GetNumber() == padnum:
                    pad = p
                    break
        if pad is None:
            report["unescapable"].append({"ref": ref, "pad": padnum,
                                          "reason": "pad not found"})
            continue
        P = pad.GetPosition()
        opp = pours.get(pcbnew.B_Cu)
        if opp is None:
            report["unescapable"].append({"ref": ref, "pad": padnum,
                                          "reason": "no bottom pour"})
            continue
        best = None
        r = 0.7
        while r <= MAX_ESCAPE and best is None:
            for a in range(0, 360, 5):
                x = int(P.x + r * IU * math.cos(math.radians(a)))
                y = int(P.y + r * IU * math.sin(math.radians(a)))
                if not circle_in(opp, x, y, R):
                    continue
                if not clear_of_pads(x, y):
                    continue
                if any((x - px) ** 2 + (y - py) ** 2 < MIN_SEP ** 2
                       for px, py in existing):
                    continue
                if any((x - ax) ** 2 + (y - ay) ** 2 < (MIN_SEP + ar) ** 2
                       for ax, ay, ar in added_circles):
                    continue
                circle = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(x, y),
                                             int(PAD / 2 * IU))
                seg = pcbnew.SHAPE_SEGMENT(P, pcbnew.VECTOR2I(x, y),
                                           int(TW * IU))
                hit = False
                for o in obstacles:
                    if o.Collide(circle, clr_iu) or o.Collide(seg, clr_iu):
                        hit = True
                        break
                if hit:
                    continue
                best = (x, y)
                break
            r += 0.15
        if best is None:
            report["unescapable"].append({
                "ref": ref, "pad": padnum,
                "reason": "no clear via site within %.1fmm" % MAX_ESCAPE,
                "pad_mm": [round(P.x / IU, 2), round(P.y / IU, 2)],
            })
            continue
        x, y = best
        add_via(x, y)
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(P)
        tr.SetEnd(pcbnew.VECTOR2I(x, y))
        tr.SetWidth(int(TW * IU))
        tr.SetLayer(pcbnew.F_Cu)
        tr.SetNetCode(nc)
        board.Add(tr)
        added_circles.append((x, y, int(PAD / 2 * IU)))
        report["escapes"].append({
            "ref": ref, "pad": padnum,
            "x_mm": round(x / IU, 3), "y_mm": round(y / IU, 3),
            "stub_mm": round(math.hypot(x - P.x, y - P.y) / IU, 2),
        })

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(pcb_path, board)
report["added_via_count"] = len(report["stitch_vias"]) + len(report["escapes"])
print("RESULT_JSON:" + json.dumps(report))
"""


def fill_zones(pcb_path: Path, timeout: float = 120.0) -> Path:
    """Fill every zone on the board and save it in place.

    `kicad-cli pcb drc` does not fill zones; running DRC on an unfilled board
    reports every pour-connected pad as unconnected.
    """
    pcb_path = Path(pcb_path).expanduser().resolve()
    if not pcb_path.is_file():
        raise FileNotFoundError(pcb_path)
    _run_pcbnew_script(_FILL_ZONES_SCRIPT, str(pcb_path), timeout=timeout)
    return pcb_path


def bond_ground(
    pcb_path: Path,
    net: str = "GND",
    *,
    via_drill_mm: float = 0.3,
    via_pad_mm: float = 0.6,
    clearance_mm: float = 0.2,
    trace_width_mm: float = 0.25,
    max_escape_mm: float = 2.0,
    escape_targets: list[tuple[str, str]] | None = None,
    timeout: float = 300.0,
) -> dict:
    """Bond a pour net back together after routing, then refill and save.

    Two passes:
      1. Every filled island with no via in it gets one stitching via, placed
         where the pad also lands inside the opposite layer's pour.
      2. Each pad in `escape_targets` (from a DRC unconnected report) gets a
         via + stub within `max_escape_mm`, if a clearance-legal site exists.

    Whatever cannot be fixed geometrically is returned in `unstitchable` /
    `unescapable` with coordinates, for a human to route in KiCAD.
    """
    pcb_path = Path(pcb_path).expanduser().resolve()
    if not pcb_path.is_file():
        raise FileNotFoundError(pcb_path)
    import json as _json
    cfg = {
        "via_drill_mm": via_drill_mm,
        "via_pad_mm": via_pad_mm,
        "clearance_mm": clearance_mm,
        "trace_width_mm": trace_width_mm,
        "max_escape_mm": max_escape_mm,
        "escape_targets": [list(t) for t in (escape_targets or [])],
    }
    out = _run_pcbnew_script(
        _GROUND_BOND_SCRIPT, str(pcb_path), net, _json.dumps(cfg), timeout=timeout
    )
    line = next(
        (ln for ln in reversed(out.splitlines()) if ln.startswith("RESULT_JSON:")),
        None,
    )
    if line is None:
        raise KicadPythonError(f"bond_ground produced no result: {out[-300:]}")
    return _json.loads(line[len("RESULT_JSON:"):])
