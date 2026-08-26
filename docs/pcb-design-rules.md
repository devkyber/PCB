# PCB Design Rules — Expert Knowledge Base

**Purpose:** Mandatory reference for Claude during PCB layout and review.  
**Sources:** TI app notes, Analog Devices mixed-signal guides, Rick Hartley (Sierra Circuits), Altium/Cadence design guides, JLCPCB DFM specs, IPC-2221.  
**Applies to:** All boards in this workspace.

---

## 1. Component Placement

### 1.1 Placement Order (Do This Sequence Every Time)

1. **Board outline, mounting holes, and keep-out zones** — these are mechanically fixed.
2. **Connectors** — positions set by enclosure, cable routing, or user access.
3. **Power supply chain** — regulator(s), input/output caps, inductors. Place along the power flow from connector to load. Keep high-current loops compact.
4. **Precision analog ICs** (ADCs, op-amps, references) — place near their input connectors to minimize analog trace length.
5. **Digital ICs** (MCU, comms modules) — place in a separate zone from analog.
6. **Decoupling capacitors** — place *immediately after* their associated IC, not as an afterthought.
7. **Crystal/oscillator** — place immediately after its IC, before routing anything.
8. **Remaining passives** (pull-ups, current limiters, voltage dividers) — place near the IC pins they serve.
9. **LEDs, test points, silkscreen** — last.

### 1.2 Placement Rules

| Rule | Detail |
|------|--------|
| **Analog/digital separation** | Draw an imaginary line on the board. All analog components and traces on one side, digital on the other. Never intermingle. |
| **Heat sources away from precision analog** | Regulators, relay coils, power transistors radiate heat. Temperature gradients between trace metals create thermoelectric voltages (Seebeck effect, ~1–40 µV/°C). Keep them ≥15 mm from ADC inputs. |
| **Components toward center** | Heat-generating parts near the board center dissipate better than at edges (more copper area for spreading). |
| **Same orientation** | Align all polarized components (ICs, diodes, electrolytic caps) in consistent directions (pin 1 same corner). Reduces assembly errors. |
| **No parts under connectors** | Connectors get mechanical stress; components underneath can crack. |
| **Assembly clearance** | Leave ≥1 mm between component bodies for soldering iron access (hand assembly) or ≥0.5 mm for reflow. |

### 1.3 Functional Grouping

Keep schematic-logical groups physically together on the PCB:

- Regulator + its input/output caps + inductor (if switching)
- ADC + its decoupling caps + reference caps + input protection resistors + crystal
- Relay + flyback diode + driver transistor + base resistor
- Each sensor connector + its protection/filtering network

---

## 2. Decoupling Capacitors

### 2.1 The #1 Beginner Mistake

Placing decoupling caps far from IC power pins or routing them through long traces. Every millimeter of trace between the cap and the IC power pin adds ~1 nH of inductance, degrading high-frequency bypass performance.

### 2.2 Placement Rules

| Rule | Spec |
|------|------|
| **Distance from IC power pin** | ≤2 mm pad-to-pad. Ideally ≤1 mm. |
| **Connection path** | Cap pad → short trace or direct pad-to-pad → IC VDD pin. GND pad → via to ground plane directly at the cap, not routed to the IC first. |
| **No via between cap and IC** | The via between the capacitor and the IC power pin adds inductance into the bypass loop. Place the cap on the same side as the IC. Route to planes from the cap's far pads. |
| **One cap per power pin** | Every VDD/AVDD/DVDD pin gets its own 100 nF ceramic (C0G or X7R). Add a 10 µF bulk cap per power rail, shared. |
| **Cap hierarchy** | Smallest value (highest frequency) closest to the pin. Bulk caps can be further away. |

### 2.3 Loop Area

The bypass current loop is: IC VDD pin → trace → cap → cap GND pad → via → ground plane → back under the IC → IC GND pin. **Minimize this loop area.** A tight loop = low inductance = effective decoupling.

### 2.4 Specific to Our Designs

- **ADS1256**: Needs separate 100 nF + 10 µF on AVDD, DVDD, and VREFP. Crystal load caps (22 pF) within 3 mm of crystal pins. Follow TI EVM exactly.
- **ADS1220**: 100 nF on AVDD (pin 13), 100 nF on DVDD (pin 4). Place on same side as IC.
- **LM7805**: 330 nF input cap *before* the regulator (≤5 mm from VIN pin). 100 nF output cap *after* (≤5 mm from VOUT pin). These are stability caps, not optional.

---

## 3. Ground Plane Strategy

### 3.1 Core Principle (Rick Hartley / Analog Devices)

**Use a single, solid, unbroken ground plane.** Do NOT split the ground plane into AGND/DGND regions. This is the modern consensus from TI, Analog Devices, and Hartley.

**Why:** Ground current returns directly beneath the signal trace that generated it (path of least impedance at high frequency). If you keep analog and digital signals physically separated by placement and routing, their return currents automatically stay separated on the shared ground plane. A split plane forces return currents to detour around the gap, creating large loop antennas.

### 3.2 Ground Plane Rules

| Rule | Detail |
|------|--------|
| **Dedicate one full layer to ground** | On a 2-layer board, use the bottom layer as a continuous ground pour. On 4-layer, use layer 2 as a solid GND plane. |
| **Never route signals across ground plane gaps** | If the ground plane has a slot or split, *no* signal trace may cross it. The return current would have to detour, creating a loop antenna. |
| **No traces on the ground layer** | Avoid routing signal traces on the ground plane layer. Every trace cuts a slot in the ground, disrupting return paths. On a 2-layer board, route on top and pour ground on bottom. Minimal bottom-side traces only where absolutely necessary, and bridge any cuts with via stitching. |
| **Ground pour on both layers** | Fill unused copper area with ground pour on both layers, connected by via stitching. |
| **Via stitching around the perimeter** | Place ground vias every 5–10 mm around the board edge to tie top and bottom ground pours together. |

