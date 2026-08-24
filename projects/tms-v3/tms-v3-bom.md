# TMS V3 Full BOM — Rev D (All Findings Resolved)

## Active Components

| Ref | Part | Description | Package | LCSC | Qty | Type |
|-----|------|-------------|---------|------|-----|------|
| U1 | Teensy 4.1 | MCU module, Cortex-M7 600MHz | Module (socket) | — | 1 | Module |
| U2 | ADS1256IDBR | 24-bit ADC, thrust (SPI0) | SSOP-28 | C28186 | 1 | Extended |
| U3 | ADS1220IPWR | 24-bit ADC, pressure (SPI1) | TSSOP-16 | C132290 | 1 | Extended |
| U4 | LM7805CT | 5V 1.5A regulator | D2PAK (TO-263) | C22467097 | 1 | Extended |
| U5 | XBee 3 802.15.4 | Wireless module (UART2) | Module (socket) | — | 1 | Module |
| K1 | HF46F-G/5-HS1T | 5V relay, 7A AgSnO₂ contacts | THT relay | C65122 | 1 | Extended |
| Q1 | MMBT3904 | NPN transistor, relay driver | SOT-23 | C20526 | 1 | Basic |
| D1 | 1N4148WS | Flyback diode, relay coil | SOD-323 | C57759 | 1 | Basic |
| D2 | PESD5V0S2BT | TVS diode, ADC input protection | SOT-23 | C356017 | 2 | Basic |
| D3 | SS54 | Schottky diode, reverse polarity protection | DO-214AC (SMA) | C22452 | 1 | Basic |
| Y1 | AT-41CD2-7.68MHZ | Crystal, ADS1256 clock | HC-49 | C891749 | 1 | Extended |

## Passive Components — Capacitors

| Ref | Value | Description | Package | LCSC | Qty | Type |
|-----|-------|-------------|---------|------|-----|------|
| C1,C2 | 100nF | ADS1256 AVDD decoupling | 0603 C0G | C14663 | 2 | Basic |
| C3,C4 | 10uF | ADS1256 AVDD bulk | 0805 X5R 16V | C15850 | 2 | Basic |
| C5,C6 | 100nF | ADS1256 DVDD decoupling | 0603 C0G | C14663 | 2 | Basic |
| C7 | 100nF | ADS1256 VREFP–VREFN decoupling (F-13) | 0603 C0G | C14663 | 1 | Basic |
| C8,C9 | 22pF | Crystal Y1 load caps | 0402 C0G | C1555 | 2 | Basic |
| C10,C11 | 100nF | ADS1220 AVDD decoupling | 0603 C0G | C14663 | 2 | Basic |
| C12 | 10uF | ADS1220 AVDD bulk | 0805 X5R 16V | C15850 | 1 | Basic |
| C13,C14 | 100nF | ADS1220 DVDD decoupling | 0603 C0G | C14663 | 2 | Basic |
| C15 | 330nF | LM7805 input cap | 0603 X7R 50V | C1615 | 1 | Basic |
| C16 | 100nF | LM7805 output cap | 0603 C0G | C14663 | 1 | Basic |
| C17 | 10uF | Excitation LC filter cap (F-05/D-04) | 0805 X5R 16V | C15850 | 1 | Basic |

**Total capacitors: 18**

## Passive Components — Inductors

| Ref | Value | Description | Package | LCSC | Qty | Type |
|-----|-------|-------------|---------|------|-----|------|
| L1 | 10uH | Excitation LC filter inductor (F-05/D-04) | 0805 | C1046 | 1 | Basic |

## Passive Components — Resistors

