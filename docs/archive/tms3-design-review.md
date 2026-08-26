# TMS V3 Preliminary Design Review

Based on schematic analysis of `2025-TMS-3.0` (EasyEDA export, 2026-08-23).

---

## 1. Is Separating Source Voltage Actually Meaningful? Is Ground Bounce Real Here?

### What the schematic shows

The board uses two voltage rails derived from the battery via separate regulators:

- **10V rail** — LM7810 (TO-220, U23) → feeds the two ADS1115 ADC modules as analog supply
- **5V rail** — three LM7805 (TO-263, U2/U26/U27) → feeds the Arduino Nano, relay module, SD card reader, and digital logic

The 10V rail exists specifically so the ADS1115s can measure higher-range analog signals (load cell amplifier output, barometer output) without clipping at the ADC's supply voltage.

### Is ground bounce a real concern for *this* design?

**Short answer: it's a minor concern, not a critical one — but the current layout probably doesn't address it well anyway.**

Here's why:

| Factor | Status |
|--------|--------|
| Relay coil switching | The 1-channel relay module (SZH-EK093) draws ~70-80 mA when the coil energizes. The inductive kick when de-energizing creates a current spike on the shared GND. This is the **biggest noise source** on this board. |
| Arduino digital I/O switching | Minimal — the Nano's digital pins source/sink a few mA at most. |
| SD card SPI bursts | Brief 20-30 mA spikes during writes, but SPI is fairly noise-tolerant. |
| ADC measurement sensitivity | The ADS1115 at 16-bit resolution is sensitive to ~7.6 µV/LSB at ±0.256V gain. Even at the default ±2.048V range, 1 LSB = 62.5 µV. Ground bounce of a few mV from the relay will absolutely show up in your readings. |

**The real problem:** Having separate voltage regulators (LM7810 vs LM7805) doesn't help with ground bounce because **all the regulators share the same GND return path back to the battery**. Voltage separation helps with supply-rail noise (the 10V rail won't see 5V rail dropout), but the ground is still common. Ground bounce happens in the GND plane/traces, not in the supply rail.

### What would actually help

1. **Star-ground topology**: Route the ADC ground and the relay/digital ground as separate traces back to a single point near the battery connector (XT60U-F, U33). Don't let relay return current flow through the ADC ground path.
2. **Decoupling caps at ADCs**: 100 nF ceramic + 10 µF electrolytic at each ADS1115's VDD and GND pins. The current BOM has no decoupling caps at all — this is a significant oversight.
3. **Don't fire the relay during ADC sampling**: If your firmware can avoid energizing/de-energizing the igniter relay while actively reading sensors, that eliminates the problem entirely. Given the TMS use case (igniter fires once, then you're in sampling mode), this is probably already the natural sequence.

### Verdict

Separate supply voltages: **useful for headroom, not for noise isolation.** The 10V rail gives the ADS1115 more analog input range, which is a legitimate reason to keep it. But don't think of it as noise protection — add decoupling caps and star-ground routing instead. For a prototype doing one-shot ignition then sustained sampling, the ground bounce from the relay is a timing issue you can dodge in firmware.

---

## 2. Is Using Two Separate ADCs for Load Cell and Pressure Sound?

### Current topology

- **Barometer ADC** (ADS1115 instance, upper section ~y=-880) — with I2C address set via `Address_B` net, powered from 10V rail, connected to Arduino via shared I2C bus (SDA/SCL)
- **Load cell ADC** (ADS1115 instance, lower section ~y=-645) — with I2C address set via `Address_L` net, powered from 10V rail, same shared I2C bus
- Both use 4.7kΩ I2C pull-ups (SFR03EZPF4701, U10/U11) and 20kΩ resistors (address select dividers, U29/U30/U37)

### Is this a good approach?

**Yes — this is a sound design choice.** Here's why:

| Benefit | Explanation |
|---------|-------------|
| **Simultaneous sampling** | The ADS1115 is a single-channel delta-sigma ADC with a multiplexer (4 inputs, but only one converts at a time). Two separate chips let you sample barometer and load cell in parallel — or at least overlap the conversion times. For a thrust measurement system where you want synchronized pressure + force data, this matters. |
| **No mux crosstalk** | If you ran both sensors through one ADS1115's multiplexer, the internal mux settling time and residual charge from the previous channel can cause crosstalk. Separate ADCs eliminate this. |
| **Different gain settings** | Each ADS1115 can run at its own PGA gain and sample rate. The load cell likely needs a high-gain, low-noise setting (±0.256V or ±0.512V range), while the barometer may output a wider voltage swing. Independent configuration is cleaner. |
| **I2C address separation** | The `Address_B` and `Address_L` nets set different I2C addresses via the ADDR pin resistor dividers. This is the standard way to run two ADS1115s on one bus — well-supported. |

### One thing to watch

The ADS1115 at its maximum rate does 860 SPS. Over I2C at 400 kHz (Fast mode), each 16-bit read takes ~200 µs including address/register overhead. Two ADCs polling continuously is about 1720 reads/sec theoretical max — plenty for thrust curve sampling at typical rates (100-500 Hz).

**However**: the Arduino Nano's Wire library defaults to 100 kHz (Standard mode). At that speed, each I2C transaction takes ~800 µs, and you'll max out around 200-300 Hz combined for both channels. If you need faster, call `Wire.setClock(400000)` in setup.

