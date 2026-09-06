#!/usr/bin/env python3
"""Generate baro-bmp390 schematic using kicad-claude-mcp ed API.

Rev 1 — real Bosch BMP390 part (LCSC C5124834, LGA-10 metal-lid), wired
for I2C per Bosch's own application circuit (datasheet §6.3, Figure 25).

Real pin map extracted directly from the fetched .kicad_sym (do NOT trust
memory — see docs/pcb-design-rules.md §15.7):
  1=VDDIO 2=SCK 3=VSS 4=SDI 5=SDO 6=CSB 7=INT 8=VSS 9=VSS 10=VDD
(SCK/SDI double as I2C SCL/SDA per Bosch datasheet §5.2 "I2C interface".)

Circuit decisions, all sourced from the Bosch BMP390 datasheet
(BST-BMP390-DS002-07), not assumed:
  - C1 (VDD decoupling) = 100nF, C2 (VDDIO decoupling) = 100nF
    — datasheet Figure 25 note: "the recommended value for C1, C2 is
    100 nF" (same value the SPI diagram, Figure 24, also recommends).
  - C3 (rail bulk) = 10uF at the J1 rail entry. NOT from the datasheet:
    Figure 25 specifies the sensor, which it assumes sits on a stiff local
    rail, so it says nothing about board-level bulk. This board has no
    regulator — +3V3 arrives down a STEMMA-QT cable — so the bulk has to
    be here. Adafruit's reference puts 10uF (C5) + 0.1uF (C6) on the same
    3.3V net that feeds IC1.VDD/VDDIO; pcb-design-rules.md 3.2 asks for
    bulk per rail. Added 2026-08-25 after the reference comparison caught
    its absence; see DESIGN_BASIS.md.
  - R1/R2 I2C pull-ups (SCK/SDI to VDDIO) = 4.7kOhm — datasheet Figure 25
    note: "for R1, R2 is 4.7 kOhm". This is stricter than the generic
    "10k default" habit — Bosch's own recommended value is used instead.
  - SDO tied directly to VDDIO (+3V3) — datasheet §5.1.1: "Connecting
    SDO to GND results in slave address 0x76; connecting it to VDDIO
    results in slave address 0x77." Hard-tied (not a resistor divider)
    per the Figure 25 reference diagram, giving I2C address 0x77.
    Known limitation: no solder-jumper/pull option to switch to 0x76 —
    acceptable for a single-sensor, fixed-purpose avionics breakout;
    document as deviation from Adafruit's reference (which brings SDO
    to a header pin with a pull-up + solder jumper for field selection).
  - CSB tied directly to VDDIO (+3V3) — selects I2C mode (CSB must not
    float per §15.2; datasheet Figure 25 shows CSB on VDDIO with a
    footnote "*" recommending an MCU GPIO drive it at POR instead of a
    hard tie for extra robustness). This board carries no MCU (STEMMA
    QT delegates all compute to the host), so CSB is hard-tied to VDDIO
    — the same simplification Adafruit's own BMP390 breakout uses
    (their CSB net is pulled high through a resistor rather than driven).
  - INT routed to a test point (TP1) rather than left unbroken — costs
    nothing, lets a host probe or wire an interrupt line later (§15.2).

STEMMA QT / Qwiic connector (JST SH 4-pin, 1mm pitch, per
pcb-design-rules.md §15.6): standard pinout GND, +3V3, SDA, SCL.
Host supplies +3V3 — no onboard regulator (unlike Adafruit's reference,
which regulates from 3-5V VIN + BSS138 level-shifts for 5V hosts). This
board is 3.3V-only; document as a deviation, acceptable since STEMMA QT
hosts are expected to provide a clean 3.3V rail on that connector pin.
"""

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'tools/kicad-claude-mcp/src'))
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'docs'))

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
SCH_PATH = PROJECT_DIR / 'baro-bmp390.kicad_sch'
LIB_DIR = find_symbol_lib_dirs()[0]
JLCPCB_LIB = PROJECT_DIR / 'libs' / 'jlcpcb.kicad_sym'
PROJECT_NAME = 'baro-bmp390'

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
    """Attach a net label to a placed symbol's exact pin via a stub wire
    (see docs/schematic_layout_helpers.py) — still ERC-exact, but doesn't
    land on top of the pin's own auto-drawn name."""
    NETMAP.setdefault(ref, {})[str(pin_number)] = net_name
    ox, oy = symbol_origin[ref]
    return labels.auto(ref, pin_number, net_name, ox, oy)


def no_connect(ref, pin_number):
    NOCONNECT.setdefault(ref, []).append(str(pin_number))
    px, py = ed.get_pin_position(tree, ref, pin_number)
    ed.add_no_connect(tree, px, py)


print("=== baro-bmp390 Schematic Generation (Rev 1 — real BMP390, I2C) ===")

# ============================================================
# SECTION 1: STEMMA QT / QWIIC CONNECTOR (left, x=10-30, y=20-40)
# ============================================================
print("Section 1: STEMMA QT connector...")

