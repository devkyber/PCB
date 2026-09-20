#!/usr/bin/env python3
"""Generate IMU (ICM-42688-P) breakout schematic using kicad-claude-mcp's
sch_editor `ed` API.

Rev 1 — real LCSC part (C1850418, TDK InvenSense ICM-42688-P, LGA-14),
fetched via easyeda2kicad, pin-accurate wiring sourced directly from the
fetched .kicad_sym (never a remembered/assumed pinout).

Real pin map, extracted from libs/jlcpcb.kicad_sym (verify by reading
that file directly — do not trust this comment blindly on future edits):
  1  = AP_SDO/AP_AD0   (SPI: dedicated SDO output. I2C: address select)
  2  = RESV             (reserved — datasheet: leave unconnected)
  3  = RESV             (reserved — leave unconnected)
  4  = INT1/INT         (interrupt 1, push-pull, active-high default)
  5  = VDDIO            (digital I/O supply, 1.71-3.6V)
  6  = GND
  7  = RESV             (reserved — leave unconnected)
  8  = VDD              (main supply, 1.71-3.6V)
  9  = INT2/FSYNC/CLKIN (interrupt 2 / frame sync / external clock in)
  10 = RESV             (reserved — leave unconnected)
  11 = RESV             (reserved — leave unconnected)
  12 = AP_CS             (SPI chip select, active low)
  13 = AP_SCL/AP_SCLK    (SPI clock / I2C clock)
  14 = AP_SDA/AP_SDIO/AP_SDI (SPI MOSI / I2C data)

Interface: SPI 4-wire (per board spec — higher throughput than I2C,
matches TMS V3's ADC pattern). AP_CS is driven per-transaction by the
host (active-low selects SPI mode per datasheet section 9.2); it is NOT
tied statically, so this device auto-selects I2C by default and only
enters SPI mode once the host actually drives CS low, matching normal
SPI master behavior.

Decoupling: TDK InvenSense app circuit (ICM-42688-P datasheet, revised
values from prior InvenSense/TDK 6-axis IMU app notes, e.g. AN-000156
family) calls for a 100nF X7R/C0G ceramic on VDD and a separate 100nF on
VDDIO, both placed as close as possible to their respective pins — no
single shared cap, no via between cap and pin.

RESV pins (2,3,7,10,11) and the unused INT2/FSYNC/CLKIN pin (9) are
explicitly no-connected rather than left silently absent (§15.2).

Header: 6-pin SPI breakout header (VCC, GND, SCLK, SDI, SDO, CS) per
board spec. INT1 is broken out separately to a test point (not the main
header) to keep the header at exactly 6 pins as specified while still
making the interrupt line probeable/accessible via a flying lead.

STEMMA QT / Qwiic (JST-SH 4-pin, I2C) — evaluated per docs/DESIGN_RULES.md
§15.6 and DELIBERATELY OMITTED this rev: the board is very small
(~20x15mm) and adding a second interface changes the wiring plan
(I2C needs AP_AD0 address-select handling + pull-ups, not just an SDO
passthrough). Rather than guess an unverified LCSC part number for the
connector, this is documented as a known gap for a future SPI+I2C dual-
mode revision — see DESIGN_BASIS.md.
"""

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'tools/kicad-claude-mcp/src'))
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'scripts'))

from pathlib import Path
from kicad_claude.tools.schematic import ed, write_blank_schematic, sch_io
from kicad_claude.utils.kicad_paths import find_symbol_lib_dirs
from schematic_layout_helpers import (LabelPlacer, SymbolPlacer,
                                      set_title_block_from_project)

# Derived from this file's own location, never hardcoded. An absolute
# project path means a copy of this script run from anywhere writes to the
# ORIGINAL board: the enforcement self-test ran a generator inside a
# throwaway sandbox and silently modified the live project, and the check
# that was supposed to prove the ownership guard worked passed for that
# reason rather than because the guard fired.
PROJECT_DIR = Path(__file__).resolve().parent
SCH_PATH = PROJECT_DIR / 'imu-icm42688.kicad_sch'
LIB_DIR = find_symbol_lib_dirs()[0]
JLCPCB_LIB = PROJECT_DIR / 'libs' / 'jlcpcb.kicad_sym'
PROJECT_NAME = 'imu-icm42688'

if SCH_PATH.exists():
    SCH_PATH.unlink()

write_blank_schematic(SCH_PATH)
tree = sch_io.parse_file(SCH_PATH)

# Title, rev and date come from the .kicad_pro's text variables — one
# place a board is named, not two. Without this the sheet prints with
# Title/Date/Rev blank, as all four boards did until 2026-08-26.
set_title_block_from_project(tree, PROJECT_DIR / f'{PROJECT_NAME}.kicad_pro')


