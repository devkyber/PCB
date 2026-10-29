# I2C temperature sensor requirements

Status: unbuilt educational DRAFT, revision A1. No fabrication, assembly or application approval is recorded.

## Purpose

Provide an inspectable 3.3 V MCP9808 temperature-sensor breakout with eight selectable I2C addresses and a separate ALERT connection. This is a fresh native design, not a replacement for an owner board.

## Electrical

- U1 is Microchip MCP9808T-E/MS, the eight-lead MSOP variant. Pins 1 SDA, 2 SCL, 3 ALERT, 4 GND, 5 A2, 6 A1, 7 A0, 8 VDD follow DS20005095B Table 3-1. The MSOP has no exposed pad.
- Operate this board from regulated 3.3 V +/-5%, with a common-ground host whose bus pullups and logic use the same rail. The chip's wider supply rating does not authorize other board voltages. No regulator, level translation, reverse-polarity, hot-plug or ESD protection is provided.
- J1: 1=3V3, 2=GND, 3=SCL, 4=SDA. J2: 1=ALERT_N, 2=GND. Both are unkeyed male 2.54 mm headers; check mating orientation before power.
- R1/R2 are fixed 4.7 kOhm 1% SCL/SDA pullups. Start with a short, 100 kHz bench bus; measure rise time and assess all parallel bus pullups before use. No bus length, capacitance or 400 kHz performance is qualified.
- R3 is a 10 kOhm ALERT pullup. The open-drain output is disabled after reset; firmware must configure thresholds, polarity and enable it. ALERT is a notification, not a safety interlock.
- R4/R5/R6 are 10 kOhm A0/A1/A2 pulldowns. JP1/JP2/JP3 each connect 3V3 (pin 1) to the selected address bit (pin 2) when an external shunt is fitted. Default assembly has no shunts, giving address 0x18. Address is 0x18 + A0 + 2*A1 + 4*A2; power off before changing shunts.
- C1 is a local 100 nF X7R ceramic decoupler between U1 VDD and GND. Supply bulk capacitance is the host's responsibility; the board adds no bulk capacitor.
- All six purchased MPN/package choices must have exact archived manufacturer documents. Official generic KiCad library geometry and models require local source receipts; these do not qualify actual part fit.

## Mechanical

Two-layer 1 oz PCB, nominal 45 x 35 mm outline, four unplated 3.2 mm mounting holes at a 39 x 29 mm center rectangle. Surface-mount 0805 passives and MSOP-8 U1 are intended for skilled hand assembly. Header, screw-head, enclosure and cable clearances remain unqualified. Generic 3D models are inspection aids.

## Interfaces

J1 requires a correctly oriented four-position 2.54 mm female mating cable. J2 requires a two-position mate if ALERT is used. Optional 2.54 mm shorting shunts for JP1..3 are user-provided accessories, absent in the default assembly; no exact shunt or mating connector is selected or claimed qualified.

## Environment

Indoor dry room-temperature bench demonstration. Board ambient-temperature accuracy, thermal time constant, self-heating, external heat coupling, condensation, EMC and environmental performance are unmeasured. The chip's datasheet accuracy is a device specification, not a demonstrated breakout accuracy.

## Success criteria

Retain a readable single A4 sheet, complete native routing, zero native ERC and refilled DRC violations, no unconnected items, exact native pin/net and schematic UUID-link parity, and verifiable evidence/library bytes. Inspect the whole sheet and circuit details after native export. Full review may remain blocked by unsigned human and supplier assembly decisions.

Before physical use: verify exact components/fit and bus voltage, scope rise time with the actual host/cable/pullups, read device identity/address and temperature, exercise all address settings and ALERT configuration, measure current, and compare temperature behavior against a suitable reference. None of these bench results is presently asserted.
