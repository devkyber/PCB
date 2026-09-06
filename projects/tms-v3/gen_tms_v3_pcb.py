#!/usr/bin/env python3
"""Generate TMS V3 PCB layout using kicad-claude-mcp's pcb_editor adapter.

Rev E — real footprints (9 fetched LCSC parts + real standard KiCad
footprints for every passive/connector), pin-accurate net assignment
sourced directly from the verified gen_tms_v3_sch.py schematic script.

Fixes vs Rev D (raw-S-expression script):
  - Rev D's `make_smd_fp`/`make_tht_fp` helpers hand-rolled fake 2-pad or
    generic circular-pad footprints for EVERY component, including the 9
    "real" ICs — the SSOP-28/TSSOP-16 footprint *names* were real but the
    actual pad geometry written was always a crude placeholder. No
    component on the old board had real, DRC-accurate pad geometry.
  - Net assignment is now parsed directly out of gen_tms_v3_sch.py's
    pin_label() calls (144 explicit + the J7/J8 Teensy header loops) —
    the single already-ERC-verified source of truth — instead of a
    hand-maintained, drift-prone NET_NAMES table.
  - Fetched EasyEDA footprints (.kicad_mod) use the legacy `(module ...)`
    head; kicad-claude-mcp's fetch_footprint_def requires the modern
    `(footprint ...)` head. Fixed by round-tripping each file through
    real pcbnew (kipython) once — FootprintLoad + FootprintSave upgrades
    the format in place. See docs/pcb-design-rules.md §15.7 (extend to
    footprints, not just symbols).

Board: 100mm × 80mm, 2-layer, JLCPCB specs.
Placement follows pcb-design-rules.md §1.1 sequence (mounting holes →
connectors → power chain → precision analog → digital → decoupling →
crystal → remaining passives → LEDs/test points).

This script produces PLACEMENT + real footprints + net-annotated pads +
ground plane + fiducials + stitching vias. It does NOT route traces —
kicad-cli 10 dropped Specctra DSN export from the CLI (GUI-only now), so
Freerouting can't be driven headlessly from this session. Route manually
in KiCad (Phase 4B, Option 1) or via GUI DSN export + Freerouting.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'tools/kicad-claude-mcp/src'))
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'docs'))

import json
import os

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
PCB_PATH = PROJECT_DIR / 'tms-v3.kicad_pcb'
SCH_SCRIPT = PROJECT_DIR / 'gen_tms_v3_sch.py'
BLANK_TEMPLATE = Path(__file__).resolve().parents[2] / 'tools/kicad-claude-mcp/src/kicad_claude/templates/blank/blank.kicad_pcb'

REAL_FP_DIR = PROJECT_DIR / 'libs' / 'jlcpcb.pretty'
STD_FP_ROOT = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')

BOARD_W = 100.0
BOARD_H = 100.0   # was 80.0 — a Teensy 4.1's 58.4mm pin span plus this parts
                  # list does not fit in 100x80 in either orientation. 100x100
                  # is still inside JLCPCB's cheapest <=100x100 2-layer tier, so
                  # the extra 20mm costs nothing.
ORIGIN_X = 10.0
ORIGIN_Y = 10.0

# ============================================================
# Step 1: Extract the verified pin->net map from the schematic script
# ============================================================
print("=== TMS V3 PCB Generation (Rev E — real footprints, real nets) ===")
print("Parsing net assignments from gen_tms_v3_sch.py (verified via ERC)...")

NETMAP_PATH = PROJECT_DIR / 'netmap.json'
if not NETMAP_PATH.exists():
    raise SystemExit(
        f"{NETMAP_PATH} not found. Run gen_tms_v3_sch.py first — it writes the\n"
        f"authoritative pin->net map. This script used to re-derive that map by\n"
        f"running regexes over the schematic script's SOURCE TEXT, which meant any\n"
        f"change to how nets were assigned there silently produced a stale netlist\n"
        f"here instead of an error."
    )

_nm = json.loads(NETMAP_PATH.read_text())
NET_MAP = {(ref, pin): net
           for ref, pins in _nm['nets'].items()
           for pin, net in pins.items()}

print(f"  {len(NET_MAP)} pin-net assignments recovered")

# PWR_FLAG symbols (#FLG01-03) and power symbols (#PWR01-02) have no
# physical PCB footprint — drop them from the net map, they were
# schematic-only ERC satisfiers
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
# Step 3: Net registry — declare every net used, in the order first seen
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

# Insert (net N "name") declarations after the existing (net 0 "") node
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


def _fetch_cached(path):
    key = str(path)
    if key not in _fp_cache:
        _fp_cache[key] = pe.fetch_footprint_def(path)
    return _fp_cache[key]


def _set_pad_nets(fp_node, ref):
    """Walk a placed footprint's pads and attach (net id "name") using
    NET_MAP[(ref, pad_number)]. Pads with no entry stay on net 0
    (legitimately unused — mounting holes, NC pins)."""
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


def _place(ref, value, lib_id, mod_path, x, y, rot):
    """Shared placement path: bounds-check and collision-check against the
    footprint's REAL extents before writing it into the board."""
    bx, by = design_to_mcp(x, y)                # for pe.add_footprint
    kx, ky = design_to_kicad(x, y)              # for the tracker / pcbnew
    _mod_text = mod_path.read_text()
    tracker.place(ref, _mod_text, kx, ky, rot)
    _PLACED_AT[ref] = (x, y, rot, _mod_text)
    node = pe.add_footprint(
        tree, qualified_lib_id=lib_id, reference=ref, value=value,
        x_mm=bx, y_mm=by, rotation=rot, fp_def_node=_fetch_cached(mod_path),
    )

    # Verify the designator actually landed, and repair it if not.
    #
    # pe.add_footprint takes reference= but does not always apply it: for a
    # footprint whose source file carries `fp_text reference` rather than
    # `property "Reference"`, the library placeholder survives. The XBee
    # socket shipped onto the board as "J**" because of this — silently,
    # since the NET map is keyed by the ref we PASSED, so the nets were all
    # correct and nothing downstream complained. A board with a part called
    # J** has no usable BOM line and no pick-and-place row.
    # The designator lives in one of two shapes depending on which library
    # the footprint came from: KiCad 10 stock parts carry
    # (property "Reference" ...), while hand-authored / older ones carry
    # (fp_text reference ...). Check both.
    found = None
    for sub in node:
        if sch_io.is_call(sub, 'property') and len(sub) > 1 and str(sub[1]) == 'Reference':
            found = sub
            break
        if sch_io.is_call(sub, 'fp_text') and len(sub) > 1 and str(sub[1]) == 'reference':
            found = sub
            break
    if found is None:
        raise SystemExit(f'{ref}: placed footprint carries no reference field at all')
    if str(found[2]) != ref:
        found[2] = ref
        _ref_repairs.append(ref)

    return _set_pad_nets(node, ref)


