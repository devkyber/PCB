# Motor filter and input-capacitor selection - A7

Current CAD retains the A6/A7 inductance and capacitor values. On 2026-10-05,
L3 changed to Coilank APS1365M3R3DW / C54431777 for stock availability. See
[JLCPCB substitution review](JLCPCB.md) for ratings and the new footprint.
Bourns-specific paragraphs below record the earlier selection.
Earlier alternatives and revision-specific checks below are historical.
Superseded check files and temporary numerical runs are preserved in the
recovery archive listed in `../review/records/cleanup-record.json`; current checks are in
`../review/records/schematic-checks-A9.json`. Do not restore an earlier value from this history.


Owner request, 2026-09-30: decide L3, C16-C19 and C5, and inspect input
capacitor values against the active LMR51450 datasheet. This is a schematic
selection for human review, not a verified PCB or hardware release.

**DC-bias verification follow-up, 2026-09-30:** the exact Murata family curve
has now been obtained and archived. It replaces the ADI proxy below. The
existing input pair has little room-temperature margin; three matching 10 uF
input parts per converter are now recommended. This is a review finding only:
the A7 CAD still contains two per converter and has not been edited.

## Adopted values

| Function | Selection | Disposition |
| --- | --- | --- |
| L3 | 3.3 uH, Coilank APS1365M3R3DW, C54431777 | 2026-10-05 stock substitution; inductance retained |
| C16-C19 | Four 10 uF / 50 V X7R 1210, Murata GRM32ER71H106KA12L, C77102 | Retain all four |
| C5 | 220 uF / 50 V, Panasonic EEU-FR1H221B, C1579630 | Retain low-impedance bulk |
| Motor input C14/C15 + C32 | Two 10 uF / 50 V X7R plus 100 nF / 50 V | Retain |
| Other converter inputs C10/C11/C30 and C12/C13/C31 | Same two 10 uF plus 100 nF bank per converter | Retain |

RT stays open: nominal 500 kHz. C35 remains 100 nF; C41/R23 remain 33 pF/1k.
Motor enable and feedback-divider wiring do not change. The 12 V and 5 V
output banks remain A6's four and five 22 uF capacitors, respectively.

## L3: calculate for this rail

TI SLUSEP7 Table 9-2 has no 22.19 V example. Use section 9.2.2.3, equations
(9)-(10), with the project's 25.2 V maximum steady battery voltage and
22.190374 V nominal output. In continuous conduction:

    dIL = Vout * (Vin - Vout) / (Vin * L * fsw)

At 500 kHz, the former 6.8 uH gives 0.779 A peak-to-peak. The adopted 3.3 uH
gives 1.606 A: 32.1% of the IC's maximum supported 5 A. This sits inside TI's
20-60% selection guideline. At the 3.5 A planning load, nominal peak current
is 4.303 A and RMS inductor current is about 3.531 A.

The choice lowers inductance rather than changing the switching-frequency
configuration. The battery-to-output headroom is small, so increasing
frequency would bring minimum-off-time foldback earlier.

Bourns specifies 18 A Irms, 30 A Isat and 6.8 mOhm maximum DCR for 3R3M.
These manufacturer test ratings are comfortably above the planning current
and the IC's 9.6 A maximum listed high-side current limit; they are not the
board's thermal rating. Approximate winding loss at the nominal planning
point is 0.085 W using maximum room-temperature DCR. Core loss and DCR
temperature rise are additional. Supplier identity was checked and archived.

A screening corner using -20% initial inductance, 405 kHz and the lower
25 C setpoint estimate of 21.549 V gives about 2.92 A ripple and 4.96 A peak
at 3.5 A output. The 405 kHz combination is an engineering screening envelope
(450 kHz oscillator minus 10%), not a guaranteed joint timing bound. These
calculations cover established regulation; startup, PFM, dropout and bias/
temperature changes of inductance are outside this simplified model.

The existing SRP1265A family footprint is retained. Its previously documented
assembly-attribute, courtyard and land-pattern review remains required before
layout; this part selection does not certify the imported footprint.

## Output capacitors: local ceramics plus bulk

