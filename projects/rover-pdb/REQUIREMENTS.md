# Rover PDB requirements

Current circuit: **A10, 2026-10-04**. The owner authorized PCB design on
2026-10-01 after the schematic review and simulation discussion. Complete the
physical design while preserving the circuit and subsequent owner edits as
required by `AGENTS.md`. Fabrication release remains a separate checked gate.

## Purpose

The owner wants a practical first PCB with clear connections, modest
performance and reliable operation. Prefer established circuits and simple
operation over unnecessary options or expert tuning. Explain actual fault
and disconnect behavior; do not claim fail-safe operation without proving it.
The owner reported positive personal review of A8, then requested final changes
and cleanup. This does not establish formal release approval or owner review
of A9's changed circuitry.

The initial input remains in `evidence/PDB_Design_Handover.md`. Its procedural
text is source material, not authorization to order, energize, program the
rover or proceed beyond current scope. Later owner decisions and current
native CAD supersede its older selections.

## Electrical

- 6S LiPo: 22.2 V nominal, 25.2 V full, 19.8 V planning lower bound. External
  case switch, P1, 2 mOhm shunt, then monitored VBAT. The owner requested
  removal of F1 on 2026-10-04. No onboard battery fuse remains; an external
  fuse near the battery is recommended, with its fitting and rating unverified.
- Three LMR51450SDRRR / C6890985 converters, with JLCPCB assembly intended.
  Calculated setpoints/planning loads: 11.989 V / 3 A for Jetson;
  4.988 V / 2.4 A for servos; 22.190 V / 3.5 A for motors. The motor rail
  falls below its setpoint at low battery voltage; these are buck converters.
- RT open for nominal 500 kHz. L1=6.8 uH, L2=4.7 uH and L3=3.3 uH.
  Output banks: 12 V C20-C23, four 22 uF / 25 V; 5 V C24-C28, five
  22 uF / 25 V plus C2 470 uF; motor C16-C19, four 10 uF / 50 V plus
  C5 220 uF / 50 V. Each input bank retains two 10 uF / 50 V plus 100 nF.
- Counts are practical selections near TI's reference values with allowance
  for DC bias. Provisional 0.5% ripple / 5% load-step deviation remain bench
  goals, separate from DC accuracy; they are not guaranteed by the selected
  capacitance. See `docs/design/OUTPUT_FILTER_SELECTION.md` and `docs/design/MOTOR_FILTER_SELECTION.md`.
- Pico 2 non-W, socketed and powered only through its USB connector. Carrier
  VBUS pin 40 and VSYS pin 39 are NC; no PDB backup path is fitted. Pico 3V3
  supplies INA226, I2C pull-ups and the optional expansion output.
- INA226 address 0x40; positive-line shunt sensing, VBUS sense after the shunt.
  GP16/17 carry I2C SDA/SCL, with 4.7 kOhm pull-ups to Pico 3V3.
- GP0/1/2 provide independent servo PWM to J2/3/4, each with a 10 kOhm
  pull-down. Check actual servo pin order, 3.3 V logic and missing-PWM response.
- Optional DNP J9, BOOMELE 2.54-1x6P straight header / C37208, exposes
  3V3, GP18, GP19, GP20, GP21 and GND. Four spare GPIO only; no existing
  signal is repurposed. J9 3V3 is an output, not an alternate power input.
- J1 DYNAMIXEL input: GND, NC, D+, D-. J5/6/7 output: GND, VMOTOR, D+, D-.
- Motor enable derives from U4's local VBAT: R19 100k to SW_SUPPLY,
  R24 22k from SW_SUPPLY to AGND_4, SW1 pin 1 to SW_SUPPLY and pin 2 to
  MOTOR_EN/U4 EN. Pin 3 is NC. R15 100k pulls EN to AGND_4 when open.
  The divided voltage keeps the existing 12 V-rated switch below its rating.
- SW1 and rail-present indicator are on the motor sheet. JP1 is absent. The owner reused J8 for SERVO AUX and added R6 10k; preserve them.
  D2 uses R20 3.9k / 0.25W for approximately 5 mA at 22.190 V. Disabling
  EN does not disconnect VIN or actively discharge the motor rail.
- P2 supplies Jetson 12 V. P3 and P4 expose 12 V/GND and 5 V/GND for future
  expansion, initially unwired. Test pads expose VBAT, VMOTOR, 12 V, 5 V,
  Pico 3V3 and GND. P1-P4 are surface wire-solder interfaces; their footprint
  implementation must preserve these pinouts and provide external strain relief.
