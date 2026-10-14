# Requirements — TMS V3 (Thrust Measurement System)

> **Status: 2026-09-20 — cross-checked against the historical
> [`PDR.md`](PDR.md) and the accepted design records.**
>
> This file was first written by reading the as-built board backwards, on the
> belief that no spec existed. One did: a 504-line Preliminary/Critical Design
> Review with a full component register, signal-chain budgets and a TBD
> register, now preserved as `PDR.md`. Phase 1 is not always "write a spec" —
> sometimes it is "find the spec that already exists", and the reference
> search has to cover this repo, not only the internet.
>
> The PDR is a historical source for anything below that cites it; accepted
> CAD and the maintained project records are current authority. Where this
> file and the PDR disagree, the disagreement is stated rather than smoothed over —
> the connector set is the live example: the PDR §1 register specifies XT60U-F
> for both batteries, and the owner superseded it on 2026-08-26 with XT30PW
> for the batteries and XT60 for the **igniter output**. Open questions are
> **[OWNER]**.
>
> **This board fires pyrotechnic igniters. Cold bridgewire resistance/current,
> ignition-path copper suitability, isolated-return intent, reset/brownout
> behavior, and physical connector/module fit remain unresolved human safety
> decisions. Do not fabricate or energize the output before resolving them.**

## Purpose
Static-fire test-stand data acquisition and ignition control for solid rocket
motors. A Teensy 4.1 reads motor thrust from a load cell (ADS1256, 24-bit,
PGA=64) and chamber pressure (ADS1220, 24-bit), streams telemetry over an
XBee 3 2.4 GHz link, and fires the igniter through an armed relay. The board
is stand-side; the operator is at a distance, which is the entire reason the
telemetry link and the remote ARM interlock exist.

## Electrical
- **Two separate batteries, deliberately.** Electronics VBAT is a 4S LiPo
  (12–16.8 V) at J1. The igniter runs from its own 2S LiPo at J2. They share
  no rail: `IGN_GND` is a separate net from `GND`.
  **[OWNER] Confirm the grounding intent.** Two isolated returns is the safe
  choice for a firing circuit; if they are meant to bond at a single point,
  that point must be designed, not left to whichever chassis screw touches.
- Electronics rail chain: `VBAT -> D3 (SS54 Schottky, reverse protection) ->
  U4 (LM7805) -> +5V`, then the Teensy's onboard LDO makes +3V3.
- **[OWNER] LM7805 dissipation is not in the record.** A linear regulator
  dropping 16.8 V to 5 V burns 11.8 V x I. At only 200 mA that is **2.4 W**
  in a TO-263, which needs real copper area, and at 4S the board is at the
  worst end of its own input range. Either budget the current and size the
  pour, or move to a switcher. This is the highest-value open electrical
  question on the board.
- Analog: ADS1256 on SPI0 for the load cell (differential `LC_AINP`/`LC_AINN`,
  external reference `VREF_P`/`VREF_N`); ADS1220 on SPI1 for pressure
  (single-ended `PRES_SIG`, internal 2.048 V reference).
- Ignition chain: `RELAY_CTRL -> Q1 (MMBT3904) -> K1 coil (HF46F-G/5-HS1T)`,
  with D1 (1N4148WS) as the coil flyback. The relay contact carries
  `IGN_BATT+ -> J5 ARM switch -> K1 COM(2) -> K1 NO(3) -> IGN_OUT -> J6`.
  **Firing requires both the external ARM switch closed and the relay
  energised** — a deliberate two-condition interlock.
- **[OWNER] Igniter current is still not specified, and the igniter is
  NOT an e-match.** It is a **nichrome bridgewire across a KNSB grain**
  (owner, 2026-08-26). That changes the number materially: a commercial
  e-match is a matched 1–2 Ω pyrotechnic device, whereas a length of
  nichrome is whatever resistance you cut it to, and it is a *deliberate
  short* across a 2S pack until it burns through. At 7.4 V into 1 Ω that is
  7.4 A; into 3 Ω, 2.5 A. K1's contacts are rated 7 A at 30 VDC (PDR §7), so
  the bridge resistance is what decides whether the relay is inside its
  rating or welding its contacts closed.
  **Measure the cold resistance of the nichrome you actually use, and
  specify a minimum.** Everything downstream — J6's rating, ignition trace
  width, relay margin — follows from it. This is the single most important
  open number on the board.

## Mechanical
- Board outline and mounting: as laid out; 2 layers, 1.6 mm FR4, 1 oz copper.
- The earlier 2.54 mm header substitutions on J1/J2/J5/J6 were corrected in
  the accepted design: J1/J2 are board-mount XT30PW-F battery connectors, J5
  is a 5.08 mm WJ500V screw terminal for the external ARM switch, and J6 is
  an XT60-F igniter output. See `DESIGN_BASIS.md` for part identities and the
  historical mismatch. This correction does not prove physical mating,
  retention under blast/vibration, or current margin.
- **[OWNER] Trace width and connector/relay margin on the ignition path are
  unverified** against the measured cold resistance and pulse current of the
  actual nichrome bridgewire.

## Interfaces
| Connector | Signal set | Notes |
|---|---|---|
| J1 | VBAT, GND | 4S LiPo electronics supply — see connector item |
| J2 | IGN_BATT+, IGN_GND | 2S LiPo igniter supply, isolated return |
| J5 | IGN_BATT+, IGN_ARM_RET | External ARM switch, in series with the relay contact |
| J6 | IGN_OUT, IGN_GND | Nichrome bridgewire igniter output, XT60-F |
| J7 / J8 | Teensy 4.1 socket | Pin map from PJRC card rev4 — see DESIGN_BASIS |
| J9 | XBee 3 socket | Pin map from Digi 90001543 |
| J3 / J4 | Load cell, pressure sensor | analog inputs, TVS-protected (D2) |
| TP1–TP9 | probe points | |

## Environment
- Outdoor test stand: temperature range, moisture and dust are uncontrolled.
  **[OWNER]** No conformal coating or enclosure is specified. A firing
  circuit that gets damp is a firing circuit that may fire.
- Vibration and blast: the board is near a firing motor. All connectors
  should retain positively under shock. The corrected connector classes still
  require physical mating and retention review with the actual harness.
- **[OWNER] Failure mode on power loss is not stated.** If the relay is
  de-energised the contact opens and the igniter is safe; confirm that
  `RELAY_CTRL` is low at Teensy reset and cannot glitch high during boot.

## Success criteria
- Load-cell channel resolves thrust to the intended resolution at PGA=64,
  with the ADS1256's noise floor measured on the assembled board.
- Pressure channel reads across its intended range on the internal 2.048 V
  reference.
- Telemetry link holds at the intended stand-to-operator distance.
- **The igniter output stays open** with the ARM switch open, with
  `RELAY_CTRL` low, and through a Teensy reset and a brownout — verified with
  a resistive dummy load and a scope, never an energetic igniter.
- Ignition fires reliably into a dummy load at the specified current with the
  ARM switch closed.
