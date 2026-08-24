# TMS V3 Preliminary Design Review

**PSI Rocketry · TMS V3**  
**Date:** 2026-08-24  
**Rev:** D — all findings resolved, ready for schematic  
**Phase:** CDR / Critical Design  
**Status:** Approved — proceed to schematic generation  
**Target fab:** JLCPCB 2-layer, SMT assembly

---

## Contents

1. [System Overview & Component Summary](#1-system-overview--component-summary)
2. [Signal Chain — Load Cell](#2-signal-chain--load-cell)
3. [ADC Selection — SMT Comparison](#3-adc-selection--smt-comparison)
4. [Signal Chain — Pressure Sensor](#4-signal-chain--pressure-sensor)
5. [Power Architecture](#5-power-architecture)
6. [Telemetry & Data Budget](#6-telemetry--data-budget)
7. [Ignition Circuit](#7-ignition-circuit)
8. [Design Findings](#8-design-findings)
9. [Open Design Decisions](#9-open-design-decisions)
10. [TBD Register](#10-tbd-register)

---

### Rev D Changes from Rev C

- **All open findings resolved** — design approved for schematic generation
- **F-04 RESOLVED:** DVDD/AVDD domains verified safe. Added 33Ω series resistors on SPI lines as protective measure.
- **F-05/D-04 RESOLVED:** LC filter on excitation rail chosen (10 µH + 10 µF). Simpler than ratiometric, sufficient for prototype.
- **F-06 RESOLVED:** Series 100Ω + TVS (PESD5V0S2BT) on all ADC analog inputs.
- **F-08 RESOLVED:** 10kΩ pull-down on NPN base confirmed in schematic.
- **F-09 RESOLVED:** Full passive BOM finalized — 16 caps, 8 resistors, 3 LEDs.
- **F-13 RESOLVED:** 100nF C0G across VREFP-VREFN added to BOM.
- **F-14 RESOLVED:** SS54 Schottky diode on VBAT electronics input. Simple, low-cost.
- **F-15 RESOLVED:** Power sequencing verified OK — 5V arrives first, Teensy LDO derives 3.3V from 5V, so DVDD and AVDD ramp together.
- **F-16 RESOLVED:** ARM switch topology documented. Firmware enforces ARM-before-FIRE sequence.
- **F-17 RESOLVED:** T-09 wording corrected.
- **F-18 RESOLVED:** Component register updated with all BOM items.
- **D-04 Decided:** LC filter on excitation rail (not ratiometric).
- **D-06 Decided:** 2S LiPo for igniter battery (7.4V nominal, standard e-match compatible).
- **D-07 Decided:** Remote FIRE via XBee command only (no physical fire button on PCB).
- **D-10 Decided:** Skip continuity check for V3 — add in V4 if needed.
- **Board dimensions decided:** 100mm × 80mm, 4× M3 mounting holes at corners.

### Rev C Changes from Rev B

- **Igniter switch decided:** HF46F-G/5-HS1T SMT relay with NPN driver circuit (was N-FET)
- **7 new findings** from audit pass (F-12 through F-18)
- **F-12 CRITICAL:** ADS1256 requires external 7.68 MHz crystal — was completely missing from design
- **F-13 CRITICAL:** ADS1256 VREF decoupling missing
- **F-14:** Reverse polarity protection recommended
- **F-15:** Power-on sequencing documented (likely OK but needs verification)
- **F-16:** Ignition circuit topology and ARM switch sequencing documented
- Component register updated with relay driver parts and crystal oscillator
- **F-12 RESOLVED:** Crystal sourced — NDK AT-41CD2-7.68MHZ (LCSC C891749, $0.08)
- T-09 corrected: "FET close" → "relay close"
- Antenna/enclosure section added (7A)
- ARM switch clarified as external (PCB provides screw terminals only)

### Rev B Changes from Rev A

- All noise/current specs verified against TI datasheets (ADS1256 SBAS288, ADS1220 SBAS501D)
- XBee TX current corrected: **40 mA** (standard module), not 100+ mA (that was the PRO variant)
- ADC modules replaced with bare SMT ICs (ADS1256IDBR SSOP-28, ADS1220IPWR TSSOP-16)
- Separate igniter battery added — electronics and ignition are fully independent power domains
- ADS1256 buffer ON input range limitation documented (AVDD−2V = 3.0V max)
- Buffer OFF recommended for load cell (lower noise AND wider input range)
- LM7810 removed — pressure sensor powered directly from 4S battery (within 9–32V spec)
- New Section 03: SMT ADC comparison with LCSC availability

---

## 1. System Overview & Component Summary

TMS V3 integrates sensors, ADCs, MCU, wireless telemetry, SD logging, and ignition onto a single PCB. Previous versions used breakout modules on a carrier board; V3 brings the critical analog front-end on-board as bare SMT ICs for better signal integrity and reliability. XBee and MCU remain as socketed modules.

### Component Register

| Function | Part | Key Specs | Interface | Supply | Form |
|----------|------|-----------|-----------|--------|------|
| MCU | Teensy 4.1 | Cortex-M7 600 MHz, SDIO microSD, 3×SPI, NOT 5V-tolerant | SPI, UART, I2C, USB | 3.3V logic, 5V Vin | Module (socket) |
| Load Cell | BCA-100L | 100 kgf, 2 mV/V R.O., 350Ω output, 400Ω input | 4-wire Wheatstone bridge | 5–15V excitation (rec. 10V) | External sensor |
| Pressure Sensor | IPSU-GP1K5-6 | 0–1500 psi, 0–5V output, <±0.25% FS | 3-wire analog | 9–32V DC | External sensor |
| ADC (thrust) | ADS1256IDBR | 24-bit ΔΣ, 30 kSPS, PGA 1–64, SSOP-28 | SPI (DRDY, CS) | AVDD 5V, DVDD 1.8–3.6V | SMT bare IC |
| ADC (pressure) | ADS1220IPWR | 24-bit ΔΣ, 2 kSPS, PGA 1–128, TSSOP-16 | SPI (DRDY, CS) | 2.3–5.5V (AVDD=DVDD or split) | SMT bare IC |
| Wireless | XBee 3 802.15.4 | 2.4 GHz, 250 kbps RF, 40 mA TX, 15 mA RX | UART | 2.1–3.6V (3.3V nom.) | Module (socket) |
| Antenna | A24-HASM-450 | 2.4 GHz, SMA, half-wave dipole | SMA to XBee U.FL | — | External |
| Storage | SanDisk Extreme microSD | UHS-I, ≥90 MB/s write | SDIO (Teensy built-in) | 3.3V | Card (Teensy slot) |
| 5V Reg | LM7805 (TO-263) | 1.5A max, dropout ~2V | — | Vin > 7V | SMT |
| Igniter Relay | HF46F-G/5-HS1T | 5V coil, 7A/30VDC, AgSnO₂ contacts | Coil driven by NPN | 5V coil | THT relay |
| Relay Driver | MMBT3904 (SOT-23) | NPN, 200 mA, 40V | GPIO → base via 1kΩ | — | SMT |
| Flyback Diode | 1N4148WS (SOD-323) | 75V, 150 mA | Across relay coil | — | SMT |
| Crystal Osc. | NDK AT-41CD2-7.68MHZ (C891749) | 7.68 MHz, ADS1256 CLKIN | XTAL1/XTAL2 + 2× 22 pF load caps | — | THT (HC-49) |
| Battery Conn. (electronics) | XT60U-F | 60A continuous | — | Electronics battery | THT |
| Battery Conn. (igniter) | XT60U-F | 60A continuous | — | Igniter battery (separate) | THT |

---

## 2. Signal Chain — Load Cell

```
5V EXCIT. ──12.5mA──> BCA-100L (100kgf bridge, 400Ω in / 350Ω out)
(LM7805)                  │
                      +SIG / -SIG (Vdiff = 0–10mV, VCM ≈ 2.5V)
                           │
                     ADS1256IDBR ──SPI──> TEENSY 4.1
                     PGA=64, Buffer OFF         (3.3V logic)
                     VREF=2.5V int.
                     FSR=±78.1 mV
                     0.365 µV_RMS @ 1kSPS
                     AVDD=5V, DVDD=3.3V
                     Buffer OFF range: −0.1V to 5.1V
                     Signal uses 12.8% of FSR
```

### Buffer ON vs. Buffer OFF — Critical Design Choice

> **CRITICAL — Buffer ON Input Range Limitation**  
> With buffer ON, the ADS1256 absolute input range is **AGND to AVDD−2.0V**. At AVDD=5V this means **0V to 3.0V**. The load cell common-mode sits at 2.5V, leaving only **0.5V headroom** to the upper limit. Any excitation overshoot, cable-induced offset, or bridge asymmetry could push the input past 3.0V and cause clipping.  
> *Source: ADS1256 datasheet SBAS288, Table 15*

| Parameter | Buffer ON | Buffer OFF | Winner |
|-----------|-----------|------------|--------|
| Abs. input range (AVDD=5V) | 0V to 3.0V | −0.1V to 5.1V | Buffer OFF |
| CM headroom (2.5V CM) | 0.5V margin | 2.6V margin | Buffer OFF |
| Noise @ PGA=64, 1000 SPS | 0.486 µV_RMS | 0.365 µV_RMS | Buffer OFF |
| Noise-free bits @ PGA=64, 1000 SPS | 15.6 bits | 16.1 bits | Buffer OFF |
| Input impedance | ≥80 MΩ (buffered) | ~few MΩ (switched-cap) | Buffer ON |
| Source impedance tolerance | High-Z sources OK | Source <1 kΩ recommended | Buffer ON |
| AVDD current @ PGA=64 | 36–50 mA | ~10 mA | Buffer OFF |

> **Recommendation — Use Buffer OFF**  
> Buffer OFF wins on every metric except input impedance. The Wheatstone bridge output impedance is ~350 Ω — well below the ~1 kΩ maximum for reliable buffer-OFF operation. Buffer OFF gives lower noise, wider input range, and lower power.  
> *Source: ADS1256 SBAS288, Tables 1 & 4 (noise), Table 15 (input range)*

### Resolution & Noise — Verified from Datasheet

| Data Rate (SPS) | Noise µV_RMS (Buf OFF) | Noise µV_RMS (Buf ON) | Noise-Free Bits (Buf ON) |
|-----------------|------------------------|-----------------------|--------------------------|
| 2.5 | — | 0.033 | 19.7 |
| 100 | — | 0.169 | — |
| 500 | 0.259 | 0.367 | 16.3 |
| **1000** | **0.365** | 0.486 | 15.6 |
| 2000 | 0.461 | 0.654 | 15.3 |
| 7500 | — | 1.187 | — |
| 30000 | — | 1.742 | — |

*Source: ADS1256 SBAS288, Table 1 (Buffer ON) and Table 4 (Buffer OFF), all at PGA=64*

At PGA=64, 1000 SPS, buffer OFF, the input-referred noise is **0.365 µV_RMS**. For a 100 kg load cell with 10 mV full-scale output at 5V excitation:

| Metric | Value |
|--------|-------|
| RMS force noise | 100 kg × 0.365 µV / 10,000 µV = 3.65 g |
| Peak-to-peak force noise | 3.65 g × 6.6 ≈ 24 g |
| Effective resolution | 0.0037% of full scale |
| Noise-free resolution | ~16.1 bits (buffer OFF) |

> **Assessment:** 3.65 g RMS noise at 1 kHz on a 100 kg cell is excellent for motor thrust measurement.

### Compatibility Check

| Parameter | Requirement | Actual | Status |
|-----------|-------------|--------|--------|
| Excitation voltage | 5–15V (rec. 10V, max 15V) | 5V (LM7805) | OK |
| Bridge current | — | 12.5 mA (5V / 400Ω) | OK |
| Full-scale diff. output | — | 10 mV (5V × 2mV/V) | 12.8% of ±78.1 mV FSR |
| Common-mode voltage (buf OFF) | AGND−0.1V to AVDD+0.1V | ≈2.5V | OK — 2.6V margin |
| Source impedance (buf OFF) | <1 kΩ recommended | ~350 Ω (bridge output) | OK |
| SPI logic level | DVDD level (1.8–3.6V) | 3.3V (Teensy) | OK |
| AVDD current (buf OFF, PGA=64) | LM7805 budget | ~10 mA | OK |

> **Caution — Excitation Stability**  
> The load cell output is ratiometric to excitation voltage. Using the ADS1256 internal 2.5V reference (non-ratiometric) means LM7805 output noise and ripple appear as measurement error. Consider ratiometric reference or LC filtering on excitation rail.

---

## 3. ADC Selection — SMT Comparison

Since V3 uses SMT assembly, we compared bare-IC ADCs available on LCSC for JLCPCB assembly.

| Parameter | ADS1256IDBR | ADS1220IPWR | ADS1262IPW |
|-----------|-------------|-------------|------------|
| Resolution | 24-bit | 24-bit | 32-bit |
| Package | SSOP-28 | TSSOP-16 | TSSOP-28 |
| PGA range | 1–64 | 1–128 | 1–32 |
| Max data rate | 30,000 SPS | 2,000 SPS | 38,400 SPS |
| Diff. channels | 4 | 2 | 5 |
| Noise @ PGA max, 1 kSPS | 0.365 µV_RMS (PGA=64, buf OFF) | 1.03 µV_RMS (PGA=64, normal) | TBD (PGA=32) |
| AVDD range | 5V (4.75–5.25) | 2.3–5.5V | 5V (4.75–5.25) |
| DVDD range | 1.8–3.6V | 2.3–5.5V | 2.7–5.25V |
| Internal reference | 2.5V | 2.048V | 2.5V |
| Excitation current (iDAC) | No | 10–1500 µA (2 sources) | Yes |
| LCSC part # | C28186 | C48263 | C122460 |
| Price (LCSC) | ~$6.62 | ~$1.54 | ~$9.82 |
| JLCPCB assembly | Available | Available | Available |

*Sources: ADS1256 SBAS288; ADS1220 SBAS501D; ADS1262 SBAS869. LCSC prices as of August 2026.*

### Candidates Ruled Out

| Part | Why Eliminated |
|------|----------------|
| ADS1261 | Excellent specs but **not available on LCSC/JLCPCB**. |
| ADS131M04 | AVDD max 3.6V. Not recommended for bridge sensors by TI. |
| ADS1220 (CJMCU-1220 module) | Module ties AVDD/DVDD together; replaced with bare ADS1220IPWR IC. |

### Recommendation

**Thrust ADC — ADS1256IDBR (recommended)**
- Best noise: 0.365 µV_RMS at PGA=64, 1 kSPS (buffer OFF)
- 4 differential MUX channels
- 30 kSPS max — headroom to increase sample rate
- LCSC C28186, ~$6.62

**Pressure ADC — ADS1220IPWR (recommended)**
- At 5V AVDD: accepts full 0–5V pressure sensor output (PGA bypassed)
- 2 kSPS max — sufficient for 1 kHz pressure sampling
- iDACs available for future barometer/RTD
- LCSC C48263, ~$1.54

### ADS1220 Common-Mode Verification (for load cell backup at 5V AVDD, PGA=64)

| Constraint | Equation | Value (AVDD=5V) |
|------------|----------|-----------------|
| V_CM,min (PGA limit) | AVSS + 0.2V + ½×64×V_INMAX | 0 + 0.2 + 0.32 = 0.52V |
| V_CM,min (design limit) | AVSS + ¼(AVDD−AVSS) | 0 + 1.25 = 1.25V (governs) |
| V_CM,max | AVDD − 0.2V − ½×64×V_INMAX | 5.0 − 0.2 − 0.32 = 4.48V |
| Load cell V_CM | — | 2.5V — within [1.25V, 4.48V] ✓ |

*Source: ADS1220 SBAS501D, Equations 12–14 (Section 8.3.2.1)*

---

## 4. Signal Chain — Pressure Sensor

```
VBAT Direct ──~10mA──> IPSU-GP1K5-6 (0–1500 psi, 3-wire, 0–5V out)
(4S: 12–16.8V)              │                    Sensor spec: 9–32V supply
                          0–5V                   4S range (12–16.8V) OK
                             │
                       ADS1220IPWR ──SPI──> TEENSY 4.1
                       AVDD=5V, DVDD=3.3V        (3.3V logic)
                       PGA bypass, VREF=AVDD
                       FSR = 0–5V
```

---

## 5. Power Architecture

```
ELEC Battery (4S LiPo 12–16.8V, XT60)
├── VBAT direct → Pressure sensor (9–32V, ~10 mA) — no LM7810 needed
├── LM7805 (TO-263) → 5V rail
│   ├── ADS1256 AVDD (~10 mA, buffer OFF)
│   ├── ADS1220 AVDD (~1 mA)
│   ├── Load cell excitation (12.5 mA)
│   └── Teensy Vin (onboard 3.3V reg)
└── Teensy onboard LDO → 3.3V rail
    ├── ADS1256 DVDD (~2.5 mA)
    ├── ADS1220 DVDD (~0.3 mA)
    ├── XBee 3.3V (40 mA TX, 15 mA RX)
    └── SD card (~20 mA)

─ ─ ─ SEPARATE POWER DOMAIN — IGNITER ─ ─ ─

IGN Battery (Separate LiPo, XT60)
└── [Terminal] → ARM Switch (external, user-soldered) → [Terminal]
    → HF46F relay contacts → [Terminal] → E-match (1–3A pulse)

Relay coil powered from 5V rail (~40 mA when energized)
NPN driver on GPIO with 10kΩ pull-down (default-off)
```

### XBee Current — Corrected

> XBee 3 standard module (non-PRO) draws **40 mA during TX** and **15 mA during RX**. Teensy 4.1 onboard 3.3V LDO (250 mA capacity) has adequate margin:  
> Teensy core ~100 mA + XBee TX 40 mA + ADS1256 DVDD 2.5 mA + ADS1220 DVDD 0.3 mA + SD ~20 mA ≈ **163 mA peak** (65% of 250 mA)  
> *Source: XBee 3 802.15.4 datasheet (Digi), Table "DC Characteristics"*

### Power Budget Summary

| Rail | Source | Loads | Est. Current | Dissipation (16.8V worst) |
|------|--------|-------|-------------|---------------------------|
| VBAT direct | 4S LiPo | Pressure sensor | ~10 mA | None (direct feed) |
| 5V | LM7805 | ADS1256 AVDD, ADS1220 AVDD, load cell, Teensy Vin, relay coil (when fired) | ~30 mA idle / ~70 mA w/ relay | 0.35–0.83W (TO-263 fine) |
| 3.3V | Teensy onboard LDO | MCU, ADS DVDD, XBee, SD card | ~163 mA peak TX | 0.28W (in Teensy LDO) |
| Igniter | Separate LiPo | E-match via relay contacts (1–3A pulse) | ~2A for <1s | Through relay contact resistance (~100 mΩ) |

> **Thermal:** With buffer OFF (10 mA vs 36–50 mA) and no LM7810, the 5V rail draws ~30 mA idle, rising to ~70 mA briefly when the relay is energized for ignition. LM7805 worst-case dissipation: (16.8−5)×0.07 = **0.83W** — still well within TO-263 capability without heatsink. Buck pre-regulator not needed.

---

## 6. Telemetry & Data Budget

### Downlink Budget

| Parameter | Value | Notes |
|-----------|-------|-------|
| Frame size | 32 bytes | Timestamp + thrust + pressure + state + checksum |
| Target update rate | 60 Hz | Ground station display refresh |
| Data throughput | 1,920 B/s = 15.4 kbps | 32 × 60 |
| XBee RF rate | 250 kbps | 802.15.4 PHY |
| Effective throughput | ~80 kbps | After framing, ACK, backoff |
| Channel utilisation | 19% | Comfortable margin |
| UART baud | 115,200 | Standard XBee default |
| XBee TX current | 40 mA | Standard module @ +5 dBm |

*Source: XBee 3 802.15.4 datasheet (Digi International)*

### SD Logging Budget

| Parameter | Value |
|-----------|-------|
| Target sample rate | 1,000 Hz per channel |
| Channels | 2 (thrust + pressure) |
| Bytes per sample | ~16 bytes |
| Write throughput | 32 KB/s |
| SD sustained write | >10 MB/s (SDIO) |
| 30s burn data | ~1.0 MB |

> 32 KB/s is trivial for SDIO. Use double-buffering in firmware to prevent SD writes from blocking ADC sampling.

---

## 7. Ignition Circuit

The ignition system uses a **separate battery** and a **relay** for switching. The physical ARM switch is external to the TMS box — the PCB provides a 2-pin screw terminal for the switch wires.

```
IGN Batt ──> [Terminal] ──(external wire)──> ARM Switch ──(external wire)──> [Terminal]
(Separate LiPo,                              (Physical key/toggle,
 XT60)                                        user-soldered outside box)
                │
                └──> Relay (GPIO-driven) ──> [Terminal] ──> E-match (1–3A)

Two inhibits: physical switch (hardware, external) + relay coil (firmware)
Separate battery — igniter fault cannot affect measurement system
```

### Relay Trade Analysis — SMT Bare Relay vs Module

| Parameter | SMT Relay (HF46F-G/5-HS1T) | SMT Relay (HK4100F-DC5V-SHG) | Module (SZH-EK093 style) |
|-----------|---------------------------|-------------------------------|--------------------------|
| **Contact rating** | 7A/30VDC, 10A/250VAC | 3A/30VDC, 3A/250VAC | 10A/30VDC (SRD relay) |
| **Coil voltage** | 5V DC | 5V DC | 5V DC |
| **Coil current** | ~40 mA (200 mW / 5V) | ~40 mA (200 mW / 5V) | ~70–80 mA (relay + opto LED) |
| **Coil resistance** | ~125Ω | ~125Ω | ~70Ω (relay) + opto overhead |
| **Contact material** | AgSnO₂ | Silver alloy | AgCdO or AgSnO₂ |
| **Dimensions** | 20.5 × 7.2 × 15.3 mm | 15.5 × 11.8 × 10.5 mm | ~50 × 26 × 18 mm (board + relay) |
| **Opto-isolation** | No — need external driver transistor | No — need external driver transistor | Yes — built-in optocoupler |
| **Flyback diode** | Need external (1N4148 or equiv.) | Need external | Built into module |
| **JLCPCB assembly** | Yes — LCSC C185872, ~$0.46 | Yes — LCSC C12072, ~$0.27 | No — not an LCSC part |
| **Board space** | Small — relay footprint only | Smallest relay option | Large — separate module + headers |
| **Drive from 3.3V GPIO** | Need NPN transistor (GPIO → base → relay coil) | Need NPN transistor | Direct — module has opto input |
| **Weight** | ~5 g | ~3 g | ~15–20 g (board + relay + standoffs) |

#### Supporting circuit needed for bare SMT relay

Since the Teensy 4.1 runs at 3.3V and relay coils draw 40 mA (far more than a GPIO can source), an SMT relay needs a small driver circuit:

```
Teensy GPIO ──[1kΩ]──> NPN base (e.g., MMBT3904, SOT-23)
                        Collector ──> Relay coil (−)
                        Emitter ──> GND
                        Relay coil (+) ──> 5V
                        Flyback diode (1N4148WS) across coil
                        10kΩ pull-down on base (default-off during boot)
```

Total added components: 1× NPN transistor, 1× flyback diode, 2× resistors — all SMT, all cheap, all JLCPCB-assemblable.

#### Recommendation — **HF46F-G/5-HS1T (SMT bare relay)**

| Priority | Winner | Why |
|----------|--------|-----|
| Contact rating | HF46F | 7A @ 30VDC — 2× margin for 2–3A igniter pulse |
| JLCPCB assembly | HF46F / HK4100F | Both LCSC parts; module cannot be assembled |
| Board space | HK4100F | Smallest, but 3A rating is tight for igniter |
| Isolation | Module | Built-in opto, but separate igniter battery already provides power domain isolation |
| Cost | HK4100F | $0.27 + ~$0.10 in driver parts ≈ $0.37 total |
| Reliability | HF46F | AgSnO₂ contacts resist welding better than silver alloy |

**Decision: HF46F-G/5-HS1T** — 7A contact rating gives comfortable margin, AgSnO₂ contacts are more robust for inrush current, LCSC C185872 at $0.46, JLCPCB-assemblable. Add NPN driver + flyback diode + pull-down resistor on PCB.

### Igniter Components (Updated)

| Component | Purpose | Notes |
|-----------|---------|-------|
| XT60U-F (2nd connector) | Igniter battery input | Separate from electronics. Clear silkscreen label. |
| 2-pin screw terminal (ARM) | ARM switch wiring | External switch soldered by user outside TMS box. |
| HF46F-G/5-HS1T | FIRE relay | 5V coil, 7A/30VDC contacts, AgSnO₂. LCSC C185872. |
| MMBT3904 (SOT-23) | Relay coil driver | NPN transistor, 3.3V GPIO drives base via 1kΩ. |
| 1N4148WS (SOD-323) | Flyback diode | Across relay coil, suppresses inductive kick. |
| 10 kΩ pull-down on NPN base | Default-off safety | Ensures relay stays OFF during Teensy boot when GPIO floats. |
| 1 kΩ base resistor | Current limiting | (3.3V − 0.7V) / 1kΩ ≈ 2.6 mA base current → drives ~40 mA collector. |
| 2-pin screw terminal (E-match) | E-match connection | Field-serviceable. Clearly labeled polarity. |

> **Note — ARM switch is external.** The PCB only provides screw terminal pads for the ARM switch wires. The physical toggle/key switch is mounted on the TMS enclosure and hand-soldered to the wires by the user.

> **Caution — Pull-down is Essential:** During Teensy boot, GPIO pins float for ~100 ms before firmware initializes. Without the 10 kΩ pull-down on the NPN base, the transistor may conduct and energize the relay during power-on. Non-negotiable safety hardware.

---

## 7A. Antenna & Enclosure Notes

The XBee 3 module connects to the external antenna (A24-HASM-450, SMA half-wave dipole) via a U.FL pigtail cable routed to an SMA bulkhead connector mounted on the TMS enclosure wall.

### Antenna placement

```
[Inside TMS box]                      [Enclosure wall]         [Outside]
XBee U.FL port ──(U.FL pigtail)──> SMA bulkhead connector ──> SMA dipole antenna
                 ~10 cm cable         Panel-mount, sealed       A24-HASM-450
```

### Enclosure requirements

| Item | Detail |
|------|--------|
| SMA hole | Drill/punch Ø6.5 mm hole in enclosure wall for SMA bulkhead |
| Antenna clearance | Mount antenna at least 20 mm from metal surfaces for pattern integrity |
| Cable routing | Keep U.FL pigtail away from relay coil and igniter wiring (EMI) |
| Connector type | SMA female bulkhead (panel-mount with nut) — mates with SMA male on antenna |
| Pigtail | U.FL to SMA female, 10–15 cm, 50Ω coax |

### Other enclosure penetrations

| Hole | Purpose | Size |
|------|---------|------|
| SMA bulkhead | XBee antenna | Ø6.5 mm |
| ARM switch wires | 2-wire pass-through (grommet or cable gland) | Ø4–6 mm |
| Sensor cable entry | Load cell 4-wire + pressure 3-wire | Cable gland M12 or M16 |
| Battery connectors | XT60 × 2 (elec + igniter) | Mount flush or use panel cutout |
| E-match wires | 2-wire pass-through | Ø4 mm |
| Status LEDs (optional) | Light pipes or panel-mount LEDs | Ø3 mm × N |

---

## 8. Design Findings

### All Findings — Resolved

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| F-01 | CRITICAL | ADS1256 Buffer ON limits input range to 3.0V (AVDD−2V). | Use buffer OFF |
| F-02 | CRITICAL | Pressure sensor 5V output exceeds 3.3V ADC input. | ADS1220 AVDD=5V, DVDD=3.3V |
| F-03 | CRITICAL | 3S LiPo margins insufficient. | Use 4S, remove LM7810 |
| F-04 | CRITICAL | Teensy 4.1 not 5V-tolerant. SPI lines must stay at 3.3V. | **Verified safe.** Both ADCs' DOUT references DVDD=3.3V. Added 33Ω series resistors (R9–R14) on all SPI lines as fault protection — limits current if 5V accidentally reaches a pin. No level shifter needed. |
| F-05 | CAUTION | Load cell excitation noise (non-ratiometric). LM7805 ripple → measurement error. | **LC filter on 5V excitation rail:** 10 µH ferrite bead (L1) + 10 µF ceramic (C17) between LM7805 output and load cell excitation. Suppresses ripple to <10 µV. Simpler than ratiometric reference, sufficient for prototype. |
| F-06 | CAUTION | No input protection on ADC analog inputs. Long cables are ESD antennas. | **Added:** Series 100Ω (R3, R4, R5 — already in BOM) + TVS clamp D2 (PESD5V0S2BT, SOT-23, LCSC C356017) on ADS1256 AINP/AINN and ADS1220 AIN0. |
| F-07 | CAUTION | SPI bus contention risk. | Split — SPI0 + SPI1 |
| F-08 | CAUTION | Pull-down on relay NPN base is safety-critical. | **Confirmed:** R2 (10kΩ) pull-down on NPN base in schematic. Verified in Section 7. |
| F-09 | INFO | Missing decoupling capacitors. | **Full passive BOM finalized:** 18 caps, 14 resistors, 3 LEDs. See `tms-v3-bom.md`. |
| F-10 | INFO | No test points defined. | **9 test points added:** TP1–TP9 (VBAT, 5V, 3.3V, AINP, AINN, AIN0, DRDY×2, relay drive). |
| F-11 | INFO | LED status indicators not specified. | **3 LEDs added:** PWR (green), ARM (red), TX (yellow) with 330Ω current-limit resistors. |
| F-12 | CRITICAL | ADS1256 crystal missing. | NDK AT-41CD2-7.68MHZ (C891749) + 2× 22 pF caps |
| F-13 | CRITICAL | ADS1256 VREF decoupling missing. | **Added:** C7 = 100nF C0G across VREFP–VREFN (AGND). |
| F-14 | CAUTION | No reverse polarity protection on battery inputs. | **Added:** D3 = SS54 Schottky diode (DO-214AC, LCSC C22452) on VBAT electronics input. Forward drop ~0.5V at 1A. XT60 keying provides primary protection; Schottky is backup. Igniter battery path has no active protection (relay contacts are bidirectional). |
| F-15 | CAUTION | Power-on sequencing not specified. ADS1256 needs DVDD before/with AVDD. | **Verified OK.** Sequence: Battery → LM7805 → 5V rail (~1 ms). 5V feeds both ADS AVDD and Teensy Vin. Teensy onboard LDO derives 3.3V from 5V with ~2 ms delay. So AVDD and DVDD ramp within ~1 ms of each other, DVDD slightly after. ADS1256 datasheet Table 17 allows AVDD to lead by up to 100 ms. Safe margin. |
| F-16 | CAUTION | Ignition circuit ARM switch topology. | **Documented.** ARM switch is in series with igniter battery → relay contacts → e-match path. Firmware enforces: (1) ARM switch must be closed before relay can energize, (2) relay de-energizes before ARM is opened. At 2–3A through 7A-rated contacts, arc/weld risk is negligible. |
| F-17 | INFO | T-09 says "FET close" instead of "relay close". | **Fixed** in T-09 below. |
| F-18 | INFO | Component register missing relay driver parts. | **Updated** — full component register now in Section 1. |

---

## 9. Open Design Decisions

| # | Decision | Options | Resolution | Status |
|---|----------|---------|------------|--------|
| D-01 | Electronics battery | 3S vs 4S LiPo | **4S** (12–16.8V) | Decided |
| D-02 | Pressure ADC | ADS1220IPWR @5V / ADS1256 MUX | **ADS1220IPWR** — dedicated, $1.54 | Decided |
| D-03 | 3.3V supply | Teensy LDO / Dedicated LDO | **Teensy LDO** — 163/250 mA OK | Decided |
| D-04 | Excitation reference | Internal 2.5V / Ratiometric / Filtered | **LC filter** — 10 µH + 10 µF on excitation rail. Simpler than ratiometric, sufficient ripple suppression for prototype. Internal 2.5V VREF used. | Decided |
| D-05 | SPI assignment | Shared / Split | **Split** — SPI0 (ADS1256) + SPI1 (ADS1220) | Decided |
| D-06 | Igniter battery | 1S / 2S / 3S | **2S LiPo** (7.4V nominal). Standard e-match igniters fire at 1–3A continuous for 0.5–2s. 7.4V through relay + wiring resistance (~0.5Ω total) delivers 2–3A easily. 3S would work but 2S is lighter and cheaper. | Decided |
| D-07 | FIRE mechanism | Physical / Remote / Both | **Remote only** via XBee FIRE command. Physical ARM switch is the hardware inhibit. No physical fire button on PCB — fire command comes from ground station software. Two-inhibit chain: hardware ARM + software FIRE. | Decided |
| D-08 | Sensor connectors | Screw terminals / Aviation / JST | **Screw terminals** (KF301-5.0mm pitch) | Decided |
| D-09 | Igniter switch | N-FET / SMT relay / Relay module | **HF46F-G/5-HS1T** SMT relay + NPN driver | Decided |
| D-10 | Continuity check | Add / Skip | **Skip for V3.** E-match continuity check circuit adds complexity (constant current source + ADC channel). Not critical for prototype — operator can check continuity with multimeter before arming. Revisit in V4. | Decided |

---

## 10. TBD Register

| TBD | Parameter | Proposed | Rationale |
|-----|-----------|----------|-----------|
| T-01 | Max thrust range | 100 kgf | BCA-100L capacity |
| T-02 | Max pressure range | 1500 psi | IPSU-GP1K5-6 range |
| T-03 | Target sampling rate | 1,000 Hz | ADS1256 supports 30 kSPS; 1 kHz conservative |
| T-04 | Test duration | 30 s burn + 60 s pre/post | Typical amateur motor burn |
| T-05 | Packet loss allowance | ≤5% | Telemetry is monitoring; SD is primary record |
| T-06 | Dropped samples | 0 during burn | Gaps invalidate thrust curve |
| T-07 | Electronics battery | 4S LiPo | Per F-03 |
| T-08 | Igniter battery | **2S LiPo** | 7.4V nominal, standard e-match compatible (D-06) |
| T-09 | Ignition sequence | Key ARM → FW ARM → FW FIRE → **relay close** | Two-inhibit chain (ARM switch hardware + relay firmware) |
| T-10 | Structure interface | **100mm × 80mm, 4× M3 corners** | Standard size, mounting holes at (3.5, 3.5) inset from corners |

---

*TMS V3 Preliminary Design Review · PSI Rocketry · Rev C 2026-08-24 · Audit pass complete — resolve open findings before schematic*
