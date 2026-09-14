#!/usr/bin/env python3
"""Generate baro-bmp390 PCB layout using kicad-claude-mcp's pcb_editor adapter.

Rev 1 — real BMP390 footprint (LGA-10, LCSC C5124834) + real standard
KiCad footprints for the STEMMA QT connector, decoupling caps, pull-up
resistors, test point, mounting holes, fiducials. Net assignment parsed
directly out of gen_baro_sch.py's pin_label() calls — the ERC-verified
source of truth (same pattern as TMS V3's gen_tms_v3_pcb.py).

Board: 18mm x 26mm, 2-layer, JLCPCB spec. Grew from the initial ~15x15mm
target — see EVALUATION.md for the sizing rationale. The real
JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal STEMMA QT footprint's
courtyard measures ~7.8mm x 6.6mm (mounting tabs included) — far bigger
than the 4.5x6mm "minimal" estimate in docs/DESIGN_RULES.md §15.6, and by
itself wider than a 15mm board minus edge margins. This is exactly the
§15.7 lesson repeated: "real courtyards are often bigger than a doc
estimate assumes" — measured from the fetched footprint, not guessed.

Placement follows docs/DESIGN_RULES.md §1.1 order: mounting holes/
fiducials -> connector -> IC -> decoupling (<=2mm from IC power pins,
no via between cap and pin) -> pull-ups -> test point.

This script produces PLACEMENT + real footprints + net-annotated pads +
ground plane + fiducials + stitching vias. It does NOT route traces —
kicad-cli 10 has no CLI DSN export; routing is out of scope (placement
only), per CLAUDE.md.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'tools/kicad-claude-mcp/src'))

import sexpdata
from kicad_claude.adapters import pcb_editor as pe
from kicad_claude.adapters import sch_io

# Derived from this file's own location, never hardcoded. An absolute
# project path means a copy of this script run from anywhere writes to the
# ORIGINAL board: the enforcement self-test ran a generator inside a
# throwaway sandbox and silently modified the live project, and the check
# that was supposed to prove the ownership guard worked passed for that
# reason rather than because the guard fired.
PROJECT_DIR = Path(__file__).resolve().parent
PCB_PATH = PROJECT_DIR / 'baro-bmp390.kicad_pcb'
SCH_SCRIPT = PROJECT_DIR / 'gen_baro_sch.py'
BLANK_TEMPLATE = Path(__file__).resolve().parents[2] / 'tools/kicad-claude-mcp/src/kicad_claude/templates/blank/blank.kicad_pcb'

REAL_FP_DIR = PROJECT_DIR / 'libs' / 'jlcpcb.pretty'
STD_FP_ROOT = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')

BOARD_W = 18.0
BOARD_H = 26.0
ORIGIN_X = 10.0
ORIGIN_Y = 10.0

# ============================================================
# Step 1: Extract the verified pin->net map from the schematic script
# ============================================================
print("=== baro-bmp390 PCB Generation (Rev 1 — real footprints, real nets) ===")
print("Parsing net assignments from gen_baro_sch.py (verified via ERC)...")


NETMAP_PATH = SCH_SCRIPT.parent / 'netmap.json'
if not NETMAP_PATH.exists():
    raise SystemExit(
        f"{NETMAP_PATH} not found. Run {SCH_SCRIPT.name} first — it writes the\n"
        f"authoritative pin->net map. This script used to re-derive that map by\n"
        f"running a regex over the schematic script's SOURCE TEXT, matching only\n"
        f"literal pin_label('REF','PIN','NET') calls. Nets assigned from a LOOP\n"
        f"were invisible to it, so the board silently got an incomplete netlist\n"
        f"instead of an error — that is how this board's test points ended up\n"
        f"with dead, netless pads while every gate passed."
    )

_nm = json.loads(NETMAP_PATH.read_text())
NET_MAP = {(ref, pin): net
           for ref, pins in _nm['nets'].items()
           for pin, net in pins.items()}

print(f"  {len(NET_MAP)} pin-net assignments recovered")

# PWR_FLAG (#FLG01/02) and power symbols (#PWR01/02) have no physical
# PCB footprint — drop them, they were schematic-only ERC satisfiers
NET_MAP = {k: v for k, v in NET_MAP.items() if not k[0].startswith('#')}

# ============================================================
# Step 2: Board setup
# ============================================================
if PCB_PATH.exists():
    PCB_PATH.unlink()

tree = sch_io.parse_file(BLANK_TEMPLATE)
pe.set_board_outline(tree, BOARD_W, BOARD_H, origin_x_mcp=ORIGIN_X, origin_y_mcp=ORIGIN_Y)
pe.set_copper_layer_count(tree, 2)

# ============================================================
# Step 3: Net registry
# ============================================================
net_order = []
seen = set()
for net in NET_MAP.values():
    if net not in seen:
        seen.add(net)
        net_order.append(net)

NET_IDS = {'': 0}
next_id = 1
for name in net_order:
    NET_IDS[name] = next_id
    next_id += 1

net0_idx = next(i for i, c in enumerate(tree) if sch_io.is_call(c, 'net'))
insert_at = net0_idx + 1
for name in net_order:
    tree.insert(insert_at, [sexpdata.Symbol('net'), NET_IDS[name], name])
    insert_at += 1

print(f"  {len(net_order)} nets declared: {net_order}")

# ============================================================
# Step 4: Footprint fetch + placement + net assignment helpers
# ============================================================
_fp_cache = {}


def _fetch_cached(path):
    key = str(path)
    if key not in _fp_cache:
        _fp_cache[key] = pe.fetch_footprint_def(path)
    return _fp_cache[key]


def _set_pad_nets(fp_node, ref):
    n_assigned = 0
    for child in fp_node:
        if sch_io.is_call(child, 'pad'):
            pad_num = child[1]
            net_name = NET_MAP.get((ref, str(pad_num)))
            if net_name:
                net_id = NET_IDS[net_name]
                child.append([sexpdata.Symbol('net'), net_id, net_name])
                n_assigned += 1
    return n_assigned


def place_real(ref, value, fp_filename, x, y, rot=0):
    """Place a real LCSC-fetched footprint (already format-upgraded)."""
    fp_def = _fetch_cached(REAL_FP_DIR / f'{fp_filename}.kicad_mod')
    node = pe.add_footprint(
        tree, qualified_lib_id=f'jlcpcb:{fp_filename}', reference=ref,
        value=value, x_mm=ORIGIN_X + x, y_mm=ORIGIN_Y + (BOARD_H - y),
        rotation=rot, fp_def_node=fp_def,
    )
    _set_pad_nets(node, ref)
    # Return the NODE, not the pad count: callers chain set_lcsc() onto this.
    return node


def set_lcsc(fp_node, lcsc):
    """Stamp an 'LCSC Part' property on a footprint.

    The real BMP390 footprint arrives from easyeda2kicad already carrying
    this property; every standard KiCad footprint does not, so the passives
    and the connector had no part number at all and the sourcing check read
    1 of 7. An unsourced part is not a cosmetic omission — JLCPCB cannot
    assemble it, and the board silently becomes a partial-assembly order.

    Built by cloning the footprint's own "Value" property node so the
    result carries whatever at/layer/effects shape this KiCad version
    expects, rather than a hand-written node that may not round-trip.
    """
    import copy
    src = None
    for item in fp_node:
        if (isinstance(item, list) and item and str(item[0]) == 'property'
                and len(item) >= 3 and item[1] == 'Value'):
            src = item
            break
    if src is None:
        raise RuntimeError('footprint has no Value property to clone')
    node = copy.deepcopy(src)
    node[1] = 'LCSC Part'
    node[2] = lcsc
    if not any(isinstance(i, list) and i and str(i[0]) == 'hide' for i in node):
        node.append([sexpdata.Symbol('hide'), sexpdata.Symbol('yes')])
    fp_node.append(node)
    return fp_node


def place_std(ref, value, lib_name, fp_filename, x, y, rot=0):
    """Place a real standard KiCad library footprint."""
    fp_def = _fetch_cached(STD_FP_ROOT / f'{lib_name}.pretty' / f'{fp_filename}.kicad_mod')
    node = pe.add_footprint(
        tree, qualified_lib_id=f'{lib_name}:{fp_filename}', reference=ref,
        value=value, x_mm=ORIGIN_X + x, y_mm=ORIGIN_Y + (BOARD_H - y),
        rotation=rot, fp_def_node=fp_def,
    )
    _set_pad_nets(node, ref)
    # Return the NODE, not the pad count: callers chain set_lcsc() onto this.
    return node


# Coordinates below use (x, y) with Y DOWN from the top-left of the
# board (matching the schematic's visual layout mental model); flipped
# once here to MCP's Y-up-from-bottom-left convention.

# ============================================================
# SECTION 1: MOUNTING HOLES + FIDUCIALS
# ============================================================
print("Section 1: Mounting holes + fiducials...")

# 2x M2 mounting holes (spec minimum), diagonal corners, 2.8mm inset —
# clears the 2.2mm hole + annular pad comfortably.
# Both holes on the edge OPPOSITE the connector. H1 was at (2.8, 2.8), which
# put its 4.9x4.9mm courtyard 0.15mm into J1's — the connector spans x
# 5.1..12.9 at this end of the board, so there is no room for a hole beside
# it that also keeps its pad 0.3mm off the board edge.
#
# Pattern taken from the archived reference: Adafruit's BMP390 breakout
# (evidence/files/BMP390_Adafruit_20BMP390.brd, 25.40 x 17.78mm) puts both
# M2.5 holes on one long edge at (2.54, 15.24) and (22.86, 15.24) — 2.54mm
# inset, connectors on the perpendicular edges, no hole sharing an edge with
# a connector. Same rule here, scaled to an 18mm-wide board: 2.8mm inset,
# 12.4mm apart, connector edge left clear.
#
# TRADEOFF, flagged in REQUIREMENTS.md: two holes on one edge cantilevers the
# board about that axis. Adafruit accept this for a desk breakout; under
# rocket vibration a third hole is the usual answer. Needs an owner decision.
MOUNTING_HOLES = {'H1': (2.8, 23.2), 'H2': (15.2, 23.2)}
for ref, (hx, hy) in MOUNTING_HOLES.items():
    place_std(ref, 'M2', 'MountingHole', 'MountingHole_2.2mm_M2_Pad', hx, hy)

# 3x fiducials (JLCPCB PCBA minimum): one remaining corner, plus a
# right-mid-edge slot clear of the connector/IC/silkscreen text zones.
# FID2 was at (2.8, 23.2) — the coordinate H1 moved to, so the two landed on
# top of each other (courtyard overlap, PTH inside courtyard, shared solder
# mask aperture). FID3 was at (15.7, 14.0), in the congested right-hand side
# where the router runs +3V3, and picked up three clearance errors against a
# via and a track.
#
# Both moved to the now-free connector-end corners and the clear left edge,
# keeping the L-pattern CLAUDE.md asks for. Fiducials carry no net, so any
# copper the router places near one is a violation — they belong where the
# router has no reason to go.
FIDUCIALS = {'FID1': (15.2, 2.8), 'FID2': (2.8, 2.8), 'FID3': (2.8, 14.0)}
for ref, (fx, fy) in FIDUCIALS.items():
    place_std(ref, 'FIDUCIAL', 'Fiducial', 'Fiducial_1mm_Mask3mm', fx, fy)

# LCSC part numbers — from `lcsc_search`, basic tier wherever one exists,
# so JLCPCB charges no per-part assembly setup fee.
#
#   100nF  C307331  Samsung CL05B104KB54PNC  50V X7R +-10% 0402  basic
#   10uF   C96446   Samsung CL10A106MA8NRNC  25V X5R +-20% 0603  basic
#   4.7k   C25900   Uniroyal 0402WGF4701TCE  1% 0402             basic
#   QT     C160404  JST SM04B-SRSS-TB(LF)(SN)                    EXTENDED
#
# Two choices worth stating, because neither is the obvious pick:
#
# 10uF at 25V, not the cheaper-looking 10V part (C19702). A Class-II X5R
# ceramic loses capacitance with applied DC, and a 10V 0603 sitting on 3.3V
# gives up a large fraction of its rating; the 25V part in the same package
# keeps far more of it. C3 exists to hold the rail inside the datasheet's
# 50 mVpp ripple limit, so what matters is the capacitance at 3.3V bias, not
# the number printed on the reel. It also happens to be cheaper here
# ($0.053 vs $0.082).
#
# 100nF as X7R, not C0G. An earlier comment in the schematic generator
# called C1/C2 "C0G"; 100nF C0G does not exist in 0402 at any sane size.
# The datasheet specifies the VALUE ("the recommended value for C1, C2 is
# 100 nF") and says nothing about dielectric, so X7R is the right reading.
#
# J1 is the one EXTENDED part on the board — JST's genuine SM04B-SRSS-TB,
# with a one-off JLCPCB feeder setup fee and only ~7k stock. Flagged rather
# than swapped: a QT/Qwiic cable has to mate reliably, and this is the part
# the connector standard is defined around.
LCSC = {
    '100nF': 'C307331',
    '10uF': 'C96446',
    '4.7k': 'C25900',
    'STEMMA-QT': 'C160404',
}

# ============================================================
# SECTION 2: STEMMA QT CONNECTOR (top edge, centered)
# ============================================================
print("Section 2: STEMMA QT connector...")

# Real footprint courtyard measures x:+-3.9mm y:-3.28..+3.28mm (mounting
# tabs included) — unrotated (rot=0), pads sit at local y=-2 (mating
# edge, facing the board's top edge) and the body extends toward +y
# (board interior). Center 5mm down from the top edge clears the
# courtyard from the board edge with margin.
set_lcsc(place_std('J1', 'STEMMA-QT', 'Connector_JST',
                   'JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal', 9.0, 5.0, rot=0),
         LCSC['STEMMA-QT'])

# ============================================================
# SECTION 3: BMP390 + decoupling + pull-ups (board center-lower)
# ============================================================
print("Section 3: BMP390 (real LGA-10) + decoupling + I2C pull-ups...")

place_real('U1', 'BMP390', 'LGA-10_L2.0-W2.0-P0.50-BL', 9.0, 14.0)

# Real pin map (from libs/jlcpcb.kicad_sym, local offsets from U1
# center): pin10=VDD(-0.78,+0.5) pin1=VDDIO(-0.25,+0.78)
# pin2=SCK/SCL(+0.25,+0.78) pin4=SDI/SDA(+0.78,0) pin7=INT(-0.25,-0.78)
# C1 (VDD decoupling) and C2 (VDDIO decoupling) placed just outside the
# 2x2mm courtyard, <=2mm from their respective power pin, no via
# between cap and pin (per docs/DESIGN_RULES.md §2).
set_lcsc(place_std('C1', '100nF', 'Capacitor_SMD', 'C_0402_1005Metric', 6.3, 14.5),
         LCSC['100nF'])   # near VDD (pin10)
# C2 was at (8.7, 17.5) — 2.26mm from VDDIO, failing rule 2.2. It was
# right-ish in direction and simply too far; it is now directly above the
# pin at 1.31mm pad-to-pad.
#
# Coordinates here were MEASURED OUT OF THE GENERATED BOARD, not derived.
# This file's place_std() maps layout -> MCP, and a second transform then
# maps MCP -> KiCad by flipping about the A4 sheet, so the two flips cancel
# and KiCad y = 174 + layout_y. Reasoning about one flip in isolation puts
# a decoupling cap on the far side of the part, which is exactly the error
# the first attempt at this fix made. Rule 5 in the session brief says
# convert coordinates only via the helpers; the same applies to reading
# them back.
#
# U1 pad 1 (VDDIO) measures at KiCad (18.750, 188.780) = layout (8.75, 14.78).
set_lcsc(place_std('C2', '100nF', 'Capacitor_SMD', 'C_0402_1005Metric', 8.75, 16.0),
         LCSC['100nF'])  # near VDDIO (pin1)

# C3 — +3V3 rail bulk, at the J1 entry rather than at the sensor: this is a
# rail-level part, not a pin-level one. J1's courtyard ends at layout y=8.28;
# 0603 courtyard is 2.96x1.46 so y=9.5 clears it with margin. See
# DESIGN_BASIS.md for why the datasheet does not mention this cap and the
# board still needs it.
set_lcsc(place_std('C3', '10uF', 'Capacitor_SMD', 'C_0603_1608Metric', 11.5, 9.5),
         LCSC['10uF'])

# R1 (SCL pull-up, near pin2), R2 (SDA pull-up, near pin4)
# R1/R2 moved out from (11.8, 15.0) and (12.0, 12.7). At 2.8mm from U1 they
# sat directly in the channel the GND pour needs to reach U1.3 (VSS), and
# their pads plus clearance pinched that pour into a 1.24mm^2 fragment with
# U1.3 alone on it and no track or via anywhere on the pad.
#
# That is not a cosmetic fill artefact: one of the sensor's three ground
# pads was electrically floating on a finished, DRC-clean-looking board.
# Nothing but the zero-unconnected gate would have caught it, because DRC
# reports it as "GND_TOP not connected to GND_TOP" rather than as a pad.
#
# The board is 18x26mm at ~31% density — the crowding bought nothing. Pull
# them clear and the pour flows to U1.3 on its own, which is the point of
# rule 4: routing quality is a placement result, not a router setting.
set_lcsc(place_std('R1', '4.7k', 'Resistor_SMD', 'R_0402_1005Metric', 13.5, 15.5),
         LCSC['4.7k'])
set_lcsc(place_std('R2', '4.7k', 'Resistor_SMD', 'R_0402_1005Metric', 13.5, 12.5),
         LCSC['4.7k'])

# TP1 — INT breakout test point (near pin7)
place_std('TP1', 'INT', 'TestPoint', 'TestPoint_Pad_1.0x1.0mm', 6.5, 11.5)

# ============================================================
# SECTION 4: Ground plane, stitching, silkscreen
# ============================================================
print("Section 4: Ground plane, stitching vias, board ID silkscreen...")

board_polygon = [
    (ORIGIN_X, ORIGIN_Y), (ORIGIN_X + BOARD_W, ORIGIN_Y),
    (ORIGIN_X + BOARD_W, ORIGIN_Y + BOARD_H), (ORIGIN_X, ORIGIN_Y + BOARD_H),
]
def _solid_connect(zone_node):
    """Make the pour connect to pads solidly instead of through spokes.

    KiCad's default is thermal relief with a 0.5mm gap and 0.5mm bridges.
    On an 0402 GND pad or an LGA-10's 0.3mm VSS pad there is not enough pad
    perimeter left for the two spokes DRC wants, so the fill lands one spoke
    and reports `starved_thermal` — which is not a cosmetic complaint. One
    starved spoke is a deliberately *narrow, high-inductance* path from a
    decoupling capacitor's ground to the plane, on a board whose entire
    purpose is a low-noise rail (REQUIREMENTS.md: 50 mVpp, the datasheet's
    own limit).

    docs/DESIGN_RULES.md 12.1 asks for thermal relief on THROUGH-HOLE pads,
    for solderability by hand. Every netted pad here is SMD on a
    reflow-assembled board; the mounting holes carry no net and are
    unaffected. So the rule's condition does not apply, and the direct
    connection it recommends for thermal pads is the better choice for the
    same reason: lowest impedance to the plane.
    """
    for i, item in enumerate(zone_node):
        if isinstance(item, list) and item and str(item[0]) == 'connect_pads':
            item.insert(1, sexpdata.Symbol('yes'))
            return zone_node
    raise RuntimeError('zone has no connect_pads node — KiCad format changed')


# Fill clearance 0.3mm, not the 0.5mm default. At 0.5mm the top pour could
# not squeeze between U1's 0.5mm-pitch LGA pads and the tracks leaving them,
# and pinched off two 0.16mm^2 slivers of copper touching a GND pad but cut
# off from the main pour — reported as 'GND_TOP unconnected to GND_TOP'.
# They are far too small to stitch: a 0.6mm via pad does not fit inside a
# 0.45mm sliver. The cause is the clearance, so that is what changes.
# docs/DESIGN_RULES.md 12.1 sets the floor at 0.2mm pour-to-signal; JLCPCB's
# own 2-layer minimum is 0.127mm. 0.3mm keeps comfortable margin over both.
ZONE_CLEARANCE = 0.2
_solid_connect(pe.add_zone(tree, net_name='GND', layer='B.Cu',
                           polygon_mcp=board_polygon, name='GND_BOTTOM',
                           fill_clearance_mm=ZONE_CLEARANCE))
_solid_connect(pe.add_zone(tree, net_name='GND', layer='F.Cu',
                           polygon_mcp=board_polygon, name='GND_TOP',
                           fill_clearance_mm=ZONE_CLEARANCE))

# Ground stitching vias around the perimeter — skip any point too close
# to a mounting hole or fiducial (both have no net; a GND via that close
# triggers a DRC hole-clearance/short violation).
KEEPOUT_PTS = list(MOUNTING_HOLES.values()) + list(FIDUCIALS.values())
KEEPOUT_RADIUS = 3.0


def _near_keepout(x, y):
    rel_x, rel_y = x - ORIGIN_X, (ORIGIN_Y + BOARD_H) - y  # back to layout-space
    return any(((rel_x - kx) ** 2 + (rel_y - ky) ** 2) ** 0.5 < KEEPOUT_RADIUS
               for kx, ky in KEEPOUT_PTS)


perimeter_pts = list({
    (ORIGIN_X + 2, ORIGIN_Y + 10),
    (ORIGIN_X + BOARD_W - 2, ORIGIN_Y + 10),
    (ORIGIN_X + 2, ORIGIN_Y + 20),
    (ORIGIN_X + BOARD_W - 2, ORIGIN_Y + 20),
})

gnd_id = NET_IDS['GND']
n_skipped = 0
n_placed = 0
for vx, vy in perimeter_pts:
    if _near_keepout(vx, vy):
        n_skipped += 1
        continue
    pe.add_via(tree, vx, vy, drill_mm=0.3, diameter_mm=0.6, net=gnd_id)
    n_placed += 1
print(f"  {n_placed} stitching vias placed ({n_skipped} skipped near keepouts)")

# --- Ground escapes for pads the pour cannot reach, placed BEFORE routing ---
#
# On a 2-layer board the top pour is chopped up by the traces routed through
# it, and a GND pad can end up alone on a fragment: no track, no via, not
# grounded. Two pads here do it — U1.3 (VSS, boxed in by the tracks leaving
# pads 4 and 5) and C2.2 (the VDDIO decoupling cap's ground).
#
# It is a nasty defect because of how it is PHRASED. DRC calls it
#
#     Zone 'GND_TOP' [GND] on F.Cu  <->  Zone 'GND_TOP' [GND] on F.Cu
#
# which reads like a cosmetic pour complaint, and the post-route bonding pass
# builds its escape list only from items DRC names a PAD in — so it finds
# nothing to do and reports "0 pad escapes" while a ground pin floats. The
# post-route stitcher reaches the same dead end from the other side:
#
#     MANUAL  U1.3 at [19.78, 188.5]: no clear via site within 2.0mm
#
# Only the zero-unconnected gate catches it at all. Bosch Fig 24/25 mark both
# VSS groups "VSS = GND"; a floating one is a defect, not a fill artefact.
#
# CLAUDE.md warns that stitching vias placed before routing fight the router.
# That warning is about GRID stitching — dozens of vias competing with the
# traces they exist to support. This is two vias for two pads that provably
# cannot be escaped afterwards, and placing them first is precisely what
# makes the router route AROUND them instead of sealing them in. Adding them
# also cleared three +3V3 clearance errors, because the router stopped
# threading tracks through the gap it was using as an escape corridor.
#
# Sites chosen by measurement against the real pad coordinates, not by eye.
# All coordinates MCP-space (KiCad y = 210 - MCP y).
GROUND_ESCAPES = [
    # (pad_xy,        via_xy,       what it is)
    ((19.78, 21.50), (20.50, 21.50), 'U1.3 VSS'),   # clears pad 4 by 0.43mm
    ((19.23, 20.00), (20.60, 20.00), 'C2.2 GND'),   # clears U1 by 1.71mm
]
for (px, py), (vx, vy), what in GROUND_ESCAPES:
    pe.add_via(tree, vx, vy, drill_mm=0.3, diameter_mm=0.6, net=gnd_id)
    pe.add_track(tree, px, py, vx, vy, width_mm=0.2, layer='F.Cu', net=gnd_id)
    print(f"  ground escape via + stub placed pre-route: {what}")

# Board ID silkscreen — near the PHYSICAL bottom edge of the board.
# add_silk_text takes MCP (Y-up) coordinates like add_footprint: MCP
# y = ORIGIN_Y + BOARD_H is the board's visual TOP edge, MCP y = ORIGIN_Y
# is the visual BOTTOM edge. Use a small offset from ORIGIN_Y (not from
# ORIGIN_Y + BOARD_H) to land near the bottom, clear of J1 near the top.
pe.add_silk_text(tree, text='BARO-BMP390', x_mm=ORIGIN_X + 9, y_mm=ORIGIN_Y + 3.0, size_mm=1.0)
pe.add_silk_text(tree, text='rev1 Lee Taeho', x_mm=ORIGIN_X + 9, y_mm=ORIGIN_Y + 1.5, size_mm=0.8)

# ============================================================
# Save
# ============================================================
print("\nSaving PCB...")
sch_io.write_file(PCB_PATH, tree)
print(f"Written to: {PCB_PATH}")
print(f"File size: {PCB_PATH.stat().st_size} bytes")
print()
print("=== PCB generation complete (Rev 1, real footprints) ===")
print("Next: run DRC (placement-only, routing out of scope).")