def fetch_and_inject(lib_path, lib_name, sym_name):
    sym_def = ed.fetch_symbol_def(lib_path, sym_name)
    qualified = f'{lib_name}:{sym_name}'
    if not ed.lib_symbols_has(tree, qualified):
        entry = ed.make_lib_symbol_entry(sym_def, qualified)
        ed.inject_lib_symbol(tree, entry)
    return sym_def, qualified


GRID_MM = 1.27  # KiCad default schematic grid (50 mil)


def snap(v):
    return round(round(v / GRID_MM) * GRID_MM, 3)


symbol_origin = {}  # ref -> (x, y) placement origin, for pin_label()'s stub direction

# Refuses any symbol placed on top of another (schematic twin of the PCB
# courtyard check) — hand-picked coordinates do not survive a symbol
# changing size, which is how C1/C2 ended up drawn inside U1's body.
symbols = SymbolPlacer(ed, tree)
labels = LabelPlacer(ed, tree, symbols=symbols)


def place(lib_name, sym_name, ref, value, x, y, rot=0, fp='', desc=''):
    """Place a symbol from the standard global KiCad libraries."""
    lib_path = LIB_DIR / f'{lib_name}.kicad_sym'
    sym_def, qualified = fetch_and_inject(lib_path, lib_name, sym_name)
    ed.add_symbol(
        tree,
        qualified_lib_id=qualified,
        reference=ref,
        value=value,
        x_mm=snap(x), y_mm=snap(y),
        rotation=rot,
        sym_def_node=sym_def,
        project_name=PROJECT_NAME,
        footprint=fp,
        description=desc,
    )
    # register() may RELOCATE the symbol to clear an overlap, and it
    # returns the final centre — record that, not the requested (x, y),
    # or pin-exit directions would be computed against a stale origin.
    symbol_origin[ref] = symbols.register(ref) or (snap(x), snap(y))


def place_real(sym_name, ref, value, x, y, rot, fp, desc):
    """Place a real LCSC-fetched symbol from the project's jlcpcb library."""
    sym_def, qualified = fetch_and_inject(JLCPCB_LIB, 'jlcpcb', sym_name)
    ed.add_symbol(
        tree,
        qualified_lib_id=qualified,
        reference=ref,
        value=value,
        x_mm=snap(x), y_mm=snap(y),
        rotation=rot,
        sym_def_node=sym_def,
        project_name=PROJECT_NAME,
        footprint=f'jlcpcb:{fp}',
        description=desc,
    )
    # register() may RELOCATE the symbol to clear an overlap, and it
    # returns the final centre — record that, not the requested (x, y),
    # or pin-exit directions would be computed against a stale origin.
    symbol_origin[ref] = symbols.register(ref) or (snap(x), snap(y))


labels.place_symbol = place  # lets .auto() place `power:*` symbols


# Authoritative pin -> net map, recorded as it is built and written to
# netmap.json at the end of this script. The PCB generator reads that file.
#
# It used to be re-derived by running a regex over THIS FILE's source text,
# matching literal `pin_label('REF', 'PIN', 'NET')` calls. Every net assigned
# from a LOOP over a table was therefore invisible to it, and the PCB got a
# silently incomplete netlist instead of an error. That is how the test
# points on this board ended up with dead, netless pads while every gate
# passed. Propagated from gen_tms_v3_sch.py, which hit this first.
NETMAP: dict[str, dict[str, str]] = {}
NOCONNECT: dict[str, list[str]] = {}


def pin_label(ref, pin_number, net_name):
    """Terminate a placed symbol's exact pin — still the single source of
    connectivity (the stub lands exactly on the pin, ERC-clean) — but via
    a short stub wire so nothing sits on top of the symbol's own auto-
    drawn pin name. See scripts/schematic_layout_helpers.py.

    `.auto()` picks the terminator: a standard global rail (GND, +3V3,
    +5V) gets a **graphical power symbol**, the way a hand-drawn
    schematic does it; every other net gets a text label. That split is
    what keeps the sheet readable — rail text was ~45% of all label text
    on these boards, and it carries no information a ground symbol
    doesn't carry better.

    Power symbols need this call too (empirically: omitting it produces an
    ERC pin_not_connected error) — the stub placement is what keeps the
    text from re-overlapping the symbol's own value text.
    """
    NETMAP.setdefault(ref, {})[str(pin_number)] = net_name
    ox, oy = symbol_origin[ref]
    return labels.auto(ref, pin_number, net_name, ox, oy)


def no_connect(ref, pin_number):
    NOCONNECT.setdefault(ref, []).append(str(pin_number))
    px, py = ed.get_pin_position(tree, ref, pin_number)
    ed.add_no_connect(tree, px, py)