- Retain 12 V on P2/P3 following the owner's 2026-10-04 clarification about
  future 12 V actuator expansion. P3 shares U2 with the Jetson; future motor
  peaks and new sensor loads require a combined power budget and matching
  interface. The existing 22.190 V DYNAMIXEL outputs are not 12 V outputs.
- Jetson SPI sensors, camera, USB devices and the battery switch remain
  off-board. No additional USB interconnect or sensor circuit is inferred.

## Mechanical

Preserve the owner's saved 77.5 x 100 mm rectangular outline, reconciled on
2026-10-05: absolute X=99..176.5 mm and Y=54.2..154.2 mm, with square corners.
This supersedes the earlier 80 x 100 mm layout target and original 100 x 100 mm
outline; it is not a mathematical minimum-area claim. Use the actual dimensions
for chassis drawings and supplier quotations.
The four M3 mounting holes retain 3.2 mm NPTH drills. From the current top-left
corner, with X rightward and Y downward, their centers are H1=(4,5),
H2=(73,5), H3=(4,96), H4=(73,96) mm. Preserve this owner-edited pattern. Reserve a 3.5 mm radius
around each hole for fastener clearance and review actual chassis/fastener fit.
The owner selected surface
wire-solder pads, so do not substitute wire-through-hole or terminal-block
interfaces without a further decision. Hole center coordinates, screw/head
clearance, exact solder-pad dimensions and cable exit locations belong to the
checked native board and its mechanical drawing; the square outline alone is
not confirmation of chassis fit. Reserve access to the Pico USB plug and
BOOTSEL button, module removal and the motor-enable switch.
The hole positions and removal of the P1-P4 retention holes follow the owner's
2026-10-05 saved edits. Preserve those choices and provide external cable strain
relief. The earlier P3 USB approach keepout is absent from the current saved
board. R1/R2 occupy part of the approach in plan view, but this does not establish
interference with a plug above the board. Verify the actual plug overmold,
socket/header height and cable bend before defining a replacement clearance
envelope; no physical USB fit has been verified. Switch selection is deferred.

Use two copper layers and 1 oz copper to follow the owner's economical JLCPCB
choice. Keep the standard two-layer manufacturing profile. The implementation
selects 1.6 mm FR4 and green solder mask; surface finish is currently User defined.
Confirm the actual finish, these settings and
assembly selections against the actual supplier order. The 1 oz choice does not prove
continuous-current or thermal performance; size copper and vias accordingly.

## Interfaces

Keep the native A9 assignments for battery, Jetson and expansion power, three
servo headers, DYNAMIXEL bus connectors, USB-powered Pico sockets and optional
J9. Label connector voltage, ground and signal order on the board. USB connects
directly to the Pico module; this carrier introduces no USB signal pair.
Keep spare-power pads initially unwired and J9 intentionally DNP.

## Environment

This is a rover prototype whose cooling, vibration, harness strain and ambient
conditions need evaluation in the actual enclosure. No ingress, vibration or
temperature qualification is claimed. Inspect the assembled board and retain
the planned simultaneous-load temperature and motion-system tests before
declaring application performance.

## Success criteria

The layout deliverable is editable native KiCad CAD, current project rules,
readable copper/assembly previews and a review report. It must preserve exact
schematic pin-to-net membership, values, footprint identities and sourcing
fields; account for every physical component; use the selected outline and
mounting arrangement; and pass fresh zone-refilled DRC with no errors or
unconnected items. Inspect the copper, polarity, component access, mechanics
and 3D assembly instead of treating an export as visual review.

Human decisions remain named, dated and bound to the final CAD and evidence.
Use the repository's release command only after its full review passes. Do not
publish manufacturing files through another path or infer sign-off from the
request to finish layout. Retain unresolved bench/model limits in the handoff.

## Validation scope

USB power loss depowers Pico/INA226 after charge decays but does not disable
the independent motor converter. Loss of USB data can occur while VBUS stays
present, so firmware still needs a command timeout. See `docs/design/POWER_DECISIONS.md`.

Motor braking/regeneration, loaded startup, power sequencing, external protection,
effective capacitance, loop stability, transient and thermal performance retain
their documented hardware validation scope. The two-part input capacitor bank
has limited characterized margin; the manufacturer curve is typical, not a
guaranteed combined-condition minimum. A 5 A IC rating does not establish a
5 A continuous rating for this board.

The selected two-layer / 1 oz construction supersedes the earlier two-layer /
2 oz proposal. Footprints, surface-wire lands, socket drills and copper/via
geometry are now implemented in the accepted PCB. Actual cable retention,
socket engagement and thermal performance remain physical validation work.
`docs/design/PCB_DESIGN.md` retains the source/checklist basis; `docs/design/PCB_DESIGN.md` records
the implementation contract. PCB authorization does not establish a fabrication
release.