C16-C19 form the local switching-ripple filter. Their combined nameplate
capacitance is 40 uF, not their actual capacitance at 22.19 V. Retaining four
keeps distributed low-impedance filtering and avoids relying on the leaded
electrolytic for the entire switching-frequency current path.

Murata's exact-family product sheet dated 2014-11-11, page 2, gives a DC-bias
curve at 25 C and 1 Vrms. Its first page explicitly lists the L and K packaging
suffixes. Approximate readings are 6.4 uF per part at 22.19 V and 5.75 uF at
25.2 V. The four motor ceramics therefore total about 25.6 uF at the nominal
motor voltage. Applying -10% initial tolerance and a separate -15% temperature
allowance gives about 19.6 uF. This is an engineering screen, not a measured
combined bias-temperature curve or a guaranteed production minimum. It
supersedes the earlier 15.9 uF proxy. C5 remains useful for load steps.

TI section 9.2.2.4 equation (13), with a provisional 0-to-3.5 A step and 5%
allowed excursion, gives 18.9 uF at 500 kHz or 23.4 uF at the 405 kHz screen.
The ceramics alone are not asserted to meet that screen under all conditions.
C5 is deliberately retained as bulk storage: its initial -20% tolerance still
leaves 176 uF under the specified capacitance test conditions. This supports
short motor-current changes without an excessive ceramic count. Capacitance
alone does not prove the loop's response or its high-frequency impedance.

For scale, a 3.5 A deficit for 50 us removes 175 uC. An ideal 220 uF capacitor
would fall 0.80 V (0.99 V at 176 uF), before ESR effects or contribution from
the ceramics and regulator. This is an illustrative pulse, not a specified
motor waveform or an assumed controller response time.

Panasonic's exact-part page lists 1.65 A ripple rating at 100 kHz and maximum
30 mOhm impedance at 100 kHz. Impedance is not a guaranteed ESR value over
all frequencies and temperatures. The nominal output ripple current is
1.606/sqrt(12) = 0.464 A RMS for the capacitor bank. Actual current sharing
depends on the installed impedances; motor pulses add current beyond that
triangular switching component.
r
C5 is not enlarged or called a regenerative clamp. With nominal 260 uF total,
only about 10.9 mJ is stored between 22.190 V and 24 V. Braking-energy handling
remains a separate unresolved architecture question.

Loaded startup must be measured. Nominal 260 uF requires approximately 1.15 A
to ramp to 22.19 V in 5 ms, or 1.80 A in 3.2 ms, before load current. Actual
ceramic capacitance is lower, but tolerance, ramp behavior and an active motor
load can change the result. The chosen bank is a practical filter/bulk starting
point, not proof that an already-stalled 3.5 A load starts without current limit.

## Input capacitors: comparison and decision

TI section 9.2.2.5 recommends 10 uF or higher high-frequency input decoupling,
X5R/X7R ceramic, voltage rating greater than maximum Vin, and a 100 nF
capacitor close to the pins. Its worked example uses two 4.7 uF / 50 V
capacitors plus 100 nF. Section 9.1 requires attention to effective capacitance.

Each of our three converters currently has two 10 uF / 50 V Murata ceramics
plus a 100 nF / 50 V bypass. A7 retained these parts before obtaining the
manufacturer curve. Nominal capacitance exceeds the worked example, with the
same bypass value and a rating approximately twice our 25.2 V input.
The 50 V rating exceeds maximum steady battery voltage;
the twice-input recommendation is a derating guideline, not a 50.4 V absolute
rating threshold. Transient limits are a separate matter.

The manufacturer's published curve is now verified. At 25.2 V it shows about
42.5% loss, or 5.75 uF per part. These are approximate graph readings; the
source is a raster chart, not a numerical CSV. The practical comparison is:

| At 25.2 V input | Existing two parts | Proposed three parts |
| --- | --- | --- |
| Nominal nameplate | 20 uF | 30 uF |
| Typical curve, 25 C / 1 Vrms | about 11.5 uF | about 17.3 uF |
| Curve scaled by 0.90 initial tolerance | about 10.4 uF | about 15.5 uF |
| Additional 0.85 temperature allowance | about 8.8 uF | about 13.2 uF |

