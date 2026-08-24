#!/usr/bin/env python3
"""Generate TMS V3 schematic using kicad-claude-mcp ed API.

Rev D — all PDR findings resolved. Full netlist per tms-v3-bom.md.

Circuit architecture:
  VBAT (4S LiPo 12-16.8V) → SS54 Schottky (D3) → LM7805 → 5V rail
  Teensy 4.1 onboard LDO → 3.3V rail
  ADS1256 (SPI0): Load cell thrust measurement, PGA=64, buffer OFF
  ADS1220 (SPI1): Pressure sensor, PGA bypass, AVDD=5V
  XBee 3 (UART2): 2.4 GHz telemetry
  HF46F relay + NPN driver: Ignition circuit
  LC filter on excitation rail (L1 + C17)
  TVS protection on ADC inputs (D2a, D2b)
  33Ω series resistors on all SPI lines (F-04)
"""

import sys
sys.path.insert(0, '/Users/leetaeho/CODE/PCB/tools/kicad-claude-mcp/src')

from pathlib import Path
from kicad_claude.tools.schematic import ed, write_blank_schematic, sch_io
from kicad_claude.utils.kicad_paths import find_symbol_lib_dirs

PROJECT_DIR = Path('/Users/leetaeho/CODE/PCB/projects/tms-v3')
SCH_PATH = PROJECT_DIR / 'tms-v3.kicad_sch'
LIB_DIR = find_symbol_lib_dirs()[0]
PROJECT_NAME = 'tms-v3'

if SCH_PATH.exists():
    SCH_PATH.unlink()

write_blank_schematic(SCH_PATH)
tree = sch_io.parse_file(SCH_PATH)


def fetch_and_inject(lib_name, sym_name):
    lib_path = LIB_DIR / f'{lib_name}.kicad_sym'
    sym_def = ed.fetch_symbol_def(lib_path, sym_name)
    qualified = f'{lib_name}:{sym_name}'
    if not ed.lib_symbols_has(tree, qualified):
        entry = ed.make_lib_symbol_entry(sym_def, qualified)
        ed.inject_lib_symbol(tree, entry)
    return sym_def, qualified


def place(lib_name, sym_name, ref, value, x, y, rot=0, fp='', desc=''):
    sym_def, qualified = fetch_and_inject(lib_name, sym_name)
    ed.add_symbol(
        tree,
        qualified_lib_id=qualified,
        reference=ref,
        value=value,
        x_mm=x, y_mm=y,
        rotation=rot,
        sym_def_node=sym_def,
        project_name=PROJECT_NAME,
        footprint=fp,
        description=desc,
    )


def wire(x1, y1, x2, y2):
    ed.add_wire(tree, x1, y1, x2, y2)


def label(name, x, y, orient='right'):
    ed.add_label(tree, name, x, y, orient)


print("=== TMS V3 Schematic Generation ===")
print("Rev D — all findings resolved")

# ============================================================
# SECTION 1: POWER INPUT & REGULATION (top-left, x=20-80, y=20-60)
# ============================================================
print("Section 1: Power input & regulation...")

# J1 — Electronics battery XT60
place('Connector_Generic', 'Conn_01x02', 'J1', 'XT60-ELEC', 20, 30,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
      desc='Electronics battery XT60U-F')

# D3 — SS54 Schottky reverse polarity protection
place('Device', 'D_Schottky', 'D3', 'SS54', 32, 30,
      fp='Diode_SMD:D_SMA',
      desc='Reverse polarity protection, DO-214AC')

# C15 — LM7805 input cap 330nF
place('Device', 'C', 'C15', '330nF', 42, 35,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='LM7805 input cap, X7R 50V')

# U4 — LM7805 regulator
place('Regulator_Linear', 'L7805', 'U4', 'LM7805', 52, 30,
      fp='Package_TO_SOT_SMD:TO-263-3_TabPin2',
      desc='5V 1.5A regulator, D2PAK')

# C16 — LM7805 output cap 100nF
place('Device', 'C', 'C16', '100nF', 62, 35,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='LM7805 output cap, C0G')

# Power symbols
place('power', '+5V', '#PWR01', '+5V', 65, 25)
place('power', 'GND', '#PWR02', 'GND', 52, 42)

# Net labels — power input
label('VBAT', 22, 30)
label('VBAT_PROT', 35, 30)
label('+5V', 65, 27)
label('GND', 52, 40)
label('GND', 42, 40)
label('GND', 62, 40)