place('Connector_Generic', 'Conn_01x04', 'J1', 'STEMMA-QT', 30, 120,
      fp='Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal',
      desc='STEMMA QT / Qwiic I2C connector, JST SH 4-pin 1mm pitch')
pin_label('J1', '1', 'GND')
pin_label('J1', '2', '+3V3')
pin_label('J1', '3', 'I2C_SDA')
pin_label('J1', '4', 'I2C_SCL')


# PWR_FLAG: host supplies +3V3 via the STEMMA QT connector — ERC can't
# see a driver on that net from a generic connector pin, so assert it
# explicitly (same idiom as TMS V3, see docs/pcb-design-rules.md §15.7).
place('power', 'PWR_FLAG', '#FLG01', 'PWR_FLAG', 30, 170)
pin_label('#FLG01', '1', '+3V3')
labels.hide_reference('#FLG01')
labels.hide_property('#FLG01', 'Value')
place('power', 'PWR_FLAG', '#FLG02', 'PWR_FLAG', 60, 170)
pin_label('#FLG02', '1', 'GND')
labels.hide_reference('#FLG02')
labels.hide_property('#FLG02', 'Value')

# ============================================================
# SECTION 2: BMP390 (center, x=50-70, y=25-45)
# ============================================================
print("Section 2: BMP390 barometric pressure sensor (real part, C5124834)...")

place_real('BMP390_C5124834', 'U1', 'BMP390', 110, 120, 0,
           'LGA-10_L2.0-W2.0-P0.50-BL',
           'Bosch BMP390 barometric pressure sensor, LGA-10 (real footprint), I2C mode')

place('Device', 'C', 'C1', '100nF', 70, 150,
      fp='Capacitor_SMD:C_0402_1005Metric',
      desc='BMP390 VDD decoupling, X7R — Bosch datasheet Fig.25 recommended 100nF')
pin_label('C1', '1', '+3V3'); pin_label('C1', '2', 'GND')

place('Device', 'C', 'C2', '100nF', 90, 150,
      fp='Capacitor_SMD:C_0402_1005Metric',
      desc='BMP390 VDDIO decoupling, X7R — Bosch datasheet Fig.25 recommended 100nF')
pin_label('C2', '1', '+3V3'); pin_label('C2', '2', 'GND')

place('Device', 'C', 'C3', '10uF', 50, 150,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='+3V3 rail bulk at the J1 entry, X5R 16V — rule 3.2 + Adafruit '
           'reference C5; the QT cable feeding this rail has no local regulator')
pin_label('C3', '1', '+3V3'); pin_label('C3', '2', 'GND')

place('Device', 'R', 'R1', '4.7k', 165, 150,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='I2C SCL pull-up to VDDIO — Bosch datasheet Fig.25 recommended 4.7kOhm')
pin_label('R1', '1', '+3V3'); pin_label('R1', '2', 'I2C_SCL')

place('Device', 'R', 'R2', '4.7k', 185, 150,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='I2C SDA pull-up to VDDIO — Bosch datasheet Fig.25 recommended 4.7kOhm')
pin_label('R2', '1', '+3V3'); pin_label('R2', '2', 'I2C_SDA')

place('Connector_Generic', 'Conn_01x01', 'TP1', 'INT', 120, 75,
      fp='TestPoint:TestPoint_Pad_1.0x1.0mm',
      desc='BMP390 INT breakout test point (unused in V1, routed per §15.2)')
pin_label('TP1', '1', 'BMP_INT')

# --- Pin-accurate nets on U1 (BMP390), direct to real pin coordinates ---
pin_label('U1', '1', '+3V3')     # VDDIO
pin_label('U1', '2', 'I2C_SCL')  # SCK / SCL
pin_label('U1', '3', 'GND')      # VSS
pin_label('U1', '4', 'I2C_SDA')  # SDI / SDA
pin_label('U1', '5', '+3V3')     # SDO — tied to VDDIO -> I2C address 0x77
pin_label('U1', '6', '+3V3')     # CSB — tied to VDDIO -> selects I2C mode
pin_label('U1', '7', 'BMP_INT')  # INT
pin_label('U1', '8', 'GND')      # VSS
pin_label('U1', '9', 'GND')      # VSS
pin_label('U1', '10', '+3V3')    # VDD

# ============================================================
# SECTION 3: MOUNTING HOLES (no electrical connection — explicit NC)
# ============================================================
print("Section 3: Mounting holes...")

for i, (hx, hy) in enumerate([(250, 150), (250, 120)], start=1):
    ref = f'H{i}'
    place('Connector_Generic', 'Conn_01x01', ref, 'M2', hx, hy,
          fp='MountingHole:MountingHole_2.2mm_M2_Pad',
          desc=f'M2 mounting hole #{i}')
    no_connect(ref, '1')

print(labels.report())
print("Saving schematic...")
sch_io.write_file(SCH_PATH, tree)
print(f"Written to: {SCH_PATH}")
print(f"File size: {SCH_PATH.stat().st_size} bytes")
print()
print("=== Schematic generation complete (Rev 1, real BMP390, pin-accurate) ===")
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
