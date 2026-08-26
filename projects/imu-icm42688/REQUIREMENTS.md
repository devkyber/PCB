# Requirements — imu-icm42688 rev1

> **Status: RECONSTRUCTED FROM THE AS-BUILT BOARD, 2026-08-25. Owner review
> required.** Written backwards out of the schematic, the layout and the
> archived datasheet, so it describes what exists rather than what was
> wanted. Open questions are marked **[OWNER]**. Every number below is quoted
> from `datasheets/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf` or measured
> from the board — none are recalled.

## Purpose
A 6-axis IMU breakout: TDK InvenSense ICM-42688-P (3-axis gyro + 3-axis
accelerometer) on a 6-pin 2.54mm SPI header. No onboard regulator, no MCU —
the host stack supplies +3V3 and does all compute. It is the attitude source
for a rocketry avionics stack; the barometer lives on its own board
(`baro-bmp390`) so either can be revised without touching the other.

## Electrical
- Supply: **+3V3 from the host**, one rail feeding both VDD and VDDIO.
  Datasheet §3.3.1: VDD **1.71 – 3.6 V**, VDDIO **1.71 – 3.6 V**. 3.3V sits
  near the top of both ranges with margin.
- Rails generated: **none.**
- Current (§3.3.1): low-noise mode 6-axis gyro+accel **0.88 mA**; accel only
  0.28 mA; gyro only 0.73 mA; full-chip sleep **7.5 µA**. Board total is
  under 1 mA — no thermal or trace-width considerations anywhere.
- **Supply noise: the datasheet specifies `Power Supply Noise ... 10 mV
  peak-peak` (§3.3.2).** This is a requirement on the board and it is five
  times tighter than the BMP390's 50 mVpp. It is the reason C1/C2/C3 are the
  values they are, and the reason the previous 100nF-only decoupling was a
  spec violation rather than a preference.
- Supply ramp (§3.3.2): monotonic, **0.01 – 3 ms** from 10% to 90%.
  **[OWNER]** Not verified against the host's rail behaviour. A slow or
  non-monotonic 3V3 ramp on the stack can leave the part mis-initialised.
- Interface: **4-wire SPI**, up to **24 MHz** (§3.5). AP_CS on pin 12.
- Signal levels: 3.3V logic. VIH = 0.7 x VDDIO, VIL = 0.3 x VDDIO (§3.3.2),
  so a 3.3V host drives it directly with no level shifting.

## Mechanical
- Board outline: **24.0 x 19.0 mm**, 1.6mm FR4, 2 layers, 1oz copper.
  Grown from a nominal 20x15mm once real footprint geometry was in hand —
  the 6-pin 2.54mm header alone spans 12.7mm.
- Mounting holes: 2 x M2 plated, at MCP (6.0, 18.0) and (24.0, 13.0).
- **[OWNER] Sensor orientation is a requirement, and it is not recorded
  anywhere.** The datasheet prints the axis convention on the pinout diagram
  (Figure 4: +X, +Y, +Z relative to pin 1). An IMU mounted in an unknown
  orientation produces an attitude solution that is wrong in a way no bench
  test catches. Decide and document which board axis points along the
  airframe, and mark it on the silkscreen.
- **[OWNER] Rigidity of the mount.** A gyro measures the board, not the
  rocket. Compliant standoffs let the board resonate and the gyro faithfully
  reports that resonance as vehicle rotation.

## Interfaces
| Connector | Signal set | Mates with | Notes |
|---|---|---|---|
| J1 | +3V3, GND, SPI_SCLK, SPI_SDI, SPI_SDO, SPI_CS | 6-pin 2.54mm header, **through-hole, hand-soldered** | JLCPCB SMT does not fit THT; sourced (C37208) so the BOM is complete |
| TP1 / TP2 / TP3 | +3V3, GND, INT1 | probe pads | INT1 (data-ready) broken out but unused in rev1 |

## Environment
- Temperature: **specified range −40 to +85 °C** (§3.3.1). Note the wording:
  *"Performance parameters are not applicable beyond Specified Temperature
  Range"*. Several drift figures are characterised only over **0 to +70 °C**
  (gyro) and −40 to +85 °C (accel).
- **[OWNER] Accelerometer full scale is ±16 g maximum** (§3.2). Rocket
  launch and especially recovery-deployment shock routinely exceed that. The
  part does not fail, it **clips**, and a clipped accelerometer trace
  integrates into a badly wrong velocity. Decide whether ±16 g covers the
  flight profile or whether a second high-g accelerometer is needed.
- Gyro full scale: up to **±2000 °/s** (§3.1), which covers typical roll
  rates with margin.
- Vibration: all-SMD passives; the only mechanically loaded part is the
  through-hole header, which is the strongest joint on the board.

## Success criteria
- Enumerates over SPI at up to 24 MHz and returns a WHO_AM_I of `0x47`.
- Gyro zero-rate output stable to within its datasheet ZRO spec at rest,
  measured on the assembled board (**±0.5 °/s** initial tolerance, §3.1).
- Rail noise at U1's VDD pad stays under the datasheet's **10 mVpp** limit
  while sampling — measured at the pad, not at the header. This is the
  criterion the original 100nF-only decoupling would have failed silently.
- Sustained sampling at the intended ODR with no FIFO overruns over a
  30-minute run.
- Survives a representative vibration profile without a reading dropout.