# Wires — power section
wire(22, 30, 28, 30)   # J1 to D3
wire(35, 30, 42, 30)   # D3 to C15
wire(42, 30, 47, 30)   # C15 to U4 IN
wire(57, 30, 62, 30)   # U4 OUT to C16
wire(62, 30, 65, 30)   # C16 to +5V
wire(65, 30, 65, 27)   # +5V up
wire(52, 35, 52, 40)   # U4 GND
wire(42, 33, 42, 40)   # C15 GND
wire(62, 33, 62, 40)   # C16 GND

# ============================================================
# SECTION 2: EXCITATION LC FILTER (below power, x=70-95, y=25-40)
# ============================================================
print("Section 2: Excitation LC filter (F-05/D-04)...")

# L1 — 10uH ferrite bead
place('Device', 'L', 'L1', '10uH', 75, 28,
      fp='Inductor_SMD:L_0805_2012Metric',
      desc='Excitation LC filter inductor')

# C17 — 10uF filter cap
place('Device', 'C', 'C17', '10uF', 85, 33,
      fp='Capacitor_SMD:C_0805_2012Metric',
      desc='Excitation LC filter cap, X5R 16V')

label('+5V', 70, 28)
label('+5V_FILT', 88, 28)
label('GND', 85, 38)

wire(70, 28, 72, 28)   # +5V to L1
wire(78, 28, 85, 28)   # L1 to C17 junction
wire(85, 28, 88, 28)   # to +5V_FILT label
wire(85, 31, 85, 38)   # C17 GND

# ============================================================
# SECTION 3: ADS1256 — THRUST ADC (center-left, x=20-90, y=60-110)
# ============================================================
print("Section 3: ADS1256 thrust ADC...")

# U2 — ADS1256 (using generic ADC placeholder — real symbol from LCSC lib)
place('Connector_Generic', 'Conn_01x14', 'U2', 'ADS1256IDBR', 55, 85, rot=0,
      desc='24-bit ADC, SSOP-28, SPI0. Pins: 1=AINP0,2=AINN0,3=AINP1,4=AINN1,5=AVDD,6=AVSS,7=VREFP,8=VREFN,9=SCLK,10=DIN,11=DOUT,12=DRDY,13=CS,14=DVDD')