### 3.3 Mixed-Signal Ground Connection

For ICs with separate AGND and DGND pins (like the ADS1256):

1. Connect both AGND and DGND to the single ground plane.
2. Connect them at the IC — use a single via right at the IC's ground pads.
3. Partition by component placement, not by cutting the ground plane.

### 3.4 Star Ground (When Applicable)

For high-current loads (relay coil, igniter), route their ground return on a separate trace back to the power input connector ground. Don't let relay switching current flow through the ground plane under the ADCs.

---

## 4. Trace Routing

### 4.1 General Routing Rules

| Rule | Detail |
|------|--------|
| **Route critical signals first** | Analog inputs, crystal, SPI clock — in that order. Everything else routes around them. |
| **Short and direct** | Minimize trace length, especially for analog signals and clocks. |
| **No right angles** | Use 45° bends or curves. Right angles create impedance discontinuities and acid traps in etching. |
| **No stubs** | Dead-end traces act as antennas. If a trace must branch, use a T-junction, not a dead-end stub. |
| **Return path awareness** | Every signal trace needs a continuous ground plane beneath it. If the return path is broken, the signal radiates. |
| **Signal layer changes** | When a signal moves from top to bottom via a via, place a ground stitching via within 2 mm to provide the return current a path between layers. |

### 4.2 Trace Width by Current (IPC-2221, 1 oz Cu, 10°C Rise)

| Current (A) | External Layer Width (mm) | Internal Layer Width (mm) |
|-------------|--------------------------|--------------------------|
| 0.5 | 0.25 | 0.50 |
| 1.0 | 0.50 | 1.10 |
| 2.0 | 1.20 | 2.60 |
| 3.0 | 2.00 | 4.30 |
| 5.0 | 3.80 | 8.20 |

**Formula:** I = k × ΔT^0.44 × A^0.725 where k = 0.048 (external) or 0.024 (internal), A = cross-sectional area in mil².

**Our defaults:**
- Signal traces: 0.254 mm (10 mil) — good for ≤500 mA
- Power traces: 0.5 mm (20 mil) — good for ~1 A
- Battery/relay traces: 1.0+ mm — size for actual current

### 4.3 Analog Signal Routing

| Rule | Detail |
|------|--------|
| **Differential pairs** | Route AINP/AINN as a matched pair: equal length, equal spacing, parallel routing. |
| **Guard ring** | For high-impedance analog inputs, surround traces with a grounded copper pour or guard trace connected to analog ground. |
| **No parallel runs with digital** | Analog traces must not run parallel to digital signals (SPI clock, UART). Cross at 90° if they must cross. |
| **Kelvin connections for current sensing** | Route sense traces separately from current-carrying traces, connecting at the measurement point only. For load cell connections: separate excitation and sense traces. |
| **Input filtering close to ADC** | Place RC input filters (100Ω + cap) within 3 mm of ADC input pins, not at the connector end. |

### 4.4 Digital Signal Routing

| Rule | Detail |
|------|--------|
| **SPI clock** | Keep as short as possible. Match MOSI/MISO length to within 5 mm of SCK length for data integrity. |
| **Series termination** | For SPI lines >50 mm, add 33Ω series resistors at the source end. |
| **Pull-ups/pull-downs** | Place near the pin they serve, not at the other end of the bus. |

---

## 5. Crystal / Oscillator Layout

### 5.1 Rules (Critical for ADS1256 7.68 MHz Crystal)

| Rule | Detail |
|------|--------|
| **Proximity** | Crystal + load caps within 5 mm of the IC oscillator pins. Shorter = better. |
| **Trace length** | XIN/XOUT traces ≤10 mm each. |
| **Symmetry** | Route XIN and XOUT traces symmetrically (equal length, equal parasitic capacitance). |
| **No ground pour under crystal** | Ground plane under the crystal body adds parasitic capacitance, shifting the oscillation frequency. Keep the ground plane pulled back under the crystal footprint. |
| **Ground pour around crystal** | While no ground under the crystal body, surround the crystal area with ground to shield it from other signals. |
| **No signal routing near crystal** | No digital or power traces within 3 mm of crystal traces. |
| **No vias on crystal traces** | Route XIN/XOUT entirely on one layer — no layer changes. |
| **Load cap grounding** | Load cap GND pads connect to ground via short vias, close to the caps. |

---

## 6. Power Supply Layout

### 6.1 Linear Regulator (LM7805)

| Rule | Detail |
|------|--------|
| **Input cap** | 330 nF ceramic, ≤5 mm from VIN pin. Required for stability. |
| **Output cap** | 100 nF ceramic, ≤5 mm from VOUT pin. Datasheet minimum. |
| **Thermal pad** | Connect tab/thermal pad to ground plane with thermal vias (4–6 vias, 0.3 mm drill). |
| **Copper pour** | Extended copper pour around regulator pad for heat spreading. |
| **Input trace width** | Size for max input current (our case: ~500 mA → ≥0.5 mm). |
| **Output trace width** | Size for max load current. Separate high-current loads from sensitive analog. |

### 6.2 Switching Regulator (Buck/Boost)