print("=== IMU ICM-42688-P Schematic Generation (Rev 1 — real part) ===")

# ============================================================
# SECTION 1: ICM-42688-P IMU (real LCSC part, C1850418, LGA-14)
# ============================================================
print("Section 1: ICM-42688-P IMU (real part)...")

place_real('ICM-42688-P', 'U1', 'ICM-42688-P', 90, 80, 0,
           'LGA-14_L3.0-W2.5-P0.50-TL',
           '6-axis accel+gyro IMU, LGA-14 (real footprint), SPI mode')

pin_label('U1', '1', 'SPI_SDO')    # AP_SDO/AP_AD0 — SDO in SPI mode
pin_label('U1', '4', 'INT1')       # INT1/INT
pin_label('U1', '5', '+3V3')       # VDDIO
pin_label('U1', '6', 'GND')        # GND
pin_label('U1', '8', '+3V3')       # VDD
pin_label('U1', '12', 'SPI_CS')    # AP_CS
pin_label('U1', '13', 'SPI_SCLK')  # AP_SCL/AP_SCLK
pin_label('U1', '14', 'SPI_SDI')   # AP_SDA/AP_SDIO/AP_SDI — MOSI in SPI mode

# Reserved pins. The previous comment here read "datasheet says leave
# unconnected" and no-connected all five. That is a MISREADING of Table 9,
# and the table draws the distinction explicitly:
#
#   pin 2, 3, 10, 11  ->  "No Connect or Connect to GND"   (either is fine)
#   pin 7             ->  "Connect to GND"                  (mandatory)
#
# Pin 7 has no "No Connect or" prefix. Figure 6 draws it grounded, and so
# does the archived anyshake reference. It was floating on this board.
no_connect('U1', '2')    # RESV — "No Connect or Connect to GND"
no_connect('U1', '3')    # RESV — "No Connect or Connect to GND"
pin_label('U1', '7', 'GND')   # RESV — "Connect to GND" (MANDATORY, Table 9)
no_connect('U1', '10')   # RESV — "No Connect or Connect to GND"
no_connect('U1', '11')   # RESV — "No Connect or Connect to GND"

# INT2 / FSYNC / CLKIN. Also previously a no-connect. Table 9: "FSYNC: Frame
# sync input; Connect to GND if FSYNC not used". It is an INPUT, and this
# design uses neither FSYNC nor an external clock, so the datasheet's
# instruction applies directly — a floating CMOS input on a vibration
# sensor is exactly the thing that picks up noise it should not.
pin_label('U1', '9', 'GND')   # INT2/FSYNC/CLKIN — grounded, FSYNC unused

# ============================================================
# SECTION 2: DECOUPLING — values are the DATASHEET's, not a house default
# ============================================================
#
# This board previously carried 100nF on VDD and 100nF on VDDIO, described
# in a comment as "per TDK app circuit". It is not what the TDK app circuit
# says. DS-000347 Figure 6 (SPI), confirmed identical in rev 1.2 and rev
# 1.6, and matched exactly by the archived anyshake reference:
#
#     VDD   (pin 8)  ->  C1 = 0.1 uF   AND   C2 = 2.2 uF
#     VDDIO (pin 5)  ->  C3 = 10 nF
#
# So the board was missing the 2.2uF bulk entirely and had VDDIO's cap 10x
# too large. Reference designators below follow the DATASHEET's numbering
# so the comparison stays checkable by eye.
#
# Why it matters here rather than being a nicety: DS-000347 §3.3.2 specifies
# "Power Supply Noise ... 10 mV peak-peak". That is five times tighter than
# the BMP390's 50 mVpp, on a part whose gyro output is what a rocket's
# attitude estimate integrates. 100nF alone does not hold a rail to 10 mVpp.
print("Section 2: Decoupling capacitors (DS-000347 Fig 6 values)...")

place('Device', 'C', 'C1', '100nF', 70, 105,
      fp='Capacitor_SMD:C_0402_1005Metric',
      desc='ICM-42688-P VDD HF decoupling, X7R — DS-000347 Fig.6 "C1, 0.1 uF"')
pin_label('C1', '1', '+3V3')
pin_label('C1', '2', 'GND')

place('Device', 'C', 'C2', '2.2uF', 110, 105,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ICM-42688-P VDD bulk, X5R — DS-000347 Fig.6 "C2, 2.2 uF". Was '
           'missing entirely; the 10mVpp supply-noise spec depends on it.')
pin_label('C2', '1', '+3V3')
pin_label('C2', '2', 'GND')

