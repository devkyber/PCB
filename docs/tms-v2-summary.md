# TMS V2 (2025-TMS-3.0) Design Summary

**Date:** 2026-08-24  
**Status:** Previous revision — superseded by TMS V3

---

## Overview

Module-based TMS board built in EasyEDA. Arduino Nano as MCU, two ADS1115 breakout modules for ADC, relay module for ignition, SD card module for logging. Single shared battery with LM7810 + LM7805 regulators.

## Power

| Rail | Source | Loads |
|------|--------|-------|
| VBAT | Polymer LiPo via XT60U-F (U33) | Input to all regulators, igniter circuit |
| 10V | LM7810L-TA3-T (U23, TO-220) | ADS1115 modules (analog supply) |
| 5V | 3x LM7805 (U2/U26/U27, TO-263) | Arduino Nano, relay module, SD card reader, digital logic |
| GND | Common | Shared across all subsystems |

Single battery powers both electronics and igniter. No power domain separation.

## MCU

- Arduino Nano (U24), socketed module
- 5V logic
- I2C bus: SDA/SCL to both ADS1115s (shared bus, 4.7kΩ pull-ups U10/U11)
- SPI bus: MOSI/MISO/SCK/CS to SD card module (SZH-EKBZ-005)
- Digital outputs: D9 (relay signal), D10 (relay control)

## ADC

- 2x ADS1115 breakout modules on shared I2C bus
- Barometer ADC: address set via `Address_B` net
- Load cell ADC: address set via `Address_L` net
- Address selection via 20kΩ resistor dividers (U29/U30/U37)
- Both powered from 10V rail
- 16-bit resolution, max 860 SPS

## Ignition

- 1-Channel 5V Relay Module (SZH-EK093, U36) with opto-isolator
- HW-674 DC-DC converter steps battery voltage to 14V for igniter
- Relay controlled via Arduino D10
- Annotation: "Relay High 시 COM 과 NC 붙음" (relay high → COM connects to NC)
- Single inhibit: relay control signal only (no physical ARM switch on PCB)

## Sensors

- Load cell: connected via WJ127-5.0-5P screw terminal (U1)
- Pressure/barometer: connected via WJ127-5.0-5P screw terminal (U3)
- Control signals from external switch box via WJ127-5.0-4P connectors (CN1/CN2)

## Connectors

| Ref | Part | Purpose |
|-----|------|---------|
| U33 | XT60U-F | Battery input |
| U1, U3 | WJ127-5.0-5P (5-pin screw) | Sensor connectors |
| CN1, CN2 | WJ127-5.0-4P (4-pin screw) | Control signal from switch box |
| U14, U17, U19, U34, U35 | DG127-5.0-02P (2-pin screw) | Relay signal/delay, igniter |
| U6, U9 | Pin Header 1x10 2.54mm | Arduino Nano socket |

## SD Logging

- External SD card reader module (SZH-EKBZ-005, U22)
- Connected via SPI (MOSI/MISO/SCK/CS)

## Known Issues (identified in review)

1. **No decoupling caps** — BOM has zero capacitors. No bypass on regulators or ADC modules.
2. **Shared ground** — Relay coil return current flows through ADC ground path. Ground bounce affects 16-bit ADC readings.
3. **Single battery** — Igniter and measurement share power. Igniter current spike causes supply droop.
4. **No physical ARM switch on PCB** — Relay control is software-only. Annotation notes external switch box provides control signals.
5. **Resistor annotation** — Schematic note "저항 수정 필요" (resistor values need modification) at sensor section, unresolved.
6. **Module-based** — All active components are breakout modules. Limited signal integrity control, no SMT assembly possible at JLCPCB.

## BOM (12 line items)

| # | Part | Qty | LCSC |
|---|------|-----|------|
| 1 | WJ127-5.0-4P | 2 | C192779 |
| 2 | WJ127-5.0-5P | 2 | C2940948 |
| 3 | LM7805 (TO-263) | 3 | C22467097 |
| 4 | Pin Header 1x10 2.54mm | 2 | — |
| 5 | 4.7kΩ (0603) | 2 | C4355002 |
| 6 | DG127-5.0-02P | 5 | C669322 |
| 7 | SD Card Reader module | 1 | — |
| 8 | LM7810L-TA3-T (TO-220) | 1 | C95077 |
| 9 | Arduino Nano | 1 | — |
| 10 | 20kΩ (0402) | 3 | C3017501 |
| 11 | XT60U-F | 1 | C19191801 |
| 12 | 1-CH Relay Module | 1 | — |