| Rule | Detail |
|------|--------|
| **Hot loop** | The switching current loop (VIN → high-side FET → inductor → load → GND → input cap → back to VIN) must be as tight and short as possible. This is the #1 priority for switcher layout. |
| **Input cap** | Place ≤3 mm from VIN and GND pins. This cap handles the high-frequency switching current spikes — it's the most layout-critical component. |
| **Inductor placement** | Adjacent to the SW pin, trace ≤5 mm. The SW node is the noisiest node — keep it small in area. |
| **Catch/bootstrap diode** | ≤3 mm from SW and GND pins. |
| **Output cap** | ≤5 mm from VOUT. Less critical than input cap but still close. |
| **Feedback trace** | Route FB/VOUT sense trace away from the SW node and inductor. Kelvin-connect to the output cap positive terminal, not the load. |
| **SW node copper** | Keep SW node copper area minimal — just enough to connect. Large SW copper = large antenna for radiated EMI. |
| **No sensitive traces near** | Keep analog signals ≥10 mm from switcher. Route on opposite side if possible. |
| **Thermal vias** | Under exposed pad, same as linear regulator. |

### 6.3 LDO Regulators

| Rule | Detail |
|------|--------|
| **Input/output caps** | Same rules as linear — ≤5 mm from pins, values per datasheet. |
| **Dropout** | Verify headroom: VIN − VOUT > dropout voltage at max load. Check across temperature. |
| **PSRR bandwidth** | LDO PSRR degrades above ~1 kHz. Add 100 nF ceramic on output for high-frequency noise that the LDO can't reject. |
| **Enable pin** | If unused, tie to VIN through a resistor (typically 100 kΩ). Never float. |

### 6.4 Power Trace Routing

- Route power traces as wide, short, and direct as possible.
- Avoid routing power traces under or near analog signal traces.
- Use copper pours for power distribution when possible.
- Star topology from regulator output: separate branches to analog ICs, digital ICs, relay.

### 6.5 Voltage Reference Layout (Critical for ADC Accuracy)

| Rule | Detail |
|------|--------|
| **Bypass cap** | 100 nF C0G ceramic ≤2 mm from VREF output pin. Add 10 µF bulk within 5 mm. |
| **Kelvin sense** | Route VREF trace directly from the reference output to the ADC VREF input. Don't share this trace with other loads. |
| **No digital noise** | Keep VREF trace away from SPI, clocks, and switching nodes. Route on analog side of the board. |
| **Thermal symmetry** | Temperature gradients shift reference voltage. Keep reference IC away from heat sources and in a thermally stable zone. |
| **Decoupling at ADC end** | Place an additional 100 nF cap at the ADC's VREF input pin, not just at the reference output. |

---

## 7. Relay and High-Current Circuit Layout

### 7.1 Rules for TMS Relay Circuit

| Rule | Detail |
|------|--------|
| **Physical isolation** | Relay, flyback diode, NPN driver, and igniter connectors in their own board zone, far from ADCs. |
| **Creepage distance** | If igniter voltage exceeds 50V: maintain ≥2 mm clearance between igniter traces and low-voltage circuits. |
| **Flyback diode** | Place 1N4148WS ≤5 mm from relay coil pins, cathode to +5V, anode to coil drive. Short traces minimize voltage spike. |
| **Ground return** | Route relay ground directly back to power input ground, not through the analog ground area. |
| **Wide traces** | Relay coil current ~80 mA — 0.5 mm trace is fine. Igniter current may be higher — size accordingly. |
| **Separate connector ground** | Igniter battery ground should return to its own connector, not share the signal ground path. |

---

## 8. Via Design

### 8.1 Via Rules

| Parameter | Value |
|-----------|-------|
| **Drill diameter** | 0.3 mm minimum (JLCPCB). Use 0.4 mm for reliability. |
| **Pad diameter** | 0.6 mm minimum (0.15 mm annular ring per side). Use 0.8 mm for 0.4 mm drill. |
| **Thermal vias** | Under thermal pads: array of 4–9 vias, 0.3 mm drill, 0.8 mm pitch. |
| **Ground stitching** | Every 5–10 mm around board perimeter. Near every signal via that changes layers. |
| **Via-in-pad** | Avoid for standard assembly. If needed, specify filled and capped (extra JLCPCB cost). |

### 8.2 When to Add Ground Stitching Vias

- Within 2 mm of every signal via (provides return current path between layers)
- Around crystal oscillator area
- Around board perimeter (every 5–10 mm)
- Between analog and digital zones (fence of vias to contain return currents)
- Around high-current zones (relay area) to prevent ground potential differences

---

## 9. Thermal Management

### 9.1 Rules

| Rule | Detail |
|------|--------|
| **Identify heat sources** | LM7805 dissipates (VIN − 5V) × I_load. At 16V in (4S LiPo), 500 mA load = 5.5W. Consider heatsink or switching regulator. |
| **Thermal pad connection** | Use thermal vias (≥4 vias, 0.3 mm drill) under exposed pads to connect to internal or opposite-side copper pour. |
| **Copper pour area** | ≥100 mm² of copper connected to regulator ground pad for heat spreading. |
| **Thermal relief on pads** | Use thermal relief (spoked connection) on through-hole pads connected to ground pour — prevents heat sinking during soldering. |
| **No thermal relief on thermal pads** | Direct connection (no spokes) for IC thermal/exposed pads — maximizes heat transfer. |
| **Component spacing** | Keep temperature-sensitive components (ADCs, references) ≥15 mm from hot regulators. |

---

