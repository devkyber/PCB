# TMS

A2 is installed under the owner-approved schematic-stage exception of
2026-10-14. The eight-sheet native hierarchy is the editable authority.
The PCB is still empty; project and design-rule files are preserved.

Read the [verification and circuit learning guide](docs/design/COMPONENT_VERIFICATION.md)
or its [printable PDF](output/component-verification.pdf). The current exports contain
[all 120 components](output/component-verification.csv),
[all 380 pins, including 59 NCs](output/pin-connections.csv), the
[schematic BOM](output/schematic-bom.csv), and
[external system/assembly parts](output/external-system-parts.csv).
The BOM is a selected schematic inventory, not an approved assembly order.

Open [tms.kicad_pro](tms.kicad_pro) in KiCad 10, then the root
[schematic](tms.kicad_sch). The [current drawing](output/tms-schematic.pdf)
covers the overview, power, Teensy, thrust, reference, pressure, radio and ignition.

A2 corrects the battery-enable short, all three AMASS connector polarities,
radio power-off/UART flow control, ADC loading and unused pins. It selects exact
passive orders, updates the main supply and adds the missing RF bypass.
[Electrical review](docs/review/ELECTRICAL_REVIEW_A2.md) binds the reviewed bytes,
checks and installation exception. Earlier A0/A1 records remain historical.

Start with [requirements](REQUIREMENTS.md), [design basis](DESIGN_BASIS.md),
[current calculations and component rationale](docs/design/COMPONENT_VERIFICATION.md),
and the [firmware contract](docs/design/FIRMWARE_CONTRACT_A2.md).
Exact sources are indexed in [evidence/index.yaml](evidence/index.yaml).
CAPTURE.md, PDR.md and tms-v3-bom.md retain historical capture/design inputs.

The author-selected accuracy, bandwidth, rail-transient, sensor loading and
ignition load assumptions are explicit qualification targets, not measurements.
Remaining work includes enclosure/outline selection, purchased-part/socket fit,
reference stability, rail ripple/thermal/transients, input sequencing/faults,
calibration, data throughput and actual harness/load qualification.
All 12 shared/project human review decisions remain unsigned; no fabrication
or live-ignition approval exists. Schematic checks do not qualify an unrouted PCB.

```sh
uv run pcb-copilot research projects/tms --verify-schematic-parts
uv run python projects/tms/check_schematic.py
uv run pcb-copilot review projects/tms
```
