#!/usr/bin/env python3
"""Generate TMS V3 schematic using kicad-claude-mcp ed API.

Rev E — real LCSC parts (via easyeda2kicad fetch), pin-accurate wiring.

Fixes vs Rev D (found while integrating real fetched parts):
  - Placeholder Connector_Generic symbols replaced with real fetched
    symbols for all 9 specialty ICs (ADS1256, ADS1220, LM7805, MMBT3904,
    1N4148WS, PESD5V0S2BT, SS54, HF46F relay, AT-41CD2 crystal).
  - EVERY net — not just the 9 ICs — now attaches via get_pin_position()
    at the symbol's real pin coordinates, instead of a label dropped at a
    hand-guessed (x,y). The Rev D script placed labels near where a pin
    was assumed to be; ERC showed this left ~184 pins actually
    unconnected (J1-J9, TP1-9, passives) despite looking wired on screen.
  - ADS1256 RESET/SYNCPDWN were floating (§15.2 violation) — now tied to
    DVDD. ADS1220 CLK was floating — now tied to GND (internal osc mode).
  - ADS1220 REFP0/REFN0/AIN0-REFP1/AIN3-REFN1 (unused when running on the
    internal 2.048V reference) get explicit no-connect flags instead of
    being silently absent.
  - J1 pin 2 (battery GND) was never tied to GND in Rev D — fixed.
  - XBee footprint was 'PinHeader_2x10_P2.00mm_Vertical' in a 2.54mm-pitch
    library (didn't exist) — fixed to the correct 2.54mm generic 2x10.
  - Mounting holes get explicit no-connect flags (they're mechanical only).

Rev F — module socket pinouts rebuilt from vendor documents.

The "known limitation" that Rev E carried forward — J7/J8 (Teensy 4.1) and
J9 (XBee 3) represented as generic headers — was not a cosmetic
placeholder. Because neither part is LCSC-sourced, fetch_part_library
couldn't retrieve them, and the pin ASSIGNMENTS were invented to match
rather than copied from the vendor's pinout. That put +5V on the Teensy's
GND pin (a dead short of the 5V rail on first power-up) and tied the
XBee's UART output to ground while leaving its actual ground pin floating.

Both are now built from documents archived in evidence/files/ and read as
rendered pages:
  - evidence/files/card11a_rev4_web.pdf   PJRC Teensy 4.1 pinout card rev4
  - evidence/files/xbee3_hardware_ref.pdf Digi 90001543, p.36 + p.45-46

Rule this revision establishes: a header net map with no comment naming the
document it came from is not finished work. See docs/WORKFLOW.md
Step 2.3b.

Circuit architecture:
  VBAT (4S LiPo 12-16.8V) → SS54 Schottky (D3) → LM7805 → 5V rail
  Teensy 4.1 onboard LDO → 3.3V rail
  ADS1256 (SPI0): Load cell thrust measurement, PGA=64, buffer OFF
  ADS1220 (SPI1): Pressure sensor, single-ended AIN2 vs AIN1-tied-GND
  XBee 3 (UART2): 2.4 GHz telemetry
  HF46F relay + NPN driver: Ignition circuit
  LC filter on excitation rail (L1 + C17)
  TVS protection on ADC inputs (D2)
  33Ω series resistors on all SPI lines (F-04)

HF46F pinout confirmed from Hongfa datasheet (wiring diagram, bottom view,
fetched and rendered from source.hongfa.com/Uploads/Product/PDF/HF46F_en.pdf):
  Pin 1, Pin 6 = coil (non-polarized, either terminal)
  Pin 2 = COM (pole)
  Pin 3 = NO (normally open contact)
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
SCH_PATH = PROJECT_DIR / 'tms-v3.kicad_sch'
LIB_DIR = find_symbol_lib_dirs()[0]
JLCPCB_LIB = PROJECT_DIR / 'libs' / 'jlcpcb.kicad_sym'
PROJECT_NAME = 'tms-v3'

if SCH_PATH.exists():
    SCH_PATH.unlink()

write_blank_schematic(SCH_PATH)
tree = sch_io.parse_file(SCH_PATH)

# A3, not the A4 default. This board is 69 components; on A4 the blocks
# have to be packed tightly enough that terminators from adjacent blocks
# collide no matter how good the placement rules are, and the auto-
# relocation search starts pushing parts under the title block. A3 is
# double the area and is a completely standard schematic sheet size —
# reach for it before compromising legibility.
set_title_block_from_project(tree, PROJECT_DIR / f'{PROJECT_NAME}.kicad_pro',
                             paper='A3')


def fetch_and_inject(lib_path, lib_name, sym_name):
    sym_def = ed.fetch_symbol_def(lib_path, sym_name)
    qualified = f'{lib_name}:{sym_name}'
    if not ed.lib_symbols_has(tree, qualified):
        entry = ed.make_lib_symbol_entry(sym_def, qualified)
        ed.inject_lib_symbol(tree, entry)
    return sym_def, qualified


GRID_MM = 1.27  # KiCad default schematic grid (50 mil) — real fetched
                # symbol pins are on this grid, so component *centers*
                # must be too or absolute pin positions land off-grid.

# Every placement coordinate below was authored against A4. The sheet is
# now A3 (see the paper override above), so scale them onto the larger
# page rather than leaving the design huddled in one corner with half the
# sheet blank. A3 is exactly sqrt(2) larger on each axis, so one uniform
# factor preserves every functional grouping the coordinates encode —
# blocks stay together, they just get more air between them.
SHEET_SCALE = 420.0 / 297.0


def snap(v):
    return round(round(v * SHEET_SCALE / GRID_MM) * GRID_MM, 3)


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
# netmap.json at the end of this script. gen_tms_v3_pcb.py reads that file.
#
# It used to re-derive the map by running regexes over THIS FILE's source
# text, which meant every change to how nets are assigned here (a dict
# instead of a list, a loop instead of literal calls) silently broke the
# PCB's netlist rather than erroring. That is how J7/J8 kept a stale map.
NETMAP: dict[str, dict[str, str]] = {}
NOCONNECT: dict[str, list[str]] = {}


def pin_label(ref, pin_number, net_name):
    """Attach a net label to a placed symbol's exact pin via a stub wire
    (see scripts/schematic_layout_helpers.py) — still ERC-exact, but doesn't
    land on top of the pin's own auto-drawn name, and raises immediately
    if the stub would cross another net's stub (silent-short defect class
    found on baro-bmp390 — see StubCrossingError)."""
    NETMAP.setdefault(ref, {})[str(pin_number)] = net_name
    ox, oy = symbol_origin[ref]
    return labels.auto(ref, pin_number, net_name, ox, oy)


def no_connect(ref, pin_number):
    NOCONNECT.setdefault(ref, []).append(str(pin_number))
    px, py = ed.get_pin_position(tree, ref, pin_number)
    ed.add_no_connect(tree, px, py)


print("=== TMS V3 Schematic Generation (Rev E — real parts, pin-accurate) ===")

# ============================================================
# SECTION 1: POWER INPUT & REGULATION (top-left, x=20-80, y=20-60)
# ============================================================
print("Section 1: Power input & regulation...")

place('Connector_Generic', 'Conn_01x02', 'J1', 'XT30PW-ELEC', 20, 30,
      # AMASS XT30PW-F, board-mount. 15A is ample for the electronics
      # rail; XT60 is reserved for the igniter output where the firing
      # current actually is. LCSC C2913282.
      fp='Connector_AMASS:AMASS_XT30PW-F_1x02_P2.50mm_Horizontal',
      desc='Electronics battery XT60U-F')
pin_label('J1', '1', 'VBAT')
pin_label('J1', '2', 'GND')  # was unterminated in Rev D — fixed

place_real('SS54_C22452', 'D3', 'SS54', 32, 30, 0,
           'SMA_L4.4-W2.8-LS5.4-R-RD',
           'Reverse polarity protection, SMA (real footprint)')
pin_label('D3', '1', 'VBAT')          # anode
pin_label('D3', '2', 'VBAT_PROT')     # cathode — protected rail

place('Device', 'C', 'C15', '330nF', 42, 20,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='LM7805 input cap, X7R 50V')
pin_label('C15', '1', 'VBAT_PROT')
pin_label('C15', '2', 'GND')

place_real('LM7805_C22467097', 'U4', 'LM7805', 52, 30, 0,
           'TO-263-2_L10.1-W9.1-P5.08-LS15.2-BR-1',
           '5V 1.5A regulator, TO-263 (real footprint)')
pin_label('U4', '1', 'VBAT_PROT')     # IN
pin_label('U4', '2', 'GND')           # GND
pin_label('U4', '3', '+5V')           # OUT

place('Device', 'C', 'C16', '100nF', 62, 20,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='LM7805 output cap, C0G')
pin_label('C16', '1', '+5V')
pin_label('C16', '2', 'GND')


# PWR_FLAG markers: real fetched EasyEDA symbols don't carry proper
# "power output" pin electrical typing (e.g. LM7805 OUT comes through as
# generic Passive), so ERC can't find a driver for +5V/+3V3 even though
# they're legitimately driven by U4/Teensy's onboard LDO. This is the
# standard KiCad idiom for asserting "this net is intentionally driven."
place('power', 'PWR_FLAG', '#FLG01', 'PWR_FLAG', 15, 25)
pin_label('#FLG01', '1', '+5V')
labels.hide_reference('#FLG01')
labels.hide_property('#FLG01', 'Value')
place('power', 'PWR_FLAG', '#FLG02', 'PWR_FLAG', 160, 116)
pin_label('#FLG02', '1', '+3V3')
labels.hide_reference('#FLG02')
labels.hide_property('#FLG02', 'Value')
place('power', 'PWR_FLAG', '#FLG03', 'PWR_FLAG', 15, 35)
pin_label('#FLG03', '1', 'GND')
labels.hide_reference('#FLG03')
labels.hide_property('#FLG03', 'Value')

# ============================================================
# SECTION 2: EXCITATION LC FILTER (below power, x=70-95, y=25-40)
# ============================================================
print("Section 2: Excitation LC filter (F-05/D-04)...")

place('Device', 'L', 'L1', '10uH', 75, 28,
      fp='Inductor_SMD:L_0805_2012Metric',
      desc='Excitation LC filter inductor')
pin_label('L1', '1', '+5V')
pin_label('L1', '2', '+5V_FILT')

place('Device', 'C', 'C17', '10uF', 90, 28,
      fp='Capacitor_SMD:C_0805_2012Metric',
      desc='Excitation LC filter cap, X5R 16V')
pin_label('C17', '1', '+5V_FILT')
pin_label('C17', '2', 'GND')

# ============================================================
# SECTION 3: ADS1256 — THRUST ADC (center-left, x=20-90, y=60-110)
# ============================================================
print("Section 3: ADS1256 thrust ADC (real part, C28186)...")

# U2 — ADS1256IDBR, real symbol, SSOP-28. Pin map confirmed from fetched
# .kicad_sym: 1=AVDD 2=AGND 3=VREFN 4=VREFP 5=AINCOM 6-13=AIN0-7
# 14=SYNCPDWN 15=RESET 16=DVDD 17=DGND 18=XTAL2 19=XTAL1CLKIN
# 20=CS 21=DRDY 22=DOUT 23=DIN 24=SCLK 25=D0CLKOUT 26-28=D1-3
place_real('ADS1256IDBR', 'U2', 'ADS1256IDBR', 55, 85, 0,
           'SSOP-28_L10.2-W5.3-P0.65-LS7.8-BL',
           '24-bit ADC, SSOP-28 (real footprint), SPI0')

place('Device', 'C', 'C1', '100nF', 25, 60,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='ADS1256 AVDD decoupling, C0G, ≤2mm from pin')
pin_label('C1', '1', '+5V'); pin_label('C1', '2', 'GND')
place('Device', 'C', 'C2', '100nF', 25, 78,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='ADS1256 AVDD decoupling #2, C0G')
pin_label('C2', '1', '+5V'); pin_label('C2', '2', 'GND')
place('Device', 'C', 'C3', '10uF', 25, 96,
      fp='Capacitor_SMD:C_0805_2012Metric', desc='ADS1256 AVDD bulk, X5R 16V')
pin_label('C3', '1', '+5V'); pin_label('C3', '2', 'GND')
place('Device', 'C', 'C4', '10uF', 25, 114,
      fp='Capacitor_SMD:C_0805_2012Metric', desc='ADS1256 AVDD bulk #2, X5R 16V')
pin_label('C4', '1', '+5V'); pin_label('C4', '2', 'GND')
place('Device', 'C', 'C5', '100nF', 78, 60,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='ADS1256 DVDD decoupling, C0G')
pin_label('C5', '1', '+3V3'); pin_label('C5', '2', 'GND')
place('Device', 'C', 'C6', '100nF', 78, 78,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='ADS1256 DVDD decoupling #2, C0G')
pin_label('C6', '1', '+3V3'); pin_label('C6', '2', 'GND')
place('Device', 'C', 'C7', '100nF', 25, 132,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='ADS1256 VREFP-VREFN decoupling (F-13), C0G')
pin_label('C7', '1', 'VREF_P'); pin_label('C7', '2', 'VREF_N')

place_real('AT-41CD2-7.68MHZ', 'Y1', '7.68MHz', 55, 105, 90,
           'CRYSTAL-SMD_L11.4-W4.7-LS12.4',
           'ADS1256 clock, NDK AT-41CD2, real footprint')
pin_label('Y1', '1', 'XTAL1'); pin_label('Y1', '2', 'XTAL2')

# C8/C9 = 33pF, not the 22pF this board carried. The crystal's LOAD
# CAPACITANCE is the spec that sets these, and it was unverified until
# 2026-08-25 because no crystal datasheet was on file — evidence/index.yaml
# recorded it as a known gap.
#
# Resolved: the 7.68MHz HC-49S-SMD parts that fit this footprint specify
# CL = 20pF (Huiyuan HY7680M49SSMDOB2R20, LCSC C5265772, now archived;
# Changjing CJ03-076802020B20 agrees; ECS's part is 18pF).
#
#     C_L = (C8 * C9) / (C8 + C9) + C_stray
#
# At 22pF that is 11 + C_stray ~= 15pF against a 20pF requirement, so the
# crystal is under-loaded and oscillates FAST. On the ADS1256 the crystal
# IS the conversion clock, so a frequency error is a sample-rate error in
# every thrust and pressure measurement this board exists to take — and it
# would never show up as a failure, only as data that is quietly wrong.
#
#     C8 = C9 = 2 * (20 - C_stray);  C_stray ~= 4pF  ->  32pF  ->  33pF E6
#
# [OWNER] C_stray is layout-dependent (pad + trace + pin), so 4pF is an
# estimate. Confirm by measuring the actual oscillator frequency on the
# assembled board and trimming these if it is off.
place('Device', 'C', 'C8', '33pF', 45, 100,
      fp='Capacitor_SMD:C_0402_1005Metric', desc='Crystal load cap, C0G')
pin_label('C8', '1', 'XTAL1'); pin_label('C8', '2', 'GND')
place('Device', 'C', 'C9', '33pF', 45, 120,
      fp='Capacitor_SMD:C_0402_1005Metric', desc='Crystal load cap, C0G')
pin_label('C9', '1', 'XTAL2'); pin_label('C9', '2', 'GND')

place('Device', 'R', 'R9', '33R', 88, 65,
      fp='Resistor_SMD:R_0402_1005Metric', desc='SPI0 MOSI series protection (F-04)')
pin_label('R9', '1', 'ADS1256_DIN_ADC'); pin_label('R9', '2', 'SPI0_MOSI')
place('Device', 'R', 'R10', '33R', 88, 85,
      fp='Resistor_SMD:R_0402_1005Metric', desc='SPI0 MISO series protection (F-04)')
pin_label('R10', '1', 'SPI0_MISO'); pin_label('R10', '2', 'ADS1256_DOUT_ADC')
place('Device', 'R', 'R11', '33R', 88, 105,
      fp='Resistor_SMD:R_0402_1005Metric', desc='SPI0 SCK series protection (F-04)')
pin_label('R11', '1', 'ADS1256_SCLK_ADC'); pin_label('R11', '2', 'SPI0_SCK')

place('Device', 'R', 'R3', '100R', 18, 62,
      fp='Resistor_SMD:R_0402_1005Metric', desc='ADS1256 AIN0 series protection (F-06)')
pin_label('R3', '1', 'LC_SIG_P'); pin_label('R3', '2', 'LC_AINP')
place('Device', 'R', 'R4', '100R', 18, 78,
      fp='Resistor_SMD:R_0402_1005Metric', desc='ADS1256 AIN1 series protection (F-06)')
pin_label('R4', '1', 'LC_SIG_N'); pin_label('R4', '2', 'LC_AINN')

# --- Pin-accurate nets on U2 (ADS1256), direct to real pin coordinates ---
pin_label('U2', '1', '+5V')            # AVDD
pin_label('U2', '2', 'GND')            # AGND
pin_label('U2', '3', 'VREF_N')         # VREFN
pin_label('U2', '4', 'VREF_P')         # VREFP
pin_label('U2', '5', 'GND')            # AINCOM — tied to AGND (single-ended ref)
pin_label('U2', '6', 'LC_AINP')        # AIN0 — load cell SIG+ (through R3)
pin_label('U2', '7', 'LC_AINN')        # AIN1 — load cell SIG- (through R4)
pin_label('U2', '16', '+3V3')          # DVDD
pin_label('U2', '17', 'GND')           # DGND
pin_label('U2', '18', 'XTAL2')
pin_label('U2', '19', 'XTAL1')
pin_label('U2', '20', 'ADS1256_CS')
pin_label('U2', '21', 'ADS1256_DRDY')
pin_label('U2', '22', 'ADS1256_DOUT_ADC')  # through R10
pin_label('U2', '23', 'ADS1256_DIN_ADC')   # through R9
pin_label('U2', '24', 'ADS1256_SCLK_ADC')  # through R11
# RESET (15) and SYNCPDWN (14): datasheet requires these NOT float — tie
# to DVDD (§15.2 pin completeness — was floating in Rev D, a real defect)
pin_label('U2', '15', '+3V3')          # RESET — tied high, no manual reset in V1
pin_label('U2', '14', '+3V3')          # SYNCPDWN — tied high, always-run mode
# D0CLKOUT/D1/D2/D3 (25-28): unused GPIO, datasheet default state (input,
# high-Z) is safe unterminated — flagged explicitly rather than silent
no_connect('U2', '25')
no_connect('U2', '26')
no_connect('U2', '27')
no_connect('U2', '28')
# AIN2-AIN7 (8-13): only AIN0/AIN1 used for the load cell differential
# pair in V1 — remaining mux inputs unused, flagged explicitly
for _ain_pin in ('8', '9', '10', '11', '12', '13'):
    no_connect('U2', _ain_pin)

# ============================================================
# SECTION 4: ADS1220 — PRESSURE ADC (center-right, x=100-160, y=60-100)
# ============================================================
print("Section 4: ADS1220 pressure ADC (real part, C132290)...")

# U3 — ADS1220IPWR, real symbol, TSSOP-16. Pin map from fetched .kicad_sym:
# 1=SCLK 2=~CS 3=CLK 4=DGND 5=AVSS 6=AIN3/REFN1 7=AIN2 8=REFN0
# 9=REFP0 10=AIN1 11=AIN0/REFP1 12=AVDD 13=DVDD 14=~DRDY
# 15=DOUT/~DRDY 16=DIN
# Using internal 2.048V reference (power-up default) — REFP0/REFN0 and
# the shared AIN0/REFP1, AIN3/REFN1 pins are unused, left NC.
place_real('ADS1220IPWR', 'U3', 'ADS1220IPWR', 125, 80, 0,
           'TSSOP-16_L5.0-W4.4-P0.65-LS6.4-BL',
           '24-bit ADC, TSSOP-16 (real footprint), SPI1, internal VREF')

place('Device', 'C', 'C10', '100nF', 85, 60,
      # 0402, not 0603: AVDD and DVDD are adjacent TSSOP pins and two 0603s
      # cannot both sit inside rule 2.2's 2mm. See gen_tms_v3_pcb.py.
      fp='Capacitor_SMD:C_0402_1005Metric', desc='ADS1220 AVDD decoupling — TI SBAS501 section 9.3.3')
pin_label('C10', '1', '+5V'); pin_label('C10', '2', 'GND')
# C11 is the DVDD decoupling cap, not a second AVDD one.
#
# It used to be "AVDD decoupling #2" on +5V, which left C10 and C11 both on
# pin 12 (AVDD) and NOTHING on pin 13 (DVDD) nearer than 3.1mm — recorded
# as a rule-2.2 deviation rather than recognised as the defect it was.
#
# TI SBAS501 §9.3.3, quoted: "AVDD, AVSS (when using a bipolar supply) and
# DVDD must be decoupled with at least a 0.1uF capacitor... Place the bypass
# capacitors as close to the power-supply pins of the device as possible."
# Two caps on one supply pin and none on the other is not that.
#
# DVDD on this board is the +3V3 rail (Teensy LDO), so C11 moves to +3V3.
# It also gives the +3V3 net local copper right at pin 13, which is where
# the router had been failing to reach.
place('Device', 'C', 'C11', '100nF', 85, 78,
      fp='Capacitor_SMD:C_0402_1005Metric',
      desc='ADS1220 DVDD decoupling — TI SBAS501 section 9.3.3')
pin_label('C11', '1', '+3V3'); pin_label('C11', '2', 'GND')
place('Device', 'C', 'C12', '10uF', 85, 96,
      fp='Capacitor_SMD:C_0805_2012Metric', desc='ADS1220 AVDD bulk, X5R 16V')
pin_label('C12', '1', '+5V'); pin_label('C12', '2', 'GND')
place('Device', 'C', 'C13', '100nF', 148, 60,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='ADS1220 DVDD decoupling, C0G')
pin_label('C13', '1', '+3V3'); pin_label('C13', '2', 'GND')
place('Device', 'C', 'C14', '100nF', 148, 78,
      fp='Capacitor_SMD:C_0603_1608Metric', desc='ADS1220 DVDD decoupling #2, C0G')
pin_label('C14', '1', '+3V3'); pin_label('C14', '2', 'GND')

place('Device', 'R', 'R12', '33R', 160, 65,
      fp='Resistor_SMD:R_0402_1005Metric', desc='SPI1 MOSI series protection (F-04)')
pin_label('R12', '1', 'ADS1220_DIN_ADC'); pin_label('R12', '2', 'SPI1_MOSI')
place('Device', 'R', 'R13', '33R', 160, 85,
      fp='Resistor_SMD:R_0402_1005Metric', desc='SPI1 MISO series protection (F-04)')
pin_label('R13', '1', 'SPI1_MISO'); pin_label('R13', '2', 'ADS1220_DOUT_ADC')
place('Device', 'R', 'R14', '33R', 160, 105,
      fp='Resistor_SMD:R_0402_1005Metric', desc='SPI1 SCK series protection (F-04)')
pin_label('R14', '1', 'ADS1220_SCLK_ADC'); pin_label('R14', '2', 'SPI1_SCK')

place('Device', 'R', 'R5', '100R', 120, 60,
      fp='Resistor_SMD:R_0402_1005Metric', desc='ADS1220 AIN2 series protection (F-06)')
pin_label('R5', '1', 'PRES_RAW'); pin_label('R5', '2', 'PRES_SIG')

# --- Pin-accurate nets on U3 (ADS1220) ---
pin_label('U3', '1', 'ADS1220_SCLK_ADC')   # through R14
pin_label('U3', '2', 'ADS1220_CS')         # ~CS
pin_label('U3', '3', 'GND')                # CLK — grounded, internal osc (datasheet default)
pin_label('U3', '4', 'GND')                # DGND
pin_label('U3', '5', 'GND')                # AVSS
pin_label('U3', '7', 'PRES_SIG')           # AIN2 — pressure signal (through R5)
pin_label('U3', '10', 'GND')               # AIN1 — tied low, pseudo-diff reference for single-ended read
pin_label('U3', '12', '+5V')               # AVDD
pin_label('U3', '13', '+3V3')              # DVDD
pin_label('U3', '14', 'ADS1220_DRDY')      # ~DRDY
pin_label('U3', '15', 'ADS1220_DOUT_ADC')  # DOUT/~DRDY, through R13
pin_label('U3', '16', 'ADS1220_DIN_ADC')   # DIN, through R12
# Unused when running on internal reference (REFSEL=00, power-up default)
no_connect('U3', '6')   # AIN3/REFN1
no_connect('U3', '8')   # REFN0
no_connect('U3', '9')   # REFP0
no_connect('U3', '11')  # AIN0/REFP1

# ============================================================
# SECTION 5: SENSOR CONNECTORS (left edge, x=5-25, y=60-100)
# ============================================================
print("Section 5: Sensor connectors...")

place('Connector_Generic', 'Conn_01x05', 'J3', 'LOAD-CELL', 10, 70,
      # JST XH 1x05 — polarised and latching, so a load-cell lead
      # cannot be plugged in backwards or shaken off. LCSC C157991.
      fp='Connector_JST:JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical',
      desc='Load cell: EXC+, EXC-, SIG+, SIG-, SHIELD')
pin_label('J3', '1', '+5V_FILT')  # EXC+
pin_label('J3', '2', 'GND')       # EXC-
pin_label('J3', '3', 'LC_SIG_P')  # SIG+ (through R3 to ADS1256 AIN0)
pin_label('J3', '4', 'LC_SIG_N')  # SIG- (through R4 to ADS1256 AIN1)
pin_label('J3', '5', 'GND')       # SHIELD

place('Connector_Generic', 'Conn_01x03', 'J4', 'PRESSURE', 10, 92,
      # JST XH 1x03 — polarised and latching. LCSC C144394.
      fp='Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical',
      desc='Pressure sensor: VBAT, SIG, GND')
pin_label('J4', '1', 'VBAT')      # direct battery, not filtered
pin_label('J4', '2', 'PRES_RAW')  # SIG (through R5 to ADS1220 AIN2)
pin_label('J4', '3', 'GND')

# ============================================================
# SECTION 6: TEENSY 4.1 MCU (center, x=100-170, y=110-170)
# ============================================================
print("Section 6: Teensy 4.1 MCU (generic header placeholder)...")
print("  NOTE: not a real fetched Teensy footprint — see module docstring.")

place('Connector_Generic', 'Conn_01x24', 'J7', 'TEENSY-L', 115, 140,
      fp='Connector_PinSocket_2.54mm:PinSocket_1x24_P2.54mm_Vertical',
      desc='Teensy 4.1 left header')
place('Connector_Generic', 'Conn_01x24', 'J8', 'TEENSY-R', 155, 140,
      fp='Connector_PinSocket_2.54mm:PinSocket_1x24_P2.54mm_Vertical',
      desc='Teensy 4.1 right header')

# ------------------------------------------------------------------
# Teensy 4.1 header net map.
#
# GROUND TRUTH: evidence/files/card11a_rev4_web.pdf (PJRC "Welcome to Teensy
# 4.1" pinout card, rev4), read as a rendered page — not from memory and
# not inferred. Both rows are indexed from the USB end.
#
#   J7 = ROW A (the Vin/GND/3.3V row), positions 1..24 from the USB end:
#     Vin, GND, 3.3V, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13,
#     GND, 41, 40, 39, 38, 37, 36, 35, 34, 33
#
#   J8 = ROW B, positions 1..24 from the USB end:
#     GND, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
#     3.3V, 24, 25, 26, 27, 28, 29, 30, 31, 32
#
# What the previous revision did, and why it was fatal: it assigned nets
# sequentially down each header (GND, +5V, +3V3, then signals in the order
# they were convenient). Against the real row that puts +5V on the Teensy's
# GND pin and GND on Vin -- a dead short of the regulated 5V rail to ground
# through the module, on first power-up -- and SPI0_SCK on the other row's
# GND pin. Nothing in ERC or DRC can see this, because electrically the
# netlist is self-consistent; only the vendor card reveals it.
#
# Peripheral pins are the Teensy 4.1's real hardware assignments:
#   SPI0 : SCK=13  MOSI=11  MISO=12          (CS is any GPIO -> 10)
#   SPI1 : SCK1=27 MOSI1=26 MISO1=1          (CS1 -> 0)
#   UART2: RX2=7   TX2=8    ("Serial2")
# Teensy 4.x pins are NOT 5V tolerant -- every signal below is 3.3V logic.
# ------------------------------------------------------------------

TEENSY_ROW_A = {          # J7 -- position: net   (blank = leave unconnected)
    1:  '+5V',            # Vin  -- 5V in from LM7805 (module accepts 3.6-5.5V)
    2:  'GND',            # GND
    3:  '+3V3',           # 3.3V -- OUTPUT of the Teensy's onboard LDO, 250mA max
    14: 'SPI0_SCK',       # D13  -- SCK (also the onboard LED)
    15: 'GND',            # GND  -- second ground, tie it
}

TEENSY_ROW_B = {          # J8
    1:  'GND',            # GND
    2:  'ADS1220_CS',     # D0  = CS1
    3:  'SPI1_MISO',      # D1  = MISO1
    4:  'RELAY_CTRL',     # D2
    5:  'LED_PWR',        # D3
    6:  'LED_ARM',        # D4
    7:  'LED_TX',         # D5
    8:  'ADS1220_DRDY',   # D6
    9:  'UART2_RX',       # D7  = RX2  <- XBee DOUT
    10: 'UART2_TX',       # D8  = TX2  -> XBee DIN
    11: 'ADS1256_DRDY',   # D9
    12: 'ADS1256_CS',     # D10 = CS
    13: 'SPI0_MOSI',      # D11 = MOSI
    14: 'SPI0_MISO',      # D12 = MISO
    15: '+3V3',           # 3.3V -- same rail as row A pin 3
    18: 'SPI1_MOSI',      # D26 = MOSI1
    19: 'SPI1_SCK',       # D27 = SCK1
}

for _ref, _map in (('J7', TEENSY_ROW_A), ('J8', TEENSY_ROW_B)):
    for _pos in range(1, 25):
        if _pos in _map:
            pin_label(_ref, str(_pos), _map[_pos])
        else:
            no_connect(_ref, str(_pos))

# ============================================================
# SECTION 7: XBEE 3 (through-hole module socket)
# ============================================================
print("Section 7: XBee 3 wireless (through-hole 20-pin socket)...")

# GROUND TRUTH: evidence/files/xbee3_hardware_ref.pdf (Digi 90001543),
# "Pin signals for the through-hole XBee 3 RF Module" (p.45-46) and the
# through-hole mechanical drawing (p.36).
#
#   1  VCC              10  GND              16  RTS/DIO6
#   2  DOUT/DIO13       11  DIO4/SPI_MOSI    17  AD3/DIO3/SPI_SSEL
#   3  DIN/CONFIG/DIO14 12  CTS/DIO7         18  AD2/DIO2/SPI_CLK
#   4  DIO12/SPI_MISO   13  ON/SLEEP/DIO9    19  AD1/DIO1/SPI_ATTN
#   5  RESET            14  [reserved]       20  AD0/DIO0
#   6  RSSI PWM/DIO10   15  ASSOCIATE/DIO5
#   7  PWM1/DIO11       ...
#   8  [reserved]
#   9  DTR/SLEEP_RQ/DIO8
#
# Digi: "The only required pin connections for two-way communication are
# VCC, GND, DOUT and DIN."
#
# Three things the previous revision got wrong, all of them destructive:
#   - GND was on pin 2. Pin 2 is DOUT, a push-pull OUTPUT. That shorts the
#     XBee's UART transmitter to ground whenever it drives high.
#   - The module's actual ground (pin 10) was never connected, so the
#     module had no return path at all.
#   - UART2_RX was on pin 4 (DIO12), not pin 2 (DOUT), so the receive path
#     went to an unrelated GPIO.
# Plus the footprint: a 2.54mm 2x10 header. The XBee is 2.00mm pitch with
# its two rows 22.0mm (0.866in) apart, and numbered counter-clockwise
# (1-10 down one side, 11-20 up the other) rather than odd/even. The stock
# KiCad 2x10 is odd/even at 2.0mm ROW spacing -- wrong pitch, wrong row
# gap, wrong numbering. Uses the hand-authored tms:XBee_THT_20pin_P2.00mm.

place('Connector_Generic', 'Conn_02x10_Counter_Clockwise', 'J9', 'XBEE3', 185, 130,
      fp='tms:XBee_THT_20pin_P2.00mm',
      desc='XBee 3 802.15.4 through-hole module socket, 2.00mm pitch')

XBEE_NETS = {
    1:  '+3V3',        # VCC (2.1-3.6V; XBee is NOT 5V tolerant)
    2:  'UART2_RX',    # DOUT -- XBee transmits -> Teensy RX2 (D7)
    3:  'UART2_TX',    # DIN  -- Teensy TX2 (D8) -> XBee receives
    10: 'GND',         # GND
}
for _pos in range(1, 21):
    if _pos in XBEE_NETS:
        pin_label('J9', str(_pos), XBEE_NETS[_pos])
    else:
        no_connect('J9', str(_pos))

# ============================================================
# SECTION 8: IGNITION CIRCUIT (bottom, x=20-100, y=150-190)
# ============================================================
print("Section 8: Ignition circuit (real relay, transistor, diode)...")

place('Connector_Generic', 'Conn_01x02', 'J2', 'XT30PW-IGN', 20, 160,
      # AMASS XT30PW-F, board-mount. LCSC C2913282.
      fp='Connector_AMASS:AMASS_XT30PW-F_1x02_P2.50mm_Horizontal',
      desc='Igniter battery XT60U-F (separate 2S LiPo)')
pin_label('J2', '1', 'IGN_BATT+')
pin_label('J2', '2', 'IGN_GND')

place('Connector_Generic', 'Conn_01x02', 'J5', 'ARM-SW', 40, 160,
      # Real 5.08mm screw terminal, matching the description.
      fp='TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',
      desc='External ARM switch screw terminal')
pin_label('J5', '1', 'IGN_BATT+')
pin_label('J5', '2', 'IGN_ARM_RET')

# K1 — HF46F relay, real symbol. Pinout confirmed from Hongfa datasheet
# wiring diagram: pin1/pin6 = coil (non-polarized), pin2 = COM, pin3 = NO
place_real('HF46F-G_5-HS1T_C5274026', 'K1', 'HF46F-G/5-HS1T', 65, 165, 0,
           'RELAYS-TH_HF46F-G-XX-HS1-XXX',
           'Relay, 1 Form A, real footprint. Pin1/6=coil, 2=COM, 3=NO')
pin_label('K1', '1', '+5V')            # coil terminal A — relay supply
pin_label('K1', '6', 'RELAY_COIL_SW')  # coil terminal B — switched by Q1
pin_label('K1', '2', 'IGN_ARM_RET')    # COM — from ARM switch return
pin_label('K1', '3', 'IGN_OUT')        # NO — to E-match

# D1 — Flyback diode across coil, real part (1N4148WS, C57759)
place_real('1N4148WS-C57759', 'D1', '1N4148WS', 65, 145, 90,
           'SOD-323_L1.8-W1.3-LS2.5-RD-1',
           'Flyback diode across relay coil, real footprint')
pin_label('D1', '1', 'RELAY_COIL_SW')  # cathode — same node as coil terminal B
pin_label('D1', '2', '+5V')            # anode — flyback returns to +5V rail

# Q1 — NPN relay driver, real part (MMBT3904, C20526)
place_real('MMBT3904-C20526', 'Q1', 'MMBT3904', 65, 195, 0,
           'SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR',
           'NPN relay coil driver, real footprint')
pin_label('Q1', '3', 'RELAY_COIL_SW')  # collector
pin_label('Q1', '2', 'GND')            # emitter
pin_label('Q1', '1', 'NPN_BASE')       # base — through R1

place('Device', 'R', 'R1', '1k', 45, 195,
      fp='Resistor_SMD:R_0402_1005Metric', desc='NPN base current limit')
pin_label('R1', '1', 'RELAY_CTRL'); pin_label('R1', '2', 'NPN_BASE')

place('Device', 'R', 'R2', '10k', 55, 205,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='NPN base pull-down — SAFETY: keeps relay OFF during boot')
pin_label('R2', '1', 'NPN_BASE'); pin_label('R2', '2', 'GND')

place('Connector_Generic', 'Conn_01x02', 'J6', 'IGN-OUT', 90, 160,
      # AMASS XT60-F. The igniter is a NICHROME bridge across a KNSB
      # grain, not a commercial e-match: a nichrome bridgewire is a low
      # resistance (order 1-3 ohm), so a 2S pack drives several amps into
      # it. XT60 (30A continuous) carries that with large margin and, more
      # importantly, latches — this is the one lead that must not fall off.
      # LCSC C98734.
      fp='Connector_AMASS:AMASS_XT60-F_1x02_P7.20mm_Vertical',
      desc='E-match output screw terminal')
pin_label('J6', '1', 'IGN_OUT')
pin_label('J6', '2', 'IGN_GND')

# ============================================================
# SECTION 9: TVS PROTECTION (near ADC inputs)
# ============================================================
print("Section 9: TVS protection array (F-06, real part C49338)...")

# D2 — PESD5V0S2BT bidirectional TVS array, real symbol. Pin map from
# fetched .kicad_sym: pin1=IO_A, pin2=IO_B, pin3=common GND
place_real('PESD5V0S2BT,215', 'D2', 'PESD5V0S2BT', 18, 95, 0,
           'SOT-23_L2.9-W1.3-P1.90-LS2.4-BR',
           'TVS array, real footprint. Pin1/2=I/O, pin3=GND common')
pin_label('D2', '1', 'LC_SIG_P')
pin_label('D2', '2', 'LC_SIG_N')
pin_label('D2', '3', 'GND')

# ============================================================
# SECTION 10: LEDs (bottom-right, x=160-200, y=160-185)
# ============================================================
print("Section 10: Status LEDs...")

# Device:LED pin map: pin1=K (cathode), pin2=A (anode)
place('Device', 'LED', 'LED1', 'GREEN', 160, 175,
      fp='LED_SMD:LED_0603_1608Metric', desc='Power indicator LED')
pin_label('LED1', '2', 'LED_PWR_A')
pin_label('LED1', '1', 'GND')
place('Device', 'R', 'R6', '330R', 160, 160,
      fp='Resistor_SMD:R_0402_1005Metric', desc='Power LED current limit')
pin_label('R6', '1', 'LED_PWR'); pin_label('R6', '2', 'LED_PWR_A')

place('Device', 'LED', 'LED2', 'RED', 180, 175,
      fp='LED_SMD:LED_0603_1608Metric', desc='ARM/fire indicator LED')
pin_label('LED2', '2', 'LED_ARM_A')
pin_label('LED2', '1', 'GND')
place('Device', 'R', 'R7', '330R', 180, 160,
      fp='Resistor_SMD:R_0402_1005Metric', desc='ARM LED current limit')
pin_label('R7', '1', 'LED_ARM'); pin_label('R7', '2', 'LED_ARM_A')

place('Device', 'LED', 'LED3', 'YELLOW', 200, 175,
      fp='LED_SMD:LED_0603_1608Metric', desc='TX activity LED')
pin_label('LED3', '2', 'LED_TX_A')
pin_label('LED3', '1', 'GND')
place('Device', 'R', 'R8', '330R', 200, 160,
      fp='Resistor_SMD:R_0402_1005Metric', desc='TX LED current limit')
pin_label('R8', '1', 'LED_TX'); pin_label('R8', '2', 'LED_TX_A')

# ============================================================
# SECTION 11: TEST POINTS
# ============================================================
print("Section 11: Test points...")

for tp_ref, tp_val, tp_x, tp_y, tp_net in [
    ('TP1', 'VBAT', 28, 25, 'VBAT'),
    ('TP2', '+5V', 68, 22, '+5V'),
    ('TP3', '+3V3', 113, 108, '+3V3'),
    ('TP4', 'AINP', 25, 62, 'LC_SIG_P'),
    ('TP5', 'AINN', 25, 73, 'LC_SIG_N'),
    ('TP6', 'PRES', 105, 62, 'PRES_RAW'),
    ('TP7', 'DRDY1', 88, 95, 'ADS1256_DRDY'),
    ('TP8', 'DRDY2', 150, 95, 'ADS1220_DRDY'),
    ('TP9', 'RELAY', 72, 175, 'RELAY_CTRL'),
]:
    place('Connector_Generic', 'Conn_01x01', tp_ref, tp_val, tp_x, tp_y,
          fp='TestPoint:TestPoint_Pad_1.0x1.0mm',
          desc=f'Test point: {tp_net}')
    pin_label(tp_ref, '1', tp_net)

# ============================================================
# SECTION 12: MOUNTING HOLES (no electrical connection — explicit NC)
# ============================================================
print("Section 12: Mounting holes...")

for i, (hx, hy) in enumerate([(200, 25), (210, 25), (200, 30), (210, 30)], start=1):
    ref = f'H{i}'
    place('Connector_Generic', 'Conn_01x01', ref, 'M3', hx, hy,
          fp='MountingHole:MountingHole_3.2mm_M3_Pad',
          desc=f'M3 mounting hole #{i}')
    no_connect(ref, '1')

print(labels.report())
print("Saving schematic...")
sch_io.write_file(SCH_PATH, tree)

import json as _json
_netmap_path = SCH_PATH.parent / 'netmap.json'
_netmap_path.write_text(_json.dumps(
    {'source': 'gen_tms_v3_sch.py', 'nets': NETMAP, 'no_connect': NOCONNECT},
    indent=1, sort_keys=True))
_n = sum(len(v) for v in NETMAP.values())
_nc = sum(len(v) for v in NOCONNECT.values())
print(f"Wrote {_netmap_path.name}: {_n} pin-net assignments, {_nc} explicit no-connects")
print(f"Written to: {SCH_PATH}")
print(f"File size: {SCH_PATH.stat().st_size} bytes")
print()
print("=== Schematic generation complete (Rev E, real parts, pin-accurate) ===")
print("Next: Run ERC with kicad-cli, then generate PCB.")
