# TMS A 2 electrical verification and circuit learning guide

Date: 2026-10-14. Author audit: Codex. Status: **installed A 2 schematic; DRAFT, under the owner-approved schematic-stage exception**. No owner engineering or fabrication sign-off.

The installed schematic has 120 physical components,380 pins,59 explicit NCs and 69 intended connected nodes. Every purchased schematic reference has an exact selected-order datasheet association, including configured passive orders supported by manufacturer family tables. Fabricated testpads need no purchased-part datasheet. Coverage does not establish physical fit or measured performance.

Native authority: `tms.kicad_sch`. Companion files: `output/tms-schematic.pdf`, `output/component-verification.pdf`, `output/component-verification.csv`, `output/pin-connections.csv` and `output/external-system-parts.csv`.

## Author-selected assumptions

The owner cannot provide accuracy/bandwidth/load measurements and authorized assumptions. These are requirements for qualification, not measured facts:

- Electronics 12-16.8 V 4S, protected/fused harness; main 5 V planning limit 1 A; protectedVBAT≥11.3 V.
- Board thermal screening 0-50C ambient. Calibrated static accuracy target 1%FS near 20-30C calibration window;50 Hz usable band;1000 SPS/channel. Wider temperature accuracy requires compensation/validation.
- Pressure output resistance≤100 Ohm; normal sensor signals 0-5 V; bridge excitation~5 V retained despite CAS10 V recommendation.
- Ignition load≤2 A at 8.4 V, cold resistance≥4.2 Ohm; dummy-load qualification before any live use. No actual nichrome current or ignition energy is known.
-5 V transient deviation≤0.10 V is a verification target. Capacitor bias/AC curves and efficiency screens are typical/model assumptions, not guaranteed manufacturer limits.

## Findings and dispositions

### F01: Corrected: RF bypass
**Affected: ** C52/U8. 47 pF now implements archived Digi revisionW p52, with 1 uF and 10 uF.
**Remaining action: ** Verify placement and ≤50 mV p-p at the module on the PCB.

### F02: Corrected: unused analog inputs
**Affected: ** U5/U7. Unused ADS1256 AINCOM/AIN2-7 and ADS1220 analog/reference pins 6-10 are explicit NC. CLK3/DGND4/AVSS5 remain GND.
**Remaining action: ** Firmware must select only connected channels; ADS1220 low-side switch/IDAC disabled.

### F03: Selected and calculated: capacitance
**Affected: ** Power and LDO capacitors. Exact KEMET parts/curves are archived. Input 30 uF/output 100 uF nominal banks meet the stated TI equation screen using typical derating models.
**Remaining action: ** Effective capacitance, loop response and temperature still need prototype evidence; simulation curves are not guaranteed limits.

### F04: Corrected: ADC loading
**Affected: ** U5/U10/R46/C44. ADS1256 bufferON replaces bufferOFF. Pressure divider now drives OPA388, then 47 Ohm/10 nF into ADS1220.
**Remaining action: ** BufferON and PGA-bypass configurations are required firmware conditions; verify settling and complete-chain calibration.

### F05: Open qualification: input faults
**Affected: ** D20/D21/D22/D40/D41. The normal contract is correctly wired 0-5 V sensors. TPD2E2U06/BAV199 do not prove sustained battery-miswire or arbitrary off-state protection.
**Remaining action: ** Before powering a prototype with field cables, evaluate actual sequencing/injection and ESD. A 16.8 V bridge-signal fault can exceed the 1k/OPA 10 mA momentary-current screen; it is outside this design contract.

### F06: Selected: reference/ferrite parts
**Affected: ** C32/C34/FB1. Panasonic FT exact capacitance/package/ESR maxima and Murata family specification are archived. C32 footprint corrected to 4x5.8 mm.
**Remaining action: ** OPA350 stability with actual ESR minima, capacitor aging/temperature and ferrite resonance remain PCB/bench qualifications.

### F07: Corrected: switching frequency
**Affected: ** U2. LMR51430YFDDCR FPWM minimum 0.95 MHz exceeds Digi 500 kHz recommendation.
**Remaining action: ** Frequency compliance does not prove RF ripple; measure at U8 during transmit/startup.

### F08: Assumed operating contract: sensors
**Affected: ** BCA-100L/IPSU-GP1K5-6. Retained 5 V bridge excitation; pressure output resistance assumed≤100 Ohm with 133.2k load. Neither assumption adds a manufacturer guarantee.
**Remaining action: ** Calibrate both complete channels.1%FS static target applies near calibration temperature (20-30C proposed), not across the sensor full ambient range.

### F09: Defined: accuracy/bandwidth intent
**Affected: ** Both acquisition channels. Author assumption: 1%FS calibrated static target,50 Hz usable band,1000 SPS per channel. Analog gains at 50 Hz are~0.987 thrust/~0.938 pressure.
**Remaining action: ** Measure sensor+analog+ADC response, independent-clock alignment and dropped samples; static accuracy and AC amplitude are separate.

### F10: Open: physical/current-path qualification
**Affected: ** Connectors/sockets/ignition. Assumed load≤2 A at 8.4 V (cold resistance≥4.2 Ohm); this does not establish actual nichrome current or ignition energy. J5 manufacturer drill mismatch is corrected; J6 is now PCB-mount XT60PW-F.
**Remaining action: ** Resolve purchased AMASS drawing revision, polarity/mating fit, sockets, enclosure, fuse/switch/harness and copper. FullPCB/human review remains open.

### F11: Corrected: unintended EN connection
**Affected: ** J1/D1/U2/R1/R2. Overlapping battery-input and EN wire segments bypassed the enable divider. Separate routed schematic wires now match the intended node groups.
**Remaining action: ** Independent contract compares every physical pin across 69nodes; a deliberate short fault must be rejected.

### F12: Corrected: UART power-off path
**Affected: ** U9/C53/C54/R52-R55. TXU0204 provides specified Ioff/VCC isolation across Teensy3V3 and RF3V3. Idle pulls stop transmit when RF is off.
**Remaining action: ** Check all USB/battery/off/ramp modes; this is common-ground power-off buffering, not galvanic isolation.

### F13: Corrected: supported UART CTS pin
**Affected: ** U1. Radio moved to documented Serial3 TX14/RX15/CTS19/RTS18. Former Serial 2 CTS on D14 was unsupported.
**Remaining action: ** Use Serial3.begin(115200), attachCts(19), attachRts(18). Supported direct CTS avoids XBAR inverted-polarity behavior.

### F14: Corrected: local footprint source lineage
**Affected: ** Five TMS local footprints. All 120 native pin sets match actual footprint pads through the normal shared resolver. Five versioned receipts bind manufacturer evidence, CAD/source hashes, selected orders, derivation notes and every pad function.
**Remaining action: ** Fault tests reject changed CAD/source, wrong part identity, missing pad functions and false owner sign-off. Physical fit and all mandatory human decisions remain open.

### F15: Specified: module silicon revision
**Affected: ** U8. Digi p101 documents an early EFR32MG revisionB brownout/ramp-dip restart failure. RevisionC corrects it; the module label identifies the revision.
**Remaining action: ** Specify/inspect revisionC or later at assembly. The user module silicon revision is unverified; if revisionB must be used, qualify power ramps and complete-powercycle recovery.

### F16: Corrected: connector footprint polarity
**Affected: ** J1/J4/J6. The assigned AMASS footprints mark pad 1 negative and pad 2 positive. A 0/A 1 symbols had these functions reversed; matching pad sets alone did not detect the error.
**Remaining action: ** Corrected schematic positive pin 2/return pin 1, retained component UUIDs, and added a check against actual footprint +/- markings plus the independent electrical node contract. Verify physical molded polarity before assembly.

## 1. Power: switching, regulation and rail margins

Native sheet: `power.kicad_sch`.

Follow J1 to D1, then U2/L1 and the output capacitor bank. D1 conducts for correct battery polarity. U2 switches at 1.1 MHz; L1 stores energy and the capacitors supply the load between switching/feedback corrections. R3/R4 set the regulated voltage, R5 is a loop-test break point, and C3 supplies the floating gate driver between CB and SW. D2 is a bounded transient clamp after the diode.

At12-16.8 V electronics battery input, protected VBAT is assumed≥11.3 V under the 1 A 5 V load. The 511k/105k enable divider gives ample enable voltage; it is not a4S discharge cutoff. External fusing and battery protection are system requirements.

DC calculation: 4.98175 V nominal; conservative feedback/reference/bias corners 4.89337-5.07041 V. With an assumed≤0.10 V transient deviation and≤12 mV analog distribution drop, +5VA screen is 4.78137-5.17041 V. This fits ADS1256 recommended 4.75-5.25 V, and reference screen≤2.58672 V including 0.02% divider corners and 1 mV U6 offset, below 2.6 V. A waveform measurement must confirm these assumptions.

Input 30 uF nominal screens to 8.16 uF at 16.8 V; output 100 uF screens to 54.43 uF at 5 V using typical bias retention and conservative tolerance/temperature/aging/small-signal factors. TI Eq14 needs 42.11 uF for 0-to 1 A,0.95 MHz and 0.10 V. The larger bank was chosen because the smaller bank failed this screen. Loop response is still unverified.

5 V planning budget: 650 mA Teensy/SD/logic/LEDs,100 mA RF branch,47 mA relay,60 mA analog/bridge/buffers =857 mA against 1 A allocation. These are author reserves, not measured maxima. An 85% efficiency thermal screen gives~0.88 W converter loss at 5 W output; actual two-layer copper/ambient must be assessed. U3 at 100 mA dissipates~0.17 W.

+5V branches through FB1 to analog+5VA, and through U3 to RF+3V3_RF. ADC digital supplies and U9 A-port use Teensy+3V3. Both 3.3 V outputs remain separate. Local bypass placement and the real return paths determine noise performance.

### Every component on this sheet

#### C1: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck input switching-current reservoir.
- **Why this value: ** Three 10 uF 50 V X7R 1210 KEMET parts give 30 uF nominal. At16.8 V, screening factors 0.45 bias x 0.90 tolerance x 0.85 temperature x 0.93 aging x 0.85 small-signal factor give 8.16 uF, above TI4.7 uF guidance. Bias/AC curves are typical models, so this is not a guaranteed effective-C limit.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place at VIN/GND; confirm effective C, input RMS current (~0.5 A at 1 A output worst duty) and hot-plug behavior.
- **Every pin: ** 1 = VBAT; 2 = GND

#### C2: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** High-frequency buck VIN bypass.
- **Why this value: ** 100 nF 50 V X7R follows TI input recommendation alongside the bulk bank. It handles faster switching edges with a short VIN/GND loop.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = VBAT; 2 = GND

#### C3: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Bootstrap supply between the floating gate-driver pins.
- **Why this value: ** 100 nF 50 V X7R directly connects CB6 to SW 2, as TI section 9.2.2.7 specifies 0.1 uF rated 16 V or higher. It is not returned toGND.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U2-CB); 2 = Net-(U2-SW)

