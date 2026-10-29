# I2C temperature sensor design basis

Revision A1, 2026-10-29. Fresh MCP9808T-E/MS breakout; all source documents are in evidence/index.yaml. No owner CAD or frozen regression input was used.

## Sourced decisions

| Reference | Function | Selected part | Source | Relevant condition | Evidence location | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Temperature sensor | MCP9808T-E/MS | Microchip DS20005095B and DS50002480A | Board restricted to 3.3 V +/-5% | DS20005095B pp3-5, Table 3-1 p11, pp33/35/40-42; DS50002480A p47 U5 | Match IC pin functions, local ceramic bypass and I2C/ALERT topology; deviate from reference DFN package and fixed-ground address pins by selecting verified MSOP package and resistively defaulted selectable address pins. |
| R1/R2 | I2C pullups | RC0805FR-074K7L | Yageo exact-part specification | 4.7 kOhm, 1%, 0.125 W at 70 C | p1 electrical and 0805 dimension table | Match selected part; bus rise time and parallel pullup loading require actual-host assessment. |
| R3/R4/R5/R6 | ALERT pullup and address pulldowns | RC0805FR-0710KL | Yageo exact-part specification | 10 kOhm, 1%, 0.125 W at 70 C | p1 electrical and 0805 dimension table | Match selected part; external shunts deliberately source small pulldown currents. |
| C1 | Local U1 bypass | C0805C104K5RACTU | KEMET exact-part specification; Microchip layout guidance | 100 nF, 10%, X7R, 50 V | KEMET p1 dimensions/electrical; DS20005095B section 6.1 p35 | Match recommended 0.1..1 uF local ceramic bypass; host supplies any needed bulk capacitance. |
| J1 | Power/I2C header | 61300411121 | Wuerth exact-part drawing | Four contacts, 2.54 mm pitch | p1 package, pin and PCB-hole drawing | Match generic straight header numbering; physical mate/orientation unqualified. |
| J2/JP1/JP2/JP3 | ALERT and address headers | 61300211121 | Wuerth exact-part drawing | Two contacts, 2.54 mm pitch | p1 package, pin and PCB-hole drawing | Match generic straight header numbering; no shunts fitted by default. |

Microchip's demonstration board DS50002480A p47 uses MCP9808 U5 in DFN, a 0.1 uF local bypass C7, I2C connections, ALERT and fixed-low address inputs. It is circuit evidence for the IC, not mechanical evidence for the chosen MSOP variant. DS20005095B supplies the actual MSOP pinout, package and operating behavior. This board adds three independently shunted, pulldown-default address inputs; it does not reproduce the demonstration board or claim its qualification.

## Limits and calculations

At 3.465 V and initial -1% tolerance, each I2C pullup draws at most 3.465/4653 = 0.745 mA when held low. Each 10 kOhm branch draws at most 3.465/9900 = 0.350 mA. With SCL/SDA/ALERT all low, all three address shunts fitted and U1's 400 uA datasheet operating maximum, the calculated sum is about 3.29 mA, excluding host loads/leakage, transitions and faults. A 5 mA supply allowance is a design budget, not a measured or protective current limit. Maximum resistor dissipation is below 2.6 mW under these assumptions. Drift, aging and out-of-range use are excluded.

Using t_r ~= 0.8473*R*C, a 4.7 kOhm pullup needs approximately C <=75 pF for 300 ns rise time. Consequently the IC's 400 kHz capability is not a board guarantee. Begin at 100 kHz and scope the actual bus; assess both sink-current limits and rise time after combining parallel pullups. No capacitor or cable-length qualification is inferred from this calculation.

Address bits are defined even without shunts: 10 kOhm to ground, no floating digital inputs. Shunts tie the address pin directly to the same 3V3 supply and only source the respective pulldown current. Address 0x18..0x1F uses the normal 0011 A2 A1 A0 code. The alternate address code in the datasheet is not used. Power-on CONFIG=0 leaves ALERT disabled; software must set thresholds and enable the output before relying on indications.

Temperature tracks the die and its thermal coupling to this board. The ground plane beneath U1 follows Microchip section 6.1. Resistor pullups and powered host/cable heat can affect readings; no precision ambient measurement, thermal isolation or calibration claim is made.

## Library and layout basis

Local symbol and footprint/model lineage is in libs/SYMBOL_PROVENANCE.json and libs/PROVENANCE.json. MCP9808_MSOP inherits the official MCP9804_MSOP geometry: inheritance is flattened, the inherited stale datasheet URL is replaced, and pin 3's electrical type is corrected from output to open_collector per Microchip section 3.3. All eight pin numbers/functions remain unchanged.

The official MSOP-8_3x3mm_P0.65mm footprint has the verified 0.65 mm pitch and 3 x 3 mm nominal body. Its IPC-style 1.625 x 0.4 mm pads differ from Microchip's p42 recommended 1.45 x 0.45 mm lands; this is disclosed generic library geometry, with soldering/physical fit still open. Wuerth recommends 1.10 +/-0.15 mm PCB holes; the generic header's 1.0 mm drill lies within that interval but does not establish worst-case mating fit. Mounting holes are fabricated NPTH features, not purchased parts.

The dated workspace two-layer/1 oz baseline supplies rules. Native board geometry uses 0.25 mm signal escapes, 0.4 mm supply distribution, 0.6/0.3 mm vias, and a refilled ground plane. No controlled impedance, current-carrying certification, autorouting or manufacturability approval is claimed. The generic official 3D packages preserve their upstream transforms.
