# TMS A2 design basis

Date:2026-10-14. Author:Codex. A2 is installed under an explicit owner-approved
schematic-stage exception, derived from the saved native A1 hierarchy. The
transaction preserves the empty PCB and its project/rule files. No engineering
or fabrication sign-off is represented. Full reasoning and all 120 references
are in docs/design/COMPONENT_VERIFICATION.md and the current PDF/CSVs.
See docs/review/ELECTRICAL_REVIEW_A2.md for the exact exception and checks.

| Area | A2 selection | Remaining qualification |
| --- | --- | --- |
| Main supply | LMR51430YFDDCR1.1MHz FPWM;3.3uH;30uF input/100uF output nominal;4.98175V;1A plan | Actual effectiveC, loop response, rail bounds, thermal/layout |
| Input clamp | Unidirectional SMBJ18A-13-F after SS54;18V stand-off/29.2V specified pulse clamp | Cable hotplug, pulse/temperature bounds, external fuse |
| Analog supply | BLM21PG601SN1D;<=60mA allocation; selected KEMET local bypasses | Ferrite resonance/noise and distribution drop |
| Reference | Two TNPU10k0.02%2ppm/K;OPA350; exact Panasonic FT47uF/100uF16V | Reference-loop stability/settling/noise and calibration |
| Thrust | OPA2388 buffers, ADS1256 PGA64/bufferON/1000SPS; unused inputs NC | Sensor5V acceptance, noise/loading/settling, calibration |
| Pressure |100k/33.2k0.1%25ppm/K;47nFC0G1206;OPA388 buffer;47Ohm/10nF ADC drive | Assumed sensorRs<=100Ohm, calibration/temperature/settling |
| Radio | Owner XB3-24AST-J/A24-HASM-450;47pF+1uF+10uF;TXU0204 power-off buffer | Ripple, sleep/recovery, physical/antenna fit, rail ramps |
| Teensy UART | Serial3 TX14/RX15/CTS19/RTS18, documented direct CTS | Firmware flow control and throughput |
| Ignition | Separate2S, physicalseriesARM, HF46F-G/5-HS1T NO relay/AO3400A | Assumed<=2A/>=4.2Ohm; actual load/fuse/switch/wire/copper/fault tests |
| Connectors | J5 corrected1.50mm drill/5.08pitch; J6 PCB-mountXT60PW-F; J1/J4/J6 positive2/return1 | AMASS drawing-revision conflict, purchased part/polarity/mating fit |
| Provenance | Five source-hash-bound local-footprint receipts; all120 pad maps checked | Physical fit and current named human acceptance |
| Accuracy/band | Author1%FS calibrated static target near20-30C;50Hz;1000SPS/channel | Complete-chain validation; not a full-temperature accuracy guarantee |
| Mechanics | EmptyPCB;100x80 versus100x100 conflict remains unresolved | Enclosure, holes, height, cable/USB/SD/RP-SMA access before layout |

Digi manualW controls the47pF recommendation. Old8.2pF guidance is recorded as
a revision conflict. The small capacitor and frequency change are now explicit.
BAV199/TPD protection is coarse ESD/steering, not a guaranteed sustained-battery-
miswire network. Correctly wired0-5V sensors are the operating contract; actual
power sequencing/injection and fault qualification remain open.

The owner authorized engineering assumptions, not invented measurements or
human sign-off. The subsequent A2 exception authorizes schematic circuit/library/document
installation only. All shared/project release decisions remain unsigned.

## Retained restart record - historical inputs

# TMS decisions and unresolved conflicts

Restart record from Git 7b8dc18's TMS requirements, basis, reference review and
PDR. Exact retained sources are indexed in evidence/index.yaml. Historical
Match statements do not qualify a new component, pin map or circuit.

## Carry forward