## 10. JLCPCB DFM Rules (2-Layer)

### 10.1 Minimum Specifications

| Parameter | JLCPCB Min | Our Design Rule |
|-----------|-----------|-----------------|
| Trace width | 0.127 mm (5 mil) | 0.254 mm (10 mil) signal |
| Trace spacing | 0.127 mm (5 mil) | 0.2 mm (8 mil) |
| Via drill | 0.3 mm | 0.3 mm (or 0.4 mm preferred) |
| Via pad | 0.6 mm | 0.6 mm (or 0.8 mm for 0.4 drill) |
| Annular ring | 0.13 mm | 0.15 mm |
| Solder mask expansion | 0.05 mm | 0.05 mm |
| Solder mask dam | 0.2 mm | 0.2 mm |
| Silkscreen width | 0.15 mm | 0.2 mm |
| Silkscreen height | 0.8 mm | 1.0 mm |
| Board edge clearance (copper) | 0.3 mm | 0.5 mm |
| Board edge clearance (component) | 0.5 mm | 1.0 mm |
| Drill-to-board-edge | 0.5 mm | 0.5 mm |

### 10.2 Assembly (PCBA) DFM

| Rule | Detail |
|------|--------|
| **Fiducial marks** | Not required — JLCPCB auto-adds its own fiducials for assembly if the board has none, so orders aren't rejected for missing them. Recommended (3, in an L-pattern, 1 mm pad / 2 mm solder mask opening) for boards with fine-pitch parts (<0.5 mm pitch) or when you want tighter placement accuracy than JLCPCB's default. |
| **Component orientation** | Mark pin 1 clearly on silkscreen for every IC. |
| **BOM format** | Comment, Designator, Footprint, LCSC Part Number. |
| **CPL format** | Designator, Mid X (mm), Mid Y (mm), Rotation (°), Layer (top/bottom). |
| **Panel rails** | For small boards (<50 mm), add 5 mm rails with V-score or mousebites. |

---

## 11. ESD and Input Protection

### 11.1 Connector ESD Protection

| Rule | Detail |
|------|--------|
| **TVS diodes at every external connector** | Place bidirectional TVS (or TVS array) within 5 mm of connector pins. Route the signal through the TVS before it reaches the IC. |
| **TVS GND connection** | Short, wide trace to the ground plane via — the TVS must dump energy to ground with minimal inductance. |
| **Series resistors** | 100Ω series resistors on analog inputs limit fault current. Place between TVS and ADC input. |
| **Clamp voltage** | Select TVS clamp voltage below the IC's absolute max rating but above the signal operating range. |

### 11.2 ADC Input Protection Network

Standard protection chain: **Connector → TVS to GND → 100Ω series R → RC filter → ADC pin**

| Rule | Detail |
|------|--------|
| **Resistor value** | 100Ω–1 kΩ series. Check datasheet for max source impedance that doesn't degrade ADC performance. ADS1256 with PGA=64: keep ≤100Ω. |
| **Filter cap** | Optional low-pass: 100 pF–1 nF to GND after the series R. Cutoff = 1/(2π×R×C). |
| **Symmetry** | Both differential inputs (AINP/AINN) must have identical protection networks — matched R and C values, symmetric layout. |
| **Placement** | Protection components near ADC, not near connector. Keeps the protected zone short. |

---

## 12. Copper Pour Rules

### 12.1 General Rules

| Rule | Detail |
|------|--------|
| **Fill all unused copper** | Pour GND copper on all unused areas of every layer. Floating copper is an antenna. |
| **Minimum connection width** | Copper pour must connect to pads with ≥0.25 mm thermal spoke width. |
| **No floating islands** | After pouring, check for copper islands not connected to any net. Remove them — they act as parasitic antennas and capacitors. |
| **Thermal relief on through-hole** | Through-hole pads in ground pour get thermal relief (4 spokes) for solderable joints. |
| **Direct connect on thermal pads** | IC exposed/thermal pads get direct pour connection (no spokes) for best heat transfer. |
| **Clearance from signals** | Pour clearance from signal traces: ≥0.2 mm (same as trace-to-trace clearance). |
| **Keep-out under crystal** | Remove ground pour under crystal body footprint. |

### 12.2 2-Layer Pour Strategy

- **Top layer:** Signal routing + GND pour fill in unused areas.
- **Bottom layer:** Continuous GND pour. Minimize traces on bottom — every trace cuts the ground plane.
- **Via stitching:** Connect top and bottom pours every 5–10 mm.

---

## 13. Layer Stackup Guidance

### 13.1 When to Use 4 Layers

Move to 4-layer when any of these apply:
- Board has >2 power rails that need plane distribution
- Mixed analog/digital design with high-resolution ADCs (≥16-bit) and fast digital clocks
- Board area is tight and 2-layer routing is impossible without cutting the ground plane
- EMC requirements demand controlled impedance traces

### 13.2 Recommended 4-Layer Stackup

| Layer | Assignment | Notes |
|-------|-----------|-------|
| L1 (Top) | Signals + components | Route analog signals here. Power traces OK. |
| L2 | Solid GND plane | **Never cut or route on this layer.** Every signal on L1 has its return path here. |
| L3 | Power plane(s) | Split into power islands as needed (+3V3, +5V). Keep a GND region for signals on L4. |
| L4 (Bottom) | Signals + components | Digital signals preferred. Ground pour in unused areas. |

### 13.3 2-Layer Strategy (Our Default)

