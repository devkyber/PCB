#!/usr/bin/env python3
"""Generate IMU (ICM-42688-P) breakout PCB layout using kicad-claude-mcp's
pcb_editor adapter.

Rev 1 — real footprints (LGA-14 IC fetched from LCSC/EasyEDA, real
standard KiCad footprints for every passive/connector/mounting hole/
fiducial). Net assignment is parsed directly out of gen_imu_sch.py's
pin_label() calls — the already-ERC-verified (0 errors) source of truth
— instead of a hand-maintained, drift-prone net table (same pattern as
TMS V3's gen_tms_v3_pcb.py).

Board: nominally ~20mm x 15mm per spec; bumped to 22mm x 17mm once real
footprint geometry was in hand — the 6-pin 2.54mm-pitch SPI header alone
spans 12.7mm, and fitting it plus the real LGA-14 IC, both decoupling
caps within 2mm of their pins, 2 M2 mounting holes (5.5mm keepout each
per docs/DESIGN_RULES.md §15.6), and 3 fiducials on a strict 20x15mm
canvas left no room for DRC-clean spacing. This mirrors the documented
§15.7 lesson: placeholder-era dimensions don't survive contact with real
part geometry — widen, don't force it. Documented as a deviation in
EVALUATION.md.

This script produces PLACEMENT + real footprints + net-annotated pads +
ground plane + fiducials + stitching vias. It does NOT route traces —
routing is out of scope per the task brief (matches TMS V3's stopping
point); kicad-cli 10 also dropped Specctra DSN export from the CLI
(GUI-only), so headless Freerouting isn't available from this session
anyway.
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
PCB_PATH = PROJECT_DIR / 'imu-icm42688.kicad_pcb'
SCH_SCRIPT = PROJECT_DIR / 'gen_imu_sch.py'
BLANK_TEMPLATE = Path(__file__).resolve().parents[2] / 'tools/kicad-claude-mcp/src/kicad_claude/templates/blank/blank.kicad_pcb'

REAL_FP_DIR = PROJECT_DIR / 'libs' / 'jlcpcb.pretty'
STD_FP_ROOT = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')

BOARD_W = 24.0
BOARD_H = 19.0
ORIGIN_X = 3.0
ORIGIN_Y = 3.0

# ============================================================
# Step 1: Extract the verified pin->net map from the schematic script
# ============================================================
print("=== IMU ICM-42688-P PCB Generation (Rev 1 — real footprints) ===")
print("Parsing net assignments from gen_imu_sch.py (verified via ERC, 0 errors)...")


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

# PWR_FLAG symbols (#FLG01-02) and power symbols (#PWR01-02) have no
# physical PCB footprint — drop them, they were schematic-only ERC
# satisfiers
NET_MAP = {k: v for k, v in NET_MAP.items() if not k[0].startswith('#')}

print(f"  {len(NET_MAP)} pin-net assignments recovered")

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
    """Place a real LCSC-fetched footprint (already format-upgraded via
    the kipython FootprintLoad/FootprintSave round-trip)."""
    fp_def = _fetch_cached(REAL_FP_DIR / f'{fp_filename}.kicad_mod')
    node = pe.add_footprint(
        tree, qualified_lib_id=f'jlcpcb:{fp_filename}', reference=ref,
        value=value, x_mm=x, y_mm=y, rotation=rot, fp_def_node=fp_def,
    )
    return _set_pad_nets(node, ref)


def place_std(ref, value, lib_name, fp_filename, x, y, rot=0):
    """Place a real standard KiCad library footprint."""
    fp_def = _fetch_cached(STD_FP_ROOT / f'{lib_name}.pretty' / f'{fp_filename}.kicad_mod')
    node = pe.add_footprint(
        tree, qualified_lib_id=f'{lib_name}:{fp_filename}', reference=ref,
        value=value, x_mm=x, y_mm=y, rotation=rot, fp_def_node=fp_def,
    )
    _set_pad_nets(node, ref)
    # Return the NODE so callers can chain set_lcsc() onto it.
    return node


def set_lcsc(fp_node, lcsc):
    """Stamp an 'LCSC Part' property, cloning the footprint's own Value
    property node so the result keeps whatever shape this KiCad version
    expects. Standard KiCad footprints carry no part number, so every
    passive here was unsourced and JLCPCB could not have assembled them."""
    import copy
    src = next((i for i in fp_node
                if isinstance(i, list) and i and str(i[0]) == 'property'
                and len(i) >= 3 and i[1] == 'Value'), None)
    if src is None:
        raise RuntimeError('footprint has no Value property to clone')
    node = copy.deepcopy(src)
    node[1], node[2] = 'LCSC Part', lcsc
    node.append([sexpdata.Symbol('hide'), sexpdata.Symbol('yes')])
    fp_node.append(node)
    return fp_node


# LCSC part numbers — basic tier where one exists (no JLCPCB setup fee).
#   100nF  C307331   Samsung CL05B104KB54PNC  50V X7R 0402   basic
#   2.2uF  C23630    Samsung CL10A225KO8NNNC  16V X5R 0603   basic
#   10nF   C15195    Samsung CL05B103KB5NNNC  50V X7R 0402   basic
LCSC = {'100nF': 'C307331', '2.2uF': 'C23630', '10nF': 'C15195'}


# Coordinates below are direct MCP mm (Y up, board bottom-left at
# ORIGIN_X, ORIGIN_Y) — no extra flip layer needed for a board this
# simple.

# ============================================================
# SECTION 1: SPI HEADER (6-pin, rotated 90 deg so its 12.7mm pin span
# runs along the board's 24mm width instead of its 19mm height)
# ============================================================
print("Section 1: SPI header...")

# NOTE on this footprint's rotation behavior: its pads are defined in
# the LIBRARY at local (0,0), (0,2.54), ... (0,12.7) — i.e. the anchor
# IS pin 1, not the component's visual center. After a 90 deg rotation
# each local (0, ly) maps to global (anchor_x + ly, anchor_y). So the
# anchor must be placed at the LEFT end of the desired pin span, not
# its midpoint (an earlier attempt anchored at the visual center and
# drove the pin row 6.35mm off the right edge of the board).
# J1 is THROUGH-HOLE. JLCPCB's standard SMT service does not fit THT parts,
# so this one is hand-soldered — which matches the workspace convention of
# preferring through-hole for prototype connectors. Sourced anyway so the
# BOM is complete and the part is a known-good 2.54mm header rather than
# "whatever is in the drawer".
set_lcsc(place_std('J1', 'SPI-HDR', 'Connector_PinHeader_2.54mm',
                   'PinHeader_1x06_P2.54mm_Vertical', 8.0, 8.0, rot=90),
         'C37208')
# -> pins span x = 8.0 .. 20.7, y = 8.0 (constant)

# ============================================================
# SECTION 2: ICM-42688-P IMU (real LGA-14, real footprint)
# ============================================================
print("Section 2: ICM-42688-P IMU (real part)...")

place_real('U1', 'ICM-42688-P', 'LGA-14_L3.0-W2.5-P0.50-TL', 16.0, 14.0)

# ============================================================
# SECTION 3: DECOUPLING (each <=2mm from its IC power pin, no via
# between cap and pin)
# ============================================================
print("Section 3: Decoupling capacitors...")

# Pin 8 (VDD) real local offset from IC center: (+1.26, +0.75) -> pin at
# (17.26, 14.75). C1 placed 1.75mm away.
# Decoupling placement, measured against the REAL pad coordinates read back
# out of the generated board (kicad_y = 210 - layout_y on this board), not
# derived from the transform. Rule 2.2 is "within 2mm of the POWER PIN", and
# on a 0.5mm-pitch LGA-14 the power pins are on opposite faces of the part:
#
#     VDD   pin 8  at kicad (17.260, 196.750)   -> east face
#     VDDIO pin 5  at kicad (15.500, 197.010)   -> south face
#
# so one cap "near U1" cannot serve both. C1 was 1.96mm from VDD — inside
# the rule by 0.04mm, which is not margin, it is luck.
set_lcsc(place_std('C1', '100nF', 'Capacitor_SMD', 'C_0402_1005Metric', 18.7, 12.4), LCSC['100nF'])   # 1.28mm from VDD pin 8
set_lcsc(place_std('C2', '2.2uF', 'Capacitor_SMD', 'C_0603_1608Metric', 19.5, 10.8), LCSC['2.2uF'])    # VDD bulk, clear of H2
set_lcsc(place_std('C3', '10nF', 'Capacitor_SMD', 'C_0402_1005Metric', 15.5, 11.7), LCSC['10nF'])     # 1.38mm from VDDIO pin 5
# Pin 5 (VDDIO) real local offset: (-0.50, +1.01) -> pin at (15.5, 15.01).
# C2 placed ~2.0mm away.

# ============================================================
# SECTION 4: TEST POINTS
# ============================================================
print("Section 4: Test points...")

place_std('TP1', '+3V3', 'TestPoint', 'TestPoint_Pad_1.0x1.0mm', 9.0, 13.0)
place_std('TP2', 'GND', 'TestPoint', 'TestPoint_Pad_1.0x1.0mm', 10.0, 18.0)
place_std('TP3', 'INT1', 'TestPoint', 'TestPoint_Pad_1.0x1.0mm', 12.0, 12.0)

# ============================================================
# SECTION 5: MOUNTING HOLES (M2, >=2)
# ============================================================
print("Section 5: Mounting holes...")

place_std('H1', 'M2', 'MountingHole', 'MountingHole_2.2mm_M2_Pad', 6.0, 18.0)
place_std('H2', 'M2', 'MountingHole', 'MountingHole_2.2mm_M2_Pad', 24.0, 13.0)

# ============================================================
# SECTION 6: FIDUCIALS (3, in an L-pattern — a RECOMMENDATION, not a
# JLCPCB requirement. JLCPCB auto-adds its own fiducials for assembly,
# so a board is never rejected for having none; these buy tighter
# placement accuracy on the 0.5mm-pitch LGA. FID3 was at (20.0, 18.5),
# 4.5mm from FID2 (not an L-pattern) and directly across the SPI_SDO
# routing corridor, where its 1.1mm keepout cost 7 DRC errors once the
# test points were given real nets and the router had to reach them.
# ============================================================
print("Section 6: Fiducials...")

# Fiducial pads carry a special (clearance 1.1) property in the library
# footprint — 1.1mm minimum copper-to-copper clearance, well above the
# board's normal 0.2mm rule — so fiducials need noticeably more breathing
# room than any other component.
place_std('FID1', 'FIDUCIAL', 'Fiducial', 'Fiducial_1mm_Mask3mm', 4.5, 12.0)
place_std('FID2', 'FIDUCIAL', 'Fiducial', 'Fiducial_1mm_Mask3mm', 24.5, 18.0)
place_std('FID3', 'FIDUCIAL', 'Fiducial', 'Fiducial_1mm_Mask3mm', 5.0, 4.5)

# ============================================================
# SECTION 7: Ground plane, stitching vias, silkscreen
# ============================================================
print("Section 7: Ground plane, stitching, board ID...")

board_polygon = [
    (ORIGIN_X, ORIGIN_Y), (ORIGIN_X + BOARD_W, ORIGIN_Y),
    (ORIGIN_X + BOARD_W, ORIGIN_Y + BOARD_H), (ORIGIN_X, ORIGIN_Y + BOARD_H),
]
def _solid_connect(zone_node):
    """Solid pad connection instead of thermal-relief spokes.

    KiCad defaults to 0.5mm thermal gaps and 0.5mm bridges. A 0402's ground
    pad has too little perimeter left for the two spokes DRC wants, so the
    fill lands one and reports `starved_thermal` — a deliberately narrow,
    high-inductance path from a decoupling cap's ground to the plane, on a
    board whose datasheet specifies 10 mVpp of allowable supply noise.

    docs/DESIGN_RULES.md 12.1 asks for thermal relief on THROUGH-HOLE pads,
    for hand-solderability. The only THT part here is J1, whose pads carry
    GND on pin 2 — see DEVIATIONS.md.
    """
    for item in zone_node:
        if isinstance(item, list) and item and str(item[0]) == 'connect_pads':
            item.insert(1, sexpdata.Symbol('yes'))
            return zone_node
    raise RuntimeError('zone has no connect_pads node — KiCad format changed')


# Fill clearance 0.2mm rather than the 0.5mm default: at 0.5mm the pour
# cannot squeeze between a 0.5mm-pitch LGA's pads and the tracks leaving
# them, and pinches off slivers that strand a ground pad. Same failure the
# baro board hit. docs/DESIGN_RULES.md 12.1 floors this at 0.2mm.
_solid_connect(pe.add_zone(tree, net_name='GND', layer='B.Cu',
                           polygon_mcp=board_polygon, name='GND_BOTTOM',
                           fill_clearance_mm=0.2))
_solid_connect(pe.add_zone(tree, net_name='GND', layer='F.Cu',
                           polygon_mcp=board_polygon, name='GND_TOP',
                           fill_clearance_mm=0.2))

# Ground stitching vias around the perimeter — skip any point within
# 4mm of a mounting hole or fiducial (both have no net; a GND via that
# close triggers a DRC short/hole-clearance violation).
KEEPOUT_PTS = [(6.0, 18.0), (24.0, 13.0),                       # mounting holes
               (4.5, 12.0), (24.5, 18.0), (20.0, 18.5)]         # fiducials
KEEPOUT_RADIUS = 4.0


def _near_keepout(x, y):
    return any(((x - kx) ** 2 + (y - ky) ** 2) ** 0.5 < KEEPOUT_RADIUS
               for kx, ky in KEEPOUT_PTS)


perimeter_pts = []
for x in range(int(ORIGIN_X) + 3, int(ORIGIN_X + BOARD_W) - 2, 6):
    perimeter_pts.append((x, ORIGIN_Y + 1.5))
    perimeter_pts.append((x, ORIGIN_Y + BOARD_H - 1.5))
for y in range(int(ORIGIN_Y) + 3, int(ORIGIN_Y + BOARD_H) - 2, 6):
    perimeter_pts.append((ORIGIN_X + 1.5, y))
    perimeter_pts.append((ORIGIN_X + BOARD_W - 1.5, y))

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

# --- Ground escape for U1.9 (INT2/FSYNC/CLKIN), placed BEFORE routing ------
#
# Pin 9 is now tied to GND because Table 9 says "Connect to GND if FSYNC not
# used". Grounding it created the problem the baro board also hit: the pin
# sits in U1's east column between pad 8 (VDD, which routes east) and the
# no-net RESV pads 10 and 11, so after routing there is nowhere left to put
# its via. The post-route bonding pass says so exactly:
#
#     MANUAL  U1.9 at [17.26, 196.25]: no clear via site within 2.0mm
#
# and the result would be a grounded-on-paper pin that is floating in copper
# — strictly worse than the no-connect it replaced, because the schematic
# now claims it is grounded.
#
# Site measured from the built board (kicad_y = 210 - MCP y here):
#   pad 9  kicad (17.26, 196.25) = MCP (17.26, 13.75)
#   via    kicad (18.40, 195.50) = MCP (18.40, 14.50)
# Clears RESV pads 10/11 by 1.17mm. The stub passes 0.43mm from pad 10, so
# it is drawn at 0.15mm wide (needs 0.35mm, JLCPCB floor is 0.127mm) rather
# than the usual 0.25mm — it carries no current, only a ground reference.
# The stub runs due EAST, not diagonally. Measured pad geometry: the east
# column pads are 0.675 x 0.280mm on a 0.5mm pitch, so between pad 9 and its
# neighbours there is exactly 0.22mm of gap. A 0.15mm stub along the pad's
# own centre line sits 0.285mm from both pad 8 and pad 10 against a 0.2mm
# rule. The first attempt cut the corner diagonally toward the via and came
# within 0.0403mm of pad 10 — a straight line between two clear points is
# not itself clear, and the arithmetic for that is not worth doing by eye.
#
# C1 also moved (13.25 -> 12.4 MCP) to vacate the via site; it is now
# 1.28mm from VDD pin 8, still well inside rule 2.2.
U19_PAD = (17.26, 13.75)
U19_VIA = (18.40, 13.75)
pe.add_via(tree, U19_VIA[0], U19_VIA[1], drill_mm=0.3, diameter_mm=0.6, net=gnd_id)
pe.add_track(tree, U19_PAD[0], U19_PAD[1], U19_VIA[0], U19_VIA[1],
             width_mm=0.15, layer='F.Cu', net=gnd_id)
print("  U1.9 FSYNC ground escape via + stub placed pre-route")

# Board ID silkscreen — the only edge-to-edge clear band on this tight
# layout is below the SPI header (header courtyard bottom edge is at
# y~6.2, board edge at y=3), which only leaves ~3.2mm of vertical room
# — too little for two lines at a legible size, so board name + rev +
# author are combined onto a single silkscreen line here.
pe.add_silk_text(tree, text='IMU-42688P rev1 Lee Taeho', x_mm=15.0, y_mm=4.7, size_mm=0.8)

# ============================================================
# Save
# ============================================================
print("\nSaving PCB...")
sch_io.write_file(PCB_PATH, tree)
print(f"Written to: {PCB_PATH}")
print(f"File size: {PCB_PATH.stat().st_size} bytes")
print()
print("=== PCB generation complete (Rev 1, real footprints) ===")
print("Next: run DRC.")