def place_real(ref, value, fp_filename, x, y, rot=0):
    """Place a real LCSC-fetched footprint (already format-upgraded)."""
    return _place(ref, value, f'jlcpcb:{fp_filename}',
                  REAL_FP_DIR / f'{fp_filename}.kicad_mod', x, y, rot)


# ==========================================================================
# LCSC SOURCING — every line here was looked up with lcsc_search and has
# real JLCPCB stock. Applied by reference designator after placement, so a
# part that moves cannot lose its part number.
#
# Three of these are engineering decisions, not catalogue lookups:
#
#   L1  10uH.  The obvious basic-tier part (C1046, SDFL2012S100KTF) is a
#       15mA multilayer signal choke with 1.15 ohm DCR. The load-cell
#       excitation draws 12.5mA through it — 83% of rating — and 1.15 ohm
#       drops 14mV of the 5V excitation, which is a gain error that drifts
#       with the inductor's temperature. TDK's MLZ2012M100HT000 is 200mA
#       and 680 milliohm in the same 0805 land pattern.
#
#   LED1 "green".  Emerald-green 0603s (515-525nm) have Vf 2.9-3.4V. These
#       LEDs are driven from Teensy GPIOs D3/D4/D5 at 3.3V through 330 ohm,
#       so an emerald green would sit at or below its forward voltage and
#       not light. XL-1608SYGC-06 is yellow-green, 575nm, Vf 2.2V ->
#       (3.3-2.2)/330 = 3.3mA. The classic low-Vf green, chosen for that.
#
#   C8/C9 33pF are C0G, not X7R: a crystal load capacitor whose value moves
#       with temperature and bias detunes the oscillator.
LCSC = {
    # capacitors
    'C1': 'C14663', 'C2': 'C14663', 'C5': 'C14663', 'C6': 'C14663',
    'C7': 'C14663', 'C13': 'C14663', 'C14': 'C14663', 'C16': 'C14663',
    'C10': 'C307331', 'C11': 'C307331',            # 100nF 0402 (U3 AVDD/DVDD)
    'C3': 'C15850', 'C4': 'C15850', 'C12': 'C15850', 'C17': 'C15850',
    'C8': 'C1663', 'C9': 'C1663',                  # 33pF C0G crystal load
    'C15': 'C1615',                                # 330nF LM7805 input
    # resistors
    'R1': 'C11702',                                # 1k relay base
    'R2': 'C25744',                                # 10k base pull-down
    'R3': 'C25076', 'R4': 'C25076', 'R5': 'C25076',        # 100R ADC series
    'R6': 'C25104', 'R7': 'C25104', 'R8': 'C25104',        # 330R LED
    'R9': 'C25105', 'R10': 'C25105', 'R11': 'C25105',      # 33R SPI series
    'R12': 'C25105', 'R13': 'C25105', 'R14': 'C25105',
    # magnetics + optics
    'L1': 'C88172',
    'LED1': 'C965805', 'LED2': 'C2286', 'LED3': 'C84268',
    # connectors
    'J1': 'C2913282', 'J2': 'C2913282',            # AMASS XT30PW-F
    'J3': 'C157991',                               # JST B5B-XH-A
    'J4': 'C144394',                               # JST B3B-XH-A
    'J5': 'C8465',                                 # WJ500V-5.08-2P, 18A
    'J6': 'C98734',                                # AMASS XT60-F
    'J7': 'C2883741', 'J8': 'C2883741',            # 1x24 female socket
    # J9 is one 2x10 footprint but TWO physical 1x10 parts: the XBee's
    # through-hole pads are two rows of ten at 2.00mm pitch. Order 2 per
    # board. Flagged here because a BOM line that reads "J9 x1" against a
    # 20-pad footprint is the kind of quantity error that arrives as a
    # board you cannot populate.
    'J9': 'C2925557',                              # 1x10 female, 2.00mm, x2
}


def apply_lcsc(tree_root):
    """Stamp 'LCSC Part' onto every placed footprint that has a number.

    Applied at the END, by reference designator, rather than at each
    place_std() call: a part number belongs to the PART, and attaching it to
    the placement call means a part that gets moved to a different line can
    silently lose it.
    """
    import copy
    n = 0
    for node in tree_root:
        if not sch_io.is_call(node, 'footprint'):
            continue
        ref = None
        val_node = None
        for item in node:
            if (isinstance(item, list) and item and str(item[0]) == 'property'
                    and len(item) >= 3):
                # str() the key. J9 comes from the hand-authored tms.pretty
                # library and its property names parse as sexpdata Symbols,
                # not str — comparing with == 'Value' silently skipped it,
                # so the XBee socket was the one part on the board with no
                # LCSC number while everything else reported sourced.
                key = str(item[1])
                if key == 'Reference':
                    ref = str(item[2])
                elif key == 'Value':
                    val_node = item
        # Legacy footprints carry `(fp_text reference ...)` instead of a
        # Reference property — J9, the XBee socket, is one. Fall back to it
        # so the part is not silently skipped, and synthesise a property
        # node when there is no Value property to clone.
        if ref is None:
            for item in node:
                if (isinstance(item, list) and len(item) >= 3
                        and str(item[0]) == 'fp_text'
                        and str(item[1]) == 'reference'):
                    ref = str(item[2])
                    break
        code = LCSC.get(ref)
        if not code:
            continue
        if val_node is None:
            node.append([sexpdata.Symbol('property'), 'LCSC Part', code,
                         [sexpdata.Symbol('at'), 0, 0, 0],
                         [sexpdata.Symbol('layer'), 'F.Fab'],
                         [sexpdata.Symbol('hide'), sexpdata.Symbol('yes')]])
            n += 1
            continue
        prop = copy.deepcopy(val_node)
        prop[1], prop[2] = 'LCSC Part', code
        prop.append([sexpdata.Symbol('hide'), sexpdata.Symbol('yes')])
        node.append(prop)
        n += 1
    print(f"  LCSC part numbers stamped on {n} footprint(s)")


def place_std(ref, value, lib_name, fp_filename, x, y, rot=0):
    """Place a real standard KiCad library footprint."""
    return _place(ref, value, f'{lib_name}:{fp_filename}',
                  STD_FP_ROOT / f'{lib_name}.pretty' / f'{fp_filename}.kicad_mod',
                  x, y, rot)


_ref_repairs: list[str] = []
_PLACED_AT: dict[str, tuple[float, float, float, str]] = {}   # ref -> (x, y, rot, mod_text)