| Layer | Assignment |
|-------|-----------|
| Top | All signals + components. Route here first. |
| Bottom | GND pour (primary). Minimal signal traces only when top-side routing is impossible. Bridge any pour cuts with stitching vias on both sides. |

---

## 14. EMC / EMI Basics

### 14.1 Rules

| Rule | Detail |
|------|--------|
| **Minimize loop area** | Every current loop is an antenna. The radiated power is proportional to loop area². Smaller loops = less EMI. |
| **Continuous ground plane** | The single most effective EMI reduction technique. No splits, no slots, no trace cuts. |
| **Bypass every IC** | Every IC power pin gets a 100 nF cap ≤2 mm away. This is non-negotiable. |
| **Filter at boundaries** | Add ferrite beads or RC filters where signals enter/leave the board (connectors). |
| **Short clock traces** | Clock signals are the #1 EMI source. Keep them short, don't route near board edges, and terminate if >50 mm. |
| **No traces near board edge** | Keep all traces ≥3 mm from board edge. Edge traces have no ground plane return on one side and radiate. |
| **Ground via fencing** | Place ground vias around the board perimeter and around noisy sections (switching regulators, relay drivers). |

---

## 15. Pre-Layout Completeness Checks

These checks catch design omissions **before** layout begins. Every item here was missed in at least one of our test designs.

### 15.1 Datasheet Value Cross-Check (Mandatory)

Before placing any component, verify every passive value against the IC datasheet's recommended application circuit:

