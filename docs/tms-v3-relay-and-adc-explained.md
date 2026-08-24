# TMS V3 — Relay Driver & ADC Selection Explained

For a mechanical engineering student who understands solenoids, flow restrictors, and spring-returns — but not transistors and delta-sigma ADCs yet.

---

## Part 1: Relay Driver Circuit

### The relay itself (HF46F)

You know how a solenoid valve works: you energize a coil, it creates a magnetic field, that pulls a plunger, and the plunger opens/closes a flow path. A relay is exactly the same thing, except instead of fluid flow, it switches an electrical circuit.

```
        5V ──────────┐
                     │
                  ┌──┴──┐
                  │COIL │  ← electromagnet, ~125Ω, draws ~40mA
                  │     │     when 5V applied across it
                  └──┬──┘
                     │
                   (drain)

    Meanwhile, on the OTHER side of the relay (galvanically separate):

    IGN Battery ──> ARM SW ──> [COM]──╮
                                      ╰──[NO]──> E-match ──> GND
                                         (normally open)
```

When the coil is **not energized**: COM and NO are disconnected. No current flows to the e-match. Safe.

When the coil **is energized**: the magnetic field pulls a metal armature (like a small lever), which physically pushes the COM contact onto the NO contact. Now igniter battery current flows through the e-match.

The key insight: **the coil side and the contact side share no electrical connection.** The only link is mechanical — a magnetic field moves a piece of metal. That's galvanic isolation.

---

### Why you can't connect the Teensy GPIO directly to the coil

Two problems:

1. **Voltage mismatch.** The coil needs 5V across it to generate enough magnetic force. The Teensy GPIO outputs 3.3V.

2. **Current mismatch.** The coil draws ~40 mA (5V / 125Ω). A Teensy GPIO can source maybe 4 mA safely. That's 10× too little — like trying to open a fire hydrant with your pinky.

---

### The NPN transistor (MMBT3904) — your amplifier

Think of the NPN transistor as a small electronic lever — a tiny current at the base controls a much larger current through the collector-emitter path.

```
                     5V
                      │
                 ┌────┴────┐
                 │  RELAY   │
                 │  COIL    │  40 mA flows here when transistor is ON
                 │  (125Ω)  │
                 └────┬────┘
                      │ (collector)
                      │
Teensy GPIO ──[1kΩ]──┤ (base)      ← MMBT3904 NPN transistor
                      │
                      │ (emitter)
                     GND
```

**How it works:**

- **GPIO HIGH (3.3V):** Current flows through the 1kΩ resistor into the base. Base current = (3.3V − 0.7V) / 1kΩ ≈ **2.6 mA**. The transistor "turns on" — it lets ~40 mA flow from collector to emitter through the relay coil. Relay energizes. Contacts close. Igniter fires.

- **GPIO LOW (0V):** No base current. Transistor is OFF — it acts like an open switch. No current through coil. Relay de-energizes. Contacts open. Safe.

The 0.7V is the base-emitter voltage drop — every NPN transistor has this, like a small threshold you need to overcome. It's a physics property of the silicon junction.

**Current gain (β):** The MMBT3904 has a current gain of ~100–300. That means 2.6 mA of base current can control 260–780 mA of collector current. We only need 40 mA, so it's well within capability. The transistor is fully "saturated" (fully on, like a valve fully open).

---

### The 1kΩ base resistor — current limiting

Without it, too much current would flow into the base and damage the Teensy GPIO or the transistor. It's like a flow restrictor.

```
R = (V_GPIO − V_BE) / I_base = (3.3V − 0.7V) / 2.6mA = 1kΩ
```

---

### The 10kΩ pull-down resistor — boot safety

```
Teensy GPIO ──[1kΩ]──┬──> NPN base
                      │
                   [10kΩ]
                      │
                     GND
```

When the Teensy first powers up, for about 100 ms the GPIO pins are in an undefined state — they "float." A floating pin might be high, low, or anywhere in between. If it happens to float high enough, the transistor turns on, the relay fires, and the igniter goes off before your code even starts running.