#### C4: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C5: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C6: 10 uF
- **Selected order: ** `C0805C106K4PACTU`; **footprint: ** `Capacitor_SMD:C_0805_2012Metric`.
- **Purpose: ** Local analog 5 V reservoir after the ferrite.
- **Why this value: ** 10 uF 16 V X5R 0805 exact KEMET order. Provides local load charge; its value is an engineering choice. A ferrite/MLCC network can resonate and must be assessed with the real layout.
- **Sources: ** [C0805C106K4PACTU](https://search.kemet.com/download/specsheet/C0805C106K4PACTU), [FERRITE](https://my.avnet.com/wcm/connect/08e0f7ea-bb4a-4b9a-a867-346f49d03172/Murata-BLM21PG601SN1-Series-EN-Datasheet.pdf?CACHE=NONE&CVID=pfYVfKq&ContentCache=NONE&MOD=AJPERES), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +5VA; 2 = GND

#### C7: 10 uF
- **Selected order: ** `C0805C106K4PACTU`; **footprint: ** `Capacitor_SMD:C_0805_2012Metric`.
- **Purpose: ** LDO input/output bypass and transient reservoir.
- **Why this value: ** 10 uF 16 V X5R 0805 exact order. At5 V a typical 0.45 bias factor with tolerance/temperature/aging/AC screening leaves 2.72 uF; at 3.3 V retention is higher. This clears TLV 755P1 uF input guidance and 0.47 uF effective output minimum in the model.
- **Sources: ** [C0805C106K4PACTU](https://search.kemet.com/download/specsheet/C0805C106K4PACTU), [LDO](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify effective capacitance and RF startup/load steps; local total RF capacitance is below the 200 uF performance recommendation.
- **Every pin: ** 1 = +5V; 2 = GND

#### C8: 10 uF
- **Selected order: ** `C0805C106K4PACTU`; **footprint: ** `Capacitor_SMD:C_0805_2012Metric`.
- **Purpose: ** LDO input/output bypass and transient reservoir.
- **Why this value: ** 10 uF 16 V X5R 0805 exact order. At5 V a typical 0.45 bias factor with tolerance/temperature/aging/AC screening leaves 2.72 uF; at 3.3 V retention is higher. This clears TLV 755P1 uF input guidance and 0.47 uF effective output minimum in the model.
- **Sources: ** [C0805C106K4PACTU](https://search.kemet.com/download/specsheet/C0805C106K4PACTU), [LDO](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify effective capacitance and RF startup/load steps; local total RF capacitance is below the 200 uF performance recommendation.
- **Every pin: ** 1 = +3V3_RF; 2 = GND

#### C11: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck input switching-current reservoir.
- **Why this value: ** Three 10 uF 50 V X7R 1210 KEMET parts give 30 uF nominal. At16.8 V, screening factors 0.45 bias x 0.90 tolerance x 0.85 temperature x 0.93 aging x 0.85 small-signal factor give 8.16 uF, above TI4.7 uF guidance. Bias/AC curves are typical models, so this is not a guaranteed effective-C limit.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place at VIN/GND; confirm effective C, input RMS current (~0.5 A at 1 A output worst duty) and hot-plug behavior.
- **Every pin: ** 1 = VBAT; 2 = GND

#### C12: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck input switching-current reservoir.
- **Why this value: ** Three 10 uF 50 V X7R 1210 KEMET parts give 30 uF nominal. At16.8 V, screening factors 0.45 bias x 0.90 tolerance x 0.85 temperature x 0.93 aging x 0.85 small-signal factor give 8.16 uF, above TI4.7 uF guidance. Bias/AC curves are typical models, so this is not a guaranteed effective-C limit.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place at VIN/GND; confirm effective C, input RMS current (~0.5 A at 1 A output worst duty) and hot-plug behavior.
- **Every pin: ** 1 = VBAT; 2 = GND

#### C13: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C14: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C15: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C16: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C17: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C18: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C19: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### C29: 10 uF
- **Selected order: ** `C1210C106K5RACTU`; **footprint: ** `Capacitor_SMD:C_1210_3225Metric`.
- **Purpose: ** Buck output charge reservoir and ripple filtering.
- **Why this value: ** Ten 10 uF 50 V X7R 1210 parts give 100 uF nominal. Same screening model with 0.90 bias retention at 5 V gives 54.43 uF. TI Eq14 needs 42.11 uF for assumed 0-to 1 A step,0.95 MHz and 0.10 V deviation. Predicted capacitive deviation 77 mV is a screen, not proof of loop stability or settling.
- **Sources: ** [C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify loop/load-step response, total distributed capacitance and actual PCB parasitics; the bank exceeds TI typical table values deliberately.
- **Every pin: ** 1 = +5V; 2 = GND

#### D1: SS54
- **Selected order: ** `SS54`; **footprint: ** `Diode_SMD:D_SMA`.
- **Purpose: ** Blocks reverse battery polarity in normal DC use.
- **Why this value: ** SS54 is a 40 V / 5 A SMA rectifier in the retained MDD sheet. 40 V exceeds 16.8 V DC; transient and thermal margins remain unqualified. P=I*VF.
- **Sources: ** [REVERSE](https://www.lcsc.com/product-detail/C22452.html)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Confirm actual manufacturer; measure input surge, reverse faults and temperature at worst load.
- **Every pin: ** 1 = VBAT; 2 = Net-(D1-A)

#### D2: SMBJ18 A
- **Selected order: ** `SMBJ18A-13-F`; **footprint: ** `Diode_SMD:D_SMB`.
- **Purpose: ** Clamps positive input transients after reverse protection.
- **Why this value: ** Unidirectional SMBJ18A-13-F:18 V stand-off exceeds 16.8 V;29.2 V maximum clamp at 20.5 A specified 10/1000us pulse is below LMR36 V operating/38 V abs max and 50 V capacitors. These pulse conditions do not cover every possible cable surge.
- **Sources: ** [TVS](https://www.diodes.com/datasheet/download/SMBJ5.0(C)A-SMBJ170(C)A.pdf), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Cathode 1 toVBAT, anode 2 GND. External fuse mandatory; verify hot-plug waveform and temperature derating.
- **Every pin: ** 1 = VBAT; 2 = GND

#### FB1: BLM21PG601SN1D
- **Selected order: ** `BLM21PG601SN1D`; **footprint: ** `Inductor_SMD:L_0805_2012Metric`.
- **Purpose: ** Reduces switching-noise coupling into analog 5 V.
- **Why this value: ** BLM21PG601SN1D is 600 Ohm at 100 MHz, not DC. Initial DCRmax 0.14 Ohm gives 8.4 mV at 60 mA;0.20 Ohm post-test bound gives 12 mV. Current rating has ample margin for 60 mA. No ADC noise attenuation is inferred from the 100 MHz rating.
- **Sources: ** [FERRITE](https://my.avnet.com/wcm/connect/08e0f7ea-bb4a-4b9a-a867-346f49d03172/Murata-BLM21PG601SN1-Series-EN-Datasheet.pdf?CACHE=NONE&CVID=pfYVfKq&ContentCache=NONE&MOD=AJPERES), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify actual analog supply noise/resonance and PCB return paths.
- **Every pin: ** 1 = +5V; 2 = +5VA

#### J1: XT30PW-F
- **Selected order: ** `XT30PW-F`; **footprint: ** `Connector_AMASS:AMASS_XT30PW-F_1x02_P2.50mm_Horizontal`.
- **Purpose: ** Electronics 4S / separateignition 2S battery connectors.
- **Why this value: ** XT30PW-F selected drawings/5mmpowerpitch. Input J1return isGND;J4return is IGN_GND. Pad 2 is positive and pad 1 is return, matching the assigned KiCad footprint +/- markings. Connector family 15 A rating exceeds planning currents; mating gender/polarity and inconsistent retention-hole drawings require exact purchased-part fit verification.
- **Sources: ** [XT30](https://www.tme.eu/Document/f383737e340bfdab1f665284174b4ea2/XT30PW-F.pdf)
- **Status: ** Static choice checked; prototype qualification remains. **Verify: ** Do not use genericcatalog dimensions interchangeably with V 1.2; verify harness/polarity and external fuse.
- **Every pin: ** 1 = GND; 2 = Net-(D1-A)

#### L1: 3.3 uH / SRP1038A-3R3M
- **Selected order: ** `SRP1038A-3R3M`; **footprint: ** `TMS:L_SRP1038A`.
- **Purpose: ** Stores switching energy between SW and 5 V.
- **Why this value: ** SRP1038A-3R3M:3.3uH +/-20%,11.8 mOhm maxDCR,Irms 11 A/Isat 20 A at 25C. TI1.1 MHz/5 V table uses 3.3uH. At16.8 V, Lmin 2.64uH/fmin 0.95 MHz gives 1.40 A p-p and 1.70 A peak at 1 A output, below IC min peak limit 3.67 A.
- **Sources: ** [IND](https://www.bourns.com/docs/product-datasheets/srp1038a.pdf), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check hot inductance/loss and switching layout; this physically large inductor favors margin over compactness.
- **Every pin: ** 1 = Net-(U2-SW); 2 = +5V

#### R1: 511 kOhm
- **Selected order: ** `CRCW0603511KFKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Upper enable divider.
- **Why this value: ** 511k with 105k gives EN about 1.93 V at assumed 11.3 V protected input, above 1.36 V max rising threshold. The 1% limits and 200nA EN source current keep startup safely below normal 12 V battery operation. Divider is not a4S battery cutoff.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = VBAT; 2 = Net-(U2-EN)

#### R2: 105 kOhm
- **Selected order: ** `CRCW0603105KFKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Lower enable divider.
- **Why this value: ** 105k completes the 511k/105k divider. Nominal rising threshold 1.227*(1+511/105)=7.20 V before EN source current; normal input 12-16.8 V is comfortably above this. External battery undervoltage protection is required.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U2-EN); 2 = GND

#### R3: 100 kOhm
- **Selected order: ** `TNPW0603100KBEEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Sets the main 5 V feedback ratio.
- **Why this value: ** R3=100k and R4=13.7k, both 0.1%/25 ppm/K. Include R5=49.9 Ohm: VOUT=0.600*(1+100049.9/13700)=4.98175 V. TI0.591-0.609 V reference, resistor tolerances and conservative +/-50nA FB bias give 4.89337-5.07041 V DC.
- **Sources: ** [TNPW](https://www.vishay.com/docs/28758/tnpw_e3.pdf), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify DC voltage at the load and ≤0.10 V transient screen; include distribution drop before accepting ADS1256 supply/reference windows.
- **Every pin: ** 1 = Net-(R3-Pad1); 2 = Net-(U2-FB)

#### R4: 13.7 kOhm
- **Selected order: ** `TNPW060313K7BEEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Sets the main 5 V feedback ratio.
- **Why this value: ** R3=100k and R4=13.7k, both 0.1%/25 ppm/K. Include R5=49.9 Ohm: VOUT=0.600*(1+100049.9/13700)=4.98175 V. TI0.591-0.609 V reference, resistor tolerances and conservative +/-50nA FB bias give 4.89337-5.07041 V DC.
- **Sources: ** [TNPW](https://www.vishay.com/docs/28758/tnpw_e3.pdf), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify DC voltage at the load and ≤0.10 V transient screen; include distribution drop before accepting ADS1256 supply/reference windows.
- **Every pin: ** 1 = Net-(U2-FB); 2 = GND

#### R5: 49.9 Ohm
- **Selected order: ** `CRCW060349R9FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Control-loop injection break point in feedback sensing.
- **Why this value: ** 49.9 Ohm is retained as a small series loop-test resistor. Its DC contribution to the upper feedback leg is included. C9 feed-forward is removed because the new regulator example does not require the old 75 pF network.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +5V; 2 = Net-(R3-Pad1)

#### TP1: VBAT
- **Selected order: ** `VBAT`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Probe protected battery and regulated 5 V.
- **Why this value: ** 2 mm pad is a probing/assembly choice, not an electrical datasheet requirement. TP1 should show protected VBAT; TP2 about 4.981 V unloaded nominal.
- **Sources: ** [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Check probe access/clearance; measure load and startup waveforms without shorting adjacent nodes.
- **Every pin: ** 1 = VBAT

#### TP2: +5V
- **Selected order: ** `+5V`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Probe protected battery and regulated 5 V.
- **Why this value: ** 2 mm pad is a probing/assembly choice, not an electrical datasheet requirement. TP1 should show protected VBAT; TP2 about 4.981 V unloaded nominal.
- **Sources: ** [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Check probe access/clearance; measure load and startup waveforms without shorting adjacent nodes.
- **Every pin: ** 1 = +5V

#### U2: LMR51430YFDDCR
- **Selected order: ** `LMR51430YFDDCR`; **footprint: ** `Package_TO_SOT_SMD:TSOT-23-6`.
- **Purpose: ** Converts protected 4S power to the main 5 V rail.
- **Why this value: ** LMR51430YFDDCR is the 1.1 MHz FPWM DDC6 order. Frequency minimum 0.95 MHz exceeds Digi 500 kHz recommendation; 4.5-36 V operation covers protected 11.3-16.8 V. Board planning limit remains 1 A. Pin 1GND/2SW/3 VIN/4FB/5EN/6CB.
- **Sources: ** [BUCK](https://www.ti.com/lit/ds/symlink/lmr51430.pdf), [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify actual 5 V/load steps and temperature; no 3 A board rating follows from this IC.
- **Every pin: ** 1 = GND; 2 = Net-(U2-SW); 3 = VBAT; 4 = Net-(U2-FB); 5 = Net-(U2-EN); 6 = Net-(U2-CB)

#### U3: TLV75533PDBVR
- **Selected order: ** `TLV75533PDBVR`; **footprint: ** `Package_TO_SOT_SMD:SOT-23-5`.
- **Purpose: ** Provides an independent 3.3 V supply for the XBee.
- **Why this value: ** TLV75533PDBVR is the fixed 3.3 V DBV package. At 100 mA, (4.981-3.3)*0.1 is about 0.168 W. The 500 mA IC rating is not this board's qualified output.
- **Sources: ** [LDO](https://www.ti.com/lit/ds/symlink/tlv755p.pdf), [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check DBV thermal resistance/copper, dropout, inrush, output discharge and RF ripple.
- **Every pin: ** 1 = +5V; 2 = GND; 3 = +5V; 5 = +3V3_RF; 4 = NC

## 2. Controller: timing, logging and supported pins

Native sheet: `controller.kicad_sch`.

Teensy 4.1 owns its MCU support circuits, clock, regulator and microSD socket. The board needs removable socket rows and local VIN reservoir, not duplicate bare-MCU circuitry. Module pad names are an explicit local convention mapped to the PJRC card.

Thrust uses SPI0 D11MOSI/D12MISO/D13SCLK, CS10 and DRDY9. Pressure uses SPI1 D26MOSI/D1MISO/D27SCLK, CS0 and DRDY2. Independent DRDY timestamps are required because the ADC clocks differ. The 1kSPS target is not a claim of zero dropped samples.

Radio uses Serial3: TX14/RX15/CTS19 and RTS18. PJRC explicitly supports pin 19 as Serial3 CTS and any digital pin for RTS. Use Serial3.begin(115200), then attachCts(19) and attachRts(18). CTS high pauses transmit. UART payload at 60frames/s x 32bytes x 10bits is 19.2kbit/s before protocol overhead, below 115.2kbit/s; RF airtime/retries and SD stalls still require testing.

JP1 connects battery 5 V to VIN. For simultaneous USB/battery, remove JP1 or cut the Teensy VIN-VUSB link per PJRC. U9 prevents direct UART drive into an unpowered RF module. USB alone leaves the analog ADC rails off, so acquisition must wait for valid analog power.

D3 controls the relay driver and must start low. D4/D5/D6 drive 1k LED resistors. Approximate currents 1.4/1.55/1.45 mA use typical LED forward voltage; real brightness and GPIO VOH vary. The red LED means commanded state. There is no physical ARM feedback.

### Every component on this sheet

#### C10: 10 uF
- **Selected order: ** `C0805C106K4PACTU`; **footprint: ** `Capacitor_SMD:C_0805_2012Metric`.
- **Purpose: ** Local Teensy VIN reservoir.
- **Why this value: ** 10 uF 16 V X5R 0805 is an added board-level reservoir near the module VIN. Module-owned regulation/decoupling remains on Teensy; the exact 10 uF value is an engineering transient choice.
- **Sources: ** [C0805C106K4PACTU](https://search.kemet.com/download/specsheet/C0805C106K4PACTU), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Teensy controller/TEENSY_VIN; 2 = GND

#### D10: GREEN
- **Selected order: ** `APTD1608LCGCK`; **footprint: ** `LED_SMD:LED_0603_1608Metric`.
- **Purpose: ** Green status indication.
- **Why this value: ** APTD1608LCGCK is a low-current 0603 green LED characterized at 2 mA. Selected current is lower, so datasheet brightness at 2 mA is not guaranteed here.
- **Sources: ** [GREEN](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LCGCK.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Confirm polarity, visibility in sunlight, thermal and mechanical assembly.
- **Every pin: ** 1 = GND; 2 = Net-(D10-A)

#### D11: RED
- **Selected order: ** `APTD1608LSURCK`; **footprint: ** `LED_SMD:LED_0603_1608Metric`.
- **Purpose: ** Red command indication.
- **Why this value: ** APTD1608LSURCK low-current red matches the approximately 1.55 mA design. No physical ARM feedback exists in this circuit.
- **Sources: ** [RED](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LSURCK.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Confirm polarity and firmware meaning; mark user interface accordingly.
- **Every pin: ** 1 = GND; 2 = Net-(D11-A)

#### D12: YELLOW
- **Selected order: ** `APTD1608LSYCK`; **footprint: ** `LED_SMD:LED_0603_1608Metric`.
- **Purpose: ** Yellow telemetry activity indication.
- **Why this value: ** APTD1608LSYCK low-current yellow matches approximately 1.45 mA design. Duty cycle is firmware-controlled.
- **Sources: ** [YELLOW](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LSYCK.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Confirm polarity and visible duty cycle.
- **Every pin: ** 1 = GND; 2 = Net-(D12-A)

#### JP1: VIN POWER LINK
- **Selected order: ** `TSW-102-07-L-S`; **footprint: ** `Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical`.
- **Purpose: ** Removable battery feed to Teensy VIN.
- **Why this value: ** Samtec TSW-102-07-L-S is a real 2-pin 2.54 mm header. A separate conductive shunt is an assembly item. Remove shunt for simultaneous USB/battery unless Teensy VIN-VUSB link is cut. This is a configuration choice, not automatic power arbitration.
- **Sources: ** [SHUNT_HEADER](https://suddendocs.samtec.com/catalog_english/tsw_th.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify mating shunt rating and the chosen USB configuration.
- **Every pin: ** 1 = +5V; 2 = Teensy controller/TEENSY_VIN

#### R10: 1 kOhm
- **Selected order: ** `CRCW06031K00FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Limits green LED/GPIO current.
- **Why this value: ** 1 kOhm gives about (3.3-1.9)/1000=1.4 mA using the LED's typical VF at 2 mA; actual current uses GPIO VOH and LED curve.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [GREEN](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LCGCK.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check visibility and worst GPIO current, VF and resistor tolerance; approximate dissipation is 2 mW.
- **Every pin: ** 1 = Net-(U1-D4_{slash}_STATUS); 2 = Net-(D10-A)

#### R11: 1 kOhm
- **Selected order: ** `CRCW06031K00FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Limits red LED/GPIO current.
- **Why this value: ** 1 kOhm gives about (3.3-1.75)/1000=1.55 mA with typical VF. Red indicates commanded state, not measured ARM or contact state.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [RED](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LSURCK.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify brightness and GPIO limits; do not treat the LED as a physical inhibit indication.
- **Every pin: ** 1 = Net-(U1-D5_{slash}_COMMAND); 2 = Net-(D11-A)

#### R12: 1 kOhm
- **Selected order: ** `CRCW06031K00FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Limits yellow LED/GPIO current.
- **Why this value: ** 1 kOhm gives about (3.3-1.85)/1000=1.45 mA with typical VF. Low-current LED is chosen for visibility without large GPIO load.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [YELLOW](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LSYCK.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check actual current and behavior while transmitting; select exact resistor.
- **Every pin: ** 1 = Net-(U1-D6_{slash}_TX_LED); 2 = Net-(D12-A)

#### TP3: +3V3
- **Selected order: ** `+3V3`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Probe Teensy-derived ADC logic supply.
- **Why this value: ** 2 mm pad exposes +3V3. This rail is separate from +3V3_RF; its ADC/pull-up allocation is less than 10 mA, to be measured.
- **Sources: ** [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Verify no two regulator outputs are joined and analog/digital sequencing remains within input limits.
- **Every pin: ** 1 = +3V3

#### U1: TEENSY41
- **Selected order: ** `TEENSY41`; **footprint: ** `TMS:Teensy41_Socket`.
- **Purpose: ** Acquisition, SD logging, telemetry and command processor.
- **Why this value: ** Owner-selected Teensy 4.1. SPI0 D11/D12/D13, CS10/DRDY9; SPI1 D26/D1/D27, CS0/DRDY2. Radio uses documented Serial3 TX14/RX15/CTS19, RTS18. Serial 2 CTS on formerD14 was unsupported and is corrected. All I/O3.3 V.
- **Sources: ** [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Use Serial3.begin(115200), attachCts(19), attachRts(18); verify buffers, timing, SD peaks and reset defaults. Official UART page is cited separately.
- **Every pin: ** 3V3L = +3V3; 3V3R = +3V3; D0 = P_CS_N; D1 = P_MISO; D10 = LC_CS_N; D11 = LC_MOSI; D12 = LC_MISO; D13 = LC_SCK; D14 = XB_TX; D15 = XB_RX; D18 = XB_RTS_N; D19 = XB_CTS_N; D2 = P_DRDY_N; D26 = P_MOSI; D27 = P_SCK; D3 = FIRE_CMD; D4 = Net-(U1-D4_{slash}_STATUS); D5 = Net-(U1-D5_{slash}_COMMAND); D6 = Net-(U1-D6_{slash}_TX_LED); D9 = LC_DRDY_N; GNDA = GND; GNDL = GND; GNDR = GND; VIN = Teensy controller/TEENSY_VIN; D16 = NC; D17 = NC; D8 = NC; D7 = NC; D20 = NC; D21 = NC; D22 = NC; D23 = NC; D24 = NC; D25 = NC; D28 = NC; D29 = NC; D30 = NC; D31 = NC; D32 = NC; D33 = NC; D34 = NC; D35 = NC; D36 = NC; D37 = NC; D38 = NC; D39 = NC; D40 = NC; D41 = NC

## 3. Thrust: bridge, filtering and buffered conversion

Native sheet: `thrust.kicad_sch`.

BCA-100L is the confirmed 100 kgf,2 mV/V +/-10% sensor. At~5 V excitation, nominal full-load signal is~10 mV. CAS recommends 10 V; retained 5 V halves signal amplitude, so datasheet noise/accuracy cannot simply be assumed unchanged. Input/output resistances are 400 Ohm +/-20 Ohm and 350 Ohm +/-3.5 Ohm. Two-point calibration is required.

J2 carries excitation, signal pair and shield. R20/R21 and C20 form a differential low-pass: 1/[2pi(1k+1k+350)220 nF] ~=308 Hz. OPA2388 unity followers avoid loading the bridge. Offset max 7.5uV per amplifier gives 15uV worst differential (~0.15% of 10 mVFS) before calibration; input/clamp leakage and temperature must also be budgeted.

Each OPA output drives a47 Ohm series resistor and 10 nF differential local reservoir at U5. Required firmware setting is ADS1256 bufferON. At1000 SPS, typical 20MOhm differential input impedance gives~4.7 ppm resistive loading from 94 Ohm; the former bufferOFF/PGA 64 typical 4.7 kOhm model gave~1.96% loss. Switched-capacitor settling still needs validation.

Use AIN0-AIN1, PGA 64,1000 SPS and 7.68 MHz. Differential full scale is +/-2 VREF/64 ~=+/-77.8 mV, so the bridge fits with ample overload headroom. Buffer common mode must remain between 0 V and AVDD-2 V; normal bridge common mode nearVEXC/2 fits the screened supply window.

Y1 exact order is ABLS-7.680MHZ-D-4-Y-T with 18 pF load. Two 30 pF capacitors give 15 pF in series; assumed 3 pF parasitic yields 18 pF. Verify frequency, cold/hot startup and drive on the real PCB.

The protection network is coarse cable ESD/rail steering. BAV199 VF can exceed an IC rail-overdrive limit. Normal correctly wired sensor operation is the contract; sustained battery-to-signal faults and off-state injection remain explicit prototype checks.

### Every component on this sheet

#### C20: 220 nF
- **Selected order: ** `C0603C224K4RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Differential bridge low-pass capacitor.
- **Why this value: ** 220 nF 16 V X7R 0603 exact KEMET order. With 1k+1k+350 Ohm sensor source, nominal pole 307.84 Hz. Differential DC is near 10 mV, so high common-mode voltage is not applied across this capacitor. Dielectric/tolerance/AC variation still affect the pole.
- **Sources: ** [C0603C224K4RACTU](https://search.kemet.com/download/specsheet/C0603C224K4RACTU), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(C20-Pad1); 2 = Net-(C20-Pad2)

#### C21: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Local dual-buffer supply bypass.
- **Why this value: ** 100 nF matches OPAx388 power-supply guidance and serves the shared supply pins of both channels. It must be near pin 8/pin 4 physically.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify effective capacitance and short return path; additional bulk depends on distribution impedance.
- **Every pin: ** 1 = +5VA; 2 = GND

#### C22: 10 nF
- **Selected order: ** `VJ0603A103JXACW1BC`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Local differential reservoir across thrust ADC inputs.
- **Why this value: ** 10 nF 50 V C0G 5%0603 actual Vishay order. With 47+47 Ohm, nominal pole 169 kHz; upstream 220 nF network sets the intentional low-frequency analog pole.
- **Sources: ** [VJ](https://www.vishay.com/docs/28548/vjw1bcbascomseries.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U5-AIN0); 2 = Net-(U5-AIN1)

#### C23: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** ADS1256 analog high-frequency supply bypass.
- **Why this value: ** 100 nF ceramic at AVDD1 follows TI Fig. 25 / bypass guidance, with C27 bulk in parallel.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place at pin 1-to-AGND2 with low loop inductance.
- **Every pin: ** 1 = +5VA; 2 = GND

#### C24: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** ADS1256 digital high-frequency bypass.
- **Why this value: ** 100 nF ceramic at DVDD16 follows TI Fig.25 / bypass guidance. RESET15 is not a supply pin.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place at pin 16-to-DGND17; preserve the pin mapping independently of ERC.
- **Every pin: ** 1 = +3V3; 2 = GND

#### C25: 30 pF
- **Selected order: ** `C0603C300J5GACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Crystal load capacitors.
- **Why this value: ** Two 30 pF C0G capacitors yield C1*C2/(C1+C2)+Cstray=15 pF+3 pF=18 pF. 3 pF total parasitic is an assumption, not a measured fact.
- **Sources: ** [C0603C300J5GACTU](https://search.kemet.com/download/specsheet/C0603C300J5GACTU), [XTAL](https://abracon.com/Resonators/ABLS.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Measure frequency/startup with a low-capacitance technique; adjust only after evaluating real parasitics and drive.
- **Every pin: ** 1 = Net-(U5-XTAL1_{slash}_CLKIN); 2 = GND

#### C26: 30 pF
- **Selected order: ** `C0603C300J5GACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Crystal load capacitors.
- **Why this value: ** Two 30 pF C0G capacitors yield C1*C2/(C1+C2)+Cstray=15 pF+3 pF=18 pF. 3 pF total parasitic is an assumption, not a measured fact.
- **Sources: ** [C0603C300J5GACTU](https://search.kemet.com/download/specsheet/C0603C300J5GACTU), [XTAL](https://abracon.com/Resonators/ABLS.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Measure frequency/startup with a low-capacitance technique; adjust only after evaluating real parasitics and drive.
- **Every pin: ** 1 = Net-(U5-XTAL2); 2 = GND

#### C27: 10 uF
- **Selected order: ** `C0805C106K4PACTU`; **footprint: ** `Capacitor_SMD:C_0805_2012Metric`.
- **Purpose: ** Thrust ADC analog bulk bypass.
- **Why this value: ** 10 uF 16 V X5R 0805 complements the 100 nF supply bypass in TI basic connection circuit. Exact bias behavior is archived; nominal 10 uF is not claimed to remain 10 uF in operation.
- **Sources: ** [C0805C106K4PACTU](https://search.kemet.com/download/specsheet/C0805C106K4PACTU), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +5VA; 2 = GND

#### C28: 1 uF
- **Selected order: ** `C0603C105K4RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Thrust ADC digital reservoir.
- **Why this value: ** 1 uF 16 V X7R 0603 is an engineering addition to 100 nF DVDD bypass. It does not replace C24 at DVDD16.
- **Sources: ** [C0603C105K4RACTU](https://search.kemet.com/download/specsheet/C0603C105K4RACTU), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +3V3; 2 = GND

#### D20: TPD2E2U06DCKR
- **Selected order: ** `TPD2E2U06DCKR`; **footprint: ** `Package_TO_SOT_SMD:SOT-323_SC-70`.
- **Purpose: ** Coarse cable ESD suppression on the bridge pair.
- **Why this value: ** TPD2E2U06DCKR is the actual 3-pin SC70 part: IO1=1, IO2=2, GND=3. Its low capacitance/leakage suit signals, but transient clamp voltage is above precision-ADC rail limits.
- **Sources: ** [ESD](https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Coordinate with series R and rail clamps; test cable ESD. Not sustained miswire or precise input overvoltage protection.
- **Every pin: ** 1 = Thrust acquisition/LC_RAW_0; 2 = Thrust acquisition/LC_RAW_1; 3 = GND

#### D21: BAV199
- **Selected order: ** `BAV199`; **footprint: ** `Package_TO_SOT_SMD:SOT-23`.
- **Purpose: ** Low-leakage steering diodes to analog rails.
- **Why this value: ** BAV199 steering pair: pin 1 anode toGND,pin 2 cathode to+5VA,pin 3 midpoint tosignal. Maxreverseleakage 5nA at 25C/80nA at 150C, VR75 V; maxVF0.9 V at 1 mA exceeds ADC rail-overdrive limits. It is not a guaranteed sustained-fault clamp.
- **Sources: ** [CLAMP](https://assets.nexperia.com/documents/data-sheet/BAV199.pdf), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Normal 0-5 V sensor harness only. Qualify cable ESD, powered/off-state injection and sustainedmiswire separately; do not infer absolute-max protection from current alone.
- **Every pin: ** 1 = GND; 2 = +5VA; 3 = Net-(C20-Pad1)

#### D22: BAV199
- **Selected order: ** `BAV199`; **footprint: ** `Package_TO_SOT_SMD:SOT-23`.
- **Purpose: ** Low-leakage steering diodes to analog rails.
- **Why this value: ** BAV199 steering pair: pin 1 anode toGND,pin 2 cathode to+5VA,pin 3 midpoint tosignal. Maxreverseleakage 5nA at 25C/80nA at 150C, VR75 V; maxVF0.9 V at 1 mA exceeds ADC rail-overdrive limits. It is not a guaranteed sustained-fault clamp.
- **Sources: ** [CLAMP](https://assets.nexperia.com/documents/data-sheet/BAV199.pdf), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Normal 0-5 V sensor harness only. Qualify cable ESD, powered/off-state injection and sustainedmiswire separately; do not infer absolute-max protection from current alone.
- **Every pin: ** 1 = GND; 2 = +5VA; 3 = Net-(C20-Pad2)

#### J2: B5B-XH-A
- **Selected order: ** `B5B-XH-A`; **footprint: ** `Connector_JST:JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical`.
- **Purpose: ** Load-cell excitation, signal pair and shield connector.
- **Why this value: ** B5B-XH-A provides five defined harness contacts. CAS may supply four or six conductors plus shield; external remote-sense termination must be defined.
- **Sources: ** [JST](https://www.jst-mfg.com/product/pdf/eng/eXH.pdf), [BRIDGE](https://www.cas-usa.com/cdn/shop/files/BCA.pdf?v=10610127605685568819)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify wire colours against the actual unit, remote-sense handling, shield/earth policy and 1:1 fit.
- **Every pin: ** 1 = +5VA; 2 = GND; 3 = Thrust acquisition/LC_RAW_0; 4 = Thrust acquisition/LC_RAW_1; 5 = GND

#### R20: 1 kOhm
- **Selected order: ** `CRCW06031K00FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Limit fault current and form differential input low-pass filter.
- **Why this value: ** Each 1 kOhm plus 220 nF differential C20 and about 350 Ohm bridge output gives fc=1/[2*pi*(2000+350)*220n]=307.8 Hz. Values are engineering choices, not CAS/TI required values.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [BRIDGE](https://www.cas-usa.com/cdn/shop/files/BCA.pdf?v=10610127605685568819), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** 1k normal-signal filter choice. A 16.8 V-to-signal miswire can exceed OPA 10 mA momentary input limit; excluded from verified operating contract and remains an open fault-qualification finding.
- **Every pin: ** 1 = Thrust acquisition/LC_RAW_0; 2 = Net-(C20-Pad1)

#### R21: 1 kOhm
- **Selected order: ** `CRCW06031K00FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Limit fault current and form differential input low-pass filter.
- **Why this value: ** Each 1 kOhm plus 220 nF differential C20 and about 350 Ohm bridge output gives fc=1/[2*pi*(2000+350)*220n]=307.8 Hz. Values are engineering choices, not CAS/TI required values.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [BRIDGE](https://www.cas-usa.com/cdn/shop/files/BCA.pdf?v=10610127605685568819), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** 1k normal-signal filter choice. A 16.8 V-to-signal miswire can exceed OPA 10 mA momentary input limit; excluded from verified operating contract and remains an open fault-qualification finding.
- **Every pin: ** 1 = Thrust acquisition/LC_RAW_1; 2 = Net-(C20-Pad2)

#### R22: 47 Ohm
- **Selected order: ** `CRCW060347R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Isolates buffer outputs from differential ADC charge pulses.
- **Why this value: ** 47 Ohm per leg follows TI-style local ADC drive damping. With 10 nF differential C22, the nominal additional pole is 169 kHz. ADS1256 bufferON avoids the old bufferOFF4.7 kOhm typical loading (~1.96% attenuation).
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U4-OUT_A); 2 = Net-(U5-AIN0)

#### R23: 47 Ohm
- **Selected order: ** `CRCW060347R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Isolates buffer outputs from differential ADC charge pulses.
- **Why this value: ** 47 Ohm per leg follows TI-style local ADC drive damping. With 10 nF differential C22, the nominal additional pole is 169 kHz. ADS1256 bufferON avoids the old bufferOFF4.7 kOhm typical loading (~1.96% attenuation).
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U4-OUT_B); 2 = Net-(U5-AIN1)

#### R24: 33 Ohm
- **Selected order: ** `CRCW060333R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Damp SPI edge ringing on SCLK, DIN and DOUT.
- **Why this value: ** 33 Ohm is a provisional series damping value. TI ADS1256 discusses small series resistors around 100 Ohm; 33 Ohm must be justified with actual driver/trace impedance and timing.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check source-end placement for each direction and scope edges at ≤1.92 MHz. These resistors are not 5 V fault protection.
- **Every pin: ** 1 = Net-(U5-SCLK); 2 = LC_SCK

#### R25: 33 Ohm
- **Selected order: ** `CRCW060333R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Damp SPI edge ringing on SCLK, DIN and DOUT.
- **Why this value: ** 33 Ohm is a provisional series damping value. TI ADS1256 discusses small series resistors around 100 Ohm; 33 Ohm must be justified with actual driver/trace impedance and timing.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check source-end placement for each direction and scope edges at ≤1.92 MHz. These resistors are not 5 V fault protection.
- **Every pin: ** 1 = Net-(U5-DIN); 2 = LC_MOSI

#### R26: 33 Ohm
- **Selected order: ** `CRCW060333R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Damp SPI edge ringing on SCLK, DIN and DOUT.
- **Why this value: ** 33 Ohm is a provisional series damping value. TI ADS1256 discusses small series resistors around 100 Ohm; 33 Ohm must be justified with actual driver/trace impedance and timing.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check source-end placement for each direction and scope edges at ≤1.92 MHz. These resistors are not 5 V fault protection.
- **Every pin: ** 1 = Net-(U5-DOUT); 2 = LC_MISO

#### R27: 10 kOhm
- **Selected order: ** `CRCW060310K0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Keeps thrust ADC deselected while MCU is high impedance.
- **Why this value: ** 10 kOhm pulls CS to DVDD. ADS1256 input leakage can be up to 10 uA; 0.1 V drop leaves about 3.2 V, above 0.8*3.3=2.64 V VIH in this simple static check.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Confirm all rail/firmware states and MCU-low sink current (~0.33 mA).
- **Every pin: ** 1 = +3V3; 2 = LC_CS_N

#### TP4: LC_DRDY_N
- **Selected order: ** `LC_DRDY_N`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Probe thrust DRDY timing.
- **Why this value: ** 2 mm pad on DRDY allows conversion-period and timestamp checks. Nominal 1000 SPS means ~1 ms periods, not guaranteed sample alignment with the other ADC.
- **Sources: ** [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Check probe loading and firmware missed-sample accounting.
- **Every pin: ** 1 = LC_DRDY_N

#### U4: OPA2388IDR
- **Selected order: ** `OPA2388IDR`; **footprint: ** `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`.
- **Purpose: ** Two unity buffers separate bridge impedance from ADC switched input.
- **Why this value: ** OPA2388 works on +5VA and accepts approximately mid-supply common-mode signals. With output-to-inverting-input feedback each channel has nominal gain 1. Offset mismatch remains differential error.
- **Sources: ** [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check +5VA 2.5-5.5 V range, noise/offset drift, output settling and capacitive-load stability with R22/R23/C22.
- **Every pin: ** 1 = Net-(U4-OUT_A); 2 = Net-(U4-OUT_A); 3 = Net-(C20-Pad1); 4 = GND; 5 = Net-(C20-Pad2); 6 = Net-(U4-OUT_B); 7 = Net-(U4-OUT_B); 8 = +5VA

#### U5: ADS1256IDBR
- **Selected order: ** `ADS1256IDBR`; **footprint: ** `Package_SO:SSOP-28_5.3x10.2mm_P0.65mm`.
- **Purpose: ** Differential thrust conversion.
- **Why this value: ** ADS1256IDBR: AVDD1/DVDD16/RESET15. Use AIN0-AIN1, gain 64, bufferON,1000 SPS and 7.68 MHz. BufferON typical input impedance 20MOhm at 1000 SPS reduces 94 Ohm resistive loading to 4.7 ppm; this estimate is not a guaranteed switched-capacitor model. Unused analog pins 5/8-13 are NC.
- **Sources: ** [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify input common-mode below AVDD-2 V, calibration, noise and timing. ADC bufferON is a required firmware condition.
- **Every pin: ** 1 = +5VA; 14 = +3V3; 15 = +3V3; 16 = +3V3; 17 = GND; 18 = Net-(U5-XTAL2); 19 = Net-(U5-XTAL1_{slash}_CLKIN); 2 = GND; 20 = LC_CS_N; 21 = LC_DRDY_N; 22 = Net-(U5-DOUT); 23 = Net-(U5-DIN); 24 = Net-(U5-SCLK); 3 = GND; 4 = Ratiometric reference/LC_VREF; 6 = Net-(U5-AIN0); 7 = Net-(U5-AIN1); 5 = NC; 8 = NC; 9 = NC; 10 = NC; 11 = NC; 12 = NC; 13 = NC; 25 = NC; 26 = NC; 27 = NC; 28 = NC

#### Y1: 7.680 MHz / CL 18 pF
- **Selected order: ** `ABLS-7.680MHZ-D-4-Y-T`; **footprint: ** `Crystal:Crystal_SMD_HC49-SD`.
- **Purpose: ** Sets ADS1256 conversion and serial timing.
- **Why this value: ** ABLS-7.680MHZ-D-4-Y-T uses standard 18 pF load. 7.68 MHz matches TI data-rate tables. Family sheet alone is not proof of received exact order.
- **Sources: ** [XTAL](https://abracon.com/Resonators/ABLS.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Confirm exact order, drive level, ESR, cold/hot startup and frequency. Datasheet rated drive typical 100 uW/max 1000 uW.
- **Every pin: ** 1 = Net-(U5-XTAL1_{slash}_CLKIN); 2 = Net-(U5-XTAL2)

## 4. Reference: why ratiometry works

Native sheet: `reference.kicad_sch`.

R30/R31 divide the actual analog excitation supply by two. Since both bridge output and ADC reference scale with excitation, slow excitation changes largely cancel in the digitized ratio. This cancellation depends on matched time response and return paths; it does not remove all switching noise.

Both 10k parts are actual TNPU0.02%/2 ppm/K orders. Independent tolerance corners give ratios 0.4999-0.5001. They are separate resistors, not a specified matched network. Initial ratio and amplifier offset are calibrated; temperature/aging remain in the budget.

R32=10k and C30=1 uF filter the divider before U6. Divider source resistance 5k adds to R32, giving nominal 15ms. Start with≥150ms after rails settle, then run ADC calibration and verify actual settling. Capacitance tolerance/bias means nominal time constant is not a guarantee.

OPA350 buffers the divider for ADS1256 reference current. A bare divider cannot be treated as a low-impedance precision source. The 147 uF aluminum bank plus 100 nF follows TI Fig 26. Panasonic FT exact ESR maxima/package sizes are now known; minimum ESR and closed-loop stability across real parts/temperature still require qualification. Place the bank at U5 reference pins.

The conservative high-rail/ratio/offset screen givesVREF≤2.58672 V against the ADS1256 limit 2.6 V. This depends on the≤0.10 V supply-transient assumption. Validate it with the complete load and layout.

### Every component on this sheet

#### C30: 1 uF
- **Selected order: ** `C0603C105K4RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Reference-divider low-pass reservoir.
- **Why this value: ** 1 uF 16 V X7R 0603 exact order. With 10k R32 and 5k divider source, nominal tau 15ms; initial ≥150ms wait is a screening choice, then wait for stable rails/calibration.
- **Sources: ** [C0603C105K4RACTU](https://search.kemet.com/download/specsheet/C0603C105K4RACTU), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U6-+); 2 = GND

#### C31: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Local reference-buffer supply bypass.
- **Why this value: ** 100 nF is used in ADS1256 Fig.26 and OPA350 layout guidance. OPA350 earlier overview mentions 10 nF; this application follows the specific reference circuit and 0.1 uF layout guidance.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place at U6 pin 7-to-pin 4 with a short ground return.
- **Every pin: ** 1 = +5VA; 2 = GND

#### C32: 47 uF / 16 V AL
- **Selected order: ** `EEEFT1C470AR`; **footprint: ** `Capacitor_SMD:CP_Elec_4x5.8`.
- **Purpose: ** Low-frequency reference output reservoir.
- **Why this value: ** Panasonic EEEFT1C470AR:47 uF 16 V,+/-20%,4x5.8 mm. Corrects the old provisional 5 mm footprint. MaxESR0.85 Ohm at 100 kHz 20C, ripple 160 mA;105C/2000h rating. TI Fig 26 uses 47 uF aluminum here.
- **Sources: ** [FT](https://industrial.panasonic.com/cdbs/www-data/pdf/RDE0000/ABA0000C1240.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Actual minimum ESR, layout and op-amp loop response remain prototype checks.
- **Every pin: ** 1 = Ratiometric reference/LC_VREF; 2 = GND

#### C33: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** High-frequency reference output bypass.
- **Why this value: ** 100 nF ceramic follows TI Fig.26, handling faster reference charge pulses alongside the electrolytics.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place near VREFP/VREFN; check return path and bank stability.
- **Every pin: ** 1 = Ratiometric reference/LC_VREF; 2 = GND

#### C34: 100 uF / 16 V AL
- **Selected order: ** `EEEFT1C101AR`; **footprint: ** `Capacitor_SMD:CP_Elec_5x5.8`.
- **Purpose: ** Reference output reservoir alongside 47 uF/100 nF.
- **Why this value: ** Panasonic EEEFT1C101AR:100 uF 16 V,+/-20%,5x5.8 mm. MaxESR0.36 Ohm at 100 kHz 20C,ripple 240 mA;105C/2000h. Follows TI Fig 26 aluminum-capacitor topology.
- **Sources: ** [FT](https://industrial.panasonic.com/cdbs/www-data/pdf/RDE0000/ABA0000C1240.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check reference settling and stability across temperature; no ceramic substitution is authorized by matching capacitance alone.
- **Every pin: ** 1 = Ratiometric reference/LC_VREF; 2 = GND

#### R30: 10 kOhm
- **Selected order: ** `TNPU060310K0HWEA00`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Precision half-excitation reference divider.
- **Why this value: ** Both 10k TNPU060310K0HWEA00:0.02%,2 ppm/K. Nominal ratio 0.5. Independent tolerance corners give 0.4999-0.5001; worst ratio drift 2 ppm/K (not guaranteed matching). Dissipation~0.62mW each is small versus 0.1 W 70C rating.
- **Sources: ** [TNPU](https://www.vishay.com/docs/28779/tnpue3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Two-point calibration absorbs initial scale; budget temperature, aging and U6 offset separately.
- **Every pin: ** 1 = +5VA; 2 = Net-(R30-Pad2)

#### R31: 10 kOhm
- **Selected order: ** `TNPU060310K0HWEA00`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Precision half-excitation reference divider.
- **Why this value: ** Both 10k TNPU060310K0HWEA00:0.02%,2 ppm/K. Nominal ratio 0.5. Independent tolerance corners give 0.4999-0.5001; worst ratio drift 2 ppm/K (not guaranteed matching). Dissipation~0.62mW each is small versus 0.1 W 70C rating.
- **Sources: ** [TNPU](https://www.vishay.com/docs/28779/tnpue3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Two-point calibration absorbs initial scale; budget temperature, aging and U6 offset separately.
- **Every pin: ** 1 = Net-(R30-Pad2); 2 = GND

#### R32: 10 kOhm
- **Selected order: ** `CRCW060310K0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Filters divider noise and isolates reference-buffer input.
- **Why this value: ** 10 kOhm copies the series reference-filter resistor in TI Fig.26. With divider source 5k and C30=1 uF, tau=15 ms.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Include U6 input bias/leakage error and validate settling; do not use an ideal zero-impedance source model.
- **Every pin: ** 1 = Net-(R30-Pad2); 2 = Net-(U6-+)

#### TP5: LC_VREF
- **Selected order: ** `LC_VREF`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Probe the ADC reference source.
- **Why this value: ** 2 mm pad exposes nominalVEXC/2 (~2.49 V). A low-bandwidth DMM check does not establish dynamic reference cleanliness.
- **Sources: ** [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf), [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Measure DC ratio, settling and ripple using high-impedance/low-capacitance probes.
- **Every pin: ** 1 = Ratiometric reference/LC_VREF

#### U6: OPA350UA
- **Selected order: ** `OPA350UA`; **footprint: ** `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`.
- **Purpose: ** Buffers divided excitation for the ADC reference input.
- **Why this value: ** OPA350UA follows the ADS1256 recommended reference-buffer topology. A bare divider would load into typical 18.5 kOhm reference impedance; output-to-inverting-input feedback gives nominal unity gain.
- **Sources: ** [REF](https://www.ti.com/lit/ds/symlink/opa350.pdf), [ADC1](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check offset, input bias, +5VA supply, temperature grade, output-bank ESR/stability and startup.
- **Every pin: ** 2 = Ratiometric reference/LC_VREF; 3 = Net-(U6-+); 4 = GND; 6 = Ratiometric reference/LC_VREF; 7 = +5VA; 1 = NC; 5 = NC; 8 = NC

## 5. Pressure: scaling and low-impedance ADC drive

Native sheet: `pressure.kicad_sch`.

The confirmed IPSU-GP1K5-6 is 0-1500 psi,0-5 V and 9-32 V supply. It runs from protected 4S VBAT, not 5 V. Board J3 is supply/signal/return; sensor DIN is supply/return/signal, so the harness deliberately maps 1/3/2. The sensor 32 V supply rating does not enlarge the board input rating.

100k/33.2k0.1% divider gives 0.249249 ratio and 1.246246 V for 5 V. It draws 37.54uA from the sensor. Output resistance is unspecified; assumed≤100 Ohm adds≤0.075% scale loss. C40=47 nF C0G 1206 with 24.925k source gives 135.86 Hz nominal pole.

OPA388 U10 buffers this filtered high-impedance node. Max 400pA input bias over 0-85C gives<10uV source error. The output drives 47 Ohm/10 nF at U7, providing ADC charge locally. Without U10, the ADS1220 datasheet provides only typical analog input-current behavior, so a guaranteed high-source-resistance loading calculation was unavailable.

ADS1220 gain 1/PGA bypass allows AIN0-to-AVSS operation. Use internal 2.048 V reference and normal 1000 SPS; IDAC/low-side switch OFF. The signal uses 60.85% of positive ADC range. Separate 100 nF capacitors bypass AVDD12 and DVDD13. CLK3/DGND4/AVSS5 are grounded; unused 6-10 are NC.

Pressure sensor nonlinearity/hysteresis is<0.25%FS BFSL, setting errors<0.5%FS, thermal zero shift<0.04%FS/C and span shift<0.015%/C. The internal ADC reference maxdrift 30 ppm/C also matters. A 1%FS static target is plausible near two-point calibration, proposed 20-30C; it is not guaranteed across the sensor entire ambient range. Include temperature compensation or narrow the qualified temperature window based on tests.

### Every component on this sheet

#### C40: 47 nF
- **Selected order: ** `C1206C473J5GACTU`; **footprint: ** `Capacitor_SMD:C_1206_3216Metric`.
- **Purpose: ** Low-frequency pressure filter at buffered divider.
- **Why this value: ** 47 nF 50 V C0G 5% KEMET C1206C473J5GACTU in 1206. The old 0603 package specification lacked a supported exact order and is explicitly changed. With 24.925k Thevenin source, pole 135.86 Hz.
- **Sources: ** [C1206C473J5GACTU](https://search.kemet.com/download/specsheet/C1206C473J5GACTU), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U10-+); 2 = GND

#### C41: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** ADS1220 analog supply bypass.
- **Why this value: ** 100 nF follows section 9.3.3 and is independent of its digital bypass.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place close to AVDD12-to-AVSS5; verify local supply noise.
- **Every pin: ** 1 = +5VA; 2 = GND

#### C42: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** ADS1220 digital supply bypass.
- **Why this value: ** 100 nF follows section 9.3.3, separate from AVDD bypass.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place close to DVDD13-to-DGND4; verify logic rail sequencing/input limits.
- **Every pin: ** 1 = +3V3; 2 = GND

#### C43: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Pressure buffer supply bypass.
- **Why this value: ** 100 nF 50 V X7R 0603 at OPA388 V+5-to-V-2 follows TI layout/supply bypass guidance.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +5VA; 2 = GND

#### C44: 10 nF
- **Selected order: ** `VJ0603A103JXACW1BC`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Supplies local pressure ADC charge pulses.
- **Why this value: ** 10 nF 50 V C0G 5%0603 across AIN0/GND; driven through 47 Ohm by U10. Keeps the switched-capacitor load local instead of on 24.925k divider.
- **Sources: ** [VJ](https://www.vishay.com/docs/28548/vjw1bcbascomseries.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U7-AIN0_{slash}_REFP1); 2 = GND

#### D40: BAV199
- **Selected order: ** `BAV199`; **footprint: ** `Package_TO_SOT_SMD:SOT-23`.
- **Purpose: ** Pressure input rail steering clamp.
- **Why this value: ** BAV199 steering pair: pin 1 anode toGND,pin 2 cathode to+5VA,pin 3 midpoint tosignal. Maxreverseleakage 5nA at 25C/80nA at 150C, VR75 V; maxVF0.9 V at 1 mA exceeds ADC rail-overdrive limits. It is not a guaranteed sustained-fault clamp.
- **Sources: ** [CLAMP](https://assets.nexperia.com/documents/data-sheet/BAV199.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Normal 0-5 V sensor harness only. Qualify cable ESD, powered/off-state injection and sustainedmiswire separately; do not infer absolute-max protection from current alone.
- **Every pin: ** 1 = GND; 2 = +5VA; 3 = Net-(U10-+)

#### D41: TPD2E2U06DCKR
- **Selected order: ** `TPD2E2U06DCKR`; **footprint: ** `Package_TO_SOT_SMD:SOT-323_SC-70`.
- **Purpose: ** Coarse pressure-cable ESD suppression.
- **Why this value: ** One channel of TPD2E2U06DCKR protects P_RAW; the unused protection channel is explicitly NC. Protection is not a sustained battery-short rating.
- **Sources: ** [ESD](https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify DCK pin 3 ground and cable fault/ESD coordination with R40/D40.
- **Every pin: ** 1 = Net-(D41-IO1); 3 = GND; 2 = NC

#### J3: B3B-XH-A
- **Selected order: ** `B3B-XH-A`; **footprint: ** `Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical`.
- **Purpose: ** Pressure sensor power, signal and return harness.
- **Why this value: ** B3B-XH-A provides three contacts. PCB order 1 supply/2 signal/3 return deliberately differs from sensor DIN order 1 supply/2 return/3 signal.
- **Sources: ** [JST](https://www.jst-mfg.com/product/pdf/eng/eXH.pdf), [SENSOR](https://datasheet.lcsc.com/datasheet/pdf/4da886fe05e2bf87f204aeba6d317782.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify actual mating cable and sensor pinout before power. Sensor 9-32 V rating does not expand board 4S limits.
- **Every pin: ** 1 = VBAT; 2 = Net-(D41-IO1); 3 = GND

#### R40: 100 kOhm
- **Selected order: ** `TNPW0603100KBEEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Scales 0-5 V pressure to ADC range.
- **Why this value: ** 100k/33.2k0.1%25 ppm/K TNPW gives k0.249249;5 V becomes 1.246246 V (60.85% of 2.048 V range). Nominal sensor load 133.2k,37.54uA at 5 V. Opposing tolerances yield +/-0.1502% ratio error; assumed 100 Ohm sensor output adds 0.075% gain loss.
- **Sources: ** [TNPW](https://www.vishay.com/docs/28758/tnpw_e3.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf), [SENSOR](https://datasheet.lcsc.com/datasheet/pdf/4da886fe05e2bf87f204aeba6d317782.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Sensor output impedance is not specified; full-chain calibration and loaded-output verification remain required.
- **Every pin: ** 1 = Net-(D41-IO1); 2 = Net-(U10-+)

#### R41: 33.2 kOhm
- **Selected order: ** `TNPW060333K2BEEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Scales 0-5 V pressure to ADC range.
- **Why this value: ** 100k/33.2k0.1%25 ppm/K TNPW gives k0.249249;5 V becomes 1.246246 V (60.85% of 2.048 V range). Nominal sensor load 133.2k,37.54uA at 5 V. Opposing tolerances yield +/-0.1502% ratio error; assumed 100 Ohm sensor output adds 0.075% gain loss.
- **Sources: ** [TNPW](https://www.vishay.com/docs/28758/tnpw_e3.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf), [SENSOR](https://datasheet.lcsc.com/datasheet/pdf/4da886fe05e2bf87f204aeba6d317782.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Sensor output impedance is not specified; full-chain calibration and loaded-output verification remain required.
- **Every pin: ** 1 = Net-(U10-+); 2 = GND

#### R42: 33 Ohm
- **Selected order: ** `CRCW060333R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Damp pressure SPI edges.
- **Why this value: ** 33 Ohm is a board signal-integrity starting value; no ADS1220 specification requires it. Must not consume SCLK setup/hold margins.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Scope at actual bus speed; place each series resistor near its driving endpoint.
- **Every pin: ** 1 = Net-(U7-SCLK); 2 = P_SCK

#### R43: 33 Ohm
- **Selected order: ** `CRCW060333R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Damp pressure SPI edges.
- **Why this value: ** 33 Ohm is a board signal-integrity starting value; no ADS1220 specification requires it. Must not consume SCLK setup/hold margins.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Scope at actual bus speed; place each series resistor near its driving endpoint.
- **Every pin: ** 1 = Net-(U7-DIN); 2 = P_MOSI

#### R44: 33 Ohm
- **Selected order: ** `CRCW060333R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Damp pressure SPI edges.
- **Why this value: ** 33 Ohm is a board signal-integrity starting value; no ADS1220 specification requires it. Must not consume SCLK setup/hold margins.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Scope at actual bus speed; place each series resistor near its driving endpoint.
- **Every pin: ** 1 = Net-(U7-DOUT_{slash}_~{DRDY}); 2 = P_MISO

#### R45: 10 kOhm
- **Selected order: ** `CRCW060310K0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Keeps pressure ADC deselected during MCU startup.
- **Why this value: ** 10 kOhm pulls CS to the same DVDD logic rail. Static low-state current is about 0.33 mA; high-state margin depends on maximum leakage.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check input leakage/VIH over temperature and all power/reset states.
- **Every pin: ** 1 = +3V3; 2 = P_CS_N

#### R46: 47 Ohm
- **Selected order: ** `CRCW060347R0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Isolates pressure buffer from the ADC reservoir.
- **Why this value: ** 47 Ohm 1%0603 creates a small isolation impedance. Together with 10 nF C44, nominal pole 338.6 kHz, well above 50 Hz design band. This is a board-level damping/charge-delivery choice.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = Net-(U10--); 2 = Net-(U7-AIN0_{slash}_REFP1)

#### TP6: P_DIV
- **Selected order: ** `P_DIV`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Probe pressure divider output.
- **Why this value: ** 2 mm pad on P_DIV should show about 1.246 V for a true 5 V input. It loads a24.9k source, so probe impedance matters.
- **Sources: ** [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Use a high-impedance probe; include probe loading when comparing sensor/ADC values.
- **Every pin: ** 1 = Net-(U10-+)

#### TP7: P_DRDY_N
- **Selected order: ** `P_DRDY_N`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Probe pressure conversion timing.
- **Why this value: ** 2 mm pad on DRDY exposes nominal 1 ms conversions. Clock tolerance and filter latency differ from ADS1256.
- **Sources: ** [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Verify timestamp alignment, dropped samples and internal-clock drift.
- **Every pin: ** 1 = P_DRDY_N

#### U7: ADS1220IPWR
- **Selected order: ** `ADS1220IPWR`; **footprint: ** `Package_SO:TSSOP-16_4.4x5mm_P0.65mm`.
- **Purpose: ** Single-ended pressure conversion.
- **Why this value: ** ADS1220IPWR PW 16: AIN0=11, AVDD12,DVDD13. Gain 1/PGA bypass/internal 2.048 V/internalclock/normal 1000 SPS. CLK3,DGND4,AVSS5 are grounded; unused 6/7/8/9/10 are NC per section 9.1.5. IDAC and low-side switch OFF.
- **Sources: ** [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify internal-reference calibration/drift, data timing and low-impedance drive from U10.
- **Every pin: ** 1 = Net-(U7-SCLK); 11 = Net-(U7-AIN0_{slash}_REFP1); 12 = +5VA; 13 = +3V3; 14 = P_DRDY_N; 15 = Net-(U7-DOUT_{slash}_~{DRDY}); 16 = Net-(U7-DIN); 2 = P_CS_N; 3 = GND; 4 = GND; 5 = GND; 10 = NC; 7 = NC; 6 = NC; 9 = NC; 8 = NC

#### U10: OPA388IDBVR
- **Selected order: ** `OPA388IDBVR`; **footprint: ** `Package_TO_SOT_SMD:SOT-23-5`.
- **Purpose: ** Buffers the pressure divider before the ADC.
- **Why this value: ** OPA388IDBVR DBV 5: OUT1,V-2,+IN3,-IN4,V+5. At gain 1, input bias max 400pA 0-85C gives<10uV through 24.925k. Offset max 7.5uV overfulltemperature is negligible beside 1.246 VFS. This removes the direct high-impedance ADS1220 drive.
- **Sources: ** [BUF](https://www.ti.com/lit/ds/symlink/opa2388.pdf), [ADC2](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify step/settling, overload recovery and stability with R46/C44; normal input stays 0-1.25 V on ~5 V supply.
- **Every pin: ** 1 = Net-(U10--); 2 = GND; 3 = Net-(U10-+); 4 = Net-(U10--); 5 = +5VA

## 6. Radio: flow control and independent power

Native sheet: `radio.kicad_sch`.

The owner selected XB3-24AST-J through-hole RP-SMA with A 24-HASM-450 antenna. This is the RP-SMA variant. Digi hardware manual W governs the cited power/pin recommendations; the older 8.2 pF recommendation is not silently mixed with W 47 pF.

C52=47 pF is closest to VCC; C50=1 uF and C51=10 uF handle progressively slower supply disturbance. The 1.1 MHz buck meets the switching-frequency recommendation. U3 and bypasses must still achieve≤50 mV p-p at the module under RF load/startup.

TXU0204 U9 uses VCCA from Teensy and VCCB from RF. Two channels carry MCU TX/RTS into XBee DIN/RTS; the other two carry DOUT/CTS back. It has specified partial-power-down/VCC isolation when either supply is off. C53/C54 bypass both domains. CommonGND remains.

100k pulls set TX/RX high and flow-control lines deasserted on the MCU side. When RF is off, CTS high prevents Serial3 transmission. TI recommends keeping inputs low before deliberately disconnecting a supply; verify uncontrolled rail ramps too. Reset 10k pull-up and DTR10k pull-down provide chosen boot defaults; recovery access uses TP8/TP9 plusUART/RTS.

Digi p101 requires attention to early SoC revisionB: supply dips in roughly 1.2-1.8 V can leave the module unresponsive until a complete powercycle. Specify/inspect revisionC or later, which fixes the issue. The user module label has not been checked.

For USB-adapter firmware recovery, remove socketed U8 and use the module adapter. TP8/TP9 are diagnostic access, not a complete programming header. With both supplies present U9 drives RF-side UART/RTS; external adapter signals must not contend with it.

The stated USB adapter is assumed to be the ground-station device. Its own 3.3 V output is never joined to the board regulator output. Confirm antenna/RP-SMA projection, module socket contact fit and enclosure/cable access during physical review.

### Every component on this sheet

#### C50: 1 uF
- **Selected order: ** `C0603C105K4RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** XBee medium-frequency supply bypass.
- **Why this value: ** 1 uF 16 V X7R 0603 follows Digi revisionW p52 alongside 47 pF. Exact KEMET order/curves are archived.
- **Sources: ** [C0603C105K4RACTU](https://search.kemet.com/download/specsheet/C0603C105K4RACTU), [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +3V3_RF; 2 = GND

#### C51: 10 uF
- **Selected order: ** `C0805C106K4PACTU`; **footprint: ** `Capacitor_SMD:C_0805_2012Metric`.
- **Purpose: ** XBee local supply reservoir.
- **Why this value: ** 10 uF 16 V X5R 0805 follows Digi additional reservoir recommendation. Effective C and actual LDO/PCB response determine RF voltage ripple.
- **Sources: ** [C0805C106K4PACTU](https://search.kemet.com/download/specsheet/C0805C106K4PACTU), [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf), [LDO](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +3V3_RF; 2 = GND

#### C52: 47 pF
- **Selected order: ** `VJ0603A470JXACW1BC`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** XBee high-frequency VCC bypass.
- **Why this value: ** 47 pF 50 V C0G 5%0603 Vishay order implements Digi 90001543 W p52. Older 8.2 pF manuals are retained as a revision conflict; the cited archivedW recommendation is followed.
- **Sources: ** [VJ](https://www.vishay.com/docs/28548/vjw1bcbascomseries.pdf), [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Place closest to U8 VCC/GND; measure ≤50 mV p-p at module.
- **Every pin: ** 1 = +3V3_RF; 2 = GND

#### C53: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Independent local bypasses for UART buffer supplies.
- **Why this value: ** 100 nF 50 V X7R 0603 for each supply pin 1/14, with commonGND7. TI recommends local bypass on both supplies; do not join the two 3.3 V outputs.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [ISOLATOR](https://www.ti.com/lit/ds/symlink/txu0204.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +3V3; 2 = GND

#### C54: 100 nF
- **Selected order: ** `C0603C104K5RACTU`; **footprint: ** `Capacitor_SMD:C_0603_1608Metric`.
- **Purpose: ** Independent local bypasses for UART buffer supplies.
- **Why this value: ** 100 nF 50 V X7R 0603 for each supply pin 1/14, with commonGND7. TI recommends local bypass on both supplies; do not join the two 3.3 V outputs.
- **Sources: ** [C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU), [ISOLATOR](https://www.ti.com/lit/ds/symlink/txu0204.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +3V3_RF; 2 = GND

#### R50: 10 kOhm
- **Selected order: ** `CRCW060310K0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Holds XBee active-low RESET inactive.
- **Why this value: ** 10 kOhm external pull-up is a deliberate reset default/recovery choice; not a manufacturer-required exact resistance.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check reset leakage/thresholds, ability of service adapter to pull low and reset timing.
- **Every pin: ** 1 = +3V3_RF; 2 = Net-(U8-~{RESET})

#### R51: 10 kOhm
- **Selected order: ** `CRCW060310K0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Holds DTR/SLEEP_RQ low when no adapter drives it.
- **Why this value: ** 10 kOhm pull-down establishes non-requested pin sleep state only for the selected firmware configuration. Digi requires DTR for firmware recovery.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Configure sleep explicitly and prove external adapter high/low levels against this pull-down.
- **Every pin: ** 1 = Net-(U8-DTR_{slash}_SLEEP_RQ); 2 = GND

#### R52: 100 kOhm
- **Selected order: ** `CRCW0603100KFKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Defines UART idle and deasserted flow-control states at MCU side.
- **Why this value: ** 100k1% pulls TX/RX/RTS/CTS to Teensy3V3. TI integrated input pulldowns are 5MOhm typical; external pull-up should be≤1MOhm.100k is comfortably below that guidance and draws 33uA when low. CTS high stops the supportedSerial3 transmitter when RF is off.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ISOLATOR](https://www.ti.com/lit/ds/symlink/txu0204.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify boot/default levels and high-level leakage margins at temperature.
- **Every pin: ** 1 = +3V3; 2 = XB_TX

#### R53: 100 kOhm
- **Selected order: ** `CRCW0603100KFKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Defines UART idle and deasserted flow-control states at MCU side.
- **Why this value: ** 100k1% pulls TX/RX/RTS/CTS to Teensy3V3. TI integrated input pulldowns are 5MOhm typical; external pull-up should be≤1MOhm.100k is comfortably below that guidance and draws 33uA when low. CTS high stops the supportedSerial3 transmitter when RF is off.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ISOLATOR](https://www.ti.com/lit/ds/symlink/txu0204.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify boot/default levels and high-level leakage margins at temperature.
- **Every pin: ** 1 = +3V3; 2 = XB_RTS_N

#### R54: 100 kOhm
- **Selected order: ** `CRCW0603100KFKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Defines UART idle and deasserted flow-control states at MCU side.
- **Why this value: ** 100k1% pulls TX/RX/RTS/CTS to Teensy3V3. TI integrated input pulldowns are 5MOhm typical; external pull-up should be≤1MOhm.100k is comfortably below that guidance and draws 33uA when low. CTS high stops the supportedSerial3 transmitter when RF is off.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ISOLATOR](https://www.ti.com/lit/ds/symlink/txu0204.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify boot/default levels and high-level leakage margins at temperature.
- **Every pin: ** 1 = +3V3; 2 = XB_CTS_N

#### R55: 100 kOhm
- **Selected order: ** `CRCW0603100KFKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Defines UART idle and deasserted flow-control states at MCU side.
- **Why this value: ** 100k1% pulls TX/RX/RTS/CTS to Teensy3V3. TI integrated input pulldowns are 5MOhm typical; external pull-up should be≤1MOhm.100k is comfortably below that guidance and draws 33uA when low. CTS high stops the supportedSerial3 transmitter when RF is off.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [ISOLATOR](https://www.ti.com/lit/ds/symlink/txu0204.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify boot/default levels and high-level leakage margins at temperature.
- **Every pin: ** 1 = +3V3; 2 = XB_RX

#### TP8: XB_RESET_N
- **Selected order: ** `XB_RESET_N`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Expose XBee reset and DTR for service/recovery.
- **Why this value: ** 2 mm test pads permit access without driving these signals from the Teensy. Probe pads are not a complete keyed programming connector.
- **Sources: ** [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Verify service harness, RTS/UART access and adapter supply isolation.
- **Every pin: ** 1 = Net-(U8-~{RESET})

#### TP9: XB_SLEEP_RQ
- **Selected order: ** `XB_SLEEP_RQ`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Expose XBee reset and DTR for service/recovery.
- **Why this value: ** 2 mm test pads permit access without driving these signals from the Teensy. Probe pads are not a complete keyed programming connector.
- **Sources: ** [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Verify service harness, RTS/UART access and adapter supply isolation.
- **Every pin: ** 1 = Net-(U8-DTR_{slash}_SLEEP_RQ)

#### U8: XB3-24AST-J
- **Selected order: ** `XB3-24AST-J`; **footprint: ** `TMS:XBee3_RPSMA_Socket`.
- **Purpose: ** Owner-selected XBee telemetry module.
- **Why this value: ** XB3-24AST-J is standard through-hole RP-SMA with A 24-HASM-450. UART DIN3/DOUT2,RTS16input/CTS12output. Digi revisionW specifies 1 uF+47 pF with 10 uF reservoir; all are now present.
- **Sources: ** [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Specify/inspect SoC revisionC or later per Digi p101. Earlier revisionB can latch after supply dips and require a complete powercycle. Configure DIO/sleep/flow-control; verify ripple, recovery and antenna fit.
- **Every pin: ** 1 = +3V3_RF; 10 = GND; 12 = XBee telemetry/RF_CTS_N; 16 = XBee telemetry/RF_RTS_N; 2 = XBee telemetry/RF_DOUT; 3 = XBee telemetry/RF_DIN; 5 = Net-(U8-~{RESET}); 9 = Net-(U8-DTR_{slash}_SLEEP_RQ); 13 = NC; 15 = NC; 6 = NC; 4 = NC; 7 = NC; 8 = NC; 11 = NC; 14 = NC; 17 = NC; 18 = NC; 19 = NC; 20 = NC

#### U9: TXU0204PWR
- **Selected order: ** `TXU0204PWR`; **footprint: ** `Package_SO:TSSOP-14_4.4x5mm_P0.65mm`.
- **Purpose: ** Buffers four UART/flow-control signals across independently powered rails.
- **Why this value: ** TXU0204PWR PW 14: two channels A-to-B and two B-to-A; VCCA Teensy3V3,VCCB RF3V3,OE tiedVCCA. Datasheet specifies Hi-Z outputs when either VCC<100 mV/disconnected and Ioff power-off behavior. Common ground remains; this is not galvanic isolation.
- **Sources: ** [ISOLATOR](https://www.ti.com/lit/ds/symlink/txu0204.pdf), [RF](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check all battery/USB/off/ramp states and idle pulls. Keep inputs low before intentionally disconnecting a rail as TI recommends; verify power-down ramps.
- **Every pin: ** 1 = +3V3; 10 = XBee telemetry/RF_CTS_N; 11 = XBee telemetry/RF_DOUT; 12 = XBee telemetry/RF_RTS_N; 13 = XBee telemetry/RF_DIN; 14 = +3V3_RF; 2 = XB_TX; 3 = XB_RTS_N; 4 = XB_RX; 5 = XB_CTS_N; 7 = GND; 8 = +3V3; 6 = NC; 9 = NC

## 7. Ignition interface: two separate current paths

Native sheet: `ignition.kicad_sch`.

The control path is 5 V relay coil -> AO3400A -> electronicsGND. The contact path is separate 2S battery -> external physical ARM -> normally-open relay -> nichrome -> IGN_GND. There is no drawn connection between IGN_GND and electronicsGND. Contact isolation and physical clearances still require layout inspection.

R60=1k and R61=10k give nominal 3.0 V gate drive from 3.3 V. AO3400A has RDS(on) max 48 mOhm at 2.5 V, so the choice uses a specified gate condition. Pull-down defaults the gate off while the MCU is high impedance; it cannot defeat a stuck-high output.

Coil 125 Ohm +/-10% draws~46 mA at the screened upper 5 V rail. D60 cathode is+5V,anode coil_low; it recirculates turn-off current and delays relay release. Verify repeated energy and release behavior. Hongfa unlabeled type 1 drawing is converted from bottom view to PCB top view; local IDs1/6 identify coil and 2/3 identify NO contacts.

Because no load measurement is available, the author contract is≤2 A at 8.4 V, requiring cold resistance≥4.2 Ohm and a bounded pulse verified on a non-energetic load. This is an assumption about the future load, not proof that the actual nichrome meets it or heats sufficiently. Relay 5 A/30 VDC resistive rating and connector ratings do not qualify the whole harness/copper path.

J5 now follows the Kangnex 1.50 mm drill drawing. J6 is PCB-mount XT60PW-F. All three AMASS connectors usepad 2 positive/pad 1 return, matching the assigned footprint markings. AMASS revision differences, polarity, externalfuse/ARM switch, wire, strain relief and copper remain layout/procurement checks. There is no continuity or physical ARM readback and no live ignition approval.

### Every component on this sheet

#### D60: 1N4148WS
- **Selected order: ** `1N4148WS`; **footprint: ** `Diode_SMD:D_SOD-323`.
- **Purpose: ** Relay flyback diode.
- **Why this value: ** Semtech1N4148WS: cathode 1 to+5V,anode 2 tocoil_low. Initial coil current~46 mA is below 150 mA average datasheet rating; VFmax 1 V at 50 mA implies clamp near 6.17 V, below 30 V MOSFET rating. Coil energy/repetition/release delay still require testing.
- **Sources: ** [DIODE](https://www.lcsc.com/product-detail/C57759.html), [RELAY](http://www.hongfaamerica.com/hq/PDF/HF46F_en.pdf), [MOS](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify PCB placement, temperature, startup and measured behavior within the stated design assumptions.
- **Every pin: ** 1 = +5V; 2 = Net-(D60-A)

#### J4: XT30PW-F
- **Selected order: ** `XT30PW-F`; **footprint: ** `Connector_AMASS:AMASS_XT30PW-F_1x02_P2.50mm_Horizontal`.
- **Purpose: ** Electronics 4S / separateignition 2S battery connectors.
- **Why this value: ** XT30PW-F selected drawings/5mmpowerpitch. Input J1return isGND;J4return is IGN_GND. Pad 2 is positive and pad 1 is return, matching the assigned KiCad footprint +/- markings. Connector family 15 A rating exceeds planning currents; mating gender/polarity and inconsistent retention-hole drawings require exact purchased-part fit verification.
- **Sources: ** [XT30](https://www.tme.eu/Document/f383737e340bfdab1f665284174b4ea2/XT30PW-F.pdf)
- **Status: ** Static choice checked; prototype qualification remains. **Verify: ** Do not use genericcatalog dimensions interchangeably with V 1.2; verify harness/polarity and external fuse.
- **Every pin: ** 1 = Ignition interface/IGN_GND; 2 = Net-(J4-+)

#### J5: ARM / WJ500 V-5.08-2P
- **Selected order: ** `WJ500V-5.08-2P-14-00A`; **footprint: ** `TMS:WJ500V_5.08_2P_14_00A`.
- **Purpose: ** External physical ARM switch loop.
- **Why this value: ** Exact green single-pitch WJ500V-5.08-2P-14-00A. Manufacturer drawingA specifies 5.08 mm pitch and 1.50 mm finishedholes. Imported pads already had 5.08 pitch despite 5.00 name, but 1.30 mm drills differed. New local footprint uses 1.50 mm drills/3 mm pads. UL10 A/300 V contact rating exceeds assumed 2 A/8.4 V.
- **Sources: ** [ARM](https://datasheet.lcsc.com/datasheet/pdf/5a3d038c44f6e3872ef57456c5bdf975.pdf?productCode=C8465)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify purchased drawingrevision, screw access/0.4Nm torque/6-7 mm strip, actual fit and series ARM switch.
- **Every pin: ** 1 = Net-(J4-+); 2 = Net-(J5-ARM_RETURN)

#### J6: XT60PW-F
- **Selected order: ** `XT60PW-F`; **footprint: ** `Connector_AMASS:AMASS_XT60PW-F_1x02_P7.20mm_Horizontal`.
- **Purpose: ** PCB-mount ignition output in the chosenXT60 family.
- **Why this value: ** XT60PW-F replaces wire-termination XT60-F with a defined horizontal PCB part. V 1.2 installation drawing matches 7.20 mm powerpitch/2.70 mm holes and 13.5 mm retention-slot separation/6 mm setback. Pad 2 is switched positive, pad 1 is IGN_GND, matching footprint +/- markings. Newer catalog body dimensions differ; order/fit must be verified.
- **Sources: ** [XT60](https://www.bto.pl/pdf/08039/XT60PW-F.pdf), [RELAY](http://www.hongfaamerica.com/hq/PDF/HF46F_en.pdf)
- **Status: ** Static choice checked; prototype qualification remains. **Verify: ** Use conservative 30 A catalog rating only as connector evidence; systempath remains 2 A design assumption, subject to fuse/switch/copper validation.
- **Every pin: ** 1 = Ignition interface/IGN_GND; 2 = Net-(J6-+)

#### K1: HF46F-G/5-HS1T
- **Selected order: ** `HF46F-G/5-HS1T`; **footprint: ** `TMS:HF46F_Type1`.
- **Purpose: ** Normally-open relay contact in the separate ignition path.
- **Why this value: ** HF46F-G/5-HS1T: local pad IDs1/6 for coil and 2/3 for NO contacts; Hongfa type 1 bottom-view drawing verifies topology/coordinates but does not number the terminals;5 V/125 Ohm +/-10%. At5.1704 V and 112.5 Ohm, coil current 45.96 mA fits 47 mA plan. Manufacturer 5 A resistive/30 VDC exceeds assumed 2 A/8.4 V; actual load is unknown.
- **Sources: ** [PART_HF46F_G_5_HS1T](https://www.lcsc.com/product-detail/C5274026.html), [RELAY](http://www.hongfaamerica.com/hq/PDF/HF46F_en.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Qualify real current, duration, temperature, contact release/faults and physical footprint with a dummy load; nolive-load acceptance.
- **Every pin: ** 1 = +5V; 2 = Net-(J5-ARM_RETURN); 3 = Net-(J6-+); 6 = Net-(D60-A)

#### Q1: AO3400A
- **Selected order: ** `AO3400A`; **footprint: ** `Package_TO_SOT_SMD:SOT-23`.
- **Purpose: ** Low-side relay-coil switch.
- **Why this value: ** AO3400A is specified up to 48 mOhm RDS(on) at VGS=2.5 V, below the nominal 3.0 V drive. VGS(th) alone is not used to claim full turn-on.
- **Sources: ** [MOS](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Confirm exact manufacturer/package, pulse/current/thermal and reset/fault behavior; it does not switch the ignition load directly.
- **Every pin: ** 1 = Net-(Q1-G); 2 = GND; 3 = Net-(D60-A)

#### R60: 1 kOhm
- **Selected order: ** `CRCW06031K00FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Limits MOSFET gate charge current/edge speed.
- **Why this value: ** 1 kOhm plus 10 kOhm pull-down forms a DC divider: VGS approximately 3.3*10/11=3.0 V. Value is an engineering choice, not an AO3400A requirement.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [MOS](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf), [MCU](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Check MCU VOH, transition time, gate leakage and brownout; GPIO supplies ~0.30 mA steady when high.
- **Every pin: ** 1 = FIRE_CMD; 2 = Net-(Q1-G)

#### R61: 10 kOhm
- **Selected order: ** `CRCW060310K0FKEA`; **footprint: ** `Resistor_SMD:R_0603_1608Metric`.
- **Purpose: ** Keeps the MOSFET off with a floating MCU output.
- **Why this value: ** 10 kOhm discharges the gate and overcomes leakage. Together with R60 it reduces the driven gate voltage to about 3.0 V.
- **Sources: ** [CRCW](https://www.vishay.com/docs/20035/dcrcwe3.pdf), [MOS](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf)
- **Status: ** Static choice checked; PCB/bench qualification remains. **Verify: ** Verify actual GPIO reset states and noise immunity; a resistor cannot defeat a stuck-high output.
- **Every pin: ** 1 = Net-(Q1-G); 2 = GND

#### TP10: COIL_LOW
- **Selected order: ** `COIL_LOW`; **footprint: ** `TestPoint:TestPoint_Pad_D2.0mm`.
- **Purpose: ** Probe relay drain/coil-low signal.
- **Why this value: ** 2 mm pad helps verify commanded ON/OFF, flyback and reset behavior with a dummy load. It is not a current measurement.
- **Sources: ** [MOS](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf), [DIODE](https://www.lcsc.com/product-detail/C57759.html), [RELAY](http://www.hongfaamerica.com/hq/PDF/HF46F_en.pdf)
- **Status: ** Fabricated probe; author-chosen geometry. **Verify: ** Use safe probing relative to electronics GND; confirm no accidental bridge to IGN_GND.
- **Every pin: ** 1 = Net-(D60-A)

## Required-versus-present support matrix

| Device / function | Implementation | Disposition | Evidence |
| --- | --- | --- | --- |
| LMR51430 power stage | C1/C11/C12 input; C2 HF; C3 CB-SW; L1; ten output MLCCs; R1/R2 and R3/R4/R5 | Present; equation screen conditional | BUCK pp 16-20. C9 removed for the new topology. D2 is an author-added bounded clamp. |
| TLV75533 stability | C7/C8 exact 10 uF 16 V; IN1/EN3 to 5 V; GND2; OUT5; NC4 | Present | LDO pp 3,15-16; effective C/ripple measured on prototype. |
| Teensy module support | VIN reservoir/shunt;48 signal-named socket pads; module owns MCU regulator/clock/SD socket | Present; USB configuration required | PJRC cards/power/UART pages; do not duplicate module support. |
| OPA2388 bridge buffers | 100 nF supply; two unity feedback loops;1k/220 nF input filter;47 Ohm/10 nF ADC drive | Present | BUF/ADC1; normal-input and overload qualification are separate. |
| ADS1256 supplies/control | AVDD1 C23/C27; DVDD16 C24/C28; GND2/17; RESET15/SYNC14 high | Present | ADC1 pin table/basic circuit. Digital IO states configured by firmware. |
| ADS1256 reference/clock | Real buffered VEXC/2 reference;47 uF/100 uF/100 nF bank;7.68 MHz crystal/30 pF loads | Present; stability/startup conditional | ADC1 Fig 25/26, REF/XTAL. No internal precision reference is assumed. |
| ADS1256 unused pins | AINCOM5/AIN2-7 pins 8-13 and DIO25-28 explicitly NC | Present | Only AIN0/AIN1 selected. |
| OPA350 reference buffer | Unity feedback;100 nF supply;15ms input filter; exactPanasonicFT output bank | Present; loop qualification open | REF and ADC1Fig26; ESR maxima known, minima/loop response unproven. |
| Pressure sensor interface | 9-32 V sensor supplied from protected 4S; board-to-DIN1/3/2 harness;100k/33.2k/47 nF | Present; sensor Rs assumption | SENSOR pp 1-3; 133.2k load not specified by sensor datasheet. |
| OPA388 pressure buffer | Unity feedback;C43 bypass;R46/C44 local ADC drive | Present | BUF DBV 5 table/layout and ADC2 input-current discussion. |
| ADS1220 supplies/input | AVDD12 C41;DVDD13 C42;CLK3/DGND4/AVSS5 GND;AIN0 pin 11 | Present | ADC2 PW 16 table. PGA bypass required for single-ended-to-AVSS. |
| ADS1220 unused pins | 6/7/8/9/10 NC;low-side switch/IDAC OFF;all digital outputs accounted for | Present | ADC2 section 9.1.5. |
| XBee supply/recovery | 47 pF+1 uF+10 uF;RESET pull-up;DTR pull-down;testpads/UART/RTS access | Present; recovery/fit conditional | Digi 90001543 W pp 45-52. |
| TXU0204 supplies/enable | C53/C54 separate 100 nF;VCCA 1/OE8 Teensy3V3;VCCB14 RF3V3;GND7;NC6/9 | Present | ISOLATOR PW 14 table and power-off conditions. |
| Relay switch/flyback | Gate resistor/pull-down;MOSFET;flyback diode;physical externalARM and separateIGN_GND | Present; system qualification open | RELAY/MOS/DIODE. No continuity/ARM sensing requested. |
| Connector footprints | All 120 pin sets match actual pads; shared geometry parses all | Source-bound pad coverage passes; fit open | Five localTMS footprints have validated manufacturer-drawing-derived receipts; these are author lineage records, not physical-fit acceptance. |

## External assembly items

These are additional to the 120 CAD references. Interface/rating requirements are specified; entries without selected stock numbers are not procurement-approved. Socket, harness, fuse and physical ARM choices require sourcing/fit review before an order.

| Item | Quantity | Purpose | Verification |
| --- | --- | --- | --- |
| BCA-100L | 1 | Confirmed external load cell; not a board-mounted component | Verify actual model/capacity, conductors, calibration and 5 V excitation performance. |
| IPSU-GP1K5-6 | 1 | Confirmed external pressure sensor | Verify actual unit, DIN mating cable, supply/return/signal and loading. |
| A 24-HASM-450 | 1 | Confirmed external antenna | Verify RP-SMA mate, mounting and enclosure clearance; extension optional. |
| microSD card | 1 | Inserted into U1 module SD socket | Select exact card; verify write-latency/peak-current/endurance and sustained logging. |
| Teensy female socket rows | 2 x 24 contacts | Physical carrier sockets represented by U1 footprint | Select exact 2.54 mm sockets, height, retention and current/contact ratings. |
| XBee female socket rows | 2 x 10 contacts | Physical sockets represented by U8 footprint | Select exact 2 mm sockets and correct 22 mm row separation/height. |
| JP1 shunt | 1 | Removable VIN link | Select exact mating shunt/current rating and define USB procedure. |
| Battery packs | 1 x 4S and 1 x 2S | Separate electronics and ignition supplies | Select packs/protection from actual loads; capacities and peak ratings unresolved. |
| External fuses/holders | TBD per supply/harness | Not present on PCB | Select from measured current, wire ratings, battery fault current and clearing characteristics. |
| Physical ARM switch | 1 | External series switch throughJ5 | Current/voltage/pulse and environmental ratings unresolved. |
| Nichrome/load assembly | 1 test assembly | External ignition load | Cold/hot resistance, construction, pulse energy and duration unresolved. |
| Harness/mating connectors | 1 mate per J1-J6, where applicable | XT30 x 2, XT60 x 1, XH5 x 1, XH3 x 1; J5 switch wiring | Verify actual connector gender, crimp contacts, wire size/length, strain relief and shield termination. |
| XBee USB adapter | 1 ground-station unit assumed | Owner stated 3.3 V supply | Exact adapter/current capacity/install location unresolved; do not parallel supply outputs. |
| Enclosure/mounting/antenna extension | TBD; extension 0 or 1 | Not established by schematic | Resolve 100x80 versus 100x100 mm envelope and mounting conflict before PCB placement. |

## Reproducible checks and honest limits

Run the project `check_schematic.py` using workspacePython. It is an independent engineering node specification, not a copied native netlist. It requires all 380 physical pins to belong to the correct one of 69nodes or 59 explicitNCs. It rejects unintended shorts, missing parts and wrong unused-pin treatment. Pin functions were checked against the selected package tables. Hongfa terminal IDs are local conventions; its source drawing is unlabeled.

`pcb-copilot research PROJECT --verify-schematic-parts` verifies exact selected-part evidence identity and stored hashes. The normal datasheet review now includes unplaced native schematic parts. A same-reference old datasheet does not qualify a replacement. No archive orERC result proves value choice, dynamic behavior or physical fit.

The normal update workflow requires matching routedPCB. This project has an emptyPCB. The owner-approvedA 1 exception covered presentation/electrical equivalence only. The owner subsequently approved the A 2 schematic-stage circuit/library/document installation. The shared transaction lock, input/target hash guards and rollback path install it without changing PCB/project/rule files. This exception is not engineering sign-off; release and all shared/project human decisions remain mandatory.

Physical fit, reference-loop stability, RF ripple, source/clamp sequencing, thermal response, sensor calibration/temperature, actual load/current path, SD timing and fault tests remain open. The installed schematic is not unconditionally okay for PCB fabrication or live ignition.

## Exact source index

### BUCK: lmr 51430.pdf
SLUSEF4 A: pp 3-6 pin map/limits; pp 16-20, Table 9-2, equations 11-17; DDC lands
[https://www.ti.com/lit/ds/symlink/lmr51430.pdf](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
Archived: `../../evidence/files/LMR51430YFDDCR_lmr51430_f7d8053844fb.pdf`
SHA 256: `f7d8053844fb07ae773844f023373c0c570507ca61603fe28dda15364987296c`

### LDO: tlv 755p.pdf
pp. 3-6, 15-16, 19; DBV package
[https://www.ti.com/lit/ds/symlink/tlv755p.pdf](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)
Archived: `../../evidence/files/TLV75533PDBVR_tlv755p_d5d9f30657f2.pdf`
SHA 256: `d5d9f30657f27c620b7ef579ade01bbf930344b4e9f963c961b6a60bf02f410b`

### ADC1: ADS1256_ti
pp. 3-5, 14-18, 27-29; Fig. 25-26
[https://www.ti.com/lit/ds/symlink/ads1256.pdf](https://www.ti.com/lit/ds/symlink/ads1256.pdf)
Archived: `../../evidence/files/ADS1256_ti.pdf`
SHA 256: `9da3323db162b59329ec1a865829441ff1605279cd802fe879649b6f54e100e6`

### ADC2: ADS1220_ti
pp. 3-7, 20-26, 35-42, 49-50, 64-65
[https://www.ti.com/lit/ds/symlink/ads1220.pdf](https://www.ti.com/lit/ds/symlink/ads1220.pdf)
Archived: `../../evidence/files/ADS1220_ti.pdf`
SHA 256: `ba264d1644fe9de625c075ddcee61eb4c59cce2780ba416cd831216c40f755cf`

### BUF: opa 2388.pdf
pp. 3, 7-9, 15, 24-26
[https://www.ti.com/lit/ds/symlink/opa2388.pdf](https://www.ti.com/lit/ds/symlink/opa2388.pdf)
Archived: `../../evidence/files/OPA2388IDR_opa2388_bfaa58483429.pdf`
SHA 256: `bfaa584834295abba9cab4c66cda702ada12def5d50e49b1beb0d7444f0775e7`

### REF: opa 350.pdf
pp. 3, 6, 12, 15-17, 22-23
[https://www.ti.com/lit/ds/symlink/opa350.pdf](https://www.ti.com/lit/ds/symlink/opa350.pdf)
Archived: `../../evidence/files/OPA350UA_opa350_185293ca6674.pdf`
SHA 256: `185293ca6674dd181d9934b5806d5a36e99e03caa1fe140b0bf24cccdc07c24d`

### RF: xbee 3_hardware_ref
90001543 W (June 2026), pp. 26-27, 45-47, 51-52
[https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf](https://www.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf)
Archived: `../../evidence/files/xbee3_hardware_ref.pdf`
SHA 256: `a02aee173feaec9b7504a1794d94e579ae62ca01ae868217befb62b1638efcfa`

### MCU: card 11a_rev4_web
pp. 1-2; companion rear card and PJRC power page
[https://www.pjrc.com/teensy/card11a_rev4_web.pdf](https://www.pjrc.com/teensy/card11a_rev4_web.pdf)
Archived: `../../evidence/files/card11a_rev4_web.pdf`
SHA 256: `d8e8f77658a43eddd3254fcf7c248e200f8a83a398b990382ee1f71f500debf0`

### BRIDGE: BCA.pdf
p. 2 specifications and wiring
[https://www.cas-usa.com/cdn/shop/files/BCA.pdf?v=10610127605685568819](https://www.cas-usa.com/cdn/shop/files/BCA.pdf?v=10610127605685568819)
Archived: `../../evidence/files/BCA-100L_BCA_b7855a5002cd.pdf`
SHA 256: `b7855a5002cd46f2c3c50ae4abfd6244824f073a96ffe6303a030a0192033bff`

### SENSOR: 4da886fe05e2bf87f204aeba6d317782.pdf
pp. 1-2 family/order/wiring
[https://datasheet.lcsc.com/datasheet/pdf/4da886fe05e2bf87f204aeba6d317782.pdf](https://datasheet.lcsc.com/datasheet/pdf/4da886fe05e2bf87f204aeba6d317782.pdf)
Archived: `../../evidence/files/IPSU-GP1K5-6_4da886fe05e2bf87f204aeba6d317782_5914137a3440.pdf`
SHA 256: `5914137a344044434474ec115fd0ef93595a07a05faddffa1608a57e1b09fc4a`

### XTAL: ABLS.pdf
pp. 1-3; CL/drive/order options
[https://abracon.com/Resonators/ABLS.pdf](https://abracon.com/Resonators/ABLS.pdf)
Archived: `../../evidence/files/ABLS-7.680MHZ-D-4-Y-T_ABLS_649cda5a6e08.pdf`
SHA 256: `649cda5a6e08b2e5a044efc5d1405588ff85cf5428b4e9fe12aae3d1d0c7203e`

### IND: srp 1038a.pdf
pp 1-2; exact -3R3M row: 3.3uH +/-20%, 11.8 mOhm max DCR, Irms 11 A/Isat 20 A at 25C
[https://www.bourns.com/docs/product-datasheets/srp1038a.pdf](https://www.bourns.com/docs/product-datasheets/srp1038a.pdf)
Archived: `../../evidence/files/SRP1038A-100M_srp1038a_92c761c358a1.pdf`
SHA 256: `92c761c358a1e5a3915a936f6f0795096bb6b965617bb5c408bd8be30ad285af`

### ESD: TPD2E2U06 TI datasheet (DCK 3-pin package selected)
pp. 3-4, 10-12; actual DCK 3-pin variant
[https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf](https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf)
Archived: `../../evidence/files/TPD2E2U06DBZR_tpd2e2u06_a133b86ea3d3.pdf`
SHA 256: `a133b86ea3d3c3d34667339b92d3b5e98d541d10e9775d63e7cdfa153794f4ed`

### CLAMP: BAV199.pdf
pp. 1-3; pin table and leakage/VF limits
[https://assets.nexperia.com/documents/data-sheet/BAV199.pdf](https://assets.nexperia.com/documents/data-sheet/BAV199.pdf)
Archived: `../../evidence/files/BAV199_BAV199_ab2f26d003e3.pdf`
SHA 256: `ab2f26d003e3c1d8f7e4e7ac674ae055849970bf7b392a7d5d31eca443aab9e2`

### MOS: AO3400A.pdf
pp. 1-3; RDS(on) at VGS=2.5 V
[https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf)
Archived: `../../evidence/files/AO3400A_AO3400A_9c60d0b6c1dd.pdf`
SHA 256: `9c60d0b6c1ddc7609a4b788a91181468d8ffe6c3e9ba425c3d8ffc5ba88c5033`

### RELAY: HF46F_hongfa_en
pp. 1-2; 5 V coil and type-1 bottom view
[http://www.hongfaamerica.com/hq/PDF/HF46F_en.pdf](http://www.hongfaamerica.com/hq/PDF/HF46F_en.pdf)
Archived: `../../evidence/files/HF46F_hongfa_en.pdf`
SHA 256: `7b0def367684a55227bdc7f85fb88da930e788c6cf661b77e273cdd0e1d624a6`

### DIODE: 1N4148WS_C57759
pp. 1-3; Semtech Electronics SC-76
[https://www.lcsc.com/product-detail/C57759.html](https://www.lcsc.com/product-detail/C57759.html)
Archived: `../../evidence/files/1N4148WS_C57759.pdf`
SHA 256: `3305a485d13b5135a2be83af66cc42f00504915802e444a0fa44ea4259c3c1bb`

### REVERSE: SS54_C22452
pp. 1-2; MDD SS54 SMA
[https://www.lcsc.com/product-detail/C22452.html](https://www.lcsc.com/product-detail/C22452.html)
Archived: `../../evidence/files/SS54_C22452.pdf`
SHA 256: `d90558a8db9d6ea0e8712c740ffea6d9c106544653faf724af75f1ab276dee66`

### GREEN: APTD1608LCGCK.pdf
pp. 1-2; low-current green
[https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LCGCK.pdf](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LCGCK.pdf)
Archived: `../../evidence/files/APTD1608LCGCK_APTD1608LCGCK_7bb244fd771d.pdf`
SHA 256: `7bb244fd771d4b3fa77df6ee1d24dff84b4bda56cfc55e28ce9cce4beda56c8b`

### RED: APTD1608LSURCK.pdf
pp. 1-2; low-current red
[https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LSURCK.pdf](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LSURCK.pdf)
Archived: `../../evidence/files/APTD1608LSURCK_APTD1608LSURCK_8c4ae4d0cb2c.pdf`
SHA 256: `8c4ae4d0cb2cb9c243b6590250d76933ace91d20c86683a6f1d713c93b0e1865`

### YELLOW: APTD1608LSYCK.pdf
pp. 1-2; low-current yellow
[https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LSYCK.pdf](https://www.kingbrightusa.com/images/catalog/SPEC/APTD1608LSYCK.pdf)
Archived: `../../evidence/files/APTD1608LSYCK_APTD1608LSYCK_9fe32571563b.pdf`
SHA 256: `9fe32571563b01358ea2c85ce392879cae46ed2b6dd0cd90c2754bb820d3a319`

### JST: eXH.pdf
pp. 1-3; XH family and B3B/B5B drawings
[https://www.jst-mfg.com/product/pdf/eng/eXH.pdf](https://www.jst-mfg.com/product/pdf/eng/eXH.pdf)
Archived: `../../evidence/files/B5B-XH-A_eXH_9426b136902f.pdf`
SHA 256: `9426b136902f11900825077535e5c65032b7fbc31ffb59c5e9e1f463bb20fb90`

### XT30: XT30PW-F.pdf
p. 1; exact connector drawing
[https://www.tme.eu/Document/f383737e340bfdab1f665284174b4ea2/XT30PW-F.pdf](https://www.tme.eu/Document/f383737e340bfdab1f665284174b4ea2/XT30PW-F.pdf)
Archived: `../../evidence/files/XT30PW-F_XT30PW-F_090aabb47c14.pdf`
SHA 256: `090aabb47c14c4e0c9f5d850dbe78164e19b5fc53dc2fc3a9e7837b0f0d53bea`

### XT60: XT60PW-F.pdf
AMASS V 1.2 p1 installation-hole drawing; also retain LCSC two-page specification with dimensional differences
[https://www.bto.pl/pdf/08039/XT60PW-F.pdf](https://www.bto.pl/pdf/08039/XT60PW-F.pdf)
Archived: `../../evidence/files/XT60PW-F_XT60PW-F_5d9495ef6e83.pdf`
SHA 256: `5d9495ef6e83499360fec9b489977c4c8fb63f5a21b5f7e1b1cde7045beb65d7`

### ARM: 5a3d038c44f6e3872ef57456c5bdf975.pdf
Drawing A 2024-03-10, p1: full ordering code; 5.08 pitch; 1.50 mm holes; UL10 A; body 10.16x10x14.07 mm
[https://datasheet.lcsc.com/datasheet/pdf/5a3d038c44f6e3872ef57456c5bdf975.pdf?productCode=C8465](https://datasheet.lcsc.com/datasheet/pdf/5a3d038c44f6e3872ef57456c5bdf975.pdf?productCode=C8465)
Archived: `../../evidence/files/WJ500V-5.08-2P-14-00A_5a3d038c44f6e3872ef57456c5bdf975_e3c3cbd8e0f7.pdf`
SHA 256: `e3c3cbd8e0f7cf4979ffd6a524501dd4dbd0f24556c4761922adcbd973e3ccda`

### ISOLATOR: txu 0204.pdf
SCES936 A pp 4-9, 21-24: PW 14 pins, Ioff/VCC isolation, integrated pulldowns, supply bypasses
[https://www.ti.com/lit/ds/symlink/txu0204.pdf](https://www.ti.com/lit/ds/symlink/txu0204.pdf)
Archived: `../../evidence/files/TXU0204PWR_txu0204_d54f3853ad68.pdf`
SHA 256: `d54f3853ad68ee6c1b59531b87f09b9e9badbac17b8eb9d90a6033ed7c7403a3`

### TVS: SMBJ5.0(C)A-SMBJ170(C)A.pdf
DS19002 Rev 20-2 pp 1-3,5-6: unidirectional ordering, pulse conditions, SMBJ18 A electrical row and SMB lands
[https://www.diodes.com/datasheet/download/SMBJ5.0(C)A-SMBJ170(C)A.pdf](https://www.diodes.com/datasheet/download/SMBJ5.0(C)A-SMBJ170(C)A.pdf)
Archived: `../../evidence/files/SMBJ18A-13-F_SMBJ5.0_C_A-SMBJ170_C_A_752945fa3aca.pdf`
SHA 256: `752945fa3acaf46947c4f9ffdca98027af4ffb4845c5250713f0b608a547d97f`

### CRCW: dcrcwe 3.pdf
Vishay 20035 14-Apr-2026 pp 1-3: 0603, F=1%, K=100 ppm/K, 0.125 W at 70C, 75 V; order table
[https://www.vishay.com/docs/20035/dcrcwe3.pdf](https://www.vishay.com/docs/20035/dcrcwe3.pdf)
Archived: `../../evidence/files/CRCW06031K00FKEA_dcrcwe3_dd2d82bab2e2.pdf`
SHA 256: `dd2d82bab2e278cd531da501db9003e37582c17e54a261b992eb6871c240db5c`

### TNPW: tnpw_e3.pdf
Vishay 28758 10-Apr-2026 pp 1-4: B=0.1%, E=25 ppm/K, 0603; 0.210 W at 70C/100 V subject to thermal management
[https://www.vishay.com/docs/28758/tnpw_e3.pdf](https://www.vishay.com/docs/28758/tnpw_e3.pdf)
Archived: `../../evidence/files/TNPW0603100KBEEA_tnpw_e3_6f0508c568cb.pdf`
SHA 256: `6f0508c568cb355aaf2accdd33fe3a780d3ea5ef207c4c9a71839a8acadc33a5`

### TNPU: tnpue 3.pdf
Vishay 28779 04-Mar-2025 pp 1-3: H=0.02%, W=2 ppm/K, 10K0; 0603 0.1 W at 70C; two discrete resistors are not a matched network
[https://www.vishay.com/docs/28779/tnpue3.pdf](https://www.vishay.com/docs/28779/tnpue3.pdf)
Archived: `../../evidence/files/TNPU060310K0HWEA00_tnpue3_d1f1bfcd0370.pdf`
SHA 256: `d1f1bfcd0370494ab90164dd8803c993f2426dc80078a35299d48d635bed1413`

### VJ: vjw 1bcbascomseries.pdf
Vishay 28548 12-Aug-2026 pp 2-6: C0G, J=5%, X=50 V, 0603 size/capacitance matrix and lands
[https://www.vishay.com/docs/28548/vjw1bcbascomseries.pdf](https://www.vishay.com/docs/28548/vjw1bcbascomseries.pdf)
Archived: `../../evidence/files/VJ0603A470JXACW1BC_vjw1bcbascomseries_757d89d0506d.pdf`
SHA 256: `757d89d0506d51683d00d16ea3477578f0dd1a280f3427a10515aa561fd1e7ad`

### FT: ABA 0000C1240.pdf
Panasonic FT ABA 0000C1240, p3: 47 uF 16 V 4x5.8 mm and 100 uF 16 V 5x5.8 mm; ESR max 0.85/0.36 Ohm at 100 kHz 20C; ripple 160/240 mA; +/-20%,105C/2000h
[https://industrial.panasonic.com/cdbs/www-data/pdf/RDE0000/ABA0000C1240.pdf](https://industrial.panasonic.com/cdbs/www-data/pdf/RDE0000/ABA0000C1240.pdf)
Archived: `../../evidence/files/EEEFT1C101AR_ABA0000C1240_affbdbc3402d.pdf`
SHA 256: `affbdbc3402d5d78e683944e78f5a641ae7f22906a4e77e24978388e491b41e2`

### FERRITE: Murata-BLM21PG601SN1-Series-EN-Datasheet.pdf
Murata manufacturer ProductSearchDataSheet mirrored by Avnet pp 1-4; 600 Ohm at 100 MHz; compare current JENF243 A_0005 AE-01
[https://my.avnet.com/wcm/connect/08e0f7ea-bb4a-4b9a-a867-346f49d03172/Murata-BLM21PG601SN1-Series-EN-Datasheet.pdf?CACHE=NONE&CVID=pfYVfKq&ContentCache=NONE&MOD=AJPERES](https://my.avnet.com/wcm/connect/08e0f7ea-bb4a-4b9a-a867-346f49d03172/Murata-BLM21PG601SN1-Series-EN-Datasheet.pdf?CACHE=NONE&CVID=pfYVfKq&ContentCache=NONE&MOD=AJPERES)
Archived: `../../evidence/files/BLM21PG601SN1D_Murata-BLM21PG601SN1-Series-EN-Datasheet_ffa5cd2dd18c.pdf`
SHA 256: `ffa5cd2dd18c5959158a0b64dbde2a42be7360bef8eac4112e910f09a5d6c62d`

### SHUNT_HEADER: tsw_th.pdf
Samtec TSW through-hole family drawing; 2 contacts/single row/2.54 mm; -07 tail choice and L plating
[https://suddendocs.samtec.com/catalog_english/tsw_th.pdf](https://suddendocs.samtec.com/catalog_english/tsw_th.pdf)
Archived: `../../evidence/files/TSW-102-07-L-S_tsw_th_3a5770b11668.pdf`
SHA 256: `3a5770b11668f4e5a11ba9ceeb4817a23f467b8507e3592f55fb6bd8f96e71bc`

### C0603C104K5RACTU: C0603C104K5RACTU
Exact KEMET part specification generated 14-Oct-2026: p1 guaranteed size/value/rating/tolerance; pp 2-3 typical simulation curves, not limits; p4 land pattern
[https://search.kemet.com/download/specsheet/C0603C104K5RACTU](https://search.kemet.com/download/specsheet/C0603C104K5RACTU)
Archived: `../../evidence/files/C0603C104K5RACTU_C0603C104K5RACTU_e918fe68ca30.pdf`
SHA 256: `e918fe68ca30cdb63db6262941b699c1389f1450a0504e87d5d2db1f8d1135e2`

### C0603C105K4RACTU: C0603C105K4RACTU
Exact KEMET part specification generated 14-Oct-2026: p1 guaranteed size/value/rating/tolerance; pp 2-3 typical simulation curves, not limits; p4 land pattern
[https://search.kemet.com/download/specsheet/C0603C105K4RACTU](https://search.kemet.com/download/specsheet/C0603C105K4RACTU)
Archived: `../../evidence/files/C0603C105K4RACTU_C0603C105K4RACTU_777610659dc1.pdf`
SHA 256: `777610659dc101e5903051a95a2f8e203a6046126151ffc76a77a0ce8524ef5a`

### C0603C224K4RACTU: C0603C224K4RACTU
Exact KEMET part specification generated 14-Oct-2026: p1 guaranteed size/value/rating/tolerance; pp 2-3 typical simulation curves, not limits; p4 land pattern
[https://search.kemet.com/download/specsheet/C0603C224K4RACTU](https://search.kemet.com/download/specsheet/C0603C224K4RACTU)
Archived: `../../evidence/files/C0603C224K4RACTU_C0603C224K4RACTU_4cce90bdd41a.pdf`
SHA 256: `4cce90bdd41ad918ef739824ec88c2f3787947c9888ac2160b511a096a47f0c6`

### C0603C300J5GACTU: C0603C300J5GACTU
Exact KEMET part specification generated 14-Oct-2026: p1 guaranteed size/value/rating/tolerance; pp 2-3 typical simulation curves, not limits; p4 land pattern
[https://search.kemet.com/download/specsheet/C0603C300J5GACTU](https://search.kemet.com/download/specsheet/C0603C300J5GACTU)
Archived: `../../evidence/files/C0603C300J5GACTU_C0603C300J5GACTU_b1e2952d0aa7.pdf`
SHA 256: `b1e2952d0aa7a498b031da1736f2d0c5eb0d90c0a005f07bdb40c691e87219bb`

### C0805C106K4PACTU: C0805C106K4PACTU
Exact KEMET part specification generated 14-Oct-2026: p1 guaranteed size/value/rating/tolerance; pp 2-3 typical simulation curves, not limits; p4 land pattern
[https://search.kemet.com/download/specsheet/C0805C106K4PACTU](https://search.kemet.com/download/specsheet/C0805C106K4PACTU)
Archived: `../../evidence/files/C0805C106K4PACTU_C0805C106K4PACTU_a9f50f5e53e4.pdf`
SHA 256: `a9f50f5e53e4f304523d9330f56af9956da40a2246fdff757532efddbd652279`

### C1206C473J5GACTU: C1206C473J5GACTU
Exact KEMET part specification generated 14-Oct-2026: p1 guaranteed size/value/rating/tolerance; pp 2-3 typical simulation curves, not limits; p4 land pattern
[https://search.kemet.com/download/specsheet/C1206C473J5GACTU](https://search.kemet.com/download/specsheet/C1206C473J5GACTU)
Archived: `../../evidence/files/C1206C473J5GACTU_C1206C473J5GACTU_6c19cd75c9bb.pdf`
SHA 256: `6c19cd75c9bb5934e35bcf919341d1cba3933e91ae4ffbda55ec2f3201faae6f`

### C1210C106K5RACTU: C1210C106K5RACTU
Exact KEMET part specification generated 14-Oct-2026: p1 guaranteed size/value/rating/tolerance; pp 2-3 typical simulation curves, not limits; p4 land pattern
[https://search.kemet.com/download/specsheet/C1210C106K5RACTU](https://search.kemet.com/download/specsheet/C1210C106K5RACTU)
Archived: `../../evidence/files/C1210C106K5RACTU_C1210C106K5RACTU_51d2b880f18f.pdf`
SHA 256: `51d2b880f18f6611726cb9c3dfd2df3def564cdf92eebcd658a2961e527fd14e`

### PART_HF46F_G_5_HS1T: HF46F_C5274026
Manufacturer datasheet: selected order, package/pin map and electrical characteristics
[https://www.lcsc.com/product-detail/C5274026.html](https://www.lcsc.com/product-detail/C5274026.html)
Archived: `../../evidence/files/HF46F_C5274026.pdf`
SHA 256: `329a8a5fa56dd44d356d90e14e11a33b6936ee1ab193b6eb568df17e2443c54a`

## Required firmware settings

See [FIRMWARE_CONTRACT_A 2.md](FIRMWARE_CONTRACT_A 2.md) for the datasheet-derived ADC register bytes, SPI setup, calibration/readback sequence, Serial3 flow control and off-board module recovery procedure. These are untested hardware bring-up requirements, not implemented firmware.

## Supplemental primary source

[PJRC hardware serial/UART table](https://www.pjrc.com/teensy/td_uart.html), retrieved 14-Oct-2026. Exact HTML retained at `docs/research/pjrc-uart-20261014.html`; it is not falsely indexed as a datasheetPDF. Serial3 TX14/RX15/CTS19 and arbitrary digitalRTS are documented here.

Drawing conventions follow workspace `docs/DESIGN_RULES.md`, adopted from TiagoGala and GregorGross. Every final rendered sheet must be inspected at page and circuit scale.