| Check | How | Common Pitfall |
|-------|-----|----------------|
| **Regulator output/bypass caps** | Compare your BOM cap values to the datasheet "Typical Application" table, row by row | Using 1µF when datasheet says 2.2µF (e.g., ICM-42688-P REGOUT pin requires 1µF per datasheet, but some refs use 2.2µF — match whichever source you're following, and document which) |
| **Crystal load caps** | Calculate: C_load = 2 × (C_L − C_stray), where C_L is from the crystal datasheet and C_stray ≈ 3–5 pF | Using generic 22pF without checking the specific crystal's C_L spec |
| **Reference voltage caps** | Match type (C0G vs X7R) and value exactly to datasheet recommendation | Using X7R where datasheet specifies C0G for low-drift reference |
| **Input protection resistor max** | Check datasheet for maximum source impedance that doesn't degrade ADC performance | Using 1kΩ when ADC spec says ≤100Ω at high PGA gain |

### 15.2 Pin Completeness Audit

For every IC, account for **every pin** — not just the ones in your signal path:

| Pin Category | Action Required |
|-------------|-----------------|
| **Address selection pins** | Add solder jumpers or resistors to set I2C/SPI address. Default to the address matching your code. Document the selected address. |
| **Mode/config pins** | Tie to VDD or GND per datasheet (e.g., SPI/I2C mode select). Never leave floating. |
| **Interrupt/DRDY outputs** | Route to MCU GPIO even if not used in firmware V1 — the trace costs nothing, the rework costs a board spin. |
| **EXTINT/SAFEBOOT/debug pins** | Break out to test points or header. These are essential for debugging and firmware updates. |
| **Unused analog inputs** | Tie to AGND through a resistor, or to a mid-rail reference per datasheet. |
| **NC (No Connect) pins** | Verify they are truly NC in the datasheet errata. Some "NC" pins must be grounded. |

### 15.3 Voltage Level Compatibility

Before connecting any two ICs, verify voltage levels match:

| Situation | Required Action |
|-----------|-----------------|
| **3.3V IC → 5V-tolerant input** | Check if the receiving input recognizes 3.3V as logic HIGH (V_IH threshold). Most 5V CMOS needs ≥3.5V — a 3.3V signal may be marginal. Add a level shifter (BSS138 MOSFET or TXB0108). |
| **5V IC → 3.3V input** | **Mandatory** level shifter or resistor divider. 5V into a 3.3V-max pin destroys the IC. |
| **Mixed-voltage I2C bus** | Use BSS138 bidirectional level shifter (one per line). Pull-ups to each side's VCC. |
| **Mixed-voltage SPI bus** | Unidirectional: resistor divider (MISO 5V→3.3V) or dedicated level shifter IC. |

### 15.4 Board Size Optimization

Calculate minimum board area before starting layout:

1. **Sum component footprint areas** — include pads and courtyard, not just body
2. **Add 50% for routing channels** on 2-layer, 30% on 4-layer
3. **Add mounting holes and connector clearance zones**
4. **Compare to reference designs** — if your board is >1.5× the reference area for equivalent functionality, re-examine placement density

Target: component density of 40–60% (footprint area / board area). Below 30% means the board is oversized.

### 15.5 Controlled Impedance (RF and High-Speed)

For any trace carrying RF (antenna, GNSS, WiFi, BLE) or high-speed signals (>100 MHz clock, USB, HDMI):

| Requirement | Spec |
|-------------|------|
| **Calculate impedance** | Use JLCPCB stackup calculator or Saturn PCB toolkit. 50Ω microstrip on 1.6mm FR4, 1oz Cu ≈ 2.85mm trace width (top layer over ground). |
| **Specify in design rules** | Create a net class with the calculated width. Do not leave as "theory only." |
| **Clearance** | Keep ≥3× trace width clearance from adjacent traces. No ground pour within 2× trace width on the same layer. |
| **Ground plane continuity** | Solid, unbroken ground plane directly beneath the RF trace. Any gap kills impedance control. |
| **Connector transition** | Match impedance through the connector (e.g., U.FL is 50Ω). Avoid pad-to-trace width changes — use tapered transitions. |
| **Length** | Minimize. Every mm of 50Ω trace on FR4 adds ~6.6 ps delay and ~0.02 dB loss at 1.5 GHz. |

### 15.6 Standardized Interfaces (Evaluate for Every Breakout)

For sensor breakout boards, evaluate whether these standard interfaces should be included:

| Interface | When to Include | Footprint Cost |
|-----------|----------------|----------------|
| **STEMMA QT / Qwiic (JST-SH 4-pin)** | Any I2C sensor breakout | 4.5mm × 6mm — minimal |
| **SWD header (2×5 1.27mm)** | Any board with ARM MCU | 5mm × 6.35mm |
| **UART header (1×4 2.54mm)** | Any board with serial debug | 10mm × 2.54mm |
| **Mounting holes (M2.5 or M3)** | Every board ≥15mm on a side | 5.5mm diameter keepout each |

Decision: include unless the board is too small. Document the decision either way.

---

## 16. Common Beginner Mistakes — Checklist

Use this as a review checklist after completing layout.

| # | Mistake | How to Check | Fix |
|---|---------|-------------|-----|
| 1 | Decoupling caps too far from IC | Measure pad-to-pad distance in KiCad | Move to ≤2 mm |
| 2 | Via between decoupling cap and IC power pin | Visual check of cap-to-pin path | Reroute: cap connects directly to pin, via on cap's far pad |
| 3 | Signal trace crosses ground plane gap | Check ground pour continuity under every signal trace | Fill the gap or reroute the signal |
| 4 | Crystal traces too long | Measure XIN/XOUT trace length | Move crystal closer to IC |
| 5 | Ground pour under crystal body | Check copper fill under crystal footprint | Add keep-out zone under crystal |
| 6 | Analog trace runs parallel to digital | Check for parallel runs >5 mm | Reroute to cross at 90° |
| 7 | Power trace too narrow for current | Calculate using IPC-2221 table above | Widen trace |
| 8 | No ground stitching near signal vias | Check every signal via for nearby GND via | Add stitching via within 2 mm |
| 9 | Traces too close to board edge | Check copper-to-edge clearance | Move traces ≥3 mm from edge |
| 10 | Missing thermal vias under thermal pads | Check regulator/IC thermal pads | Add 4–9 thermal vias, 0.3 mm drill |
| 11 | Relay ground sharing analog ground path | Trace relay GND return path | Route relay GND directly to power input |
| 12 | Flyback diode too far from relay coil | Measure diode-to-coil distance | Move to ≤5 mm |
| 13 | Unused IC pins floating | Check every IC pin in schematic | Tie to VDD/GND/appropriate rail per datasheet |
| 14 | No test points on critical signals | Check TP coverage | Add test points for power rails, DRDY, key analog signals |
| 15 | Silkscreen overlaps pads | Run DRC | Adjust silkscreen placement |
| 16 | No self-placed fiducials on a fine-pitch PCBA board | Check board has fiducials if using PCBA with <0.5 mm pitch parts | Optional: add 1 mm fiducial pads with 2 mm mask opening for tighter placement accuracy — JLCPCB auto-adds its own if you skip this, so it will not reject the order |
| 17 | Thermocouple effect near ADC | Check for heat sources near ADC inputs | Move regulator/relay ≥15 mm away from ADC |
| 18 | Antenna trace near ground pour edge | Check RF/antenna trace clearance | Pull back ground pour ≥2 mm from antenna |
| 19 | Load cell traces not matched | Compare AINP/AINN trace lengths | Match lengths within 2 mm, route as parallel pair |
| 20 | No bulk capacitor on power rail | Check each power rail | Add ≥10 µF electrolytic or ceramic near power input |
| 21 | Passive values don't match datasheet | Compare every cap/resistor to IC datasheet app circuit | Fix value to match datasheet exactly (see §15.1) |
| 22 | Missing I2C address select jumpers | Check every I2C device for address pins | Add solder jumpers (see §15.2) |
| 23 | Missing voltage level shifters | Check every inter-IC connection for voltage mismatch | Add BSS138 or resistor divider (see §15.3) |
| 24 | Board oversized for the design | Calculate component density (§15.4) | Target 40–60% density, compare to reference boards |
| 25 | Placeholder footprints in final design | Check `fidelity` field from fetch_part_library | Re-fetch or manually create real footprint before layout |

---

## 17. Layout Review Protocol (6+1 Pass)

Before declaring layout complete, run through these checks in order.

### 15.7 Real-Part Symbol Verification (Mandatory for Fetched Parts)

Real symbols fetched via `fetch_part_library` (EasyEDA → easyeda2kicad conversion) are geometrically accurate but carry two systematic gaps that placeholder-era designs never surface. Found while integrating real parts into TMS V3 — 184 pins were "connected" only by a label sitting near a guessed coordinate, and a relay's coil/COM/NO assignment was unverified.

| Check | Why | How |
|-------|-----|-----|
| **Library auto-registration is not guaranteed** | `fetch_part_library` may not add the `jlcpcb` library to the project's `sym-lib-table`/`fp-lib-table` | After fetching, grep both tables for a `jlcpcb` entry; add it manually if missing before schematic work starts |
| **Never trust a placeholder-era pin-map comment** | Rev D described ADS1256 as "1=AINP0,2=AINN0..." — invented, not the real pinout | Extract the actual `(pin (name...)(number...))` pairs from the fetched `.kicad_sym` and build the wiring plan from that, every time |
| **Multi-function pins (relay COM/NO, TVS common) need the manufacturer datasheet, not the symbol** | EasyEDA-converted symbols often carry only generic numeric pin names ("1","2","3") with no functional label | Pull the real datasheet. If WebFetch's text extraction comes back empty/garbled (common on vector wiring diagrams), use `docs/fetch_reference_doc.py`'s `render_pdf_pages()` to render the relevant pages to PNG and read them visually — confirm the wiring diagram before connecting anything safety-critical (igniter, power switching) |
| **WebFetch summarizes — it cannot answer "what exact value is on this exact pin"** | A GitHub-hosted Eagle `.sch` reference fetched via WebFetch truncated before the pin-level cap wiring survived; a manufacturer PDF returned empty text | Use `docs/fetch_reference_doc.py`: `fetch_raw()` + `parse_eagle_schematic()` for exact part values *and* pin-level net connections from a real `.sch`/`.brd` file (validated: recovered Adafruit's exact BMP390 decoupling and caught a 10kΩ-vs-4.7kΩ pull-up discrepancy a summary-based fetch missed); `render_pdf_pages()` for PDFs. Always `verify_url()` a link before citing it — report "verified dead, HTTP 404," never "couldn't fetch, unknown reason" |
| **Wire every net to the symbol's real pin coordinate, never a guessed (x,y)** | A label near a pin *looks* connected in a screenshot but ERC will show it dangling | If the generation tooling exposes a pin-position lookup (e.g. `get_pin_position`), use it for 100% of connections — don't hand-place any label |
| **Component placement should land on the schematic grid (1.27mm)** | Real symbol pins are grid-aligned; if the component's placed center isn't, every pin inherits the offset | Snap all placement coordinates to the nearest 1.27mm before placing |
| **EasyEDA conversion drops KiCad electrical pin-type metadata** | Causes `pin_to_pin`/`power_pin_not_driven` ERC noise even on correctly-wired nets | Expected and harmless as warnings; if `power_pin_not_driven` shows as an **error**, add a `power:PWR_FLAG` symbol on that net rather than chasing the metadata |
| **Run ERC after every section, not just at the end** | Catches naming bugs (e.g. two different nets accidentally reusing the same label) while the section is still fresh in context | `kicad-cli sch erc` is fast enough to run per section during script-based generation |
| **Every genuinely unused pin gets an explicit no-connect flag** | Silence looks identical to "forgot this pin" in a diff | Use the no-connect marker, not just an absent label |
| **Document generic-header substitutions as a known gap** | Modules without an LCSC listing (Teensy, XBee) can't go through `fetch_part_library` | State explicitly in the script/PDR which headers are placeholders and what pins are actually wired vs. left as approximate |
| **Fetched `.kicad_mod` footprints may be in the legacy `(module ...)` format** | Some `fetch_part_library` output pre-dates KiCad 7's `(footprint ...)` format; PCB tooling built against the modern format rejects it outright | Round-trip each file through real `pcbnew` once: `kipython -c "import pcbnew; fp = pcbnew.FootprintLoad(dir, name); pcbnew.FootprintSave(dir, fp)"` upgrades it in place |
| **PCB placement coordinates from a placeholder-footprint-era script don't transfer to real footprints** | Real IC/relay/connector bodies are frequently *much* larger than the crude 2-pad or generic-circle placeholders a hand-rolled S-expression generator used — inherited (x,y) positions collide the moment real geometry is substituted in | **Use `docs/pcb_layout_helpers.py` — don't hand-check this.** `get_courtyard_bbox()` extracts a footprint's real size before you pick a coordinate; `PlacementTracker.place()` raises immediately on a collision, with the exact overlap in mm, as you generate the board — not 40 DRC violations later with no indication which placement decision caused which one. Confirmed on the exact TMS V3 relay/header collision: caught instantly, `K1 overlaps J8 by 2.28mm x 6.98mm`, instead of a generic `pth_inside_courtyard` DRC line discovered after the whole board was built. A second instance recurred 2026-08-25 on the same board: crystal `Y1` (`jlcpcb:CRYSTAL-SMD_L11.4-W4.7-LS12.4`, a 12.4mm lead-span part) was centered in an ~11mm gap between `U2` and `R9/R10/R11`, colliding with both sides at once — a coordinate chosen when the crystal's real footprint size wasn't yet known. Fix pattern when a part is simply too big for its gap: check if rotating 90° trades its long axis for its short one against the tighter-constrained direction (worked here — freed ~7mm), then relocate to open board area if that's still not enough. This is not a one-off; budget real board area for any component whose real courtyard hasn't been checked yet. |

### Pass 0 — Pre-Layout Completeness (Run Before Starting Layout)
- [ ] Every passive value verified against IC datasheet app circuit (§15.1)
- [ ] Every IC pin accounted for — no floating config/address/debug pins (§15.2)
- [ ] Voltage levels verified at every inter-IC connection (§15.3)
- [ ] Board dimensions justified against component density target (§15.4)
- [ ] RF/high-speed traces have calculated impedance in net class (§15.5)
- [ ] All footprints are real (fidelity = "real"), no placeholders
- [ ] Fiducials considered for fine-pitch PCBA (optional — JLCPCB auto-adds its own if omitted)

### Pass 1 — Power Integrity
- [ ] Every IC power pin has a decoupling cap ≤2 mm away
- [ ] Power trace widths match current requirements
- [ ] Regulator thermal pad has thermal vias
- [ ] Bulk caps on every power rail
- [ ] No power trace crosses ground plane gap

### Pass 2 — Signal Integrity
- [ ] Analog input traces are short, matched, and guarded
- [ ] Crystal traces ≤10 mm, no ground pour under crystal body
- [ ] No analog/digital parallel runs >5 mm
- [ ] SPI clock trace is short, with ground return path intact
- [ ] Ground stitching via near every signal layer-change via

### Pass 3 — Thermal
- [ ] Heat sources identified and >15 mm from precision analog
- [ ] Thermal vias under exposed pads
- [ ] Adequate copper pour for heat spreading

### Pass 4 — EMC
- [ ] No traces within 3 mm of board edge
- [ ] Ground via stitching around perimeter
- [ ] Clock traces short and not near edges
- [ ] Filter components at I/O connectors

### Pass 5 — DFM (JLCPCB)
- [ ] All clearances ≥ design rule minimums
- [ ] Annular ring ≥ 0.15 mm
- [ ] Solder mask dams ≥ 0.2 mm
- [ ] Silkscreen readable (≥1 mm height, no pad overlaps)
- [ ] Fiducials present if fine-pitch (<0.5mm) PCBA — optional otherwise, JLCPCB auto-adds its own
- [ ] Pin 1 marked on every IC

### Pass 6 — Mechanical
- [ ] Board outline matches spec
- [ ] Mounting holes in correct positions
- [ ] Connector positions match enclosure/panel
- [ ] Component clearance from board edge ≥1 mm
- [ ] No parts under mechanical stress zones (connectors, mounting holes)

### Pass 7 — Post-Route Verification (After All Traces Are Routed)
- [ ] **Zero unconnected nets** — run DRC, confirm 0 unconnected items
- [ ] **Zero DRC violations** — all clearance, width, and drill rules pass
- [ ] **No placeholder footprints** — every component uses its real LCSC footprint
- [ ] **Silkscreen legibility** — no overlaps with pads, all text ≥1mm height
- [ ] **Silkscreen content** — board name, revision, author, pin 1 marks, TP labels all present
- [ ] **Edge clearance** — no copper within 0.5mm of board edge, no components within 1mm
- [ ] **Fiducials** — optional; recommended (3, L-pattern) for fine-pitch (<0.5mm) PCBA boards. JLCPCB auto-adds its own fiducials for assembly if the board has none, so orders are not rejected for omitting them.
- [ ] **Net class compliance** — power nets use Power/HighCurrent width, RF nets use impedance-controlled width

---

## Sources

- [Analog Devices — Successful PCB Grounding with Mixed-Signal Chips](https://www.analog.com/en/resources/technical-articles/successful-pcb-grounding-with-mixedsignal-chips--follow-the-path-of-least-impedance.html)
- [Analog Devices — Mixed-Signal PCB Layout Guidelines](https://www.analog.com/en/resources/analog-dialogue/articles/what-are-the-basic-guidelines-for-layout-design-of-mixed-signal-pcbs.html)
- [Rick Hartley — 7 PCB Design Tips (Sierra Circuits)](https://www.protoexpress.com/blog/7-pcb-design-tips-by-rick-hartley/)
- [Rick Hartley — Signal Integrity Design Recommendations (Sierra Circuits)](https://www.protoexpress.com/blog/rick-hartley-pcb-design-recommendations-to-minimize-emi/)
- [JLCPCB — PCB Design Rules and Best Practices](https://jlcpcb.com/blog/pcb-design-rules-best-practices)
- [JLCPCB — Decoupling Capacitor Guide](https://jlcpcb.com/blog/decoupling-capacitors-guide)
- [JLCPCB — Component Placement Guide](https://jlcpcb.com/blog/pcb-component-placement-guide-2026)
- [JLCPCB — Thermal Vias Guide](https://jlcpcb.com/blog/thermal-vias-in-pcb-design-for-heat-management)
- [Altium — Decoupling and Bypass Capacitor Placement](https://resources.altium.com/p/bypass-and-decoupling-capacitor-placement-guidelines)
- [Altium — Crystal Oscillator PCB Layout](https://resources.altium.com/p/crystal-oscillators-your-pcb-layout-keep-frequencies-steady)
- [Altium — Crosstalk in Mixed-Signal Traces](https://resources.altium.com/p/crosstalk-in-mixed-signal-pcb-traces-and-ground-planes)
- [Cadence — Mixed Signal PCB Design Guidelines](https://resources.pcb.cadence.com/blog/2022-mixed-signal-pcb-design-guidelines-for-circuit-board-layout)
- [Siemens — Decoupling Capacitor Placement Best Practices](https://blogs.sw.siemens.com/electronic-systems-design/2024/12/19/where-to-put-decoupling-capacitors-on-a-pcb-best-practices-and-design-considerations/)
- [ECS Inc. — Crystal and Oscillator PCB Design Considerations](https://ecsxtal.com/crystal-and-oscillator-printed-circuit-board-design-considerations/)
- [Henry Ott Consultants — Grounding of Mixed-Signal PCBs](https://hott.shielddigitaldesign.com/techtips/split-gnd-plane.html)
- [Sierra Circuits — PCB Design Tips for EMI/EMC](https://www.protoexpress.com/blog/7-pcb-design-tips-solve-emi-emc-issues/)
- [IPC-2221 — Trace Width Calculator (Altium)](https://resources.altium.com/p/ipc-2221-calculator-pcb-trace-current-and-heating)
- [Schemalyzer — 25 PCB Layout Best Practices](https://www.schemalyzer.com/en/blog/pcb-design/best-practices/pcb-layout-best-practices)

---

*PSI Rocketry · PCB Design Knowledge Base · 2026-08-24*