The 10kΩ resistor pulls the base firmly to GND during this boot window. It's a safety net. Think of it like a spring-return on a pneumatic valve — if the control signal disappears, the valve goes to its safe state.

**Why 10kΩ and not lower?** It has to be much larger than the 1kΩ base resistor so it doesn't steal too much current during normal operation. When GPIO is HIGH, the 10kΩ only diverts 0.26 mA to ground — the remaining 2.3 mA still drives the transistor just fine.

---

### The flyback diode (1N4148WS) — coil kick protection

```
                5V
                 │
            ┌────┴────┐
        ┌──►│  DIODE   │──┐
        │   └─────────┘   │
        │                  │
        │   ┌─────────┐   │
        └───│  RELAY   │──┘
            │  COIL    │
            └────┬────┘
                 │
              (to NPN collector)
```

This is the one that catches most non-EE people off guard. When you suddenly cut current to an inductor (the relay coil is an inductor), it generates a voltage spike in the opposite direction — this is Lenz's law. The coil "kicks back" with a brief voltage spike that can be 50–100V, easily enough to destroy the transistor.

The diode is wired "backwards" across the coil — it does nothing during normal operation (current flows the wrong way for the diode). But when the coil kicks back, the spike reverses the voltage polarity, and now the diode conducts, clamping the spike to ~0.7V. The energy dissipates as heat in the diode instead of blowing up your transistor.

Same principle as a snubber diode on a solenoid valve driver — if you've seen those in pneumatic control circuits, it's identical.

---

### Complete circuit — all 5 components

```
                          5V
                           │
                      ┌────┴────┐
                  ┌──►│ 1N4148WS│──┐    (flyback diode — reverse-biased
                  │   └─────────┘   │    normally, conducts on coil kick)
                  │                  │
                  │   ┌─────────┐   │
                  └───│ HF46F   │──┘
                      │ COIL    │         (relay — 5V, 125Ω, 40mA)
                      └────┬────┘
                           │ (collector)
                           │
Teensy GPIO ──[1kΩ]──┬────┤               MMBT3904 NPN
                      │    │ (base)        (electronic switch)
                   [10kΩ]  │
                      │    │ (emitter)
                     GND  GND

    Meanwhile, isolated on the contact side:

    IGN Batt ──> [terminal] ──> ARM switch (external) ──> [terminal]
                                                              │
                                                         [COM relay contact]
                                                              │
                                                         [NO relay contact]
                                                              │
                                                      [terminal] ──> E-match
```

### Summary — 5 components, each with one job

| # | Component | Job | Mech-E Analogy |
|---|-----------|-----|----------------|
| 1 | HF46F relay | Switches igniter power on/off | Solenoid valve |
| 2 | MMBT3904 NPN | Amplifies 2.6 mA GPIO signal → 40 mA coil current | Pilot valve driving a bigger valve |
| 3 | 1kΩ resistor | Limits base current to safe level | Flow restrictor |
| 4 | 10kΩ pull-down | Keeps relay OFF during boot | Spring-return to safe state |
| 5 | 1N4148WS diode | Absorbs coil voltage spike on turn-off | Snubber / pressure relief valve |

---

## Part 2: ADC Selection — Why These Two ICs

### What each sensor needs

| | Load Cell (BCA-100L) | Pressure Sensor (IPSU-GP1K5-6) |
|---|---|---|
| **Output type** | Differential, 0–10 mV (at 5V excitation) | Single-ended, 0–5V |
| **Output impedance** | ~350Ω (low) | Low (active output stage) |
| **Signal level** | Tiny — needs high PGA gain | Large — no amplification needed |
| **Required resolution** | High — you're measuring grams on a 100 kg range | Moderate — 0.25% FS accuracy from sensor itself is the limit |
| **Required speed** | 1 kSPS target | 1 kSPS target (can be lower) |
| **Noise sensitivity** | Very high — µV-level signals | Low — signal is volts, not microvolts |

These two sensors have completely different signal characteristics. That's why they get different ADCs — each one optimized for its signal.

---

### ADS1256 for the load cell — why

The load cell outputs **10 millivolts full-scale**. That's a tiny signal sitting on top of a 2.5V common-mode pedestal. You need:

