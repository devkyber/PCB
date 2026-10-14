# Requirements - TMS A2 design contract

Fresh recreation started 2026-10-13 from design-bases/tms. The owner confirmed
the sensors and selected XB3-24AST-J / A24-HASM-450 during capture.

## Purpose

Stand-side static-fire instrumentation: acquire thrust and chamber pressure,
log to the Teensy's microSD, transmit monitoring telemetry, and provide a remote
ignition command with an external physical ARM inhibit.

## Electrical

- Socketed Teensy 4.1; 3.3 V I/O; on-module SD is the primary record.
- Electronics: 4S LiPo12-16.8 V, fused and externally protected harness.
  SS54 reverse protection, SMBJ18A input surge clamp, LMR51430YFDDCR nominal4.982V, full 1 A planning
  allocation; see docs/design/CAPTURE.md. The IC's 3 A rating is not a board rating.
- Teensy3.3 V supplies ADC logic/pull-ups only (under 10 mA allocation). Independent
  TLV75533PDBVR supplies RF3.3 V (100 mA allocation). Do not join these outputs.
- Verify simultaneous MCU/SD/RF peaks, thermal margin, startup, power-off
  injection and brownout. Planning allocations are not measured guarantees.
- Thrust: confirmed BCA-100L, 100 kgf, nominal2 mV/V, retained nominal5 V
  excitation. ADS1256IDBR on SPI0, PGA64, bufferON, 7.68 MHz crystal.
  OPA2388 input buffers and a buffered half-excitation reference. Unused analog inputs are NC.
  Verify/calibrate noise, loading, bandwidth, offset and reference settling.
- Pressure: confirmed IPSU-GP1K5-6, 0-1500 psi /0-5 V /9-32 V sensor supply.
  Supply from protected4S VBAT. ADS1220IPWR, AVDD5VA/DVDD3.3 V, 100k/33.2k
  divider, OPA388 unity buffer and47Ohm/10nF ADC drive, internal2.048V reference, gain1 PGA bypass. The sensor rating does
  not expand the board input rating to32 V. Sensor loading needs verification.
- Radio: owner-selected standard XB3-24AST-J through-hole RP-SMA and
  A24-HASM-450 antenna, 3.3V UART through TXU0204 power-off buffering. TeensySerial3 uses TX14/RX15/CTS19/RTS18. The stated USB adapter is assumed at the
  ground station; exact installation and supply capacity remain unverified.
- Separate2S ignition battery. IGN_GND distinct from electronics GND.
  External hardware ARM in series with normally-open HF46F-G/5-HS1T contacts.
  AO3400A coil driver, gate pull-down and flyback diode. No on-board FIRE
  button, continuity sense or physical ARM feedback. Red LED means command state.
- Owner authorized assumptions because measurements are unavailable: ignition load≤2A at8.4V, cold resistance≥4.2Ohm. These are unmeasured contracts. Qualify actual current/duration/energy and reset/brownout/interlocks/faults on a non-energetic dummy load.

## Mechanical

The outline remains unresolved: PDR100x80 mm /3.5 mm insets versus retired
100x100 mm /4.5 mm insets. Confirm enclosure, hole pattern, height and cable
exits before placement. No outline/holes are inherited; PCB is empty.
Historical process: two layers, 1.6 mm FR4, 1 oz, green mask, lead-free HASL target.
Use the dated native geometry baseline, then reassess actual layout/process.
Verify socket, SD/USB access, RP-SMA projection and enclosure fit physically.

## Interfaces

| Ref | Interface | Board-side assignment |
| --- | --- | --- |
| J1 | XT30PW-F electronics battery | 2 positive, 1 electronics GND |
| J2 | B5B-XH-A load cell | 1 EXC+, 2 EXC-, 3 SIG+, 4 SIG-, 5 shield |
| J3 | B3B-XH-A pressure | 1 supply, 2 signal, 3 return; map to sensor DIN1/3/2 |
| J4 | XT30PW-F ignition battery | 2 positive, 1 IGN_GND |
| J5 | WJ500V-5.08-2P external ARM | 1 battery positive to switch, 2 return to relay |
| J6 | XT60PW-F PCB-mount igniter | 2 switched positive, 1 IGN_GND |
| U1 | Teensy 4.1 removable sockets | Two24-contact2.54 mm rows; vendor signal pad IDs |
| U8 | XB3-24AST-J removable sockets | Two ten-contact2 mm rows; RP-SMA envelope |
| JP1 | VIN power shunt | Fit for battery; remove for USB unless VIN/VUSB link is cut |
| TP1-TP10 | Probes | Rails, reference, pressure, DRDY, radio recovery, coil drain |

Historical C-numbers are not stock/package approval. Original C8465 supplier CAD is retained. A2 J5 uses a corrected manufacturer-drawing-derived footprint with1.50mm holes. Exact purchased-part physical fit remains open.
The capture BOM is not an approved assembly order.

## Environment

Outdoor motor test stand with vibration, blast, moisture and dust. Review retention,
protection, EMI, shield/earth bonding, relay suitability and RF separation explicitly.
Ambient limits and enclosure protection are insufficiently specified for final
thermal/environmental qualification.

## Success criteria

- Target1kHz/channel, primary microSD, zero missing burn samples.
- Author assumptions:1%FS calibrated static target near20-30C calibration window,50Hz usable band; pressure sensor output resistance≤100Ohm. Wider temperature accuracy needs compensation/qualification.
- Board thermal screening ambient0-50C; power/ripple/stability and sensor performance are prototype verification targets.
- Record30 s burn plus60 s pre/post; exact pre/post split remains open.
- Monitoring target60 Hz /32-byte frames /UART115200 /at most5% packet loss.
- Timestamp independent ADC DRDY; prove alignment, filter delay, rate, noise,
  accuracy and end-to-end throughput against measurements.
- Confirm OFF with physical ARM open, without valid command, and through the
  documented reset/brownout/fault tests.
- Fresh named human decisions and full shared release checks remain mandatory.
  Schematic/ERC completion does not establish these success criteria.
