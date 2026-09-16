# Requirements — baro-bmp390 rev1

> **Status: RECONSTRUCTED FROM THE AS-BUILT BOARD, 2026-08-25. Owner review
> required.** This board was designed before the workspace had a Phase 1
> deliverable, so this file was written *backwards* — read out of the
> schematic, the layout, the datasheet and the archived reference. That makes
> it an accurate description of what exists, not a statement of what was
> wanted, and those differ exactly where a requirement was never articulated.
> Four open questions are marked **[OWNER]**. Other statements include cited
> values and reconstructed design assumptions, not completed bench or
> environmental validation.

## Purpose
A minimal barometric-pressure breakout: a Bosch BMP390 on a 4-wire STEMMA-QT /
Qwiic I2C drop, with no onboard regulator and no onboard MCU. It plugs into an
existing avionics stack as an altitude source; the host supplies +3V3 and does
all compute. Deliberately not a flight computer — one sensor, one connector,
one job, so it can be swapped or duplicated without touching the stack.

## Electrical
- Supply: **+3V3 nominal, supplied by the host over the QT cable.** Datasheet
  VDD range 1.65–3.6V, VDDIO 1.2–3.6V (BST-BMP390-DS002-07 p.7 Table 2).
  The nominal rail is within both ranges, near their upper limit; host-supply
  tolerance and transients still need checking at the sensor.
- Rails generated: **none.** No regulator on this board — that is the reason
  C3 (10uF bulk) is retained at the connector: the rail arrives down a cable
  without a local regulator. Host/cable impedance still needs evaluation.
- Current (datasheet §1, values read from the table, not recalled): sleep
  `IDDSL` 1.4µA at 1.8V / 1.5µA at 3.6V; peak `Ipeak` **660–730µA during a
  pressure measurement**; `IDDT` 240–320µA during a temperature measurement.
  Bus pull-ups R1/R2 4.7k draw ~0.7mA each worst case while a line is held
  low. The listed operating loads total under 3mA. This estimate does not
  eliminate fabrication trace-width limits, fault-current checks or thermal
  review of the actual assembly.
- **Supply ripple: the datasheet specifies `VDD ripple max. 50 mVpp`** (§1,
  p.7 Table 2, sensor supply voltage row). C1/C2/C3 support that requirement,
  but their nominal capacitances alone prove neither compliance nor a prior
  violation. Verify ripple at U1 with the intended host, cable and operating
  conditions; supply impedance, capacitor characteristics and layout matter.
- Signal levels: 3.3V logic throughout, no level shifting. SDA/SCL pulled to
  VDDIO by R1/R2 = 4.7k, the datasheet's own recommended value (§6.3 Fig 25).
- I2C address: **0x77 fixed** (SDO tied to VDDIO). Not selectable — see
  DESIGN_BASIS.md. One BMP390 per bus.
- No inductive actuator or ignition path is present. Sensor conversion and
  bus activity still produce changing load current; host/cable transients
  and hot-plug behavior have not been characterized.

## Mechanical
- Board outline: **18.0 x 26.0 mm**, 1.6mm FR4, 2 layers, 1oz copper (JLCPCB
  budget default per CLAUDE.md).
- Mounting holes: **2 x M2 plated (2.2mm), at (2.8, 23.2) and (15.2, 23.2)** —
  both on the edge opposite the connector, 12.4mm apart, 2.8mm inset.
  Pattern follows the archived Adafruit reference board, which keeps
  connector edges hole-free.
  - **[OWNER] Two holes on one edge cantilevers the board about that axis.**
    Fine on a bench, questionable under rocket vibration. A third hole, or a
    diagonal pair on a slightly wider board, is the usual fix. Not changed
    unilaterally because it depends on the stack's standoff pattern, which is
    not recorded anywhere.
- Connector edge: J1 (STEMMA-QT, JST SH 4-pin horizontal) at the low-y edge,
  centred on x. Cable exits along the board axis.
- **[OWNER] Height limit not specified.** Tallest part is J1 at ~2.9mm.
- **[OWNER] Stack position / mating standoff pattern not specified.**

## Interfaces
| Connector | Signal set | Mates with | Notes |
|---|---|---|---|
| J1 | GND, +3V3, SDA, SCL | STEMMA-QT / Qwiic 4-pin JST-SH 1.00mm cable | Host supplies power; polarised, so no reverse-connection protection is fitted |
| TP1 | BMP_INT | test pad, 1.0mm | BMP390 INT broken out for data-ready interrupts; unused in rev1, present so it is not a respin to start using it |

## Environment
- Temperature: BMP390 operational range **−40 to +85°C**, but **full accuracy
  only over 0 to +65°C** (datasheet §1). The board adds no narrower part.
  **[OWNER]** That accuracy window is the real environmental limit for a
  rocket: the sensor keeps working cold, it just stops meeting its stated
  accuracy, and an altitude reading that is silently out of spec is worse
  than one that stops. Decide whether the flight profile stays inside 0–65°C
  or whether the error budget has to absorb it.
- Pressure: full-accuracy range **300–1250 hPa** (datasheet §1) — 300 hPa is
  roughly 9 km, which bounds usable apogee for altitude data.
- Vibration / shock: rocket flight loads. Two consequences already handled —
  all-SMD 0402/0603 passives, and no connector that can back out under load
  except J1 itself, which is latched. See the **[OWNER]** mounting note above;
  that is the real open vibration risk.
- Datasheet §7.2 warns the LGA package is sensitive to PCB bending stress near
  the port hole; the mounting holes are at the far edge from U1, which helps.
- Conformal coating: **must not be applied over the BMP390's port hole** — it
  is a barometric sensor and needs an open path to ambient air. If the stack
  is coated, mask U1.

## Success criteria
- Enumerates at I2C address **0x77** on a 400kHz bus and returns a pressure
  reading within ±50 Pa of a co-located reference barometer at ambient.
- Sustains **50 Hz** sampling over the QT cable with no bus errors across a
  30-minute run.
- Rail ripple at U1's VDD pad stays under the datasheet's **50 mVpp** limit
  while sampling at 50Hz, measured at the pad and not at the connector.
  This remains an unverified measurement criterion; adding C3 does not itself
  establish a pass or prove what the earlier circuit would have measured.
- Survives a vibration profile representative of the intended flight without
  a reading dropout or a cracked solder joint.