def place_near_pin(placer, part_ref, ic_ref, ic_pin, gap_mm=1.3, max_reach_mm=7.0):
    """Place a part as close as physically possible to a specific IC PIN.

    pcb-design-rules.md 2.2 measures decoupling distance pad-to-pad from
    the POWER PIN, and an SSOP-28's power pins are ~10mm apart — so "next
    to U2" and "next to U2's AVDD pin" are different places. Rev E placed
    every cap on an arithmetic grid (x = 22/30/38), which looks tidy, has
    no relationship to any pin, and left all nine bypass caps 3-10mm from
    the pin they bypass. DRC has nothing to say about that: it is a design
    rule, not a manufacturing one, which is exactly why it survived so long.

    `placer` is called as placer(x, y) once a clear spot is found. Offsets
    are tried outward in 8 directions and the first the tracker accepts
    wins, so the result is collision-safe by construction and always the
    closest legal position rather than a guess.
    """
    ic_x, ic_y, ic_rot, ic_mod = _PLACED_AT[ic_ref]
    pads = local_pad_positions(ic_mod)
    if str(ic_pin) not in pads:
        raise SystemExit(f"{ic_ref} has no pad '{ic_pin}' — cannot place {part_ref}")
    lx, ly = pads[str(ic_pin)]
    dx, dy = _rotate_local(lx, ly, ic_rot)
    # local +y grows toward +kicad_y, and design->kicad is a pure offset,
    # so local +y also grows toward +design_y. Subtracting dy here (the
    # first attempt) mirrors every pin about the IC centre, which put C1
    # 9.2mm from the pin it bypasses on the far side of the package.
    pin_x, pin_y = ic_x + dx, ic_y + dy

    reach = gap_mm
    while reach <= max_reach_mm:
        for ux, uy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                       (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
            cx, cy = round(pin_x + ux * reach, 3), round(pin_y + uy * reach, 3)
            try:
                placer(cx, cy)
            except (CourtyardCollisionError, OffBoardError):
                continue
            return cx, cy
        reach += 0.2
    raise SystemExit(
        f"no clear spot for {part_ref} within {max_reach_mm}mm of "
        f"{ic_ref}.{ic_pin} — the parts around that pin need rearranging, "
        f"not the cap moving further away.")


def cap_at(ref, value, fp, ic_ref, ic_pin, gap=0.8, max_reach=7.0):
    lib = 'Capacitor_SMD'
    return place_near_pin(lambda x, y: place_std(ref, value, lib, fp, x, y),
                          ref, ic_ref, ic_pin, gap_mm=gap, max_reach_mm=max_reach)


def place_tms(ref, value, fp_filename, x, y, rot=0):
    """Place a footprint hand-authored for this board (libs/tms.pretty)."""
    return _place(ref, value, f'tms:{fp_filename}',
                  PROJECT_DIR / 'libs' / 'tms.pretty' / f'{fp_filename}.kicad_mod',
                  x, y, rot)


# Note on coordinates: pe.add_footprint uses MCP convention (Y up from
# board bottom-left). Our layout below is specified as (x, y) with Y
# DOWN from the top-left, matching the old script's mental model — so we
# flip Y here (BOARD_H - y) to convert once, centrally.

from pcb_layout_helpers import (PlacementTracker, CourtyardCollisionError,
                                OffBoardError, local_pad_positions, _rotate_local)

# Every placement below goes through this. It raises at GENERATION time on
# a courtyard/pad collision or on any part whose real extents fall outside
# the board outline — the two defect classes that shipped on Rev E.
# NOTE ON FRAMES — this bit bit us. pe.add_footprint() takes MCP coords
# (Y up) and writes KiCad coords (Y down) as kicad_y = PAGE_H - mcp_y. It
# mirrors the ANCHOR only; the footprint's own local geometry is not
# mirrored, so a part still grows toward +kicad_y. Checking collisions in
# MCP space therefore models every part as extending the wrong way, which
# is how J1/J3 read as 8mm apart here and overlapping in DRC. The tracker
# is fed real KiCad coordinates, and the board rectangle in the same frame.
PAGE_H = 210.0
BOARD_RECT = (ORIGIN_X, PAGE_H - ORIGIN_Y - BOARD_H,
              ORIGIN_X + BOARD_W, PAGE_H - ORIGIN_Y)


# There are three frames in play and mixing them up has now caused the same
# bug three separate times (J1/J3 read as clear while overlapping; stitching
# keepouts queried in the wrong half of the board; decoupling caps placed on
# the mirror image of the pin they bypass). So: convert ONLY through these.
#
#   design : what the layout below is written in. Origin bottom-left of the
#            board, +y UP. Human-friendly, matches how the sections read.
#   mcp    : what pe.add_footprint / pe.add_via take. +y UP from the page
#            bottom, offset by ORIGIN.
#   kicad  : what actually lands in the file and what pcbnew reports.
#            +y DOWN from the page top.
#
# Derivation, verified against pcbnew on this board:
#   mcp_y   = ORIGIN_Y + (BOARD_H - design_y)
#   kicad_y = PAGE_H - mcp_y = PAGE_H - ORIGIN_Y - BOARD_H + design_y
#           = 100 + design_y   (for ORIGIN_Y=10, BOARD_H=100, PAGE_H=210)
# so design and kicad differ by a pure OFFSET, not a flip: a footprint's
# local +y (which grows toward +kicad_y) also grows toward +design_y.
KICAD_Y0 = PAGE_H - ORIGIN_Y - BOARD_H


def design_to_mcp(x, y):
    return ORIGIN_X + x, ORIGIN_Y + (BOARD_H - y)


def design_to_kicad(x, y):
    return ORIGIN_X + x, KICAD_Y0 + y


def kicad_to_design(x, y):
    return x - ORIGIN_X, y - KICAD_Y0

tracker = PlacementTracker(
    # 0.5mm, matching rule 1.2's reflow assembly clearance.
    #
    # 0.25mm was tried, on the theory that a footprint's courtyard already
    # encodes IPC clearance so adding 0.5mm charges the design twice. It
    # bought ~0.25mm on decoupling distance and cost 12 silk-over-copper
    # and 7 silk-overlap violations plus 5 more unrouted connections. Not
    # a good trade: the decoupling numbers were already inside the range
    # where the remaining error is dominated by package geometry, and the
    # silkscreen damage is real. Kept at 0.5mm.
    margin_mm=0.5,
    board_mm=BOARD_RECT,
    edge_margin_mm=0.3,
    # TMS_PLACE_SURVEY=1 collects every placement problem in one run
    # instead of stopping at the first. For the fix-up loop only.
    survey=bool(os.environ.get('TMS_PLACE_SURVEY')),
)

unassigned_report = []

# ============================================================
# SECTION 1: MOUNTING HOLES (corners, 3.5mm inset)
# ============================================================
print("Section 1: Mounting holes + fiducials...")

for ref, (hx, hy) in [('H1', (4.5, 4.5)), ('H2', (95.5, 4.5)),
                       ('H3', (4.5, 95.5)), ('H4', (95.5, 95.5))]:
    place_std(ref, 'M3', 'MountingHole', 'MountingHole_3.2mm_M3_Pad', hx, hy)

# Fiducials — JLCPCB PCBA requires ≥3. Placed in open silkscreen-free
# corners, clear of both mounting holes and the nearest components
# (D3/TP1 sit near (10-14, 8-12); LED1/TP9 near the right/bottom edges).
# FID1 moved from (12,92) to (30,95): the real XT60 at J1 is 16.5 x 9.2mm
# where the old header was 3.6 x 6.2mm, and it now occupies the top-left
# corner the fiducial used to sit in. L-pattern preserved.
# FID3 moved from (92,72). Measured, not estimated: the XBee socket's
# courtyard is x 73.30..98.70, y 34.97..61.70 — it reaches almost to the
# right board edge, which three guesses in a row got wrong. The free slot
# is the 6.2mm band between the LED cluster (ends y 28.8) and the XBee
# (starts y 34.97). Fiducials end up spread (30,95) / (86,92) / (94,32).
for i, (fx, fy) in enumerate([(30, 95), (86, 92), (94, 32)], start=1):
    ref = f'FID{i}'
    place_std(ref, 'FIDUCIAL', 'Fiducial', 'Fiducial_1mm_Mask3mm', fx, fy)

# ============================================================
# SECTION 2: CONNECTORS (left/bottom edges)
# ============================================================
print("Section 2: Connectors...")

# CONNECTOR SET, finalised 2026-08-26 to the owner's spec. Every one of
# these is a real, LCSC-orderable part with a matching KiCad land pattern —
# the previous revision had four of them as PinHeader_1x02_P2.54mm while
# their Values claimed XT60s and screw terminals.
#
#   J1, J2  battery in      AMASS XT30PW-F   C2913282   15A, board-mount
#   J3      load cell       JST XH 1x05      C157991    polarised, latching
#   J4      pressure        JST XH 1x03      C144394    polarised, latching
#   J5      ARM switch      Phoenix MKDS     screw terminal (PDR section 7:
#                                            "PCB provides a 2-pin screw
#                                            terminal for the switch wires")
#   J6      IGNITER OUT     AMASS XT60-F     C98734     nichrome firing lead
#   J7, J8  Teensy 4.1      PinSocket 1x24   C2883741   FEMALE — the Teensy
#                                            plugs in and can be removed
#
# XT30PW rather than XT60 on the batteries: 15A is ample (the electronics
# draw under an amp, the igniter pulse a few amps) and the XT30 is far
# smaller on a board that is already full. XT60 is kept where the current
# actually is — the igniter output.
#
# ANCHOR/EXTENT WARNING — all measured from the .kicad_mod, relative to the
# PIN 1 anchor, because none of these are centred on it:
#   XT30PW-F   x -4.65..+9.65   y -14.55.. +2.25   (14.3 x 16.8, body in -y)
#   XT60-F     x -4.65..+11.85  y  -4.60.. +4.60   (16.5 x  9.2)
#   XH 1x05    x -2.95..+12.95  y  -2.85.. +3.90   (15.9 x  6.8)
#   XH 1x03    x -2.95.. +7.95  y  -2.85.. +3.90   (10.9 x  6.8)
# Left-edge budget. The Teensy socket rows span nearly the full width and
# fix three usable bands:  A = design y 8..64.9,  B = 68.6..80.2 (11.6mm),
# C = 83.8..92.0 (8.2mm).  Two XT30PWs are 16.8mm tall each, so they take
# band A between them; the two XH sensor connectors are 6.75mm and drop
# into B and C. Trying to fit all four into band A overlapped J2/J3 by
# 14.8mm — the bands, not the edge length, are the real constraint.
place_std('J1', 'XT30PW-ELEC', 'Connector_AMASS', 'AMASS_XT30PW-F_1x02_P2.50mm_Horizontal', 6, 58)
# J2 (igniter battery) and J6 (igniter output) are kept TOGETHER on the
# left. IGN_GND is a separate net from GND — the igniter is an isolated
# power domain — so it cannot ride the ground pour and has to be routed as
# a normal trace between exactly two pads: J2.2 and J6.2. With J2 left and
# J6 right, that net crossed the whole board and the router could not
# finish it. Adjacent, it is a few millimetres.
#
# J5 (ARM switch terminal) stays beside K1 on the right, so IGN_ARM_RET is
# short too; IGN_BATT+ and IGN_OUT are the two nets that cross, which is
# the same topology the board routed successfully before.
place_std('J2', 'XT30PW-IGN', 'Connector_AMASS', 'AMASS_XT30PW-F_1x02_P2.50mm_Horizontal', 6, 38)
place_std('J3', 'LOAD-CELL', 'Connector_JST', 'JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical', 4, 74)
place_std('J4', 'PRESSURE', 'Connector_JST', 'JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical', 4, 87.5)
place_std('J5', 'ARM-SW', 'TerminalBlock_Phoenix', 'TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal', 90, 68)
place_std('J6', 'IGN-OUT', 'Connector_AMASS', 'AMASS_XT60-F_1x02_P7.20mm_Vertical', 6, 14)

# ============================================================
# SECTION 3: POWER SUPPLY CHAIN (near J1, top-left)
# ============================================================
print("Section 3: Power supply chain (real SS54, LM7805)...")

place_real('D3', 'SS54', 'SMA_L4.4-W2.8-LS5.4-R-RD', 22, 12)  # +6mm: the XT60 at J6 reaches design x=17.85

# U4 is a real TO-263 body (~10x9mm) — give it more room than the old
# placeholder-footprint spacing allowed (courtyard was overlapping C15/C16)
place_real('U4', 'LM7805', 'TO-263-2_L10.1-W9.1-P5.08-LS15.2-BR-1', 36, 12)
# Rule 6.1: input cap at VIN (pin 1), output cap at VOUT (pin 3), both <=5mm.
cap_at('C15', '330nF', 'C_0603_1608Metric', 'U4', 1)
cap_at('C16', '100nF', 'C_0603_1608Metric', 'U4', 3)

# ============================================================
# SECTION 4: EXCITATION LC FILTER
# ============================================================
print("Section 4: Excitation LC filter...")

place_std('L1', '10uH', 'Inductor_SMD', 'L_0805_2012Metric', 22, 19)  # +6mm: clears the XT60 at J6
place_std('C17', '10uF', 'Capacitor_SMD', 'C_0805_2012Metric', 27, 19)  # follows L1; the two form the excitation LC filter

# ============================================================
# SECTION 5: ADS1256 THRUST ADC (real SSOP-28, real crystal, real TVS)
# ============================================================
print("Section 5: ADS1256 thrust ADC (real parts)...")

place_real('U2', 'ADS1256IDBR', 'SSOP-28_L10.2-W5.3-P0.65-LS7.8-BL', 30, 50)
# Crystal FIRST, before the decoupling caps.
#
# Rule 1.1 lists decoupling at step 6 and the crystal at step 7, but both
# are "place against the IC before routing". In practice the order has to
# run largest-first: a 12.4mm crystal cannot fit into whatever a handful
# of already-placed 0603s left behind, and place_near_pin correctly
# refuses rather than quietly drifting it out to 10mm. Rule 5.1 (<=5mm
# from the oscillator pins) is a tighter constraint than 2.2 is on any
# single cap, so the crystal gets first claim on the space.
place_near_pin(
    lambda x, y: place_real('Y1', '7.68MHz', 'CRYSTAL-SMD_L11.4-W4.7-LS12.4', x, y, 90),
    'Y1', 'U2', 19, gap_mm=4.5, max_reach_mm=11.0)
# Load caps at the crystal's own pads (rule 5.1: <=3mm), reusing the same
# pin-relative search — Y1 pad 1 = XTAL1, pad 2 = XTAL2.
cap_at('C8', '22pF', 'C_0402_1005Metric', 'Y1', 1, gap=1.2)
cap_at('C9', '22pF', 'C_0402_1005Metric', 'Y1', 2, gap=1.2)

# Decoupling placed against the PIN it serves, not on a grid.
# Pin map from netmap.json: 1 = AVDD(+5V), 14/15/16 = DVDD(+3V3),
# 3/4 = VREF_N/VREF_P, 18/19 = XTAL2/XTAL1.
# Order matters, and it is the documented hierarchy (rule 2.2, "cap
# hierarchy: smallest value closest to the pin; bulk caps can be further
# away"). Placing the 10uF bulk first let it take the 2.6mm slot beside
# DVDD and pushed the 100nF that actually does the high-frequency work out
# to 6.2mm — the opposite of the rule. All 100nF first, bulk afterwards.
cap_at('C1', '100nF', 'C_0603_1608Metric', 'U2', 1)     # AVDD bypass
cap_at('C2', '100nF', 'C_0603_1608Metric', 'U2', 1)     # second AVDD bypass
cap_at('C5', '100nF', 'C_0603_1608Metric', 'U2', 14)    # DVDD bypass
cap_at('C6', '100nF', 'C_0603_1608Metric', 'U2', 15)    # DVDD bypass
cap_at('C7', '100nF', 'C_0603_1608Metric', 'U2', 4)     # VREF_P/VREF_N reference
cap_at('C3', '10uF', 'C_0805_2012Metric', 'U2', 1)      # AVDD bulk
cap_at('C4', '10uF', 'C_0805_2012Metric', 'U2', 16)     # DVDD bulk

place_real('D2', 'PESD5V0S2BT', 'SOT-23_L2.9-W1.3-P1.90-LS2.4-BR', 18, 54)
place_std('R3', '100R', 'Resistor_SMD', 'R_0402_1005Metric', 18, 45)
place_std('R4', '100R', 'Resistor_SMD', 'R_0402_1005Metric', 18, 42)
place_std('R9', '33R', 'Resistor_SMD', 'R_0402_1005Metric', 46, 52)
place_std('R10', '33R', 'Resistor_SMD', 'R_0402_1005Metric', 46, 49)
place_std('R11', '33R', 'Resistor_SMD', 'R_0402_1005Metric', 46, 46)

# ============================================================
# SECTION 6: ADS1220 PRESSURE ADC (real TSSOP-16)
# ============================================================
print("Section 6: ADS1220 pressure ADC (real part)...")

place_real('U3', 'ADS1220IPWR', 'TSSOP-16_L5.0-W4.4-P0.65-LS6.4-BL', 30, 28)
# TSSOP-16's real courtyard is tighter than the old placeholder assumed —
# push decoupling caps further from center
# Pin map: 12 = AVDD(+5V), 13 = DVDD(+3V3).
# Pin map: 12 = AVDD(+5V), 13 = DVDD(+3V3). 100nF first, bulk after.
# U3's AVDD (pin 12) and DVDD (pin 13) are ADJACENT on a 0.65mm-pitch
# TSSOP-16, and TI SBAS501 section 9.3.3 requires BOTH to be decoupled with
# at least 0.1uF placed "as close to the power-supply pins as possible".
# They are different nets, so one cap cannot serve both.
#
# Two 0603s cannot do it. Side by side they need 3.3mm of width, which puts
# the outer one 2.05mm from its pin — over rule 2.2 — and auto-placement
# landed C11 at 2.86mm. Two 0402s need 2.04mm and both land 1.38mm from
# their own pin. A smaller package is also the better decoupling part here:
# less ESL in the path that matters.
#
# MEASURED, then TESTED. A +0.5mm shift was tried here to open the escape
# channel north of U3 pin 15 (ADS1220_DOUT_ADC), which at these positions is
# 0.57mm wide against the 0.654mm a 0.254mm track with clearance needs — so
# that one pin cannot escape north, consistently, across eight independent
# routing attempts.
#
# The shift made the board WORSE: best-of-8 went from a consistent 2
# unconnected to a consistent 5, because moving the caps closed C6's ground
# escape and J7's +3V3 approach. Reverted. The lesson is that on a board
# this dense, a local fix has to be measured GLOBALLY — "8 attempts, same
# number every time" is what distinguishes a structural block from router
# noise, and it is also what proves a change helped or hurt.
#
# Placed explicitly, rotated 90 so the long axis points at the pin row.
# Measured: pin 12 at kicad (40.330, 125.130), pin 13 at (39.680, 125.130).
# U3's courtyard reaches y~123.76, so the caps cannot sit closer than
# y=122.7 without overlapping the package.
#
# Even with 0402s, BOTH pins cannot be inside 2mm. The pins are 0.65mm
# apart, the caps need ~1.6mm of separation not to collide, so pushing one
# to 1.98mm pushes the other to 2.06mm. DVDD gets the closer position and
# AVDD's 2.06mm is DECLARED in DEVIATIONS.md rather than hidden — the
# binding requirement is TI SBAS501 section 9.3.3 ("as close to the
# power-supply pins as possible"), which is met; rule 2.2's 2mm is a house
# number that this package geometry cannot honour on both pins at once.
place_std('C10', '100nF', 'Capacitor_SMD', 'C_0402_1005Metric', 31.0, 22.7, rot=90)
place_std('C11', '100nF', 'Capacitor_SMD', 'C_0402_1005Metric', 29.4, 22.7, rot=90)
cap_at('C13', '100nF', 'C_0603_1608Metric', 'U3', 13)
cap_at('C14', '100nF', 'C_0603_1608Metric', 'U3', 13)
cap_at('C12', '10uF', 'C_0805_2012Metric', 'U3', 12)
place_std('R5', '100R', 'Resistor_SMD', 'R_0402_1005Metric', 20, 28)  # +2mm: the real XT60 at J2 reaches design x=17.85
place_std('R12', '33R', 'Resistor_SMD', 'R_0402_1005Metric', 46, 31)
place_std('R13', '33R', 'Resistor_SMD', 'R_0402_1005Metric', 46, 28)
place_std('R14', '33R', 'Resistor_SMD', 'R_0402_1005Metric', 46, 25)

# ============================================================
# SECTION 7: TEENSY 4.1 SOCKET HEADERS
# ============================================================
print("Section 7: Teensy 4.1 socket headers (rotated, bounds-checked)...")

# Rev E placed these VERTICALLY at (55, 37) and (70.24, 37) and shipped with
# a comment calling the resulting overhang a "KNOWN ISSUE". It was not a
# tuning problem: a 1x24 2.54mm header's pin span is 23 x 2.54 = 58.42mm,
# and its footprint ANCHOR IS PIN 1, not its centre — so an anchor sitting
# comfortably mid-board still puts pin 24 some 60mm away. Both headers ran
# 16.3mm past the bottom edge.
#
# Fixed three ways, in order of importance:
#   1. rot=90 so the 58.42mm span runs along the board's 100mm width
#      instead of its (then) 80mm height;
#   2. the board grew to 100x100 (same JLCPCB price tier) to make room;
#   3. placement now goes through PlacementTracker, which knows the real
#      anchor offset and raises OffBoardError rather than emitting a comment.
#
# Row assignment matches gen_tms_v3_sch.py:
#   J7 = ROW A (Vin/GND/3.3V side), J8 = ROW B (GND/D0.../side).
# Rows sit 15.24mm (0.6in) apart — the Teensy 4.1's header spacing.
# Pin 1 of both rows is the USB end; TEENSY_USB silkscreen marks it.
TEENSY_X   = 26.0        # pin-1 x; span runs +x to 20 + 58.42 = 78.42
TEENSY_Y_A = 82.0        # J7 row A
TEENSY_Y_B = TEENSY_Y_A - 15.24   # J8 row B, 0.6in away

place_std('J7', 'TEENSY-L', 'Connector_PinSocket_2.54mm',
          'PinSocket_1x24_P2.54mm_Vertical', TEENSY_X, TEENSY_Y_A, rot=90)
place_std('J8', 'TEENSY-R', 'Connector_PinSocket_2.54mm',
          'PinSocket_1x24_P2.54mm_Vertical', TEENSY_X, TEENSY_Y_B, rot=90)

# ============================================================
# SECTION 8: XBEE 3 SOCKET
# ============================================================
print("Section 8: XBee 3 through-hole socket (real 2.00mm geometry)...")

# Rev E used Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Vertical.
# Every part of that is wrong for an XBee: the pitch is 2.00mm not 2.54mm,
# the two rows are 22.0mm (0.866in) apart not 2.0mm, and the numbering runs
# counter-clockwise (1-10 down one side, 11-20 up the other) not odd/even.
# The module would not have fitted the board at all.
# tms:XBee_THT_20pin_P2.00mm is hand-authored from Digi 90001543 p.36 —
# see SIGNOFF.md, it wants a physical fit check before you order.
place_tms('J9', 'XBEE3', 'XBee_THT_20pin_P2.00mm', 75.0, 42.0)

# ============================================================
# SECTION 9: IGNITION CIRCUIT (real relay, transistor, flyback diode)
# ============================================================
print("Section 9: Ignition circuit (real HF46F relay, MMBT3904, 1N4148WS)...")

# HF46F's real body is 20.5mm long — old placeholder spacing had Q1
# sitting inside the relay's courtyard. Widened, but kept clear of J7's
# column (x=55) since J7/J8 span nearly the full board height (see note
# above section 7).
place_real('K1', 'HF46F-G/5-HS1T', 'RELAYS-TH_HF46F-G-XX-HS1-XXX', 65, 14)
place_real('Q1', 'MMBT3904', 'SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR', 58, 25)
place_real('D1', '1N4148WS', 'SOD-323_L1.8-W1.3-LS2.5-RD-1', 66, 25)
place_std('R1', '1k', 'Resistor_SMD', 'R_0402_1005Metric', 52, 30)
place_std('R2', '10k', 'Resistor_SMD', 'R_0402_1005Metric', 52, 33)

# ============================================================
# SECTION 10: LEDs
# ============================================================
print("Section 10: Status LEDs...")

place_std('LED1', 'GREEN', 'LED_SMD', 'LED_0603_1608Metric', 90, 28)
# LED cluster (R6-R8 / LED1-3) shifted +4mm in x: the real MKDS terminal
# block at J6 reaches design x=88.13, and the XBee socket J9 reaches 87.7.
place_std('R6', '330R', 'Resistor_SMD', 'R_0402_1005Metric', 90, 24)
place_std('LED2', 'RED', 'LED_SMD', 'LED_0603_1608Metric', 94, 28)
place_std('R7', '330R', 'Resistor_SMD', 'R_0402_1005Metric', 94, 24)
place_std('LED3', 'YELLOW', 'LED_SMD', 'LED_0603_1608Metric', 98, 28)
place_std('R8', '330R', 'Resistor_SMD', 'R_0402_1005Metric', 98, 24)

# ============================================================
# SECTION 11: TEST POINTS
# ============================================================
print("Section 11: Test points...")

for ref, val, tx, ty in [
    # Bottom edge strip — clear of the power chain (y~7-17) and the
    # analog columns (x 14-46, y 24-60).
    ('TP1', 'VBAT', 14.0, 4.0), ('TP2', '+5V', 22.0, 4.0), ('TP3', '+3V3', 30.0, 4.0),
        # Rule 1.2: the load-cell and pressure probe points carry precision
    # analog, so they are kept away from the LM7805 and the relay coil
    # rather than sharing the bottom edge with them.
    # x 12 -> 20: the real XT60 at J2 reaches design x=17.85.
    ('TP4', 'AINP', 20.0, 38.0), ('TP5', 'AINN', 20.0, 35.0), ('TP6', 'PRES', 20.0, 32.0),
    ('TP7', 'DRDY1', 62.0, 4.0), ('TP8', 'DRDY2', 70.0, 4.0), ('TP9', 'RELAY', 50.0, 4.0),  # was (78,4): the MKDS terminal block at J5 now occupies design x 76.96..88.13
]:
    place_std(ref, val, 'TestPoint', 'TestPoint_Pad_1.0x1.0mm', tx, ty)

# Check which pins never got a net (diagnostic, not a failure)
placed_refs = set(ref for ref, pin in NET_MAP.keys())
print(f"\n{len(placed_refs)} references had net assignments in the schematic script.")

# ============================================================
# SECTION 12: Ground plane, silkscreen, stitching
# ============================================================
print("Section 12: Ground plane, fiducial silkscreen, board ID...")

board_polygon = [
    (ORIGIN_X, ORIGIN_Y), (ORIGIN_X + BOARD_W, ORIGIN_Y),
    (ORIGIN_X + BOARD_W, ORIGIN_Y + BOARD_H), (ORIGIN_X, ORIGIN_Y + BOARD_H),
]
def _solid_connect(zone_node):
    """Solid pad connection instead of thermal-relief spokes.

    KiCad's default 0.5mm thermal gap / 0.5mm bridge leaves too little pad
    perimeter on 0402s and on fine-pitch IC grounds for the two spokes DRC
    requires, so the fill lands one and reports `starved_thermal` — a
    narrow, high-inductance path from a ground pad to the plane, on a board
    doing 24-bit measurements.

    pcb-design-rules.md 12.1 asks for thermal relief on THROUGH-HOLE pads,
    for hand-solderability. This board HAS through-hole pads that matter
    (J1-J9, the Teensy and XBee sockets), so that trade is real here in a
    way it was not on the sensor boards — recorded in DEVIATIONS.md.
    """
    for item in zone_node:
        if isinstance(item, list) and item and str(item[0]) == 'connect_pads':
            item.insert(1, sexpdata.Symbol('yes'))
            return zone_node
    raise RuntimeError('zone has no connect_pads node — KiCad format changed')


# Fill clearance 0.2mm rather than 0.5mm. Rule 12.1 floors pour-to-signal at
# 0.2mm; JLCPCB's own minimum is 0.127mm. At 0.5mm the pour cannot reach
# between fine-pitch pads and the tracks leaving them, which is what strands
# ground pads on slivers.
_z_bot = _solid_connect(pe.add_zone(
    tree, net_name='GND', layer='B.Cu', polygon_mcp=board_polygon,
    name='GND_BOTTOM', fill_clearance_mm=0.3))
# TOP-LAYER GROUND POUR: deliberately omitted.
#
# Rule 3.2's first line is "on a 2-layer board, use the bottom layer as a
# continuous ground pour... route on top and pour ground on bottom". The
# same table also says "ground pour on both layers", and on a sparse board
# both are achievable. On this one they conflict, and the top pour loses.
#
# With the top poured, the routed traces cut it into islands. KiCad deletes
# unconnected islands (island_removal_mode 0), so any GND pad that ended up
# on one simply stopped being connected to anything — 12 unconnected items,
# all of them ADC ground pins, and no amount of stitching fixed it because
# an inner pin of a 0.65mm-pitch SSOP has no clear path out to a via.
#
# Without the top pour, GND is an ordinary routed net on the top layer and
# the autorouter connects every ground pad down to the bottom plane the
# same way it connects everything else. The bottom pour is the real plane
# either way, which is what rules 3.1 and 3.2 actually care about.
_z_top = None

# Solid pad connection on both ground zones, not thermal reliefs.
# Thermal spokes on a 0.65mm-pitch IC's GND pad are so narrow that KiCad
# reports them "starved" (10 such violations on the first routed build),
# and a starved thermal is a real impedance in the return path — the one
# thing an ADC front end cannot afford. These are all reflow-soldered
# parts, so the usual argument for thermal reliefs (hand-soldering heat)
# does not apply. The through-hole parts that ARE hand-soldered (J1-J6,
# K1) sit on the perimeter with plenty of copper, and JLCPCB reflows them
# anyway if assembly is ordered.
# connect_pads is a direct child of (zone ...), NOT of (zone (fill ...)).
# Getting that wrong fails silently: the zone still writes, DRC still runs,
# and the only symptom is the starved_thermal violations coming back.
for _zone in (_z_bot,):
    for _i, _item in enumerate(_zone):
        if sch_io.is_call(_item, 'connect_pads'):
            # 0.2mm, not 0.5mm. Rule 12.1 floors pour-to-signal clearance
            # at 0.2mm and JLCPCB's own minimum is 0.127mm; at 0.5mm the
            # pour cannot reach between fine-pitch pads and the tracks
            # leaving them, which is what strands ground pads on slivers.
            # 0.3mm: the pour must clear the WIDEST netclass on the board
            # (HighCurrent, 0.3mm) or a Power-class via lands 0.15mm from
            # the pour and DRC fails on the zone, not on anything a layout
            # change could move.
            _zone[_i] = [sexpdata.Symbol('connect_pads'), sexpdata.Symbol('yes'),
                         [sexpdata.Symbol('clearance'), 0.3]]

# Ground stitching vias around the perimeter, every ~10mm.
#
# Keepouts come from the placement tracker, which already knows every
# part's real board-frame extents. Rev E kept a hand-written KEEPOUT_PTS
# list here instead — a second copy of the mounting-hole and fiducial
# coordinates. When the board was resized and those parts moved, the list
# did not, so vias were drilled inside pads and through other holes.
# Anything generated onto the board after placement must ask the tracker.
VIA_DRILL, VIA_DIA = 0.3, 0.6
VIA_CLEARANCE = 0.5      # copper-to-copper breathing room around the via pad
VIA_EDGE_KEEPOUT = 1.0   # keep via copper off the routed board edge

# Full-board grid, not just the perimeter. With a ground pour on both
# layers, a top-side pour gets chopped into islands by the routed traces;
# an island with no via to the bottom pour is dead copper, and any GND pad
# sitting on it reads as unconnected. Perimeter-only stitching left 12
# such items on the first routed build. A 8mm grid ties the islands down.
perimeter_pts = []
# Ground stitching is NOT done here. It happens after routing, in
# docs/stitch_vias.py — which is now invoked by docs/pipeline.py's route
# stage. It used to say "called from build.sh", and build.sh had since been
# reduced to a shim that execs pipeline.py, so for a while NOTHING called it
# and this board's ground bonding quietly stopped happening. A comment
# naming the caller is not the same as a caller.
#
# A via placed at placement time is an obstacle the router must then avoid.
# Generating a grid here took this board's unrouted connections from 1 to 8
# at 8mm pitch, and 4 at 12mm — the vias were competing with the traces they
# exist to support. Stitching is filler for copper nobody used, so it can
# only be computed once you know what nobody used.

# ------------------------------------------------------------------
# Net classes — written HERE, not hand-edited into the .kicad_pro
# ------------------------------------------------------------------
#
# These lived only in tms-v3.kicad_pro, which nothing regenerates and which
# reverted an edit made to it earlier in the session. A design rule that
# lives in a file no generator owns is a rule that drifts.
#
# Power clearance is 0.2mm, NOT 0.3mm. At 0.3mm the rule was physically
# unsatisfiable: the ADS1256's SSOP-28 land pattern has 0.286mm between
# adjacent pads, so U2 violated it on three pin pairs no layout change
# could fix. A clearance rule wider than the finest package on the board
# cannot be met by definition.
#
# 0.2mm is still 1.6x JLCPCB's 0.127mm minimum, and the Power class carries
# +5V and +3V3 only. VBAT (up to 16.8V) and the IGN_* firing nets keep
# 0.3mm on the HighCurrent class, which is where the voltage and current
# actually are.
NETCLASSES = {
    'Default':     dict(clearance=0.2, track_width=0.254, via_diameter=0.6, via_drill=0.3),
    'Power':       dict(clearance=0.2, track_width=0.5,   via_diameter=0.8, via_drill=0.4),
    'HighCurrent': dict(clearance=0.3, track_width=1.0,   via_diameter=1.0, via_drill=0.5),
}
_pro = PCB_PATH.with_suffix('.kicad_pro')
if _pro.is_file():
    _d = json.loads(_pro.read_text())
    _ns = _d.setdefault('net_settings', {})
    for _c in _ns.get('classes', []):
        _want = NETCLASSES.get(_c.get('name'))
        if _want:
            _c.update(_want)
    _pro.write_text(json.dumps(_d, indent=2))
    print(f"  net classes written to {_pro.name}: " +
          ", ".join(f"{k} clr={v['clearance']}" for k, v in NETCLASSES.items()))

# ------------------------------------------------------------------
# Silkscreen pass
# ------------------------------------------------------------------
# Rev E printed a reference designator for all 69 footprints. On a board
# this dense that is mostly noise: an "R13" rendered next to an 0402 is
# unreadable at actual size, and the collisions it caused accounted for
# 18 of the DRC violations.
#
# What silkscreen is actually for on this board is a person at a bench
# with a wire in their hand. So: keep designators on the parts someone
# needs to identify by eye (ICs, the relay, discrete semis, LEDs,
# connectors), drop them on passives and mechanical items, and spend the
# freed space on connector FUNCTION labels instead.
# Designators kept on the physical silkscreen: things a person needs to
# identify by eye at a bench. Small SMD discretes (D, Q, Y) came off the
# list after the caps moved in beside their ICs — a "D2" printed next to a
# SOT-23 that is 1mm from a 0603 is unreadable at actual size and just
# collides with its neighbours. They stay on F.Fab, where the assembly
# drawing and KiCad both still show them.
SILK_KEEP_PREFIXES = ('U', 'J', 'K', 'LED')
SILK_DROP_EXACT = set()          # nothing forced off beyond the rule below

def _ref_prefix_kept(ref: str) -> bool:
    if ref in SILK_DROP_EXACT:
        return False
    # TP/FID/H are mechanical or probe-only: the netlist and the fab
    # drawing carry them, the silkscreen does not need to.
    if ref[:2] in ('TP', 'FI') or (ref[0] == 'H' and ref[1:].isdigit()):
        return False
    return ref.startswith(SILK_KEEP_PREFIXES)

def _ref_property(fp_node):
    """The footprint's (property "Reference" ...) node, or None."""
    for sub in fp_node:
        if sch_io.is_call(sub, 'property') and len(sub) > 1 and str(sub[1]) == 'Reference':
            return sub
    return None


n_hidden = 0
for child in tree:
    if not sch_io.is_call(child, 'footprint'):
        continue
    prop = _ref_property(child)
    if prop is None:
        continue
    ref = str(prop[2])
    if _ref_prefix_kept(ref):
        continue
    # Move the designator to F.Fab: still in the design and on the fab
    # drawing, just not printed on the physical board.
    for k, item in enumerate(prop):
        if sch_io.is_call(item, 'layer'):
            prop[k] = [sexpdata.Symbol('layer'), 'F.Fab']
    n_hidden += 1

# Shrink the designators that remain to 0.8mm — JLCPCB's MINIMUM silkscreen
# height per pcb-design-rules.md 10.1, not below it. 0.7mm was tried first
# and produced 15 text_height DRC violations: the rules doc gives 0.8mm min
# / 1.0mm recommended, and "smaller looks tidier" is not a licence to go
# under a fab limit. 1.0mm (KiCad's default) was the main source of the
# silk_overlap hits on this density of board, so 0.8mm is the compromise.
n_shrunk = 0
for child in tree:
    if not sch_io.is_call(child, 'footprint'):
        continue
    prop = _ref_property(child)
    if prop is None or not _ref_prefix_kept(str(prop[2])):
        continue
    for item in prop:
        if sch_io.is_call(item, 'effects'):
            for sub in item:
                if sch_io.is_call(sub, 'font'):
                    for m, f in enumerate(sub):
                        if sch_io.is_call(f, 'size'):
                            sub[m] = [sexpdata.Symbol('size'), 0.8, 0.8]
                        elif sch_io.is_call(f, 'thickness'):
                            sub[m] = [sexpdata.Symbol('thickness'), 0.12]
                    n_shrunk += 1
if _ref_repairs:
    print(f"  repaired {len(_ref_repairs)} footprint reference(s) pe.add_footprint "
          f"left as library placeholders: {', '.join(_ref_repairs)}")
print(f"  {n_shrunk} kept designators set to 0.8mm (JLCPCB silkscreen minimum)")
print(f"  {n_hidden} passive/mechanical/discrete designators moved to F.Fab "
      f"(kept on silk: ICs, connectors, relay, LEDs)")

# Board ID — top edge, clear of the Teensy band (design y 80-84) and the
# corner mounting holes. Coordinates are MCP (Y up); see the frame note above.
def _silk(text, x, y, size=1.0):
    pe.add_silk_text(tree, text=text, x_mm=ORIGIN_X + x,
                     y_mm=ORIGIN_Y + (BOARD_H - y), size_mm=size)

_silk('TMS V3', 50, 96, size=2.0)
_silk('rev1 - Lee Taeho', 50, 92, size=1.0)

# Connector function labels — what the board actually needs at a bench.
# Placed just inboard of each connector's pin column (connectors sit at
# x=5, growing +y from their anchor).
for _txt, _x, _y in [
    ('BATT 4S',   11, 87),
    ('LOAD CELL', 11, 76),
    ('PRESSURE',  11, 61),
    ('IGN BATT',  11, 46),
    ('ARM SW',    11, 36),
    ('E-MATCH',   11, 26),
]:
    _silk(_txt, _x, _y, size=1.0)

# Module orientation marks. A plug-in module socket with no pin-1/USB
# reference is an invitation to insert it backwards.
_silk('TEENSY 4.1', 45, 77, size=1.5)
_silk('USB', 20, 77, size=1.2)
_silk('XBEE 3', 86, 32, size=1.5)
_silk('PIN 1', 70, 45, size=1.0)

print("\n--- placement tracker ---")
print(tracker.report())
_probs = [w for w in tracker.warnings if w.startswith(('OFF-BOARD', 'COLLIDE'))]
if _probs and not tracker.survey:
    raise SystemExit(f"{len(_probs)} placement problem(s) — not writing the board.")

print("\nSaving PCB...")
apply_lcsc(tree)
sch_io.write_file(PCB_PATH, tree)
print(f"Written to: {PCB_PATH}")
print(f"File size: {PCB_PATH.stat().st_size} bytes")
print()
print("=== PCB generation complete (Rev E, real footprints) ===")
print("Next: run DRC, then route traces (Phase 4B — manual in KiCad or")
print("GUI DSN export + Freerouting; kicad-cli 10 dropped CLI DSN export).")