### Verdict

**Two separate ADS1115s is the right call.** It's cleaner than multiplexing through one, gives you independent gain/rate control, and avoids channel crosstalk. The only alternative worth considering would be an HX711 for the load cell (which is purpose-built for bridge sensors and gives 80 SPS at 24-bit), but the ADS1115 is more flexible and the 16-bit resolution is adequate if your load cell amp outputs a reasonable voltage swing.

---

## 3. Relay vs N-FET for Ignitor Switching — Are Both Stable?

### What the previous design (TMS 3.0) uses

The schematic shows:
- **1-Channel 5V Relay Module** (SZH-EK093, U36) with opto-isolator
- Connected via pins: VCC, GND, control signal (D10 from Arduino), NC (normally closed), COM (common), NO (normally open)
- Annotation says "Relay High 시 COM 과 NC 붙음" (When relay is HIGH, COM and NC connect)
- A separate **HW-674 DC-DC converter** steps up to 14V for the igniter supply
- The relay switches the 14V igniter circuit

### Relay approach — pros and cons

| Aspect | Assessment |
|--------|------------|
| **Galvanic isolation** | The relay + opto-isolator gives full electrical isolation between the Arduino control side and the igniter power side. This is a real safety advantage — a firmware bug or Arduino failure can't accidentally create a current path to the igniter. |
| **Contact bounce** | Mechanical relay contacts bounce for 1-5 ms when switching. For an igniter (which needs sustained current, not edge-triggered), this is irrelevant — the igniter wire heats over hundreds of milliseconds. |
| **Current capacity** | Typical 5V SRD relay handles 10A at 30VDC. More than enough for an igniter. |
| **Failure mode** | Relays fail open (contacts wear/weld). A welded-closed contact is the dangerous failure — rare but possible with high inrush. The opto-isolator adds another layer: even if the relay welds, cutting power to the opto's LED side kills the control path. |
| **Speed** | ~5-10 ms switching time. Fine for ignition — you're not PWM-ing the igniter. |

### N-FET approach — pros and cons

| Aspect | Assessment |
|--------|------------|
| **No mechanical parts** | No bounce, no wear, no audible click. Infinite switching cycles. |
| **Speed** | Microsecond switching. Irrelevant for ignition, but nice if you ever need PWM heating control. |
| **No isolation** | An N-FET (e.g., IRLZ44N, IRF540) shares a ground reference with the Arduino. A gate driver failure or ESD event could theoretically turn on the igniter. You'd need careful gate pull-down resistors (10kΩ to GND) and potentially a gate driver IC for reliable control. |
| **Voltage rating** | Need V_DS > 14V with margin. A 30V-rated FET works. Easy to source. |
| **Heat** | R_DS(on) of a logic-level FET is typically 20-50 mΩ. At 2A igniter current, that's 80-200 mW — no heatsink needed. |
| **Gate control** | The Arduino Nano runs at 5V logic. You need a logic-level FET (gate threshold < 4V, fully enhanced at 4.5V). Standard IRLZ44N or IRLB8721 works directly from a digital pin. |

### Which is better for an igniter?

**Both are stable and will work reliably.** The choice comes down to your priorities:

| Priority | Winner |
|----------|--------|
| Safety (galvanic isolation) | **Relay** — the opto-isolated relay module gives two layers of isolation. For pyrotechnic ignition, this is the standard aerospace/rocketry practice. |
| Simplicity | **Relay module** — it's a drop-in module, no external components needed beyond wiring. |
| Board space / weight | **N-FET** — a single SOT-223 or TO-220 FET + pull-down resistor vs a chunky relay module. |
| Reliability (no mechanical wear) | **N-FET** — but the relay will outlast your prototype phase by thousands of cycles. |
| EMI / noise | **N-FET** — no coil induction spike when switching. If you're sampling ADCs near ignition time, the FET is quieter. |

### Recommendation

**For a TMS igniter, stick with the relay module.** The galvanic isolation is the right default for pyrotechnic circuits. The opto-isolated relay module (SZH-EK093) is a proven, safe choice. An N-FET would work electrically, but you'd want to add:
- 10kΩ gate-to-source pull-down resistor (ensures FET stays OFF during Arduino boot/reset when pins float)
- Flyback diode if driving any inductive load
- Careful layout to keep the high-current path away from signal traces

The relay module handles all of that internally. Unless you're optimizing for weight or board area in a flight-critical design, the relay is the lower-risk option.

---

## Summary of Actionable Items

1. **Add decoupling capacitors** — 100 nF + 10 µF at each ADS1115 VDD/GND. Currently missing from BOM entirely.
2. **Star-ground the layout** — Keep relay return current and ADC ground current on separate paths back to the battery connector.
3. **Two ADS1115s is good** — Keep the dual-ADC topology. Set `Wire.setClock(400000)` in firmware if you need >200 Hz combined sample rate.
4. **Keep the relay for igniter** — Galvanic isolation is the right choice for pyro circuits. The relay module works. If you switch to N-FET later (e.g., for a flight board), add proper gate pull-down and consider an opto-gate-driver for isolation.
5. **The note "저항 수정 필요" (resistor needs modification)** — There's an annotation in the schematic at ~[375, -665] flagging resistor values that need updating. Don't forget to resolve this.
