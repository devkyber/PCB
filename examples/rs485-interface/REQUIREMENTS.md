# RS-485 interface requirements

## Purpose

An editable educational UART-to-half-duplex-RS-485 board using TI THVD1450DR.
Unbuilt DRAFT; no fabrication approval or measured link performance.

## Electrical

- Externally regulated 3.3 V nominal, 3.0–3.6 V at J1, current-limited bench source.
- Separate 3.3 V UART TX, RX, DE and active-low nRE; common ground required.
- 10 kOhm pull-downs make DE low (driver disabled) and nRE low (receiver enabled).
- 100 nF local ceramic bypass and 1 uF nominal board-entry ceramic reservoir.
- A/B/GND bus interface, no isolation or board-level surge/ESD rating.
- Removable 120 Ohm, 1% end termination via a two-pin header and shunt.
- Initial validation target: 115200 baud on a short bench link, not a guaranteed rating.

## Mechanical

50 × 35 mm, two copper layers, 1.6 mm nominal board, four 3.2 mm NPTH mounting holes.
SOIC-8 and 0805/1206 passives with through-hole headers; exact fit remains unqualified.

## Interfaces

J1: 1=3V3, 2=GND, 3=TX/DI into board, 4=RX/RO out, 5=DE, 6=nRE.
J2: 1=A, 2=B, 3=GND. JP1 shunt enables end termination only when installed.
Use both physical cable ends' appropriate termination; remove JP1 at middle nodes.
No MCU, cable, second transceiver or power supply is included or qualified.

## Environment

Indoor low-voltage educational bench use, approximately room temperature.
No outdoor wiring, industrial transient, ground-offset, isolation, EMC or safety qualification.

## Success criteria

Native editable single-sheet A4 CAD, sourced exact parts, project-local libraries/models,
routed PCB, fresh ERC/DRC and exact native schematic/PCB parity, inspected schematic
and board renders. Current human release decisions and physical/bench validation remain open.
