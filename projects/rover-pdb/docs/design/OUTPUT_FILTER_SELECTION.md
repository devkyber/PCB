# Frequency and output-filter selection — A6 / A7

Current A9 retains the adopted A6/A7 filter selections in this document.
Earlier alternatives and revision-specific checks below are historical.
Superseded check files and temporary numerical runs are preserved in the
recovery archive listed in `../review/records/cleanup-record.json`; current checks are in
`../review/records/schematic-checks-A9.json`. Do not restore an earlier value from this history.


A7 selects the motor rail separately: L3=3.3 uH / C1329348, C16-C19 remain
four 10 uF / 50 V, and C5 remains 220 uF / 50 V. Input banks and nominal
500 kHz remain unchanged. See [MOTOR_FILTER_SELECTION.md](MOTOR_FILTER_SELECTION.md).
The A6 12 V / 5 V decision below remains current; later sections labelled
historical do not override A7's motor inductor.

## Adopted capacitor counts

On 2026-09-30 the owner asked to decide and apply practical numbers close
to the datasheet, with some conservative margin. The adopted A6 choice is:

| Rail | Inductor | Output ceramic bank | Typical effective capacitance | TI Table 9-2 reference |
| --- | --- | --- | ---: | ---: |
| 12 V | 6.8 uH | C20-C23: 4 x 22 uF / 25 V | 35.8 uF | 20 uF |
| 5 V | 4.7 uH | C24-C28: 5 x 22 uF / 25 V | 87.5 uF | 66 uF |

Both use Samsung CL32B226KAJNNNE / C309062. Typical effective values come
from the exact archived DC-bias curve at the nominal rail voltages. Applying
the initial -10% tolerance gives approximate planning values of 32.2 uF and
78.8 uF. These are estimates, not guaranteed all-temperature minima.

The common method is to start from TI's effective-capacitance reference,
account for our actual part's DC-bias loss, and leave practical margin.
Four parts on 12 V avoid the small margin of three under combined variation;
five on 5 V avoid the approximately 63 uF estimate of four after initial
-10% tolerance. Six are not retained merely because they were already drawn.
No identical count or arbitrary identical percentage margin is required.

Removed C29/C42/C43. Retained the servo-side C2 470 uF bulk capacitor,
inductors, dividers, feed-forward networks, RT-open nominal 500 kHz and motor
rail. The remaining components keep their references, UUIDs and properties.

This supersedes the conversational three-on-12-V/six-on-5-V proposal and the
A4/A5 six-part banks. The previous conservative 0-to-full-load/405 kHz screen
is no longer the acceptance basis for choosing these counts: the 12 V bank
does not meet its 37.1 uF screen. The owner's 0.5% ripple / 5% load-step
figures remain bench goals, to check with the actual loads and board. A6 does
not guarantee those figures from a typical-capacitance sum.

