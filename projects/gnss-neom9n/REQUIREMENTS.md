# Requirements — gnss-neom9n rev1

> **Status: RECONSTRUCTED FROM THE AS-BUILT BOARD, 2026-08-25. Owner review
> required.** Written backwards out of the schematic, the layout and the
> archived u-blox documents. Open questions are marked **[OWNER]**. Numbers
> are quoted from `datasheets/NEO-M9N-00B_..._UBX-19014285.pdf` or from
> `reference-designs/..._Integrationmanual_UBX-19014286.pdf`, or measured.

## Purpose
A GNSS receiver breakout: u-blox NEO-M9N-00B with an onboard 3.3V LDO, a
soldered backup cell for warm/hot starts, and a U.FL connector for an
external antenna. It provides position, velocity and a 1PPS timing edge to
a rocketry avionics stack over UART and/or I2C. Concurrent GPS + GLONASS +
Galileo + BeiDou reception in a 12.2 x 16.0 mm module.

## Electrical
- Input: **VIN 3.3–5.5 V** at J1, regulated on-board to 3.3 V by U1
  (Torex XC6206P332MR-G, 200 mA, SOT-23-3).
- Rail generated: **VCC 3.3 V**. Both the module's VCC (pin 23) and the rest
  of the board run from it.
- **[OWNER] The LDO's headroom is not verified against a 3.3 V input.**
  The XC6206 needs its dropout voltage above the output; at VIN = 3.3 V it
  cannot regulate to 3.3 V. This board works at 5 V in and is out of spec at
  the bottom of its own stated input range. Either restate the input as
  4.0–5.5 V, or change the regulator. Flagged, not silently changed, because
  the answer depends on what the stack actually supplies.
- Backup: **BT1, Panasonic CR1220 solder-tab cell direct to V_BCKP (pin 22)**.
  Maintains the RTC and battery-backed RAM so the receiver warm/hot-starts
  instead of cold-starting. Integration manual §4.2.2: *"If V_BCKP is not
  provided, the module performs a cold start at power up."*
- Supply integrity (Integration manual §4.2.1): *"Do not add any series
  resistance greater than 0.2 Ω to the VCC supply"*, and the module draws
  large short-duration peaks when leaving backup mode. C3 (1 µF at the pin)
  and C4 (10 µF bulk) exist for this.
- Interface: **UART + I2C**, selected by D_SEL (pin 2) pulled to VCC via R2.
  Manual: *"open or VCC = UART + I2C; GND = SPI"*. Default UART is
  38400 8N1.
- **V_USB (pin 7) is tied to GND** because USB is unused — manual §4.2.3,
  *"the V_USB pin must be connected to GND"*.

## Mechanical
- Board outline: **34.0 x 40.0 mm**, 1.6 mm FR4, 2 layers, 1 oz copper.
  Grown from a ~25 x 25 mm target to fit real footprint geometry.
- Mounting holes: 2 x M2.5.
- Antenna: **U.FL (Hirose U.FL-R-SMT-1)**, for an external active or passive
  GNSS antenna. RF_IN carries D1 (0.5 pF ESD) at the connector.
- **[OWNER] Antenna type and ground plane are unresolved.** This board feeds
  RF_IN directly from U.FL with no bias-tee, so it assumes a **passive**
  antenna (LNA_EN, pin 14, is left open). A powered/active antenna needs
  VCC_RF fed onto the coax through an inductor. And manual §4.9.5: a patch
  antenna needs *"a sufficient antenna ground plane"* — which is a property
  of the airframe, not of this 34 x 40 mm board.
- **[OWNER] Antenna siting.** Manual §4.9.4: keep the antenna away from
  noisy circuitry. In a rocket that means away from the pyro/ignition
  harness, which is not this board's decision.

## Interfaces
| Connector | Signal set | Mates with | Notes |
|---|---|---|---|
| J1 | VIN, GND | 2-pin 2.54 mm header | 3.3–5.5 V in, see the **[OWNER]** dropout note |
| J3 | VCC, GND, UART_TXD, UART_RXD, I2C_SDA, I2C_SCL | 6-pin 2.54 mm header | TXD is module-out; I2C pulled up by R4/R5 (4.7k) |
| J4 | TIMEPULSE, EXTINT | 2-pin 2.54 mm header | 1PPS out; EXTINT in |
| J2 | RF_IN | U.FL coax | 50 Ω, ESD-protected by D1 |
| TP1 / TP2 | SAFEBOOT_N, RESET_N | probe pads | SAFEBOOT_N for firmware recovery |
| SW1 | RESET_N to GND | tactile, Omron B3U-1000P | manual reset |

## Environment
- Temperature: **[OWNER]** — the tightest part on this board is not the
  module. `BT1` (Panasonic CR1220) and the LCSC-listed switch are rated to
  **+70 °C / +85 °C**, and a primary lithium cell's capacity and shelf life
  degrade sharply with temperature. Confirm the stack's thermal environment.
- Vibration: the backup cell is **soldered, not socketed** — deliberately, so
  it cannot shake loose. It is therefore not field-replaceable.
- ESD: manual §4.9.4 makes RF-input protection mandatory; D1 provides it.
  §4.9.3 additionally warns that pre-charged patch antennas can discharge
  into RF_IN during assembly.

## Success criteria
- Acquires a 3D fix outdoors with a passive antenna and reports it over UART
  at 38400 8N1 within the datasheet's cold-start TTFF.
- **Warm start measurably faster than cold start** after VCC is removed and
  restored — this is the only test that proves BT1 and V_BCKP actually work,
  and it is the reason that circuit exists.
- 1PPS present and stable on J4.
- I2C responds at the module's address with VIN across its accepted range.
- Rail holds up through the backup-to-normal transition current peak that
  §4.2.1 warns about.