| Ref | Value | Description | Package | LCSC | Qty | Type |
|-----|-------|-------------|---------|------|-----|------|
| R1 | 1kΩ | NPN base resistor | 0402 | C11702 | 1 | Basic |
| R2 | 10kΩ | NPN base pull-down (F-08, safety) | 0402 | C25744 | 1 | Basic |
| R3 | 100Ω | ADS1256 AINP series protection (F-06) | 0402 | C25076 | 1 | Basic |
| R4 | 100Ω | ADS1256 AINN series protection (F-06) | 0402 | C25076 | 1 | Basic |
| R5 | 100Ω | ADS1220 AIN0 series protection (F-06) | 0402 | C25076 | 1 | Basic |
| R6 | 330Ω | Power LED current limit | 0402 | C25179 | 1 | Basic |
| R7 | 330Ω | ARM LED current limit | 0402 | C25179 | 1 | Basic |
| R8 | 330Ω | TX LED current limit | 0402 | C25179 | 1 | Basic |
| R9 | 33Ω | SPI0 MOSI series protection (F-04) | 0402 | C25077 | 1 | Basic |
| R10 | 33Ω | SPI0 MISO series protection (F-04) | 0402 | C25077 | 1 | Basic |
| R11 | 33Ω | SPI0 SCK series protection (F-04) | 0402 | C25077 | 1 | Basic |
| R12 | 33Ω | SPI1 MOSI series protection (F-04) | 0402 | C25077 | 1 | Basic |
| R13 | 33Ω | SPI1 MISO series protection (F-04) | 0402 | C25077 | 1 | Basic |
| R14 | 33Ω | SPI1 SCK series protection (F-04) | 0402 | C25077 | 1 | Basic |

**Total resistors: 14**

## LEDs

| Ref | Value | Description | Package | LCSC | Qty | Type |
|-----|-------|-------------|---------|------|-----|------|
| LED1 | Green | Power indicator | 0603 | C72043 | 1 | Basic |
| LED2 | Red | ARM/fire indicator | 0603 | C72041 | 1 | Basic |
| LED3 | Yellow | TX activity | 0603 | C72038 | 1 | Basic |

## Connectors

| Ref | Part | Description | LCSC | Qty | Type |
|-----|------|-------------|------|-----|------|
| J1 | XT60U-F | Electronics battery input (with D3 reverse protection) | C19191801 | 1 | Extended |
| J2 | XT60U-F | Igniter battery input | C19191801 | 1 | Extended |
| J3 | KF301-5.0-5P | Load cell connector (EXC+, EXC−, SIG+, SIG−, SHIELD) | C474881 | 1 | Extended |
| J4 | KF301-5.0-3P | Pressure sensor connector (V+, SIG, GND) | C474880 | 1 | Extended |
| J5 | KF301-5.0-2P | ARM switch connector | C474879 | 1 | Extended |
| J6 | KF301-5.0-2P | Igniter output connector | C474879 | 1 | Extended |
| J7 | Pin Socket 1×24 2.54mm | Teensy 4.1 socket (left side) | — | 1 | — |
| J8 | Pin Socket 1×24 2.54mm | Teensy 4.1 socket (right side) | — | 1 | — |
| J9 | Pin Socket 2×10 2.0mm | XBee socket (2 rows × 10 pins) | — | 1 | — |

## Test Points

| Ref | Net | Description | Qty |
|-----|-----|-------------|-----|
| TP1 | VBAT | Battery voltage | 1 |
| TP2 | +5V | Regulated 5V rail | 1 |
| TP3 | +3V3 | Teensy 3.3V output | 1 |
| TP4 | LC_AINP | Load cell SIG+ (after R3) | 1 |
| TP5 | LC_AINN | Load cell SIG− (after R4) | 1 |
| TP6 | PRES_SIG | Pressure sensor output (after R5) | 1 |
| TP7 | ADS1256_DRDY | Thrust ADC data ready | 1 |
| TP8 | ADS1220_DRDY | Pressure ADC data ready | 1 |
| TP9 | RELAY_CTRL | Relay coil NPN collector | 1 |

## Mounting Holes

| Ref | Size | Position (from board corner, 100×80mm board) | Qty |
|-----|------|-----------------------------------------------|-----|
| H1 | M3 | (3.5, 3.5) — top-left | 1 |
| H2 | M3 | (96.5, 3.5) — top-right | 1 |
| H3 | M3 | (3.5, 76.5) — bottom-left | 1 |
| H4 | M3 | (96.5, 76.5) — bottom-right | 1 |

