"""Teach Freerouting about pad clearances that KiCad's DSN export drops.

The defect
----------
`pcbnew.ExportSpecctraDSN` writes ONE global clearance rule:

    (rule (width 254) (clearance 200) (clearance 50 (type smd_smd)))

and nothing else. A pad that overrides that clearance locally is exported as
a plain pad, so the router happily lays copper 0.2mm from it. KiCad's DRC
then applies the pad's REAL local clearance afterwards and reports a
violation the router was never given a chance to avoid.

The case that found it: KiCad's own stock `Fiducial_1mm_Mask3mm` footprint
carries `(clearance 1.1)` — a fiducial needs a copper-free ring so the
pick-and-place camera can resolve it. On imu-icm42688 (24 x 19 mm, with a
6-pin header across the middle) Freerouting routed SPI_SDO straight through
FID3's keepout, producing 7 DRC errors: 3 clearance, 1 hole_clearance and 3
solder_mask_bridge, all naming FID3.

Chasing it as a placement problem is what it looks like from the outside and
is a trap — moving FID3 to three different corners produced 6, 6 and 1
errors, because the router simply followed it. The board was not too full;
the router was working from a specification that omitted the constraint.

This affects every board with a fiducial, and any footprint carrying a local
clearance override — thermal pads and high-voltage pads most often.

The fix
-------
After exporting the DSN and before routing, inject an explicit Specctra
`keepout` circle for every pad whose local clearance exceeds the global rule.
The circle's diameter is the pad's largest dimension plus twice its local
clearance, so the router treats the whole forbidden ring as solid.

This does NOT relax any DRC rule; it tells the router the rule that already
existed. A board that passed before still passes.

Measured limit
--------------
Freerouting honours these for WIRING but not for VIAS. On imu-icm42688 the
injection removed every track violation (3 of 7 errors) and the router then
placed GND vias inside the same ring anyway; `via_keepout` and `wire_keepout`
alongside the plain `keepout` made no difference to that. So a board with a
tight fiducial can still need two vias nudged by hand. Do not read a clean
track result as proof the whole ring is respected.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Emitted by KiCad's exporter; matched to find where to insert and to read
# the global clearance the local ones are compared against.
_RULE_RE = re.compile(r'\(rule\s*\n?\s*\(width\s+([\d.]+)\)\s*\n?\s*'
                      r'\(clearance\s+([\d.]+)\)')

_COLLECT_SCRIPT = r"""
import sys, json, pcbnew
board = pcbnew.LoadBoard(sys.argv[1])
out = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        c = pad.GetLocalClearance()
        # KiCad returns None (or an unset optional) when the pad simply
        # inherits the board rule — that is the common case, not a defect.
        try:
            c = 0 if c is None else int(c)
        except Exception:
            c = 0
        if c <= 0 or not pad.IsOnCopperLayer():
            continue
        pos = pad.GetPosition()
        size = pad.GetSize()
        out.append({
            "ref": fp.GetReference(),
            "pad": str(pad.GetPadName()),
            "x_nm": int(pos.x), "y_nm": int(pos.y),
            "w_nm": int(size.x), "h_nm": int(size.y),
            "clearance_nm": c,
        })
print(json.dumps(out))
"""


def collect(pcb_path: Path, runner) -> list:
    """Pads carrying a local clearance override. `runner` is the module's
    `_run_pcbnew_script`, passed in so this file stays import-cycle free."""
    try:
        raw = runner(_COLLECT_SCRIPT, str(pcb_path))
    except Exception:                                        # noqa: BLE001
        # Never let this optional hardening break a route that used to work.
        return []
    try:
        return json.loads(raw.strip().splitlines()[-1])
    except Exception:                                        # noqa: BLE001
        return []


def inject(dsn_path: Path, pads: list) -> int:
    """Add a keepout circle per over-clearance pad. Returns the count added.

    DSN coordinates here are micrometres with Y negated, matching what
    KiCad's own exporter writes (`(place FID1 4500 -198000 ...)`), so the
    conversion is nm -> um with the sign flip.
    """
    if not pads:
        return 0
    dsn_path = Path(dsn_path)
    text = dsn_path.read_text()
    if '(keepout' in text:            # already injected; do not double up
        return 0
    m = _RULE_RE.search(text)
    if not m:
        return 0
    global_clearance_um = float(m.group(2))

    lines = []
    for p in pads:
        clear_um = p['clearance_nm'] / 1000.0
        if clear_um <= global_clearance_um:
            continue
        dia_um = max(p['w_nm'], p['h_nm']) / 1000.0 + 2 * clear_um
        x_um = p['x_nm'] / 1000.0
        y_um = -p['y_nm'] / 1000.0
        for layer in ('F.Cu', 'B.Cu'):
            # All three kinds, deliberately. Freerouting honours `keepout`
            # for wiring but kept dropping GND stitching vias inside the
            # ring until `via_keepout` was named explicitly — a plain
            # `keepout` was not enough to keep a VIA out of it.
            for kind in ('keepout', 'via_keepout', 'wire_keepout'):
                lines.append(f'    ({kind} "{p["ref"]}.{p["pad"]}" '
                             f'(circle {layer} {dia_um:.0f} {x_um:.0f} {y_um:.0f}))')
    if not lines:
        return 0

    # Insert just before the closing paren of the (structure ...) block, which
    # is the line following the global rule KiCad writes last in it.
    end = text.index(')', m.end())            # close of (clearance ...)
    end = text.index('\n  )', end)            # close of (structure ...)
    text = text[:end] + '\n' + '\n'.join(lines) + text[end:]
    dsn_path.write_text(text)
    return len(lines)