place('Device', 'C', 'C3', '10nF', 130, 105,
      fp='Capacitor_SMD:C_0402_1005Metric',
      desc='ICM-42688-P VDDIO decoupling, X7R — DS-000347 Fig.6 "C3, 10 nF". '
           'Was 100nF, 10x the specified value.')
pin_label('C3', '1', '+3V3')
pin_label('C3', '2', 'GND')

# ============================================================
# SECTION 3: SPI HEADER (6-pin: VCC, GND, SCLK, SDI, SDO, CS)
# ============================================================
print("Section 3: SPI header...")

place('Connector_Generic', 'Conn_01x06', 'J1', 'SPI-HDR', 30, 80,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',
      desc='SPI breakout header: VCC, GND, SCLK, SDI, SDO, CS')
pin_label('J1', '1', '+3V3')     # VCC
pin_label('J1', '2', 'GND')      # GND
pin_label('J1', '3', 'SPI_SCLK')
pin_label('J1', '4', 'SPI_SDI')  # host MOSI -> IMU SDI
pin_label('J1', '5', 'SPI_SDO')  # IMU SDO -> host MISO
pin_label('J1', '6', 'SPI_CS')

# ============================================================
# SECTION 4: TEST POINTS (power rails + interrupt, per §15.4-ish probeability)
# ============================================================
print("Section 4: Test points...")

for tp_ref, tp_val, tp_x, tp_y, tp_net in [
    ('TP1', '+3V3', 60, 50, '+3V3'),
    ('TP2', 'GND', 90, 50, 'GND'),
    ('TP3', 'INT1', 120, 50, 'INT1'),
]:
    place('Connector_Generic', 'Conn_01x01', tp_ref, tp_val, tp_x, tp_y,
          fp='TestPoint:TestPoint_Pad_1.0x1.0mm',
          desc=f'Test point: {tp_net}')
    pin_label(tp_ref, '1', tp_net)

# ============================================================
# SECTION 5: POWER SYMBOLS + PWR_FLAG
# ============================================================
print("Section 5: Power symbols + PWR_FLAG...")

# Every rail pin on this sheet now terminates in its own graphical power
# symbol (see pin_label -> LabelPlacer.auto), so the old pair of lone
# standalone +3V3/GND symbols parked in the corner is redundant and has
# been dropped — they existed only to give the rails a visible presence.
#
# PWR_FLAG is still required: the real fetched EasyEDA symbol doesn't
# carry proper KiCad power-pin-type metadata, so ERC can't find a driver
# for +3V3 even though J1 pin 1 (VCC, from an external host) legitimately
# drives it — same idiom used on TMS V3. Attaching each flag through
# pin_label() gives it a real power symbol on its pin, which is the
# standard KiCad way to draw a PWR_FLAG (and satisfies ERC's per-instance
# pin_not_connected check, which is separate from same-name net joining —
# tested empirically: removing these produced 2 ERC errors).
place('power', 'PWR_FLAG', '#FLG01', 'PWR_FLAG', 25, 120)
pin_label('#FLG01', '1', '+3V3')
labels.hide_reference('#FLG01')
labels.hide_property('#FLG01', 'Value')
place('power', 'PWR_FLAG', '#FLG02', 'PWR_FLAG', 25, 145)
pin_label('#FLG02', '1', 'GND')
labels.hide_reference('#FLG02')
labels.hide_property('#FLG02', 'Value')

# ============================================================
# SECTION 6: MOUNTING HOLES (M2, no electrical connection)
# ============================================================
print("Section 6: Mounting holes...")

for i, (hx, hy) in enumerate([(250, 60), (250, 90)], start=1):
    ref = f'H{i}'
    place('Connector_Generic', 'Conn_01x01', ref, 'M2', hx, hy,
          fp='MountingHole:MountingHole_2.2mm_M2_Pad',
          desc=f'M2 mounting hole #{i}')
    no_connect(ref, '1')

print("Saving schematic...")
sch_io.write_file(SCH_PATH, tree)
print(f"Written to: {SCH_PATH}")
print(f"File size: {SCH_PATH.stat().st_size} bytes")
print()
print("=== Schematic generation complete (Rev 1, real part) ===")
print("Next: Run ERC with kicad-cli, then generate PCB.")


# --- authoritative netmap for the PCB generator -----------------------------
import json as _json
_netmap_path = SCH_PATH.parent / 'netmap.json'
_netmap_path.write_text(_json.dumps(
    {'source': __file__.split('/')[-1], 'nets': NETMAP, 'no_connect': NOCONNECT},
    indent=2) + '\n')
_n = sum(len(v) for v in NETMAP.values())
_nc = sum(len(v) for v in NOCONNECT.values())
print(f"Wrote {_netmap_path.name}: {_n} pin-net assignments, {_nc} explicit no-connects")
