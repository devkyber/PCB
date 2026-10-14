# Requirements — TMS recreation basis

Choices carried forward on 2026-10-13 from the historical TMS requirements,
design basis and [PDR](PDR.md). These are design inputs, not verification of
retired CAD. [DESIGN_BASIS.md](DESIGN_BASIS.md) separates conflicts and provisional
implementations. Do not ask the owner to restate recorded choices.

## Purpose

Stand-side static-fire instrumentation: acquire thrust and chamber pressure,
log locally, transmit monitoring telemetry to a distant ground station, and
provide remotely commanded ignition with a physical ARM inhibit.

## Electrical

- Socketed Teensy 4.1; 3.3 V logic. Use archived PJRC front/back cards for
  every numbered socket pin.
- Electronics supply: 4S LiPo, recorded range 12–16.8 V, generating 5 V.
  Previous LM7805 implementation is provisional until the complete upstream
  load and thermal budget is recalculated. The Teensy's onboard 3.3 V supply
  is also provisional pending MCU, SD, radio and ADC peak-load review.
- Thrust: BCA-100L, 100 kgf, 2 mV/V bridge; historical 5 V excitation.
  Dedicated ADS1256IDBR on SPI0, PGA 64, buffer OFF; nominal 7.68 MHz clock.
  Its external reference source is unresolved. Do not inherit the PDR's
  unsupported internal-2.5-V-reference claim.
- Pressure: IPSU-GP1K5-6, recorded 0–1500 psi, 0–5 V signal and 9–32 V
  supply, historically powered directly from electronics VBAT.
  ADS1220IPWR on SPI1, AVDD 5 V / DVDD 3.3 V. Reference/input scaling remain
  unresolved: later internal-2.048 V choice conflicts with PDR AVDD-reference
  operation over 0–5 V.
- Verify ADC decoupling and cable protection against actual datasheets/EVMs.
  SPI series resistors do not establish safe 5 V fault protection.
- Standard/non-PRO XBee 3 802.15.4, UART, external antenna concept.
  Exact module/antenna/socket and physical fit remain open.
- Separate 2S LiPo ignition supply; IGN_GND distinct from electronics GND
  unless an explicit reviewed bonding decision changes this.
- External hardware ARM in series with normally-open relay contacts; remote
  FIRE energizes a default-OFF coil driver. No onboard physical FIRE button.
  HF46F-G/5-HS1T, MMBT3904 and flyback diode were the previous implementation;
  retain as candidates pending actual load and reset/fault review.
- Actual igniter is nichrome bridgewire, not the PDR commercial e-match.
  Actual cold resistance, current, duration and path margins remain unmeasured.
  Continuity sensing was deliberately deferred for V3.
- Verify reset, brownout, supply sequencing, interlocks and single faults
  with a non-energetic dummy load.

## Mechanical

The PDR specified 100 × 80 mm and four M3 holes with 3.5 mm insets:
(3.5,3.5), (96.5,3.5), (96.5,76.5), (3.5,76.5) mm from the board corner.
The retired CAD used 100 × 100 mm with 4.5 mm insets. Confirm the desired
envelope before placement; neither conflict is silently decided here.

Historical fabrication target: two layers, 1.6 mm FR4, 1 oz copper, green mask,
lead-free HASL. Reassess if the recreated circuit requires another process.
Module height, enclosure, antenna and cable clearances still need physical input.

## Interfaces

| Interface | Recorded choice | Qualification still required |
| --- | --- | --- |
| Both battery inputs | XT30PW-F; historical C2913282 | Later owner choice supersedes PDR XT60 inputs; exact sourcing/fit |
| Igniter output | XT60-F; historical C98734 | Harness choice retained; margin from measured load |
| ARM switch | WJ500V-5.08-2P; historical C8465 | External screw-terminal connection |
| Load cell | JST B5B-XH-A; historical C157991 | Five pins including shield; supersedes PDR screw terminals |
| Pressure | JST B3B-XH-A; historical C144394 | Three-pin polarized connection |
| Teensy | Female removable 2.54 mm socket rows | Vendor pin map and mating geometry |
| XBee | Two ten-pin female 2.00 mm rows | Exact module/antenna/socket, spacing/drill fit |
| Debug | Rail, ADC and driver probe points; status LEDs | New designators; no old netmap import |

C-numbers are historical identities, not live stock or package approval.

## Environment

Outdoor motor test stand with vibration, blast, moisture and dust exposure.
Review retention, enclosure protection, shielding and grounding explicitly.
Retain the external SMA/U.FL-pigtail concept subject to the selected XBee
variant and actual mechanical installation.

## Success criteria

Inherit targets of 1 kHz per channel, primary microSD logging, zero missing
burn samples, a 30 s burn and 60 s pre/post capture (exact split unspecified).
Telemetry targets: 60 Hz, 32-byte frames, UART 115200, at most 5% monitoring
packet loss. These are requirements, not proven acquisition configuration.

Verify range/noise/accuracy against an error budget, link range against actual
operator distance, and thermal/power margin at simultaneous load. Confirm output
stays OFF with ARM open, through reset/brownout and without a valid FIRE command.
Only fresh review decisions and the shared release checks approve new CAD.