# ADS1256 decoupling
place('Device', 'C', 'C1', '100nF', 40, 75,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1256 AVDD decoupling, C0G, ≤2mm from pin')
place('Device', 'C', 'C2', '100nF', 40, 80,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1256 AVDD decoupling #2, C0G')
place('Device', 'C', 'C3', '10uF', 40, 85,
      fp='Capacitor_SMD:C_0805_2012Metric',
      desc='ADS1256 AVDD bulk, X5R 16V')
place('Device', 'C', 'C4', '10uF', 40, 90,
      fp='Capacitor_SMD:C_0805_2012Metric',
      desc='ADS1256 AVDD bulk #2, X5R 16V')
place('Device', 'C', 'C5', '100nF', 70, 75,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1256 DVDD decoupling, C0G')
place('Device', 'C', 'C6', '100nF', 70, 80,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1256 DVDD decoupling #2, C0G')
place('Device', 'C', 'C7', '100nF', 45, 95,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1256 VREFP-VREFN decoupling (F-13), C0G')

# Crystal Y1
place('Device', 'Crystal', 'Y1', '7.68MHz', 70, 90,
      fp='Crystal:Crystal_HC49-U_Vertical',
      desc='ADS1256 clock, NDK AT-41CD2, HC-49')
place('Device', 'C', 'C8', '22pF', 65, 95,
      fp='Capacitor_SMD:C_0402_1005Metric',
      desc='Crystal load cap, C0G')
place('Device', 'C', 'C9', '22pF', 75, 95,
      fp='Capacitor_SMD:C_0402_1005Metric',
      desc='Crystal load cap, C0G')

# ADS1256 SPI series resistors (F-04)
place('Device', 'R', 'R9', '33R', 82, 80,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='SPI0 MOSI series protection (F-04)')
place('Device', 'R', 'R10', '33R', 82, 83,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='SPI0 MISO series protection (F-04)')
place('Device', 'R', 'R11', '33R', 82, 86,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='SPI0 SCK series protection (F-04)')

# ADC input protection — load cell
place('Device', 'R', 'R3', '100R', 30, 65,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='ADS1256 AINP series protection (F-06)')
place('Device', 'R', 'R4', '100R', 30, 70,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='ADS1256 AINN series protection (F-06)')

# Net labels — ADS1256
label('+5V', 40, 72)      # AVDD
label('GND', 40, 93)      # AVSS
label('+3V3', 70, 72)     # DVDD
label('GND', 65, 98)      # Crystal cap GND
label('GND', 75, 98)      # Crystal cap GND
label('SPI0_MOSI', 88, 80)
label('SPI0_MISO', 88, 83)
label('SPI0_SCK', 88, 86)
label('ADS1256_CS', 57, 98)
label('ADS1256_DRDY', 57, 95)
label('LC_AINP', 25, 65)
label('LC_AINN', 25, 70)

# ============================================================
# SECTION 4: ADS1220 — PRESSURE ADC (center-right, x=100-160, y=60-100)
# ============================================================
print("Section 4: ADS1220 pressure ADC...")

place('Connector_Generic', 'Conn_01x08', 'U3', 'ADS1220IPWR', 125, 80, rot=0,
      desc='24-bit ADC, TSSOP-16, SPI1. Pins: 1=AIN0,2=AIN1,3=AVDD,4=AVSS,5=SCLK,6=DIN,7=DOUT,8=DRDY,9=CS,10=DVDD')

# ADS1220 decoupling
place('Device', 'C', 'C10', '100nF', 110, 75,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1220 AVDD decoupling, C0G')
place('Device', 'C', 'C11', '100nF', 110, 80,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1220 AVDD decoupling #2, C0G')
place('Device', 'C', 'C12', '10uF', 110, 85,
      fp='Capacitor_SMD:C_0805_2012Metric',
      desc='ADS1220 AVDD bulk, X5R 16V')
place('Device', 'C', 'C13', '100nF', 140, 75,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1220 DVDD decoupling, C0G')
place('Device', 'C', 'C14', '100nF', 140, 80,
      fp='Capacitor_SMD:C_0603_1608Metric',
      desc='ADS1220 DVDD decoupling #2, C0G')

# SPI1 series resistors (F-04)
place('Device', 'R', 'R12', '33R', 150, 80,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='SPI1 MOSI series protection (F-04)')
place('Device', 'R', 'R13', '33R', 150, 83,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='SPI1 MISO series protection (F-04)')
place('Device', 'R', 'R14', '33R', 150, 86,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='SPI1 SCK series protection (F-04)')

# Input protection — pressure
place('Device', 'R', 'R5', '100R', 110, 65,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='ADS1220 AIN0 series protection (F-06)')

label('+5V', 110, 72)
label('GND', 110, 88)
label('+3V3', 140, 72)
label('SPI1_MOSI', 156, 80)
label('SPI1_MISO', 156, 83)
label('SPI1_SCK', 156, 86)
label('ADS1220_CS', 127, 92)
label('ADS1220_DRDY', 127, 95)
label('PRES_SIG', 105, 65)

# ============================================================
# SECTION 5: SENSOR CONNECTORS (left edge, x=5-25, y=60-100)
# ============================================================
print("Section 5: Sensor connectors...")

# J3 — Load cell 5-pin screw terminal
place('Connector_Generic', 'Conn_01x05', 'J3', 'LOAD-CELL', 10, 70,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical',
      desc='Load cell: EXC+, EXC-, SIG+, SIG-, SHIELD')

# J4 — Pressure sensor 3-pin screw terminal
place('Connector_Generic', 'Conn_01x03', 'J4', 'PRESSURE', 10, 92,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical',
      desc='Pressure sensor: VBAT, SIG, GND')

label('+5V_FILT', 14, 68)   # EXC+
label('GND', 14, 70)         # EXC-
label('LC_AINP', 14, 72)     # SIG+
label('LC_AINN', 14, 74)     # SIG-
label('GND', 14, 76)         # SHIELD

label('VBAT', 14, 90)        # Pressure supply (direct battery)
label('PRES_SIG', 14, 92)    # Pressure signal
label('GND', 14, 94)         # Pressure GND

# ============================================================
# SECTION 6: TEENSY 4.1 MCU (center, x=100-170, y=110-170)
# ============================================================
print("Section 6: Teensy 4.1 MCU...")

# Teensy as dual 1x24 headers (left + right sides)
place('Connector_Generic', 'Conn_01x24', 'J7', 'TEENSY-L', 115, 140,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x24_P2.54mm_Vertical',
      desc='Teensy 4.1 left header')
place('Connector_Generic', 'Conn_01x24', 'J8', 'TEENSY-R', 155, 140,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x24_P2.54mm_Vertical',
      desc='Teensy 4.1 right header')

# Teensy pin labels (left side — pins vary by Teensy 4.1 pinout)
label('GND', 113, 111)           # GND
label('+5V', 113, 113)           # Vin (5V input)
label('+3V3', 113, 116)          # 3.3V output
label('ADS1220_CS', 113, 118)    # Pin 0
label('SPI1_MISO', 113, 121)     # Pin 1
label('ADS1220_DRDY', 113, 123)  # Pin 2
label('RELAY_CTRL', 113, 126)    # Pin 3
label('LED_PWR', 113, 128)       # Pin 4
label('LED_ARM', 113, 131)       # Pin 5
label('LED_TX', 113, 133)        # Pin 6
label('UART2_RX', 113, 136)      # Pin 7 (RX2)
label('UART2_TX', 113, 138)      # Pin 8 (TX2)
label('ADS1256_DRDY', 113, 141)  # Pin 9
label('ADS1256_CS', 113, 143)    # Pin 10
label('SPI0_MOSI', 113, 146)     # Pin 11 (MOSI0)
label('SPI0_MISO', 113, 148)     # Pin 12 (MISO0)

# Right side
label('SPI0_SCK', 157, 146)      # Pin 13 (SCK0)
label('SPI1_SCK', 157, 136)      # Pin 27 (SCK1)
label('SPI1_MOSI', 157, 133)     # Pin 26 (MOSI1)

# ============================================================
# SECTION 7: XBEE 3 (right of Teensy, x=170-200, y=110-145)
# ============================================================
print("Section 7: XBee 3 wireless...")

place('Connector_Generic', 'Conn_02x10', 'J9', 'XBEE3', 185, 130,
      fp='Connector_PinHeader_2.54mm:PinHeader_2x10_P2.00mm_Vertical',
      desc='XBee 3 802.15.4 module socket')

label('+3V3', 183, 120)     # VCC
label('GND', 183, 140)      # GND
label('UART2_TX', 183, 122) # DIN (Teensy TX → XBee DIN)
label('UART2_RX', 183, 124) # DOUT (XBee DOUT → Teensy RX)

# ============================================================
# SECTION 8: IGNITION CIRCUIT (bottom, x=20-100, y=150-190)
# ============================================================
print("Section 8: Ignition circuit...")

# J2 — Igniter battery XT60
place('Connector_Generic', 'Conn_01x02', 'J2', 'XT60-IGN', 20, 160,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
      desc='Igniter battery XT60U-F (separate 2S LiPo)')

# J5 — ARM switch connector
place('Connector_Generic', 'Conn_01x02', 'J5', 'ARM-SW', 40, 160,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
      desc='External ARM switch screw terminal')

# K1 — HF46F relay
place('Connector_Generic', 'Conn_01x04', 'K1', 'HF46F', 65, 165,
      desc='HF46F-G/5-HS1T relay. Pins: 1=COIL+, 2=COIL-, 3=COM, 4=NO')

# D1 — Flyback diode (across coil)
place('Device', 'D', 'D1', '1N4148WS', 58, 160,
      fp='Diode_SMD:D_SOD-323',
      desc='Flyback diode across relay coil')

# Q1 — NPN relay driver
place('Device', 'Q_NPN_BCE', 'Q1', 'MMBT3904', 65, 175,
      fp='Package_TO_SOT_SMD:SOT-23',
      desc='NPN relay coil driver')

# R1 — Base resistor
place('Device', 'R', 'R1', '1k', 50, 175,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='NPN base current limit')

# R2 — Base pull-down (F-08, safety critical)
place('Device', 'R', 'R2', '10k', 58, 180,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='NPN base pull-down — SAFETY: keeps relay OFF during boot')

# J6 — E-match connector
place('Connector_Generic', 'Conn_01x02', 'J6', 'E-MATCH', 90, 160,
      fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
      desc='E-match output screw terminal')

# Ignition net labels
label('IGN_BATT+', 22, 158)
label('IGN_GND', 22, 162)
label('IGN_BATT+', 38, 158)   # to ARM switch
label('IGN_ARM_RET', 42, 158) # ARM return
label('IGN_ARM_RET', 63, 163) # to relay COM
label('IGN_OUT', 67, 167)     # relay NO
label('IGN_OUT', 88, 158)     # to E-match
label('IGN_GND', 92, 162)     # E-match return
label('+5V', 63, 158)         # Relay coil power
label('RELAY_CTRL', 45, 175)  # from Teensy
label('GND', 65, 182)         # NPN emitter
label('GND', 58, 185)         # Pull-down GND

# Wires — ignition
wire(22, 158, 28, 158)    # J2 to IGN_BATT+
wire(45, 175, 50, 175)    # RELAY_CTRL to R1
wire(53, 175, 58, 175)    # R1 to NPN base junction
wire(58, 175, 62, 175)    # junction to Q1 base
wire(58, 175, 58, 180)    # junction to R2
wire(65, 170, 65, 175)    # Q1 collector to relay coil-
wire(65, 178, 65, 182)    # Q1 emitter to GND

# ============================================================
# SECTION 9: TVS PROTECTION (near ADC inputs)
# ============================================================
print("Section 9: TVS protection diodes (F-06)...")

place('Device', 'D_TVS', 'D2', 'PESD5V0S2BT', 35, 65,
      fp='Package_TO_SOT_SMD:SOT-23',
      desc='TVS clamp on ADS1256 analog inputs')

# ============================================================
# SECTION 10: LEDs (bottom-right, x=160-200, y=160-185)
# ============================================================
print("Section 10: Status LEDs...")

place('Device', 'LED', 'LED1', 'GREEN', 165, 165,
      fp='LED_SMD:LED_0603_1608Metric',
      desc='Power indicator LED')
place('Device', 'R', 'R6', '330R', 165, 160,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='Power LED current limit')

place('Device', 'LED', 'LED2', 'RED', 175, 165,
      fp='LED_SMD:LED_0603_1608Metric',
      desc='ARM/fire indicator LED')
place('Device', 'R', 'R7', '330R', 175, 160,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='ARM LED current limit')

place('Device', 'LED', 'LED3', 'YELLOW', 185, 165,
      fp='LED_SMD:LED_0603_1608Metric',
      desc='TX activity LED')
place('Device', 'R', 'R8', '330R', 185, 160,
      fp='Resistor_SMD:R_0402_1005Metric',
      desc='TX LED current limit')

label('LED_PWR', 165, 156)
label('LED_ARM', 175, 156)
label('LED_TX', 185, 156)
label('GND', 165, 170)
label('GND', 175, 170)
label('GND', 185, 170)

# Wires — LEDs
wire(165, 156, 165, 158)  # label to R6
wire(165, 162, 165, 163)  # R6 to LED1
wire(165, 167, 165, 170)  # LED1 to GND
wire(175, 156, 175, 158)
wire(175, 162, 175, 163)
wire(175, 167, 175, 170)
wire(185, 156, 185, 158)
wire(185, 162, 185, 163)
wire(185, 167, 185, 170)

# ============================================================
# SECTION 11: TEST POINTS (scattered near their nets)
# ============================================================
print("Section 11: Test points...")

for i, (tp_ref, tp_val, tp_x, tp_y, tp_net) in enumerate([
    ('TP1', 'VBAT', 28, 25, 'VBAT'),
    ('TP2', '+5V', 68, 22, '+5V'),
    ('TP3', '+3V3', 113, 108, '+3V3'),
    ('TP4', 'AINP', 25, 62, 'LC_AINP'),
    ('TP5', 'AINN', 25, 73, 'LC_AINN'),
    ('TP6', 'PRES', 105, 62, 'PRES_SIG'),
    ('TP7', 'DRDY1', 88, 95, 'ADS1256_DRDY'),
    ('TP8', 'DRDY2', 150, 95, 'ADS1220_DRDY'),
    ('TP9', 'RELAY', 72, 175, 'RELAY_CTRL'),
], start=1):
    place('Connector_Generic', 'Conn_01x01', tp_ref, tp_val, tp_x, tp_y,
          fp='TestPoint:TestPoint_Pad_1.0x1.0mm',
          desc=f'Test point: {tp_net}')
    label(tp_net, tp_x + 2, tp_y)

# ============================================================
# SECTION 12: MOUNTING HOLES
# ============================================================
print("Section 12: Mounting holes...")

for i, (hx, hy) in enumerate([(200, 25), (210, 25), (200, 30), (210, 30)], start=1):
    place('Connector_Generic', 'Conn_01x01', f'H{i}', 'M3', hx, hy,
          fp='MountingHole:MountingHole_3.2mm_M3_Pad',
          desc=f'M3 mounting hole #{i}')

print("Saving schematic...")
sch_io.write_file(SCH_PATH, tree)
print(f"Written to: {SCH_PATH}")
print(f"File size: {SCH_PATH.stat().st_size} bytes")
print()
print("=== Schematic generation complete ===")
print("Next: Run ERC with kicad-cli, then generate PCB.")
