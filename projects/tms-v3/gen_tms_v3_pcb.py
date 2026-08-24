#!/usr/bin/env python3
"""Generate TMS V3 PCB layout with design-rule-compliant placement.

Board: 100mm × 80mm, 2-layer, JLCPCB specs.
Placement follows pcb-design-rules.md §1.1 sequence:
  1. Board outline + mounting holes
  2. Connectors (battery, sensor, igniter — along edges)
  3. Power supply chain (LM7805, Schottky, caps — near battery connector)
  4. Precision analog (ADCs — near sensor connectors, away from digital)
  5. Digital (Teensy, XBee — center/right, separate from analog)
  6. Decoupling caps (≤2mm from IC power pins)
  7. Crystal (≤5mm from ADS1256)
  8. Remaining passives
  9. LEDs, test points, silkscreen

Ground zones on F.Cu and B.Cu with stitching vias.
No trace routing — that's for Freerouting or manual KiCad routing.
"""

import uuid
from pathlib import Path

PROJECT_DIR = Path('/Users/leetaeho/CODE/PCB/projects/tms-v3')
PCB_PATH = PROJECT_DIR / 'tms-v3.kicad_pcb'

BOARD_W = 100.0
BOARD_H = 80.0
ORIGIN_X = 100.0
ORIGIN_Y = 100.0

def uid():
    return str(uuid.uuid4())

def pos(rel_x, rel_y):
    return (ORIGIN_X + rel_x, ORIGIN_Y + rel_y)


# ============================================================
# Net definitions
# ============================================================
NET_NAMES = {
    0: '',
    1: '+5V',
    2: 'GND',
    3: '+3V3',
    4: 'VBAT',
    5: 'VBAT_PROT',
    6: '+5V_FILT',
    7: 'SPI0_MOSI',
    8: 'SPI0_MISO',
    9: 'SPI0_SCK',
    10: 'ADS1256_CS',
    11: 'ADS1256_DRDY',
    12: 'SPI1_MOSI',
    13: 'SPI1_MISO',
    14: 'SPI1_SCK',
    15: 'ADS1220_CS',
    16: 'ADS1220_DRDY',
    17: 'UART2_TX',
    18: 'UART2_RX',
    19: 'RELAY_CTRL',
    20: 'LC_AINP',
    21: 'LC_AINN',
    22: 'PRES_SIG',
    23: 'IGN_BATT+',
    24: 'IGN_GND',
    25: 'IGN_ARM_RET',
    26: 'IGN_OUT',
    27: 'LED_PWR',
    28: 'LED_ARM',
    29: 'LED_TX',
}

def net_str(net_id):
    name = NET_NAMES.get(net_id, '')
    return f'(net {net_id} "{name}")'

NETS = [(nid, f'"{name}"') for nid, name in NET_NAMES.items()]

# ============================================================
# Component placement plan (rel_x, rel_y from board origin)
#
# Layout zones:
#   Left edge (x=0-15): Battery connectors, sensor connectors
#   Left-center (x=15-40): Power regulation, ADC analog front-end
#   Center (x=35-65): ADS1256 + crystal + decoupling
#   Center-right (x=50-75): ADS1220 + decoupling
#   Right-center (x=55-85): Teensy 4.1 (large module, 62mm long)
#   Right (x=75-95): XBee, LEDs
#   Bottom (y=55-75): Ignition circuit
# ============================================================