## Net List Summary

| Net | From | To | Notes |
|-----|------|----|-------|
| VBAT | J1 pin 1 | D3 anode → LM7805 IN, J4 V+ (pressure sensor supply) | Through Schottky D3 for electronics |
| +5V | LM7805 OUT | U2 AVDD, U3 AVDD, L1 → excitation, Teensy Vin, K1 coil+ | Main power rail |
| +5V_FILT | L1 out, C17 | J3 EXC+ | Filtered excitation for load cell |
| +3V3 | Teensy 3.3V out | U2 DVDD, U3 DVDD, XBee VCC, pull-ups | Teensy-derived 3.3V |
| GND | Common | All grounds, J3 EXC−/SHIELD | Single solid ground |
| SPI0_MOSI | Teensy pin 11 | R9 → U2 DIN | ADS1256 SPI data in |
| SPI0_MISO | Teensy pin 12 | R10 → U2 DOUT | ADS1256 SPI data out |
| SPI0_SCK | Teensy pin 13 | R11 → U2 SCLK | ADS1256 SPI clock |
| ADS1256_CS | Teensy pin 10 | U2 CS | ADS1256 chip select |
| ADS1256_DRDY | Teensy pin 9 | U2 DRDY | ADS1256 data ready |
| SPI1_MOSI | Teensy pin 26 | R12 → U3 DIN | ADS1220 SPI data in |
| SPI1_MISO | Teensy pin 1 | R13 → U3 DOUT | ADS1220 SPI data out |
| SPI1_SCK | Teensy pin 27 | R14 → U3 SCLK | ADS1220 SPI clock |
| ADS1220_CS | Teensy pin 0 | U3 CS | ADS1220 chip select |
| ADS1220_DRDY | Teensy pin 2 | U3 DRDY | ADS1220 data ready |
| UART2_TX | Teensy pin 8 (TX2) | XBee DIN | XBee serial TX |
| UART2_RX | Teensy pin 7 (RX2) | XBee DOUT | XBee serial RX |
| RELAY_CTRL | Teensy pin 3 | R1 → Q1 base | Relay driver control |
| LC_AINP | J3 SIG+ | R3 → D2a → U2 AINP | Load cell positive |
| LC_AINN | J3 SIG− | R4 → D2a → U2 AINN | Load cell negative |
| PRES_SIG | J4 SIG | R5 → D2b → U3 AIN0 | Pressure sensor output |
| LED_PWR | Teensy pin 4 | R6 → LED1 | Power indicator |
| LED_ARM | Teensy pin 5 | R7 → LED2 | ARM status |
| LED_TX | Teensy pin 6 | R8 → LED3 | TX activity |
| IGN_BATT+ | J2 pin 1 | J5 pin 1 (to ARM switch) | Igniter battery positive |
| IGN_ARM_RET | J5 pin 2 | K1 COM | ARM switch return to relay |
| IGN_OUT | K1 NO | J6 pin 1 | To e-match positive |
| IGN_GND | J2 pin 2 | J6 pin 2 | Igniter battery return |

## Summary

| Category | Count |
|----------|-------|
| ICs | 3 (2 ADC + 1 regulator) |
| Transistors | 1 (NPN relay driver) |
| Modules | 2 (Teensy + XBee) — relay is bare SMT |
| Crystal | 1 |
| Diodes | 4 (1 flyback + 2 TVS + 1 Schottky) |
| Inductors | 1 |
| Capacitors | 18 |
| Resistors | 14 |
| LEDs | 3 |
| Connectors | 9 |
| Test points | 9 |
| Mounting holes | 4 |
| **Total unique line items** | **~45** |
| **JLCPCB Basic parts** | ~30 |
| **JLCPCB Extended parts** | ~8 |
| **Non-JLCPCB (modules, sockets)** | ~4 |
