# GPIO indicator requirements

Status: educational, unbuilt DRAFT. This board is an inspection example, not an approved fabrication or assembly package.

## Purpose

Provide four independent active-high indicators for an external controller's 3.3 V GPIO outputs, while demonstrating a small editable KiCad project and auditable pipeline checks.

## Electrical

- Four independent, active-high LED indicators for externally driven 0 to 3.3 V GPIO signals sharing ground.
- J1 is a five-position 2.54 mm male header: pins 1 through 4 are IN1 through IN4; pin 5 is GND.
- Each input connects through its own 1.1 kOhm, 1% resistor to a red 3 mm LED anode; each LED cathode returns to GND.
- At 3.3 V and the initial 1% resistance tolerance, I <= 3.3 V / 1089 Ohm = 3.031 mA per channel, even if LED forward voltage is taken as zero. Four-channel sum <= 12.122 mA. This is a calculation, not a measurement or GPIO drive guarantee.
- The source controller must support this per-pin and aggregate load; no particular controller is qualified here. Floating/reset inputs need external defined behavior if indication matters.
- The board supplies no voltage, isolation, buffering, level conversion, surge protection or reverse-polarity protection. Inputs must remain between GND and 3.3 V; intended for an indoor bench at room temperature.
- Exact selected manufacturer documents and official KiCad library provenance must be retained locally. No invented pin maps or placeholder footprints/models.
- Native ERC, refilled DRC and schematic/PCB parity must be reported separately from physical fit, brightness and bench qualification.

## Mechanical

Single-sheet readable schematic, native editable two-copper-layer PCB, nominal 45 x 35 mm outline, hand-soldered through-hole parts and two nonplated 3.2 mm mounting holes. Board coordinates span X100..145 mm and Y100..135 mm. Hole centers are (104,104) and (104,131) mm. No enclosure or mating cable is selected; fit and component-height clearance are unqualified.

## Interfaces

J1 is an unkeyed five-position 2.54 mm male header. Pins 1..4 carry IN1..IN4 and pin 5 is GND. A matching five-position 2.54 mm female cable/socket must be selected and checked before use. Pin 1 is square and marked IN1. The board has no power-supply connector.

## Environment

Indoor, dry, room-temperature bench demonstration only. No vibration, shock, humidity, temperature-range, ESD or EMC qualification is claimed. The resistance/current calculation uses initial room-temperature tolerance and omits drift and aging.

## Success criteria

The inspection artifact must show all four channels, a readable complete sheet, zero native ERC/DRC violations, zero unrouted items and exact native schematic/PCB pin-net and UUID-link parity. Every purchased part must have exact archived manufacturer evidence. Physical success remains unmeasured: each channel must respond independently, measured input current must satisfy the specified controller's limits, and brightness must be useful to its owner.

Open before any physical use: verify actual component dimensions and polarity, mating-header orientation, controller drive limits, LED brightness at this low current, assembly/soldering, mounting clearances and measured behavior. No human sign-off is recorded.