COMPONENTS = [
    # === MOUNTING HOLES (corners, 3.5mm inset) ===
    ('H1', 'MountingHole:MountingHole_3.2mm_M3_Pad', 3.5, 3.5, 0, 2, 'M3'),
    ('H2', 'MountingHole:MountingHole_3.2mm_M3_Pad', 96.5, 3.5, 0, 2, 'M3'),
    ('H3', 'MountingHole:MountingHole_3.2mm_M3_Pad', 3.5, 76.5, 0, 2, 'M3'),
    ('H4', 'MountingHole:MountingHole_3.2mm_M3_Pad', 96.5, 76.5, 0, 2, 'M3'),

    # === CONNECTORS (left/bottom edges) ===
    # J1: Electronics battery — top-left
    ('J1', 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', 5.0, 12.0, 0, 4, 'XT60-ELEC'),
    # J2: Igniter battery — bottom-left
    ('J2', 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', 5.0, 62.0, 0, 23, 'XT60-IGN'),
    # J3: Load cell 5-pin — left side, near ADS1256
    ('J3', 'Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical', 5.0, 28.0, 0, 20, 'LOAD-CELL'),
    # J4: Pressure sensor 3-pin — left side, near ADS1220
    ('J4', 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical', 5.0, 45.0, 0, 22, 'PRESSURE'),
    # J5: ARM switch — bottom edge
    ('J5', 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', 25.0, 72.0, 0, 25, 'ARM-SW'),
    # J6: E-match output — bottom edge
    ('J6', 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', 40.0, 72.0, 0, 26, 'E-MATCH'),

    # === POWER SUPPLY CHAIN (near J1, top-left) ===
    # D3: Schottky — right after J1
    ('D3', 'Diode_SMD:D_SMA', 14.0, 12.0, 0, 5, 'SS54'),
    # C15: LM7805 input cap — ≤5mm from U4 input
    ('C15', 'Capacitor_SMD:C_0603_1608Metric', 20.0, 12.0, 0, 5, '330nF'),
    # U4: LM7805 — main regulator
    ('U4', 'Package_TO_SOT_SMD:TO-263-3_TabPin2', 26.0, 12.0, 0, 1, 'LM7805'),
    # C16: LM7805 output cap — ≤5mm from U4 output
    ('C16', 'Capacitor_SMD:C_0603_1608Metric', 32.0, 12.0, 0, 1, '100nF'),

    # === EXCITATION LC FILTER (near load cell path) ===
    ('L1', 'Inductor_SMD:L_0805_2012Metric', 14.0, 22.0, 0, 1, '10uH'),
    ('C17', 'Capacitor_SMD:C_0805_2012Metric', 20.0, 22.0, 0, 6, '10uF'),

    # === ADS1256 THRUST ADC (center-left, near J3) ===
    # Placed 15mm from J3, analog zone
    ('U2', 'Package_SO:SSOP-28_5.3x10.2mm_P0.65mm', 30.0, 30.0, 0, 0, 'ADS1256'),
    # Decoupling ≤2mm from power pins
    ('C1', 'Capacitor_SMD:C_0603_1608Metric', 27.0, 26.0, 0, 1, '100nF'),   # AVDD
    ('C2', 'Capacitor_SMD:C_0603_1608Metric', 27.0, 28.0, 0, 1, '100nF'),   # AVDD
    ('C3', 'Capacitor_SMD:C_0805_2012Metric', 33.0, 26.0, 0, 1, '10uF'),    # AVDD bulk
    ('C4', 'Capacitor_SMD:C_0805_2012Metric', 33.0, 28.0, 0, 1, '10uF'),    # AVDD bulk
    ('C5', 'Capacitor_SMD:C_0603_1608Metric', 27.0, 34.0, 0, 3, '100nF'),   # DVDD
    ('C6', 'Capacitor_SMD:C_0603_1608Metric', 33.0, 34.0, 0, 3, '100nF'),   # DVDD
    ('C7', 'Capacitor_SMD:C_0603_1608Metric', 30.0, 37.0, 0, 0, '100nF'),   # VREF
    # Crystal ≤5mm from ADS1256
    ('Y1', 'Crystal:Crystal_HC49-U_Vertical', 37.0, 30.0, 0, 0, '7.68MHz'),
    ('C8', 'Capacitor_SMD:C_0402_1005Metric', 36.0, 35.0, 0, 2, '22pF'),
    ('C9', 'Capacitor_SMD:C_0402_1005Metric', 39.0, 35.0, 0, 2, '22pF'),
    # Input protection — near J3 trace path
    ('R3', 'Resistor_SMD:R_0402_1005Metric', 14.0, 30.0, 0, 20, '100R'),
    ('R4', 'Resistor_SMD:R_0402_1005Metric', 14.0, 33.0, 0, 21, '100R'),
    ('D2', 'Package_TO_SOT_SMD:SOT-23', 18.0, 30.0, 0, 0, 'TVS'),
    # SPI series resistors — between U2 and Teensy
    ('R9', 'Resistor_SMD:R_0402_1005Metric', 42.0, 28.0, 0, 7, '33R'),
    ('R10', 'Resistor_SMD:R_0402_1005Metric', 42.0, 30.0, 0, 8, '33R'),
    ('R11', 'Resistor_SMD:R_0402_1005Metric', 42.0, 32.0, 0, 9, '33R'),

    # === ADS1220 PRESSURE ADC (center, near J4) ===
    ('U3', 'Package_SO:TSSOP-16_4.4x5mm_P0.65mm', 30.0, 48.0, 0, 0, 'ADS1220'),
    ('C10', 'Capacitor_SMD:C_0603_1608Metric', 27.0, 44.0, 0, 1, '100nF'),  # AVDD
    ('C11', 'Capacitor_SMD:C_0603_1608Metric', 27.0, 46.0, 0, 1, '100nF'),  # AVDD
    ('C12', 'Capacitor_SMD:C_0805_2012Metric', 33.0, 44.0, 0, 1, '10uF'),   # AVDD bulk
    ('C13', 'Capacitor_SMD:C_0603_1608Metric', 27.0, 52.0, 0, 3, '100nF'),  # DVDD
    ('C14', 'Capacitor_SMD:C_0603_1608Metric', 33.0, 52.0, 0, 3, '100nF'),  # DVDD
    ('R5', 'Resistor_SMD:R_0402_1005Metric', 14.0, 47.0, 0, 22, '100R'),
    # SPI series resistors
    ('R12', 'Resistor_SMD:R_0402_1005Metric', 42.0, 46.0, 0, 12, '33R'),
    ('R13', 'Resistor_SMD:R_0402_1005Metric', 42.0, 48.0, 0, 13, '33R'),
    ('R14', 'Resistor_SMD:R_0402_1005Metric', 42.0, 50.0, 0, 14, '33R'),

    # === TEENSY 4.1 (center-right, large module) ===
    # Teensy 4.1: 61mm × 18mm. Two 1×24 headers spaced 15.24mm (600mil)
    ('J7', 'Connector_PinHeader_2.54mm:PinHeader_1x24_P2.54mm_Vertical', 55.0, 37.0, 0, 0, 'TEENSY-L'),
    ('J8', 'Connector_PinHeader_2.54mm:PinHeader_1x24_P2.54mm_Vertical', 70.24, 37.0, 0, 0, 'TEENSY-R'),

    # === XBEE 3 (right side, digital zone) ===
    ('J9', 'Connector_PinHeader_2.54mm:PinHeader_2x10_P2.00mm_Vertical', 82.0, 20.0, 0, 0, 'XBEE3'),

    # === IGNITION CIRCUIT (bottom zone, separated from analog) ===
    # K1: Relay — bottom center
    ('K1', 'Relay_THT:Relay_SPDT_HF46F', 32.0, 65.0, 0, 0, 'HF46F'),
    # Q1: NPN driver — near relay
    ('Q1', 'Package_TO_SOT_SMD:SOT-23', 25.0, 65.0, 0, 2, 'MMBT3904'),
    # D1: Flyback diode — across relay coil
    ('D1', 'Diode_SMD:D_SOD-323', 32.0, 60.0, 0, 0, '1N4148WS'),
    # R1: Base resistor
    ('R1', 'Resistor_SMD:R_0402_1005Metric', 20.0, 65.0, 0, 19, '1k'),
    # R2: Pull-down (safety)
    ('R2', 'Resistor_SMD:R_0402_1005Metric', 22.0, 68.0, 0, 2, '10k'),

    # === LEDs (right edge, visible) ===
    ('LED1', 'LED_SMD:LED_0603_1608Metric', 90.0, 10.0, 0, 27, 'GREEN'),
    ('R6', 'Resistor_SMD:R_0402_1005Metric', 90.0, 13.0, 0, 27, '330R'),
    ('LED2', 'LED_SMD:LED_0603_1608Metric', 93.0, 10.0, 0, 28, 'RED'),
    ('R7', 'Resistor_SMD:R_0402_1005Metric', 93.0, 13.0, 0, 28, '330R'),
    ('LED3', 'LED_SMD:LED_0603_1608Metric', 96.0, 10.0, 0, 29, 'YELLOW'),
    ('R8', 'Resistor_SMD:R_0402_1005Metric', 96.0, 13.0, 0, 29, '330R'),

    # === TEST POINTS ===
    ('TP1', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 10.0, 8.0, 0, 4, 'VBAT'),
    ('TP2', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 35.0, 8.0, 0, 1, '+5V'),
    ('TP3', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 50.0, 8.0, 0, 3, '+3V3'),
    ('TP4', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 12.0, 27.0, 0, 20, 'AINP'),
    ('TP5', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 12.0, 35.0, 0, 21, 'AINN'),
    ('TP6', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 12.0, 44.0, 0, 22, 'PRES'),
    ('TP7', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 45.0, 35.0, 0, 11, 'DRDY1'),
    ('TP8', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 45.0, 52.0, 0, 16, 'DRDY2'),
    ('TP9', 'TestPoint:TestPoint_Pad_1.0x1.0mm', 18.0, 65.0, 0, 19, 'RELAY'),
]


def make_smd_fp(ref, fp_lib, rx, ry, rot, net_id, value):
    x, y = pos(rx, ry)
    return f"""  (footprint "{fp_lib}"
    (layer "F.Cu")
    (uuid "{uid()}")
    (at {x} {y} {rot})
    (property "Reference" "{ref}" (at 0 -2) (layer "F.SilkS") (uuid "{uid()}")
      (effects (font (size 0.8 0.8) (thickness 0.12))))
    (property "Value" "{value}" (at 0 2) (layer "F.Fab") (uuid "{uid()}")
      (effects (font (size 0.8 0.8) (thickness 0.12))))
    (pad "1" smd rect (at -0.5 0) (size 0.8 0.8)
      (layers "F.Cu" "F.Paste" "F.Mask") {net_str(net_id)} (uuid "{uid()}"))
    (pad "2" smd rect (at 0.5 0) (size 0.8 0.8)
      (layers "F.Cu" "F.Paste" "F.Mask") {net_str(2)} (uuid "{uid()}"))
  )
"""


def make_tht_fp(ref, fp_lib, rx, ry, rot, net_id, value, pin_count=2, pitch=2.54):
    x, y = pos(rx, ry)
    pads = []
    for p in range(pin_count):
        py_off = p * pitch - (pin_count - 1) * pitch / 2
        shape = "rect" if p == 0 else "circle"
        pads.append(f'    (pad "{p+1}" thru_hole {shape} (at 0 {py_off:.4f}) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask") (uuid "{uid()}"))')
    pads_str = "\n".join(pads)
    return f"""  (footprint "{fp_lib}"
    (layer "F.Cu")
    (uuid "{uid()}")
    (at {x} {y} {rot})
    (property "Reference" "{ref}" (at 0 {-(pin_count-1)*pitch/2 - 2.5:.1f}) (layer "F.SilkS") (uuid "{uid()}")
      (effects (font (size 0.8 0.8) (thickness 0.12))))
    (property "Value" "{value}" (at 0 {(pin_count-1)*pitch/2 + 2.5:.1f}) (layer "F.Fab") (uuid "{uid()}")
      (effects (font (size 0.8 0.8) (thickness 0.12))))
{pads_str}
  )
"""


def make_component(ref, fp_lib, rx, ry, rot, net_id, value):
    if 'PinHeader_1x' in fp_lib:
        count_str = fp_lib.split('PinHeader_1x')[1].split('_')[0]
        return make_tht_fp(ref, fp_lib, rx, ry, rot, net_id, value, int(count_str))
    elif 'PinHeader_2x' in fp_lib:
        count_str = fp_lib.split('PinHeader_2x')[1].split('_')[0]
        return make_tht_fp(ref, fp_lib, rx, ry, rot, net_id, value, int(count_str) * 2)
    elif 'MountingHole' in fp_lib:
        x, y = pos(rx, ry)
        return f"""  (footprint "{fp_lib}"
    (layer "F.Cu")
    (uuid "{uid()}")
    (at {x} {y})
    (property "Reference" "{ref}" (at 0 -3) (layer "F.SilkS") (uuid "{uid()}")
      (effects (font (size 0.8 0.8) (thickness 0.12))))
    (property "Value" "{value}" (at 0 3) (layer "F.Fab") (uuid "{uid()}")
      (effects (font (size 0.8 0.8) (thickness 0.12))))
    (pad "1" thru_hole circle (at 0 0) (size 6.0 6.0) (drill 3.2) (layers "*.Cu" "*.Mask") {net_str(net_id)} (uuid "{uid()}"))
  )
"""
    elif 'TestPoint' in fp_lib:
        x, y = pos(rx, ry)
        return f"""  (footprint "{fp_lib}"
    (layer "F.Cu")
    (uuid "{uid()}")
    (at {x} {y})
    (property "Reference" "{ref}" (at 0 -1.5) (layer "F.SilkS") (uuid "{uid()}")
      (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "{value}" (at 0 1.5) (layer "F.Fab") (uuid "{uid()}")
      (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" smd rect (at 0 0) (size 1.0 1.0)
      (layers "F.Cu" "F.Paste" "F.Mask") {net_str(net_id)} (uuid "{uid()}"))
  )
"""
    elif any(pkg in fp_lib for pkg in ['SSOP', 'TSSOP', 'SOT-23', 'TO-263', 'D_SMA', 'D_SOD', 'LED_0603', 'Crystal', 'Relay']):
        return make_smd_fp(ref, fp_lib, rx, ry, rot, net_id, value)
    else:
        return make_smd_fp(ref, fp_lib, rx, ry, rot, net_id, value)


# ============================================================
# Build the PCB file
# ============================================================
print("=== TMS V3 PCB Generation ===")
print(f"Board: {BOARD_W}mm × {BOARD_H}mm, 2-layer")

lines = []

# Header
lines.append(f"""(kicad_pcb
  (version 20240108)
  (generator "tms-v3-gen-revD")
  (generator_version "2.0")
  (general
    (thickness 1.6)
    (legacy_teardrops no)
  )
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user "B.Mask")
    (39 "F.Mask" user "F.Mask")
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user "B.Fabrication")
    (49 "F.Fab" user "F.Fabrication")
  )
  (setup
    (pad_to_mask_clearance 0.05)
    (allow_soldermask_bridges_in_footprints no)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros no)
      (usegerberextensions yes)
      (usegerberattributes yes)
      (usegerberadvancedattributes yes)
      (creategerberjobfile yes)
      (dashed_line_dash_ratio 12.000000)
      (dashed_line_gap_ratio 3.000000)
      (svgprecision 4)
      (plotframeref no)
      (viasonmask no)
      (mode 1)
      (useauxorigin no)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.000000)
      (pdf_front_fp_property_popups yes)
      (pdf_back_fp_property_popups yes)
      (dxfpolygonmode yes)
      (dxfimperialunits yes)
      (dxfusepcbnewfont yes)
      (psnegative no)
      (psa4output no)
      (plotreference yes)
      (plotvalue yes)
      (plotfptext yes)
      (plotinvisibletext no)
      (sketchpadsonfab no)
      (subtractmaskfromsilk yes)
      (outputformat 1)
      (mirror no)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "fabrication/")
    )
  )
""")

# Nets
for net_id, net_name in NETS:
    lines.append(f'  (net {net_id} {net_name})')
lines.append('')

# Board outline
bx1, by1 = pos(0, 0)
bx2, by2 = pos(BOARD_W, BOARD_H)
lines.append(f"""  (gr_rect
    (start {bx1} {by1})
    (end {bx2} {by2})
    (stroke (width 0.15) (type solid))
    (fill none)
    (layer "Edge.Cuts")
    (uuid "{uid()}")
  )
""")

# Silkscreen text
sx, sy = pos(BOARD_W/2, BOARD_H - 2)
lines.append(f"""  (gr_text "TMS V3 - PSI Rocketry"
    (at {sx - 20} {sy})
    (layer "F.SilkS")
    (uuid "{uid()}")
    (effects (font (size 1.5 1.5) (thickness 0.2)) (justify left bottom))
  )
  (gr_text "Rev 1 · Lee Taeho · 2026-08-24"
    (at {sx - 20} {sy + 2})
    (layer "F.SilkS")
    (uuid "{uid()}")
    (effects (font (size 1 1) (thickness 0.15)) (justify left bottom))
  )
""")

# Zone labels on silkscreen
zone_labels = [
    (15, 5, "POWER"),
    (30, 20, "ANALOG"),
    (60, 20, "DIGITAL"),
    (82, 12, "RF"),
    (30, 58, "IGNITION"),
]
for zx, zy, ztxt in zone_labels:
    lx, ly = pos(zx, zy)
    lines.append(f"""  (gr_text "{ztxt}"
    (at {lx} {ly})
    (layer "Cmts.User")
    (uuid "{uid()}")
    (effects (font (size 1.2 1.2) (thickness 0.15)) (justify left bottom))
  )
""")

# Components
print("Placing components...")
for comp in COMPONENTS:
    ref, fp, rx, ry, rot, net_id, value = comp
    lines.append(make_component(ref, fp, rx, ry, rot, net_id, value))

# Ground stitching vias — perimeter every 10mm + near ADCs
print("Adding ground stitching vias...")
via_positions = []
# Perimeter vias
for vx in range(10, int(BOARD_W), 10):
    via_positions.append((vx, 3.0))
    via_positions.append((vx, BOARD_H - 3.0))
for vy in range(10, int(BOARD_H), 10):
    via_positions.append((3.0, vy))
    via_positions.append((BOARD_W - 3.0, vy))
# Near ADS1256
for vx in [25, 30, 35]:
    for vy in [25, 32, 38]:
        via_positions.append((vx, vy))
# Near ADS1220
for vx in [25, 30, 35]:
    for vy in [43, 48, 53]:
        via_positions.append((vx, vy))

for vx, vy in via_positions:
    x, y = pos(vx, vy)
    lines.append(f'  (via (at {x} {y}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 2) (uuid "{uid()}"))')

# Ground zones on F.Cu and B.Cu
print("Adding ground zones...")
zx1, zy1 = pos(0, 0)
zx2, zy2 = pos(BOARD_W, BOARD_H)
for layer in ["F.Cu", "B.Cu"]:
    lines.append(f"""  (zone
    (net 2)
    (net_name "GND")
    (layer "{layer}")
    (uuid "{uid()}")
    (hatch edge 0.5)
    (connect_pads (clearance 0.2))
    (min_thickness 0.2)
    (filled_areas_thickness no)
    (fill yes (thermal_gap 0.3) (thermal_bridge_width 0.25))
    (polygon
      (pts
        (xy {zx1} {zy1})
        (xy {zx2} {zy1})
        (xy {zx2} {zy2})
        (xy {zx1} {zy2})
      )
    )
  )
""")

# Close
lines.append(')')

# Write
pcb_content = '\n'.join(lines)
PCB_PATH.write_text(pcb_content)
print(f"Written to: {PCB_PATH}")
print(f"File size: {PCB_PATH.stat().st_size} bytes")
print(f"Components: {len(COMPONENTS)}")
print(f"Stitching vias: {len(via_positions)}")
print()
print("=== PCB generation complete ===")
print("Next steps:")
print("  1. Open in KiCad to assign real footprints (replace placeholders)")
print("  2. Import netlist from schematic")
print("  3. Run Freerouting or route manually")
print("  4. Run DRC")
print("  5. Export Gerbers")