Sources: [TI Table 9-2 and section 9.2.2.4](https://www.ti.com/lit/ds/symlink/lmr51450.pdf#page=20),
[Samsung exact-part characterization](https://product.samsungsem.com/mlcc/CL32B226KAJNNN.do).
Native delta and rendered-sheet review: capacitor-A6-checks.json. The following
A5/A4 sections are historical rationale and must not override current CAD.

## Historical A5 5 V choice

Owner request, 2026-09-30: match the inductor to TI's example and keep the
capacitor explanation practical. **L2 is now 4.7 uH, Bourns SRP1265A-4R7M,
LCSC/JLCPCB C780205.** RT stays open for nominal 500 kHz. This matches the
LMR51450 **Table 9-2**, 5 V row, in TI SLUSEP7 p.20. R11/R16 (100k/19.1k)
and C40/R22 (33p/1k) already match that row.

**Keep C24-C29: six 22 uF / 25 V X7R ceramics in parallel.** The selection is:

1. TI's example asks for **66 uF after derating**, not merely 66 uF printed on
   the purchased parts. Ceramic capacitance decreases under DC voltage.
2. Samsung's typical curve for our exact part gives **about 17.5 uF per part
   at 5 V**. Six in parallel therefore provide about **105 uF effective**,
   compared with their 132 uF nameplate sum. Four would provide only about 70 uF,
   leaving little margin over TI's reference before other variation.
3. The existing six-part bank also exceeds the previously selected load-step
   screening requirement of about 71 uF. With L2 changed to 4.7 uH, the previous
   ripple screen requires about 52 uF, still below that step requirement. There
   is no need to add capacitors for this inductor change.

The bank absorbs the inductor's ripple current and supplies the temporary
difference between load current and inductor current. Since dV/dt = I/C, more
capacitance reduces the voltage change for a given current imbalance. Parallel
connection puts every capacitor across the same 5 V and GND nodes: capacitances
add, ripple current is shared, and the bank's ESR is generally reduced with
good placement. It does not multiply the voltage rating.

The existing C2 470 uF / 16 V electrolytic near the servo connectors provides
additional bulk storage. It is not counted as a substitute for local converter
ceramics because the connecting traces have impedance. These are practical
starting selections, not a reason to keep adding capacitance indefinitely;
startup and transient behavior are checked on the assembled board. The 105 uF
number is a typical estimate, not a guaranteed minimum.

At VIN=25.2 V, VOUT=4.988 V and 500 kHz, the new L2 gives about 1.703 A
peak-to-peak ripple and 3.251 A peak current at the provisional 2.4 A load.
Bourns specifies 13.5 A Irms, 28 A Isat and 8.4 mOhm maximum DCR for 4R7M.
The purchased-part identity is preserved in supplier evidence; the existing
shared family footprint remains subject to the corrections in DESIGN_BASIS.md.

A5 changes only L2's three selection fields, root/5 V revisions and three
explanatory notes. All capacitor parts and wires are unchanged. All 88 physical
symbols, pin identities and 36 connected nets are preserved. See
inductor-A5-checks.json for native verification. The detailed A4 basis below is
retained so the earlier capacitor decision remains traceable.

Sources: [TI Table 9-2 and section 9.2.2.4](https://www.ti.com/lit/ds/symlink/lmr51450.pdf#page=20),
[Samsung exact-part characterization](https://product.samsungsem.com/mlcc/CL32B226KAJNNN.do),
[Bourns SRP1265A datasheet, p.1](https://www.bourns.com/docs/product-datasheets/srp1265a.pdf),
[JLCPCB C780205 identity](https://jlcpcb.com/partdetail/SRP1265A-4R7M/C780205).

## A4 capacitor decision and calculations

Owner-selected provisional targets, 2026-09-30: **0.5% peak-to-peak output ripple and 5% load-step deviation**. These are dynamic targets, not a guarantee of total DC accuracy or proof that every connected load accepts these excursions.

A4 adds **C42/C43** to the 12 V output: six Samsung CL32B226KAJNNNE / LCSC C309062 capacitors, each 22 µF / 25 V. Other circuit connections and components remain unchanged. The output-capacitor selection is a review-stage design; effective capacitance, ESR, loop response and startup still require validation. The preceding A3 audit remains in SCHEMATIC_FIX_REVIEW.md.

## Why RT is open

TI SLUSEP7 p.3 pin table and p.14 §8.3.4 explicitly define open RT as the nominal **500 kHz** selection. It is a supported configuration, not an accidentally floating control pin. RT shorted to ground selects 1 MHz; a resistor sets another frequency. Table 8-1 includes 84.5 kΩ for nominal 200 kHz and 31.6 kΩ for nominal 495 kHz. Adding the latter does not improve this design merely by making the pin look connected.

The original replacement used TI's 500 kHz reference circuits as the starting point. This was not the outcome of a completed efficiency/EMI/thermal optimization. For 12 V and 5 V it gives a useful compromise between filter size and switching loss. Higher frequency reduces the L/C required for a given ripple/transient target but raises frequency-dependent switching losses. Lower frequency reduces those losses while usually requiring a larger filter. Compare the whole filter and thermal design before changing RT; see TI p.21 §9.2.2.2.

The selected **S** variant uses PFM and spread spectrum. Thus 500 kHz is not an exact frequency at all loads. TI lists 450–550 kHz for the open-RT oscillator, ±10% spread, light-load PFM and high-duty-cycle foldback. Calculations at 500 kHz alone are insufficient.

### The motor rail warrants a separate frequency decision

For a 22.190 V output, the ideal input voltage before minimum-off-time foldback is

\[
V_{IN,min}=\frac{22.190}{1-f_{SW}\,135\mathrm{ns}}.
\]

| Nominal clock | Ideal minimum VIN before off-time foldback |
| --- | ---: |
| 200 kHz | 22.81 V |
| 500 kHz | 23.80 V |
| 1 MHz | 25.65 V |

These use TI's typical timing and ignore conduction losses; they are not guaranteed dropout thresholds. At 1 MHz this motor setpoint would already encounter off-time foldback at the planned 25.2 V full battery. Consequently, raising all three clocks merely to reduce capacitor count is a poor starting choice.

There are two useful motor candidates: 500 kHz with a smaller L3, or a lower programmed frequency with the present 6.8 µH L3. At 200 kHz, that present inductor gives about 1.95 A ripple at VIN 25.2 V, or 39% of the IC's 5 A rating. The A3 recommendation for 3.3 µH was conditional on 500 kHz. It is not a universal inductor value independent of RT. Neither motor alternative is adopted by A4; changing frequency also requires control-loop, capacitor and timing checks.

## Capacitor calculation used for A4

The provisional step amplitudes are **0 → 3.0 A** on 12 V, **0 → 2.4 A** on 5 V and **0 → 3.5 A** on the motor rail. These come from planning loads; measured load amplitudes and slew rates can change the selection.

TI p.22 §9.2.2.4 gives:

\[
\Delta V_{ESR}=\Delta i_L\,ESR,
\qquad
\Delta V_C=\frac{\Delta i_L}{8f_{SW}C_{eff}},
\qquad
C_{eff}>\frac{3\Delta I_{load}}{f_{SW}\Delta V_{step}}.
\]

The last expression is TI Equation (13), a simplified load-step screening model. The analysis assigns half the 0.5% ripple allowance to capacitance and half to ESR, conservatively. A **405 kHz** screening clock combines 450 kHz with another −10% for spread; this is a conservative engineering envelope, not a guaranteed joint bound. PFM transition delays and actual closed-loop response are not captured by these equations.

| Rail; A4 inductor (L2 superseded by A5 above) | C from ripple screen at 405 kHz | C from step screen at 405 kHz | ESR ripple allocation at 405 kHz |
| --- | ---: | ---: | ---: |
| 11.989 V; 6.8 µH | 23.5 µF | **37.1 µF** | 13.1 mΩ |
| 4.988 V; 6.8 µH | 36.0 µF | **71.3 µF** | 8.58 mΩ |
| 22.190 V; 6.8 µH | about 5.35 µF | **23.4 µF** | about 57.7 mΩ |

The motor row applies only at a regulated 25.2 V input operating point with the assumed clock. Foldback and dropout require separate analysis. At a representative 200 kHz regulated operating point, Equation (13) instead gives about **47.3 µF** for the same motor step. That does not establish a guaranteed minimum foldback frequency.

### 12 V: increase four ceramics to six

TI p.20 Table 9-2 lists 2 × 10 µF **after derating** for its 12 V / 500 kHz reference. That is a reference filter value; Equation (13) supplies the application-specific load-step requirement. A different step amplitude or allowance may require more than that table value.

Samsung's exact 25 °C DC-bias characterization gives about 8.95 µF per selected nominal 22 µF capacitor at 11.989 V. The former four-capacitor bank therefore gives about 35.8 µF typically. That exceeds the table's 20 µF reference but falls below this new 37.1 µF step screen even before tolerance or temperature allowances. This explains the change from the preceding audit's provisional advice to retain four.

The adopted six-capacitor bank provides approximately **53.7 µF typically at 12 V**. Samsung also publishes a joint biased-temperature curve at 12.5 V: its lowest plotted capacitance from −55 to +125 °C is about 33.83% of nominal. Applying that typical characterization and the initial −10% tolerance to six parts gives a **40.2 µF planning estimate**. Do not multiply an additional temperature loss into that figure: temperature under bias has already been included.

That estimate is not a guaranteed minimum. Aging, the supplier's characterization limits, actual temperature range, voltage dependence and the full feedback-voltage envelope still need a documented margin. A4 makes the requirement and the evidence visible on the sheet; it does not claim that a typical curve guarantees the targets on hardware.

C20–C23 retain their references and UUIDs. C42/C43 are parallel additions with the same value, footprint, MPN and supplier identity; all six have a link to the manufacturer characterization. The bank was re-spaced so fields remain readable. The DC value labels stay 22 µF because that is the purchased part rating.

### 5 V: retain six ceramics and evaluate the servo bulk

The same selected 22 µF part provides about 17.51 µF typically at 4.988 V. Six parts give about **105.0 µF**, above the 71.3 µF transient screen. Four would give only about 70.0 µF typically, already below that screen before additional allowances. Therefore this revision does not remove C28/C29 just to reduce the drawing's count.

C2 adds 470 µF nominal bulk at the servo circuit. It must be included in startup and low-frequency loop evaluation, with its tolerance and ESR. At high frequency the route to C2 has impedance: the bulk cannot simply substitute for local ceramics. Exact combined capacitance/ESR over the operating range remains to be validated; 105 µF typical is not a guaranteed effective minimum. A5 adopts TI's 4.7 µH L2: the 405 kHz capacitive ripple requirement is about 52.0 µF and the ESR allocation about 5.93 mΩ. The six-part bank is retained.

### Motor: retain the bulk while resolving the actual network

There is no 22.19 V row in TI Table 9-2, so copying the 12 V capacitor pair is unjustified. C16–C19 are four Murata 10 µF / 50 V ceramics and C5 is a Panasonic 220 µF / 50 V electrolytic. The bulk supplies ample nominal low-frequency storage relative to the capacitance screen, but that does not validate the high-frequency ESR, control loop or loaded startup. The exact Murata bias curve and Panasonic impedance/current ratings must be applied to the combined network.

Do not remove C5 solely to resemble TI's basic drawing. Do not enlarge it as an assumed regeneration solution either. A4 retains this bank while the already-listed motor startup, braking, power-down and frequency decisions remain open.

## Verification and independent cross-check

The A4 candidate was checked against the current native CAD, not regenerated from an old intent. The only new electrical connections are C42/C43 between +12V and GND. All 86 existing physical-component identities and pin UUIDs remain; unrelated symbols, five other child sheets, project settings and libraries are unchanged. There are now 88 physical components and 36 connected nets. All seven rendered candidate sheets were visually inspected. Native ERC reports zero errors and warnings; this is not hardware validation or owner sign-off.

Sources:

- [TI LMR51450 datasheet](https://www.ti.com/lit/ds/symlink/lmr51450.pdf), printed pp.3, 6, 14–16, 18, 20–22. Exact archived copy is in `../../evidence/files/LMR51450SDRRR_lmr51450_7f80073eb777.pdf`.
- [Samsung CL32B226KAJNNN characterization](https://product.samsungsem.com/mlcc/CL32B226KAJNNN.do), DC-bias and biased-temperature curves. Exact downloaded response, extracted chart arrays and their provenance are in `../../evidence/characterization`.
- Reproducible numerical screen: `.pcb-copilot/fix-audit/output-filter-screen.json`. Exact native delta and CAD hashes: `capacitor-A4-checks.json`. This report's motor row uses the retained 6.8 µH; the numerical file also contains the previously discussed 3.3 µH alternative.