Recommendation: add one matching 10 uF / 50 V capacitor at each converter
input, retaining each 100 nF bypass. Three parts give useful margin against
TI's 10 uF effective-capacitance recommendation under this screen. The
schematic has not been changed by this verification request. Two parts are
not proven inadequate in operation, but their small margin does not support
calling the full-condition 10 uF check closed.

The -15% factor is an independent engineering allowance based on X7R's
temperature class. It is not a verified temperature curve at 25.2 V. Neither
this multiplication nor the manufacturer's typical graph establishes an
exact guaranteed minimum across production spread, temperature, AC amplitude
and aging. The source curve uses 1 Vrms; actual converter ripple is smaller,
so it is not a direct operating-impedance measurement. No guaranteed minimum
under all those simultaneous conditions is specified in this retrieved sheet.

The owner authorized access to Murata's live SimSurfing viewer. Both exact
part search and P/N List Selection returned no matching part numbers. Thus
no current numerical CSV or combined bias-temperature curve was obtained;
the result above is explicitly based on the archived manufacturer chart,
not a claimed live simulation. This does not establish product lifecycle status.

As an independent scale check, the ideal buck input-ripple model

    dVin = Iout * D * (1-D) / (Cin * fsw), D = Vout/Vin

with the earlier conservative 7.96 uF proxy and 405 kHz gives about 0.11 V peak-to-peak for the motor converter
at 25.2 V input, and at most about 0.23 V for the 12 V converter across the
planned battery range. ESR, wiring inductance, source impedance, simultaneous
rail switching and transients are excluded. These are sizing estimates, not
an achieved input-ripple specification.

Place the ceramics directly between VIN and PGND with a short return loop.
The common GND net name is correct: physical placement at the power-ground
pad determines the loop. C1, the shared 220 uF battery bulk, stays in place but
does not replace these local capacitors. C35 also stays 100 nF / 50 V, matching
TI section 9.2.2.6's 100 nF bootstrap recommendation (16 V or higher).

## Sources and remaining validation

- [TI LMR51450 SLUSEP7](https://www.ti.com/lit/ds/symlink/lmr51450.pdf), pp.19-23,
  sections 9.1 and 9.2.2.3-6. Exact PDF is already in evidence/index.yaml.
- [Bourns SRP1265A](https://www.bourns.com/docs/product-datasheets/srp1265a.pdf),
  3R3M row and common mechanical drawing; archived exact PDF and supplier record.
- [Panasonic EEUFR1H221B](https://industrial.panasonic.com/ww/products/pt/aluminum-cap-lead/models/EEUFR1H221B),
  exact-part ratings; archived FR family datasheet also retained.
- [ADI MAXREFDES1092](https://www.analog.com/en/resources/reference-designs/maxrefdes1092.html),
  input-capacitor calculation and exact Murata family. Its converter is different;
  its 48% loss at 28 V agrees with the retrieved Murata graph. It is now only
  a cross-check, not the source for our operating-voltage capacitance estimates.
- [Murata exact-family characteristic sheet, RS-hosted](https://docs.rs-online.com/2a0d/0900766b813885a3.pdf),
  dated 2014-11-11, p.1 identity and p.2 DC-bias plot. Exact bytes and SHA-256
  are recorded in evidence/index.yaml. Original plot and reading method are in
  evidence/characterization/GRM32ER71H106KA12-Murata-provenance.json.
- [Murata SimSurfing measurement conditions](https://ds.murata.com/simsurfing_data/pdf/en-us/mlcc/sim_mlcc_measuringcond_e.pdf),
  pp.7-10, explaining DC-bias and temperature measurement conditions. This
  general document does not provide an exact-part minimum capacitance.

Motor counts and L3 remain selected. The input count recommendation above is
pending a specific CAD edit request. Typical DC-bias characterization is now
archived; remaining hardware verification covers operating capacitance/impedance,
input heating/ripple, loop stability, loaded
startup, motor-current steps, low-battery dropout and braking behavior. These
are not additional capacitor-count alternatives. No PCB or fabrication signoff
is created by A7. Native comparison and visual review are recorded separately.