| Area | Choice | Source / next check |
| --- | --- | --- |
| Controller | Teensy 4.1, removable female sockets, 3.3 V logic | PDR §1; archived PJRC front/back cards |
| Acquisition | ADS1256 thrust, ADS1220 pressure, split SPI0/SPI1 | PDR §2–4, D-02/D-05; TI datasheets/EVMs |
| Load cell | BCA-100L, historical 5 V excitation, PGA 64, buffer OFF | PDR §2; verify common mode, impedance and full reference network |
| Data | microSD primary; 1 kHz/channel, 60 Hz monitoring targets | PDR §6/TBD register; throughput remains unverified |
| Radio | Standard XBee 3 802.15.4, UART, external antenna concept | PDR §1/6/7A; Digi hardware reference |
| Supplies | 4S electronics, separate 2S ignition, distinct IGN_GND | Later requirements and PDR D-01/D-06; bonding review remains |
| Control | Physical ARM plus remote FIRE, default OFF; no physical FIRE button | PDR §7/D-07; dummy-load and fault tests |
| Continuity | Deferred for V3 | PDR D-10; add only after an explicit requirement change |
| Harness | XT30 batteries, XT60 output, terminal ARM, JST XH sensors | Later owner decisions supersede PDR connector entries |
| Fabrication | Standard two-layer/1.6 mm/1 oz process | Historical requirements; confirm recreated layout feasibility |

## Resolve before the affected circuit is finalized

| Issue | Conflict or missing proof | Required treatment |
| --- | --- | --- |
| ADS1256 reference | PDR calls it internal; later native audit found only U2/C7 on VREF_P/VREF_N | Choose a real external reference; use ADS1256_ti.pdf and TI SBAU090E. A capacitor is not a reference source |
| Pressure range | PDR AVDD reference for 0–5 V versus later internal 2.048 V | Resolve reference and input scaling together against the actual sensor and error budget |
| 5 V power | PDR 30/70 mA estimate omits complete upstream Teensy/radio/SD demand | Recalculate load/heat at 16.8 V before retaining LM7805 or selecting another topology |
| 3.3 V power | PDR 163 mA estimate and stated regulator capacity are historical | Verify exact Teensy and MCU/SD/radio/ADC peak demands |
| Igniter | E-match assumptions superseded by nichrome | Measure actual cold resistance/current/duration and size the path from them |
| Mechanics | PDR 100×80/3.5 mm inset versus retired CAD 100×100/4.5 mm inset | Confirm outline/holes; do not import the old placement |
| XBee | Undersized old courtyard; exact module/antenna/socket unknown | Select physical parts and rebuild/verify geometry from vendor drawings |
| Clock | PDR 22 pF versus later 33 pF for another 20 pF-load crystal; 0402/0603 supplier mismatch | Select exact crystal and calculate load network with parasitics; neither old value is universal |
| ADS1256 supply pin | Old waiver calls pin 15 DVDD; datasheet identifies RESET 15, DVDD 16 | Extract true pin map; verify each supply independently; inherit no waiver |
| Sequencing/default OFF | Historical claims marked resolved without present hardware evidence | Verify ramps, reset/brownout, interlock and fault behavior on the new circuit |
| Filtering/protection | PDR calls 33-ohm SPI resistors 5 V fault protection and calls 10 µH an inductor/ferrite interchangeably | Reassess actual components and protection rather than inheriting those claims |

## Defects not to repeat

Never invent Teensy/XBee pin assignments. Supply ADS1220 AVDD 12 and DVDD 13
with their own bypasses. Do not waive distance to conceal a missing capacitor.
Check relay numbering from the selected variant's drawing (historical candidate:
coil 1/6, COM 2, NO 3). Use real connector classes/packages instead of generic
headers with misleading Values. Re-source package-compatible capacitors.

No old deviation, sign-off, placement, preview or fabrication package transfers.
The retained review profile lists ten board-specific human decisions; the shared
loader adds its mandatory schematic and layout items.
