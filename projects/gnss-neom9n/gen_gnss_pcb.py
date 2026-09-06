#!/usr/bin/env python3
"""Generate GNSS NEO-M9N breakout PCB layout using kicad-claude-mcp's
pcb_editor adapter.

Rev1 — real footprints (NEO-M9N-00B castellated SMD-24P + XC6206P332MR
SOT-23-3, both fetched from LCSC via easyeda2kicad) plus real standard
KiCad footprints for every passive/connector/battery holder. Net
assignment is parsed directly out of gen_gnss_sch.py's pin_label() calls
— the already-ERC-verified (0 errors) source of truth.

Board: 34mm x 40mm, 2-layer, JLCPCB specs. Grown from the ~25x25mm target
to fit a real CR1220 backup-battery holder + U.FL antenna connector +
breakout headers alongside the 16x12.2mm module without crowding real
component courtyards.

IMPORTANT — generic KiCad pin-header footprints (PinHeader_1xNN_Vertical)
anchor at PIN 1, not the geometric center, and their pads run purely in
+Y from that anchor (verified by reading the actual .kicad_mod pad
coordinates, not assumed). All header placements below account for this.
The CR1220 holder's courtyard was also read directly from its .kicad_mod
(F.CrtYd bounding box) rather than guessed, since its coin-cell body is
much larger than its 2-pad SMD footprint suggests.

Component placement is derived from the NEO-M9N-00B's REAL fetched pad
map (extracted from the .kicad_mod, not assumed):
  pin11 RF_IN   @ local (+6.1, -5.9)  -> right edge, upper-middle
  pin9  VCC_RF  @ local (+6.1, -3.7)  -> right edge
  pin22 V_BCKP  @ local (-6.1, +4.8)  -> left edge, upper
  pin23 VCC     @ local (-6.1, +5.9)  -> left edge, upper
  pin18 SDA     @ local (-6.1, +0.4)  -> left edge, middle
This places the antenna connector on the module's right edge (near
RF_IN) and the backup battery + VCC decoupling on the left edge (near
V_BCKP/VCC) — read off the real footprint, not arbitrary.

RESOLVED 2026-08-25 — SW1 is now placed. This docstring used to say the
reset button was deliberately left off the PCB because "its footprint
proved far larger than its symbol suggested and its pad geometry collided
with the module and every neighboring component regardless of spacing".
That diagnosis was right about the footprint and wrong about the
conclusion: the footprint chosen was SW_Push_1P1T_NO_CK_PTS125Sx43SMTR,
whose courtyard measures 16.8 x 12.5mm on a 34 x 40mm board. The answer
was a different switch, not no switch. Omron's B3U-1000P is 4.8 x 3.3mm,
has an exact KiCad land pattern, and drops into the free area below the
module without touching anything.

The wider lesson is about WHERE that decision lived. It was written in
this docstring and in EVALUATION.md — both Tier 3 — and never in
DEVIATIONS.md, which is the file the gates read. Meanwhile
validate_pcb.py reported "0 schematic-parity issue(s)" on every run,
because it read a kicad-cli field that is only populated with
--schematic-parity, which the pipeline never passed. So a part present in
the schematic and absent from the board was invisible to every check for
the whole life of the design. There is now a real presence check.

This script produces PLACEMENT + real footprints + net-annotated pads +
ground plane (pulled back from the RF corridor) + fiducials + stitching
vias. It does NOT route traces — kicad-cli 10 dropped Specctra DSN
export from the CLI (GUI-only now).
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
PCB_PATH = PROJECT_DIR / 'gnss-neom9n.kicad_pcb'
SCH_SCRIPT = PROJECT_DIR / 'gen_gnss_sch.py'
BLANK_TEMPLATE = Path(__file__).resolve().parents[2] / 'tools/kicad-claude-mcp/src/kicad_claude/templates/blank/blank.kicad_pcb'

REAL_FP_DIR = PROJECT_DIR / 'libs' / 'jlcpcb.pretty'
STD_FP_ROOT = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')

BOARD_W = 34.0
BOARD_H = 40.0
ORIGIN_X = 10.0
ORIGIN_Y = 10.0

# ============================================================
# Step 1: Extract the verified pin->net map from the schematic script
# ============================================================
print("=== GNSS NEO-M9N PCB Generation (Rev1 — real footprints, real nets) ===")
print("Parsing net assignments from gen_gnss_sch.py (verified via ERC, 0 errors)...")


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

# PWR_FLAG symbols (#FLG01-02) are schematic-only ERC satisfiers with no
# physical footprint. SW1 used to be excluded here too; it is placed now,
# so excluding it would strip the nets from its pads and leave a button
# soldered to nothing.
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

print(f"  {len(net_order)} nets declared")

# ============================================================
# Step 4: Footprint fetch + placement + net assignment helpers
# ============================================================
_fp_cache = {}
PLACED_ANCHORS = []  # [(x, y, radius_mm)] in layout space, for via keepout


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


def place_real(ref, value, fp_filename, x, y, rot=0, keepout=5.0):
    fp_def = _fetch_cached(REAL_FP_DIR / f'{fp_filename}.kicad_mod')
    node = pe.add_footprint(
        tree, qualified_lib_id=f'jlcpcb:{fp_filename}', reference=ref,
        value=value, x_mm=ORIGIN_X + x, y_mm=ORIGIN_Y + (BOARD_H - y),
        rotation=rot, fp_def_node=fp_def,
    )
    PLACED_ANCHORS.append((x, y, keepout))
    return _set_pad_nets(node, ref)


def place_std(ref, value, lib_name, fp_filename, x, y, rot=0, keepout=4.0):
    fp_def = _fetch_cached(STD_FP_ROOT / f'{lib_name}.pretty' / f'{fp_filename}.kicad_mod')
    node = pe.add_footprint(
        tree, qualified_lib_id=f'{lib_name}:{fp_filename}', reference=ref,
        value=value, x_mm=ORIGIN_X + x, y_mm=ORIGIN_Y + (BOARD_H - y),
        rotation=rot, fp_def_node=fp_def,
    )
    PLACED_ANCHORS.append((x, y, keepout))
    _set_pad_nets(node, ref)
    # Return the NODE, not the pad count: callers chain set_lcsc() onto this.
    return node


def set_lcsc(fp_node, lcsc):
    """Stamp an 'LCSC Part' property by cloning the footprint's own Value
    node, so the result keeps whatever shape this KiCad version expects."""
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


# LCSC sourcing. Basic tier chosen where one exists; where it does not, the
# note says why the extended part is still the right call.
#
#   C15849  1uF 0603 50V X5R      basic
#   C14663  100nF 0603 50V X7R    basic
#   C15850  10uF 0805 25V X5R     basic
#   C25744  10k 0402 1%           basic
#   C25900  4.7k 0402 1%          basic
#   C88374  Hirose U.FL-R-SMT-1(80)   EXTENDED — genuine Hirose, and the
#           KiCad footprint is the Hirose land pattern. On an RF connector
#           a near-enough footprint is a mismatched launch, so exact match
#           beats basic tier here.
#   C117554 Semtech RCLAMP0521PATCT  EXTENDED — 0.5pF. See the schematic
#           for why a 15pF general-purpose ESD part would ruin the RF.
#   C231329 Omron B3U-1000P           EXTENDED — matches the exact KiCad
#           footprint SW_SPST_B3U-1000P. The basic-tier alternative
#           (C318884, 5.1x5.1mm) has NO matching footprint in the KiCad
#           library, and a wrong land pattern is a dead board.
#   C492401 1x2P 2.54mm header,  C37208 1x6P 2.54mm header  (both THT,
#           hand-soldered; JLCPCB SMT does not fit them)
LCSC = {
    '1uF': 'C15849', '100nF': 'C14663', '10uF': 'C15850',
    '10k': 'C25744', '4.7k': 'C25900',
    'U.FL': 'C88374', 'ESD': 'C117554', 'SW': 'C231329',
    'HDR2': 'C492401', 'HDR6': 'C37208',
}


def to_mcp(x, y):
    """Convert a layout-space (Y-down-from-top) point to MCP absolute
    board coordinates (Y-up-from-bottom-left)."""
    return (ORIGIN_X + x, ORIGIN_Y + (BOARD_H - y))


# ============================================================
# SECTION 1: MOUNTING HOLES + FIDUCIALS
# ============================================================
print("Section 1: Mounting holes (M2.5, x2) + fiducials (x3)...")

for ref, (hx, hy) in [('H1', (4.0, 4.0)), ('H2', (30.0, 4.0))]:
    place_std(ref, 'M2.5', 'MountingHole', 'MountingHole_2.7mm_M2.5_Pad', hx, hy, keepout=4.5)

for ref, (fx, fy) in [('FID1', (17.0, 4.0)), ('FID2', (4.0, 36.0)), ('FID3', (31.0, 30.0))]:
    place_std(ref, 'FIDUCIAL', 'Fiducial', 'Fiducial_1mm_Mask3mm', fx, fy, keepout=3.0)

# ============================================================
# SECTION 2: POWER INPUT + LDO (top edge, left of center)
# ============================================================
print("Section 2: Power input + 3.3V LDO (real XC6206P332MR)...")

# PinHeader_1x02_Vertical anchors at pin1, pads run +Y: pin1@(0,0) pin2@(0,2.54)
set_lcsc(place_std('J1', 'PWR-IN', 'Connector_PinHeader_2.54mm', 'PinHeader_1x02_P2.54mm_Vertical', 9.0, 8.0), LCSC['HDR2'])
set_lcsc(place_std('C1', '1uF', 'Capacitor_SMD', 'C_0603_1608Metric', 14.0, 8.0, keepout=2.0), LCSC['1uF'])
place_real('U1', 'XC6206P332MR', 'SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR', 18.0, 8.0, keepout=3.0)
set_lcsc(place_std('C2', '1uF', 'Capacitor_SMD', 'C_0603_1608Metric', 22.0, 8.0, keepout=2.0), LCSC['1uF'])

# ============================================================
# SECTION 3: NEO-M9N MODULE (real 24-pad castellated footprint)
# ============================================================
print("Section 3: NEO-M9N-00B GNSS module (real footprint, real pad map)...")

MOD_X, MOD_Y = 18.0, 18.0
place_real('U2', 'NEO-M9N-00B', 'GPSM-SMD_24P-L16.0-W12.2-P1.10-BL', MOD_X, MOD_Y, keepout=8.0)

# ============================================================
# SECTION 4: RIGHT-EDGE COMPONENTS (near RF_IN/VCC_RF/SAFEBOOT_N/D_SEL/
#            TIMEPULSE/EXTINT/RESET_N — module pads at local x=+6.1)
# ============================================================
print("Section 4: RF antenna + right-edge pull-ups/test points...")

set_lcsc(place_std('J2', 'U.FL-ANT', 'Connector_Coaxial', 'U.FL_Hirose_U.FL-R-SMT-1_Vertical', 31.0, 11.0, keepout=3.5), LCSC['U.FL'])
set_lcsc(place_std('C5', '100nF', 'Capacitor_SMD', 'C_0603_1608Metric', 27.5, 15.0, keepout=2.0), LCSC['100nF'])

set_lcsc(place_std('R3', '10k', 'Resistor_SMD', 'R_0402_1005Metric', 26.0, 17.0, keepout=2.0), LCSC['10k'])
place_std('TP2', 'RESET_N', 'TestPoint', 'TestPoint_Pad_1.0x1.0mm', 30.0, 17.0, keepout=2.0)

# PinHeader_1x02_Vertical, rot=90 -> pads spread along +X from anchor at
# fixed Y (verified empirically from the generated file's absolute pad
# coordinates — KiCad's rotation sign for this footprint puts the row
# in +X, not -X as first assumed)
set_lcsc(place_std('J4', 'PPS-INT', 'Connector_PinHeader_2.54mm', 'PinHeader_1x02_P2.54mm_Vertical', 28.0, 21.0, rot=90, keepout=3.0), LCSC['HDR2'])

set_lcsc(place_std('R2', '10k', 'Resistor_SMD', 'R_0402_1005Metric', 28.0, 24.0, keepout=2.0), LCSC['10k'])

set_lcsc(place_std('R1', '10k', 'Resistor_SMD', 'R_0402_1005Metric', 26.0, 27.0, keepout=2.0), LCSC['10k'])
place_std('TP1', 'SAFEBOOT_N', 'TestPoint', 'TestPoint_Pad_1.0x1.0mm', 30.0, 27.0, keepout=2.0)

# ============================================================
# SECTION 5: LEFT-EDGE COMPONENTS (near V_BCKP/VCC/SDA/SCL/GND —
#            module pads at local x=-6.1)
# ============================================================
print("Section 5: VCC decoupling, backup battery, I2C pull-ups...")

set_lcsc(place_std('R4', '4.7k', 'Resistor_SMD', 'R_0402_1005Metric', 8.0, 17.0, keepout=2.0), LCSC['4.7k'])
set_lcsc(place_std('R5', '4.7k', 'Resistor_SMD', 'R_0402_1005Metric', 8.0, 19.0, keepout=2.0), LCSC['4.7k'])
set_lcsc(place_std('C6', '100nF', 'Capacitor_SMD', 'C_0603_1608Metric', 8.0, 21.5, keepout=2.0), LCSC['100nF'])
# C3 is the 1uF u-blox names BY NAME, and it is moved right up against the
# module. UBX-19014286 §4.9.1: "Is there a 1 uF cap right next to the module
# VCC pin?" It was 100nF at 2.2mm.
#
# A separate C7 was tried first and would not fit: U2's PADS extend 0.9mm
# past its courtyard (pad 23 centre kicad x=21.900, edge ~20.95), and the
# LDO output column ends at x=19.53, leaving a 1.42mm slot for a part that
# is 1.55mm wide even on its side. Moving the cap that is already there is
# the better answer than wedging in a second one.
#
# At layout x=9.4 (kicad 19.4) C3's courtyard runs 17.875..20.925 — clear of
# U2's pads by 0.03mm and of C6/C4 in y — and its nearest pad sits 0.78mm
# from the VCC pad. That is "right next to" in the sense the checklist means.
set_lcsc(place_std('C3', '1uF', 'Capacitor_SMD', 'C_0603_1608Metric', 9.4, 24.0, keepout=2.0), LCSC['1uF'])
set_lcsc(place_std('C4', '10uF', 'Capacitor_SMD', 'C_0805_2012Metric', 8.0, 26.5, keepout=2.5), LCSC['10uF'])

# CR1220 holder courtyard read from .kicad_mod F.CrtYd: x [-4.93,+8.18],
# y [-3.38,+0.93] relative to anchor -> anchor placed so the courtyard
# clears the module above and J3 header below
# --- Parts that existed in the SCHEMATIC and had no footprint on the board ---
#
# SW1 (reset button) and D1 (RF ESD). See the module docstring for why SW1
# was absent and why the fix was a different switch rather than no switch.
set_lcsc(place_std('SW1', 'RESET', 'Button_Switch_SMD', 'SW_SPST_B3U-1000P',
                   19.5, 30.5, keepout=3.0), LCSC['SW'])


# D1 — RF_IN ESD, at the CONNECTOR end of the RF trace, which is where the
# discharge arrives. J2 courtyard starts at kicad x=38.8; D1 ends at 38.25.
set_lcsc(place_std('D1', 'RCLAMP0521P', 'Diode_SMD', 'D_0402_1005Metric',
                   27.3, 12.8, keepout=1.5), LCSC['ESD'])

place_std('BT1', 'CR1220', 'Battery', 'Battery_Panasonic_CR1220-VCN_Vertical_CircularHoles', 8.0, 33.0, keepout=8.0)

# ============================================================
# SECTION 6: UART/I2C BREAKOUT HEADER (bottom edge)
# ============================================================
print("Section 6: UART/I2C breakout header (bottom edge)...")

# PinHeader_1x06_Vertical, rot=90 -> pads spread +X from anchor at fixed Y
# (empirically verified — see J4 comment above for the rotation-sign note)
set_lcsc(place_std('J3', 'UART-I2C', 'Connector_PinHeader_2.54mm', 'PinHeader_1x06_P2.54mm_Vertical', 17.0, 36.0, rot=90, keepout=4.0), LCSC['HDR6'])

# ============================================================
# Diagnostics
# ============================================================
placed_refs = set(ref for ref, pin in NET_MAP.keys())
print(f"\n{len(placed_refs)} references had net assignments in the schematic script.")

# ============================================================
# SECTION 7: GROUND PLANE (with RF corridor pull-back)
# ============================================================
print("Section 7: Ground plane, pulled back from the RF/antenna corridor "
      "(SS15.5/checklist #18)...")

NOTCH_X0, NOTCH_Y0, NOTCH_Y1 = 22.0, 9.0, 16.0
gnd_layout_pts = [
    (2.0, 2.0), (32.0, 2.0), (32.0, NOTCH_Y0), (NOTCH_X0, NOTCH_Y0),
    (NOTCH_X0, NOTCH_Y1), (32.0, NOTCH_Y1), (32.0, 38.0), (2.0, 38.0),
]
gnd_polygon_mcp = [to_mcp(x, y) for x, y in gnd_layout_pts]

def _solid_connect(zone_node):
    """Solid pad connection rather than thermal-relief spokes. A 0603's
    ground pad has too little perimeter for the two spokes DRC wants, so
    the fill lands one and reports `starved_thermal` — a narrow,
    high-inductance path to the plane. Rule 12.1 asks for thermal relief on
    THROUGH-HOLE pads (J1/J3/J4/BT1 here — see DEVIATIONS.md)."""
    for item in zone_node:
        if isinstance(item, list) and item and str(item[0]) == 'connect_pads':
            item.insert(1, sexpdata.Symbol('yes'))
            return zone_node
    raise RuntimeError('zone has no connect_pads node — KiCad format changed')


# Fill clearance 0.2mm, not the 0.5mm default: at 0.5mm the pour cannot
# reach between the module's 1.1mm-pitch castellated pads and the tracks
# leaving them, and strands ground pads on isolated slivers. Rule 12.1
# floors pour-to-signal at 0.2mm.
_solid_connect(pe.add_zone(tree, net_name='GND', layer='B.Cu',
                           polygon_mcp=gnd_polygon_mcp, name='GND_BOTTOM',
                           fill_clearance_mm=0.2))
_solid_connect(pe.add_zone(tree, net_name='GND', layer='F.Cu',
                           polygon_mcp=gnd_polygon_mcp, name='GND_TOP',
                           fill_clearance_mm=0.2))

# ============================================================
# SECTION 8: GROUND STITCHING VIAS
# ============================================================
print("Section 8: Ground stitching vias (skip all placed-component keepouts)...")



def _near_any_component(x, y):
    return any(((x - kx) ** 2 + (y - ky) ** 2) ** 0.5 < kr
               for kx, ky, kr in PLACED_ANCHORS)


def _in_rf_notch(x, y):
    return x >= NOTCH_X0 - 1.0 and NOTCH_Y0 - 1.0 <= y <= NOTCH_Y1 + 1.0


candidate_pts = []
for x in range(3, 32, 3):
    candidate_pts.append((float(x), 3.0))
    candidate_pts.append((float(x), 38.0))
for y in range(3, 39, 3):
    candidate_pts.append((3.0, float(y)))
    candidate_pts.append((32.0, float(y)))

gnd_id = NET_IDS['GND']
n_skipped = 0
n_placed = 0
placed_via_pts = []
for vx, vy in candidate_pts:
    if _near_any_component(vx, vy) or _in_rf_notch(vx, vy):
        n_skipped += 1
        continue
    # also keep stitching vias >=2mm apart from each other
    if any(((vx - px) ** 2 + (vy - py) ** 2) ** 0.5 < 3.0 for px, py in placed_via_pts):
        n_skipped += 1
        continue
    mx, my = to_mcp(vx, vy)
    pe.add_via(tree, mx, my, drill_mm=0.3, diameter_mm=0.6, net=gnd_id)
    placed_via_pts.append((vx, vy))
    n_placed += 1
print(f"  {n_placed} stitching vias placed ({n_skipped} skipped near keepouts/RF notch)")

# ============================================================
# SECTION 9: SILKSCREEN
# ============================================================
print("Section 9: Silkscreen (board ID + revision)...")

silk_pos = to_mcp(17.0, 2.0)
silk_pos2 = to_mcp(17.0, 39.5)
pe.add_silk_text(tree, text='GNSS NEO-M9N rev1', x_mm=silk_pos[0], y_mm=silk_pos[1], size_mm=1.0)
pe.add_silk_text(tree, text='Lee Taeho', x_mm=silk_pos2[0], y_mm=silk_pos2[1], size_mm=1.0)

# --- Ground escape for C6.2, placed BEFORE routing ------------------------
#
# C6 is the V_BCKP decoupling cap. Its ground pad ends up on a stranded
# sliver of top pour once the router has run, and the post-route bonding
# pass cannot rescue it:
#
#     MANUAL  C6.2 at [18.77, 181.5]: no clear via site within 2.0mm
#
# Same failure mode as baro-bmp390's U1.3 and imu-icm42688's U1.9: a ground
# pad that is fine before routing and unreachable after. Placing the via
# first is what makes the router route around it.
#
# Site measured from the built board (kicad_y = 160 + layout y here):
#   C6 pad 2  kicad (18.775, 181.5) = layout (8.775, 21.5)
#   via       kicad (19.900, 181.5) = layout (9.900, 21.5)
# The stub runs due east along the pad centre line. U2's pads start at
# kicad x=20.95, so the via clears them by 0.75mm; C3 sits below in y and
# R5 is 2.5mm above.
_c6_pad = to_mcp(8.775, 21.5)
_c6_via = to_mcp(9.900, 21.5)
pe.add_via(tree, _c6_via[0], _c6_via[1], drill_mm=0.3, diameter_mm=0.6, net=NET_IDS['GND'])
pe.add_track(tree, _c6_pad[0], _c6_pad[1], _c6_via[0], _c6_via[1],
             width_mm=0.25, layer='F.Cu', net=NET_IDS['GND'])
print("  C6.2 ground escape via + stub placed pre-route")


# ============================================================
# Save
# ============================================================
print("\nSaving PCB...")
sch_io.write_file(PCB_PATH, tree)
print(f"Written to: {PCB_PATH}")
print(f"File size: {PCB_PATH.stat().st_size} bytes")
print()
print("=== PCB generation complete (Rev1, real footprints) ===")
print("Next: run DRC, then route manually in KiCad (GUI DSN export + "
      "Freerouting, or hand-route — kicad-cli 10 dropped CLI DSN export).")