**1. High PGA gain** to amplify 10 mV into a range the ADC can resolve well. ADS1256 at PGA=64 maps ±78.1 mV input to its full digital range — your 10 mV signal uses 12.8% of that, which is reasonable.

**2. Low noise** because at µV signal levels, ADC noise directly eats into your resolution. The ADS1256 at 1 kSPS delivers 0.365 µV_RMS — that translates to 3.65 g of force noise on a 100 kg cell. Very good.

**3. Differential input** because the bridge outputs a differential voltage (SIG+ minus SIG−). The ADS1256 has true differential inputs — it measures the voltage between two pins, rejecting the 2.5V common-mode.

**4. SPI interface** — faster data transfer than I2C, and the Teensy 4.1 has three SPI buses.

#### What about other ADCs for the load cell?

| Alternative | Problem |
|-------------|---------|
| ADS1220 | Noise at 1 kSPS is 1.03 µV_RMS — about 3× worse. You'd get ~10 g force noise instead of 3.65 g. Also maxes out at 2 kSPS, less headroom. |
| ADS1262 | 32-bit, even lower noise, but $9.82 vs $6.62. Overkill. |
| HX711 | The "classic" load cell ADC, but only 80 SPS max. Way too slow for 1 kHz thrust curves. |
| ADS1115 (V2 design) | 16-bit, I2C, max 860 SPS. Much worse noise floor than ADS1256. Fine for a kitchen scale, insufficient for precision thrust measurement. |

**ADS1256 is the right choice for thrust measurement.** It hits the sweet spot of noise, speed, and cost.

---

### ADS1220 for the pressure sensor — why

The pressure sensor outputs **0–5V single-ended**. Totally different problem:

**1. No PGA needed** — the signal is already 5V full-scale. You bypass the PGA (gain=1) and use the full ADC input range.

**2. Noise is irrelevant** — the sensor itself is ±0.25% FS accurate (±3.75 psi). Even a noisy ADC can't make this worse. The ADS1220's noise at PGA=1 is way below the sensor's own error.

**3. Speed is less critical** — pressure changes slower than thrust force. Even 100 SPS would be fine, though 1 kSPS is comfortable.

**4. 5V AVDD needed** — the sensor outputs up to 5V, so the ADC must accept 5V analog input. ADS1220 at AVDD=5V handles this directly.

**5. Cheap** — $1.54. Why spend $6.62 on an ADS1256 for a signal that doesn't need it?

#### Could you just run both sensors through the ADS1256?

Yes — it has 4 MUX channels. But:

- The pressure sensor's 0–5V output at PGA=1 uses full FSR, while the load cell at PGA=64 uses 12.8%. You'd need to switch PGA settings between channels, adding latency and settling artifacts.
- You'd share one SPI bus for both, meaning you can't read both simultaneously.
- A $1.54 ADS1220 is cheaper than the complexity of multiplexing.

---

### The pairing works well

| Aspect | ADS1256 (thrust) | ADS1220 (pressure) | Conflict? |
|--------|-------------------|---------------------|-----------|
| SPI bus | SPI0 | SPI1 | No — separate buses |
| AVDD | 5V | 5V | Same rail, simple |
| DVDD | 3.3V (from Teensy) | 3.3V (from Teensy) | Same rail |
| Sample rate | 1 kSPS | 1 kSPS (or lower) | Independent |
| Firmware driver | TI ADS1256 library | TI ADS1220 library | Both well-supported |
| DRDY pin | Dedicated GPIO | Dedicated GPIO | No conflict |

Both are delta-sigma ADCs with digital filters, so they have a **latency of ~1/SPS** from input change to output ready. At 1 kSPS, that's 1 ms. For thrust curves this is fine — your signal doesn't change faster than the mechanical system's response time.

### Verdict

**Keep both. The pairing is sound.** ADS1256 for the hard problem (tiny differential signal, need low noise), ADS1220 for the easy problem (big single-ended signal, just digitize it). Two separate SPI buses, no interference, independent configuration. Total ADC cost: ~$8.16.
