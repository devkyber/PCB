#!/usr/bin/env python3
"""Generate GNSS NEO-M9N breakout schematic using kicad-claude-mcp ed API.

Rev1 — real LCSC parts (via easyeda2kicad fetch), pin-accurate wiring.

Real parts fetched:
  - NEO-M9N-00B (LCSC C5119087) — u-blox standard-precision GNSS module,
    SMD-24P castellated. fidelity=real (symbol + footprint + STEP).
  - XC6206P332MR (LCSC C5446) — 3.3V LDO, SOT-23-3. fidelity=real.

Pin map extracted directly from the fetched NEO-M9N-00B .kicad_sym
(regex over (name "...")(number "...") pairs — NOT from memory, per
docs/DESIGN_RULES.md §15.7):
  1  SAFEBOOT_N        13 GND
  2  D_SEL             14 LNA_EN
  3  TIMEPULSE         15 Reserved
  4  EXTINT            16 Reserved
  5  USB_DM            17 Reserved
  6  USB_DP            18 SDA/SPCS_N
  7  V_USB             19 SCL/SPI-SLK
  8  RESET_N           20 TXD/SPI-MISO
  9  VCC_RF            21 RXD/SPI-MOSI
  10 GND               22 V_BCKP
  11 RF_IN             23 VCC
  12 GND               24 GND

Design decisions (see EVALUATION.md for full reference-design comparison):
  - D_SEL pulled to VCC (not floating) -> selects UART+DDC(I2C) mode
    simultaneously available per u-blox NEO-M9N Integration Manual
    (UBX-19014286): "If open, UART and DDC are available."
  - SAFEBOOT_N: pulled up to VCC (normal boot) + broken to test point so
    it CAN be pulled low for firmware recovery — datasheet explicitly
    recommends the application retain the ability to assert this pin.
    (Prior TMS-derived eval flagged a missing SAFEBOOT_N as a defect on
    a similar board — accounted for here.)
  - RESET_N: has an internal pull-up per datasheet, but an external 10k
    pull-up + reset button to GND is added for robustness/testability.
  - EXTINT, TIMEPULSE (PPS): broken out to a 1x2 header — cheap now,
    per docs/DESIGN_RULES.md §15.2 reasoning.
  - USB_DM/USB_DP/V_USB: left NC — USB interface unused in this design,
    datasheet permits leaving these open.
  - LNA_EN: left NC — no external LNA/bias-tee for an active antenna in
    V1 (module's internal LNA is used with a passive antenna). Documented
    deviation vs. designs that support active antennas.
  - Reserved (15/16/17): left NC per datasheet.
  - V_BCKP: CR1220 primary (non-rechargeable) coin cell, decoupled with
    100nF. No trickle-charge circuit — CR1220 is NOT rechargeable, unlike
    SparkFun's design (see EVALUATION.md comparison table).
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
SCH_PATH = PROJECT_DIR / 'gnss-neom9n.kicad_sch'
LIB_DIR = find_symbol_lib_dirs()[0]
JLCPCB_LIB = PROJECT_DIR / 'libs' / 'jlcpcb.kicad_sym'
PROJECT_NAME = 'gnss-neom9n'

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

# Refuses any symbol placed on top of another — hand-picked coordinates
# do not survive a symbol changing size (real part vs. placeholder).
symbols = SymbolPlacer(ed, tree)
labels = LabelPlacer(ed, tree, stub_mm=3.81, symbols=symbols)


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
    """Attach a net label to a placed symbol's exact pin via a stub wire
    (see scripts/schematic_layout_helpers.py) — still ERC-exact, but doesn't
    land on top of the pin's own auto-drawn name, and raises immediately
    if the stub would cross another net's stub (a silent-short defect
    class found on baro-bmp390 — see StubCrossingError)."""
    NETMAP.setdefault(ref, {})[str(pin_number)] = net_name
    ox, oy = symbol_origin[ref]
    return labels.auto(ref, pin_number, net_name, ox, oy)


def no_connect(ref, pin_number):
    NOCONNECT.setdefault(ref, []).append(str(pin_number))
    px, py = ed.get_pin_position(tree, ref, pin_number)
    ed.add_no_connect(tree, px, py)


print("=== GNSS NEO-M9N Schematic Generation (Rev1, real parts, pin-accurate) ===")

# ============================================================
# SECTION 1: POWER INPUT + LDO (top-left, x=20-70, y=20-45)
# ============================================================
print("Section 1: Power input & 3.3V LDO (real XC6206P332MR, C5446)...")

place('Connector_Generic', 'Conn_01x02', 'J1', 'PWR-IN', 25, 175,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
      desc='3.3-5.5V input, GND')
pin_label('J1', '1', 'VIN')
pin_label('J1', '2', 'GND')

place('Device', 'C', 'C1', '1uF', 50, 170,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='XC6206 input cap (datasheet: 1uF X7R)')
pin_label('C1', '1', 'VIN'); pin_label('C1', '2', 'GND')

# XC6206P332MR pin map (fetched .kicad_sym): 1=GND 2=Vout 3=Vin
place_real('XC6206P332MR', 'U1', 'XC6206P332MR', 75, 178, 0,
           'SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR',
           '3.3V LDO, SOT-23-3 (real footprint)')
pin_label('U1', '3', 'VIN')
pin_label('U1', '1', 'GND')
pin_label('U1', '2', 'VCC')

place('Device', 'C', 'C2', '1uF', 105, 170,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='XC6206 output cap (datasheet: 1uF X7R)')
pin_label('C2', '1', 'VCC'); pin_label('C2', '2', 'GND')

place('power', 'PWR_FLAG', '#FLG01', 'PWR_FLAG', 25, 145)
pin_label('#FLG01', '1', 'VCC')
labels.hide_reference('#FLG01')
labels.hide_property('#FLG01', 'Value')
place('power', 'PWR_FLAG', '#FLG02', 'PWR_FLAG', 50, 145)
pin_label('#FLG02', '1', 'GND')
labels.hide_reference('#FLG02')
labels.hide_property('#FLG02', 'Value')

# ============================================================
# SECTION 2: NEO-M9N MODULE (center, x=80-140, y=60-120)
# ============================================================
print("Section 2: NEO-M9N-00B GNSS module (real part, C5119087)...")

place_real('NEO-M9N-00B', 'U2', 'NEO-M9N-00B', 120, 100, 0,
           'GPSM-SMD_24P-L16.0-W12.2-P1.10-BL',
           'u-blox NEO-M9N-00B standard-precision GNSS, real footprint (STEP available)')

# --- VCC decoupling: 100nF + 10uF near pin 23, per datasheet ---
# C3 = 1uF, not 100nF. UBX-19014286 §4.9.1 design checklist asks by name:
# "Is there a 1 uF cap right next to the module VCC pin?" The module has an
# internal DC/DC converter and the 1uF is the mid-frequency reservoir for
# its switching current; 100nF is too small to supply it and the 0805 bulk
# (C4) is too slow. The 100nF that used to sit here is NOT replaced by a
# second part — see DEVIATIONS.md for why there is no room for one.
place('Device', 'C', 'C3', '1uF', 175, 165,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='NEO-M9N VCC 1uF at the pin — UBX-19014286 §4.9.1 checklist')
pin_label('C3', '1', 'VCC'); pin_label('C3', '2', 'GND')
place('Device', 'C', 'C4', '10uF', 195, 165,
      fp='Capacitor_SMD:C_0805_2012Metric', desc='NEO-M9N VCC bulk decoupling, X5R')
pin_label('C4', '1', 'VCC'); pin_label('C4', '2', 'GND')


# --- VCC_RF decoupling (pin 9), per datasheet even without ext. LNA ---
place('Device', 'C', 'C5', '100nF', 215, 165,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='NEO-M9N VCC_RF decoupling, C0G')
pin_label('C5', '1', 'VCC_RF'); pin_label('C5', '2', 'GND')

# --- V_BCKP decoupling (pin 22) ---
place('Device', 'C', 'C6', '100nF', 235, 165,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='NEO-M9N V_BCKP decoupling, C0G')
pin_label('C6', '1', 'V_BCKP'); pin_label('C6', '2', 'GND')

# --- Pin-accurate nets on U2 (NEO-M9N-00B), direct to real pin coords ---
pin_label('U2', '1', 'SAFEBOOT_N')
pin_label('U2', '2', 'D_SEL')
pin_label('U2', '3', 'TIMEPULSE')
pin_label('U2', '4', 'EXTINT')
no_connect('U2', '5')   # USB_DM — USB interface unused
no_connect('U2', '6')   # USB_DP — USB interface unused
# V_USB. This line previously read:
#     no_connect('U2', '7')   # V_USB — USB interface unused, datasheet permits open
# No u-blox document says that. The Integration Manual (UBX-19014286 R10,
# archived in evidence/files/) says the opposite in three places:
#   §4.2.3  "If the USB interface is not used, the V_USB pin must be
#            connected to GND."
#   §4.9.1  "If USB is not used, connect the V_USB pin to ground."
#   §4.9.6  "If USB is not used connect V_USB to ground."
# and Figure 31, the manufacturer's own minimal design, draws pin 7 with a
# ground symbol on it. Leaving it floating lets the module's USB PHY sit at
# an undefined potential and can back-power that domain through the I/O.
pin_label('U2', '7', 'GND')   # V_USB — USB unused -> GND (UBX-19014286 §4.2.3)
pin_label('U2', '8', 'RESET_N')
pin_label('U2', '9', 'VCC_RF')
pin_label('U2', '10', 'GND')
pin_label('U2', '11', 'RF_IN')
pin_label('U2', '12', 'GND')
pin_label('U2', '13', 'GND')
no_connect('U2', '14')  # LNA_EN — no external LNA/bias-tee in V1 (passive antenna)
no_connect('U2', '15')  # Reserved
no_connect('U2', '16')  # Reserved
no_connect('U2', '17')  # Reserved
pin_label('U2', '18', 'I2C_SDA')
pin_label('U2', '19', 'I2C_SCL')
pin_label('U2', '20', 'UART_TXD')   # module TX -> host RX
pin_label('U2', '21', 'UART_RXD')   # module RX <- host TX
pin_label('U2', '22', 'V_BCKP')
pin_label('U2', '23', 'VCC')
pin_label('U2', '24', 'GND')

# ============================================================
# SECTION 3: RF ANTENNA (right of module, x=140-165, y=80-100)
# ============================================================
print("Section 3: RF antenna connector (U.FL, 50-ohm net)...")

place('Connector', 'Conn_Coaxial', 'J2', 'U.FL-ANT', 200, 105, 0,
      fp='Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical',
      desc='Passive GNSS antenna, U.FL. RF_IN net -> RF_50ohm net class '
           '(target 50-ohm microstrip width, see EVALUATION.md)')
pin_label('J2', '1', 'RF_IN')   # center pin
pin_label('J2', '2', 'GND')     # shield

# D1 — ESD protection on RF_IN. UBX-19014286 §4.9.4 antenna checklist:
# "ESD protection on the RF input is mandatory." The board had none, on the
# one net that leaves the PCB through a connector a person handles.
#
# The PART CHOICE is the whole engineering content here. A general-purpose
# ESD diode (ESD9B5.0ST5G and friends) is 8-15pF. At GPS L1, 1.575GHz,
# 8pF is about 12 ohms to ground — that does not protect a 50-ohm RF line,
# it shunts it, and the fix would cost more signal than the ESD event it
# guards against. RCLAMP0521PATCT is 0.5pF, roughly 200 ohms at L1, which
# is the class of part GNSS front ends actually use.
#
# Placed at the CONNECTOR, not at the module: §4.9.3 says the discharge
# path is the connector, and a protection device downstream of the thing
# it protects is decoration.
place('Device', 'D_TVS', 'D1', 'RCLAMP0521P', 200, 130, 0,
      fp='Diode_SMD:D_0402_1005Metric',
      desc='RF_IN ESD protection, 0.5pF bidirectional — UBX-19014286 §4.9.4 '
           '"ESD protection on the RF input is mandatory"')
pin_label('D1', '1', 'RF_IN')
pin_label('D1', '2', 'GND')

# ============================================================
# SECTION 4: BACKUP POWER (below module, x=80-100, y=125-145)
# ============================================================
print("Section 4: RTC backup power (CR1220 primary coin cell)...")

# Device:Battery_Cell pin map: 1=+, 2=-
place('Device', 'Battery_Cell', 'BT1', 'CR1220', 55, 105, 0,
      fp='Battery:Battery_Panasonic_CR1220-VCN_Vertical_CircularHoles',
      desc='RTC backup, CR1220 primary lithium cell (non-rechargeable, '
           'no trickle-charge circuit — see EVALUATION.md deviation note)')
pin_label('BT1', '1', 'V_BCKP')
pin_label('BT1', '2', 'GND')

# ============================================================
# SECTION 5: SAFEBOOT_N / RESET_N / D_SEL pull-ups + test access
# ============================================================
print("Section 5: SAFEBOOT_N, RESET_N, D_SEL pull-ups...")

place('Device', 'R', 'R1', '10k', 30, 55,
      fp='Resistor_SMD:R_0402_1005Metric', desc='SAFEBOOT_N pull-up (normal boot default)')
pin_label('R1', '1', 'VCC'); pin_label('R1', '2', 'SAFEBOOT_N')

place('Device', 'R', 'R2', '10k', 95, 55,
      fp='Resistor_SMD:R_0402_1005Metric', desc='D_SEL pull-up -> UART+DDC(I2C) mode (not SPI)')
pin_label('R2', '1', 'VCC'); pin_label('R2', '2', 'D_SEL')

place('Device', 'R', 'R3', '10k', 120, 55,
      fp='Resistor_SMD:R_0402_1005Metric', desc='RESET_N external pull-up (redundant w/ internal)')
pin_label('R3', '1', 'VCC'); pin_label('R3', '2', 'RESET_N')

place('Switch', 'SW_Push', 'SW1', 'RESET', 60, 50, 0,
      # Omron B3U-1000P, not the CK PTS125 this used to specify. The
      # PTS125 footprint's courtyard is 16.8 x 12.5mm on a 34 x 40mm board,
      # which is why the PCB generator silently skipped placing SW1 at all.
      # The B3U is 4.8 x 3.3mm and has an exact KiCad land pattern.
      fp='Button_Switch_SMD:SW_SPST_B3U-1000P',
      desc='Manual reset button, RESET_N to GND')
pin_label('SW1', '1', 'RESET_N')
pin_label('SW1', '2', 'GND')

for tp_ref, tp_net, tp_x, tp_y in [
    ('TP1', 'SAFEBOOT_N', 40, 40),
    ('TP2', 'RESET_N', 115, 45),
]:
    place('Connector_Generic', 'Conn_01x01', tp_ref, tp_net, tp_x, tp_y,
          fp='TestPoint:TestPoint_Pad_1.0x1.0mm', desc=f'Test point: {tp_net}')
    pin_label(tp_ref, '1', tp_net)

# ============================================================
# SECTION 6: I2C PULL-UPS + UART/I2C BREAKOUT HEADER
# ============================================================
print("Section 6: I2C pull-ups + UART/I2C breakout header...")

place('Device', 'R', 'R4', '4.7k', 175, 55,
      fp='Resistor_SMD:R_0402_1005Metric', desc='I2C SDA pull-up')
pin_label('R4', '1', 'VCC'); pin_label('R4', '2', 'I2C_SDA')

place('Device', 'R', 'R5', '4.7k', 195, 55,
      fp='Resistor_SMD:R_0402_1005Metric', desc='I2C SCL pull-up')
pin_label('R5', '1', 'VCC'); pin_label('R5', '2', 'I2C_SCL')

place('Connector_Generic', 'Conn_01x06', 'J3', 'UART-I2C', 255, 100,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',
      desc='VCC, GND, UART TXD/RXD, I2C SDA/SCL breakout')
pin_label('J3', '1', 'VCC')
pin_label('J3', '2', 'GND')
pin_label('J3', '3', 'UART_TXD')
pin_label('J3', '4', 'UART_RXD')
pin_label('J3', '5', 'I2C_SDA')
pin_label('J3', '6', 'I2C_SCL')

# ============================================================
# SECTION 7: TIMEPULSE (PPS) / EXTINT BREAKOUT HEADER
# ============================================================
print("Section 7: TIMEPULSE/EXTINT breakout header (cheap now, per SS15.2)...")

place('Connector_Generic', 'Conn_01x02', 'J4', 'PPS-INT', 250, 50,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
      desc='TIMEPULSE (PPS) and EXTINT breakout, unused in V1 but cheap to add')
pin_label('J4', '1', 'TIMEPULSE')
pin_label('J4', '2', 'EXTINT')

# ============================================================
# SECTION 8: MOUNTING HOLES (M2.5, no electrical connection)
# ============================================================
print("Section 8: Mounting holes...")

for i, (hx, hy) in enumerate([(150, 20), (150, 130)], start=1):
    ref = f'H{i}'
    place('Connector_Generic', 'Conn_01x01', ref, 'M2.5', hx, hy,
          fp='MountingHole:MountingHole_2.7mm_M2.5_Pad',
          desc=f'M2.5 mounting hole #{i}')
    no_connect(ref, '1')

print(labels.report())
print("Saving schematic...")
sch_io.write_file(SCH_PATH, tree)
print(f"Written to: {SCH_PATH}")
print(f"File size: {SCH_PATH.stat().st_size} bytes")
print()
print("=== Schematic generation complete (Rev1, real parts, pin-accurate) ===")
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
