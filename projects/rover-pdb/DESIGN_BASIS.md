# Design basis - A10

Current schematic revision: **A10, 2026-10-04**. Seven editable KiCad sheets
capture the owner's selected circuit. A9 derives motor enable from local
VBAT, restores USB-only Pico power and identifies the optional expansion
header. Converter models, frequencies, inductors and capacitor banks remain
as selected. See `docs/design/POWER_DECISIONS.md` for enable/USB calculations and sources.

A10 removes F1 at the owner's request. P1 and the shunt input share
BAT_SWITCHED; the old VBAT_FUSED name is absent from current connectivity.
The onboard fuse holder and its mounting hole are removed from the PCB.
No upstream fuse is assumed fitted; use an externally fused battery lead
before treating the input wiring as protected. The Jetson converter remains
12 V. On 2026-10-04 the owner clarified that 12 V was chosen for future
XM430/XM540 actuator expansion; retain that shared P2/P3 voltage. This does
not change the existing 22.190 V motor distribution or its four-pin interface.
P3 shares U2's current budget with the Jetson; its availability is not a
dedicated motor-current rating. Future actuator/interface sizing is separate.

The owner reported positive personal review of A8 and requested these final
changes. Author verification of A9's delta is separate from that report;
no named, hash-bound fabrication sign-off or blanket waiver is recorded.
On 2026-10-01 the owner requested completion of PCB design. The physical baseline
below incorporates their later saved geometry, reconciled on 2026-10-02.
This authorizes placement and routing while preserving
the reviewed circuit; it is not a manufacturing release or a technical waiver.
`docs/design/PCB_DESIGN.md` retains the pre-layout checklist and source locators.

Current CAD supersedes historical guide examples and the initial handover,
which remains unchanged in `evidence/PDB_Design_Handover.md`. Exact downloaded
source bytes and hashes are recorded in `evidence/index.yaml`. Preserve
manual edits under `AGENTS.md`.

## Authorized PCB baseline

- Outline: the owner's saved 77.5 x 100 mm rectangle with square corners,
  absolute X=99..176.5 mm and Y=54.2..154.2 mm, with four M3 mounting holes.
  This supersedes the earlier 80 x 100 mm layout target and original 100 x 100 mm
  outline. Preserve the manual narrowing/repositioning. Exact hole centers,
  fastener clearances and cable exits must be visible in the native board and
  review drawing; no chassis-fit evidence is inferred from the outline choice.
- Mechanical implementation: 3.2 mm NPTH holes in the owner's current pattern,
  recorded in `docs/design/PCB_DESIGN.md` relative to the current top-left corner;
  reserve a 3.5 mm radius at each for fastener clearance.
  Use 1.6 mm FR4 and green solder mask. The current native finish is
  "User defined"; select and confirm finish in the JLCPCB order (the older HASL
  proposal was not a verified checkout choice).
  These are implementation selections, not independently supplied chassis data.
- Construction: two copper layers, 1 oz copper on each side, selected for an
  economical JLCPCB implementation. This replaces the earlier 2 oz proposal.
  `jlcpcb_2layer_default` is retained. Review and release now independently check
  the dated two-layer / 1 oz / green-mask geometry baseline; they do not verify
  a supplier checkout choice. Check thickness, copper and finish in both
  board setup and supplier order before release.
- P1-P4: surface wire-solder pads, with the existing electrical pin numbering.
  Their mechanical land geometry and harness strain relief need explicit
  review. The owner removed their separate retention holes; provide external
  cable strain relief. They are PCB copper features, not purchased headers. A layout request
  does not authorize unrelated schematic changes.
- Pico USB access: the current owner save has no USB approach keepout. The
  previous P3 envelope was provisional and has been removed. Establish actual
  plug, socket/header and cable-bend clearance before recording physical fit or
  defining a replacement envelope; a top-view overlap with low-profile parts
  does not alone prove interference.
- Converter layout: follow TI SLUSEP7 section 9.5 and Figure 9-10, plus the
  archived SNVU838A EVM copper views. Keep each input bypass and PGND loop
  compact, SW small, BOOT local and feedback/AGND away from switching copper.
  The EVM's four-layer thermal performance cannot be transferred to this board.
- Current measurement: route separate Kelvin takeoffs from RS1 to INA226;
  keep load-current copper out of the sensing path. See Bourns CSS2H-2512 and
  TI INA226 layout guidance already indexed in `docs/design/PCB_DESIGN.md`.
- Verification: use complete native schematic/PCB parity and two fresh DRC
  runs after zone fill. Review actual copper and assembly images. Record width,
  via, ground-return and thermal decisions against the selected 1 oz geometry.
  No model or passive-network simulation validates the eventual PCB thermals.
- Clearance implementation: 0.15 mm absolute board floor, 0.20 mm Default
  netclass, and a local 0.15 mm U1 footprint override for INA226 pad spacing
  and escape. Converter/free copper retains 0.20 mm; no net-wide relaxation
  or converter clearance-area exception is adopted.

`docs/design/PCB_DESIGN.md` expands the implementation and review checklist. This section
and `REQUIREMENTS.md` are included in the repository's source fingerprint, so
the manufacturing assumptions remain bound to any later human sign-off.

## Adopted circuit

P1 positive -> RS1 -> VBAT; all returns are GND. U1 measures both the
2 mOhm shunt drop and VBAT after the shunt. Positive discharge current enters
U1 IN+ from the battery side. Pico supplies U1 and the two I2C pull-ups through
its USB-derived 3V3 output. Pico is powered only through its USB connector;
carrier VBUS/VSYS pins 40/39 are NC and no PDB backup path is fitted.

| Function | Captured values and references |
| --- | --- |
| Jetson converter | U2 LMR51450SDRRR, L1 6.8 uH, R10 100k / R17 7.15k, R13 100k EN pull-up |
| Servo converter | U3 LMR51450SDRRR, L2 4.7 uH, R11 100k / R16 19.1k, R14 100k EN pull-up |
| Motor converter | U4 LMR51450SDRRR, L3 3.3 uH, R12 100k / R18 3.74k, R15 100k EN pull-down |
| Converter inputs | C10/11 (U2), C12/13 (U3), C14/15 (U4): 2 x 10 uF / 50 V each; C30/31/32: 100 nF |
| Converter support | C33/34/35: 100 nF / 50 V, 0805, C1711, BOOT-SW; C36/37/38 removed because this IC has no external VCC pin |
| Feed-forward | C39/R21, C40/R22, C41/R23: 33 pF in series with 1k, each branch across its top feedback resistor |
| Analog returns | U2/U3/U4 AGND and divider bottoms use separate local nets, joined to GND at the exposed pad through NT1/NT2/NT3; PCB copper features, no purchased parts |
| Outputs | U2 C20-23: 4 x 22 uF; U3 C24-28: 5 x 22 uF plus C2 470 uF; U4 C16-19: 4 x 10 uF plus C5 220 uF |
| Motor enable | Local VBAT -> R19 100k -> SW_SUPPLY; R24 22k from SW_SUPPLY to AGND_4. SW1 pin 1=SW_SUPPLY, pin 2=MOTOR_EN/U4 EN, pin 3=NC. R15 100k defines OFF. All local to sheet 5. |
| DYNAMIXEL | J1 pin 2 NC; J5/6/7 pin 2 VMOTOR; all four share GND, D+, D- |
| Indicator | VMOTOR -> R20 3.9k / 0.25W -> D2 anode (manufacturer pin 1); D2 pin 2 cathode -> GND; approximately 5 mA |
| Expansion | P3 +12V/GND; P4 +5V/GND; initially unwired. J9 DNP / BOOMELE C37208: 3V3, GP18, GP19, GP20, GP21, GND. |
| Pico power | USB connector -> module's onboard diode -> VSYS -> onboard 3V3 regulator. Q1 removed; carrier pins 39/40 intentionally NC. |

JP1 remains absent. The owner reused J8 for SERVO AUX with R6 10k; both remain. SW1 and the indicator are integrated into the motor
sheet. NT1-NT3 preserve distinct schematic nets but connect them with a small
local copper bridge. Locate each at its converter's exposed PGND pad during
layout, rather than joining analog and switching return paths elsewhere.

## Pin verification

### Reference comparison and adopted decisions

These rows compare the existing reviewed circuit with archived manufacturer
implementations. They document a design basis, not measured performance or
human release approval. Evidence identities and unchanged downloaded bytes
are in `evidence/index.yaml`.

| References | Function | Manufacturer implementation | Reference choice | Current circuit | Source locator | Decision and limits |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Current/bus monitor | TI INA226EVM, SBOU276 | 3.3 V supply; 100 nF plus 1 uF bypass; configurable address, input filter and shunt | 100 nF local bypass; fixed grounded address pins; 2 mOhm shunt; direct sense inputs; 4.7k pull-ups; ALERT unused | [SBOU276](evidence/files/INA226AIDGSR_sbou276_e5dc5b492908.pdf), pp.19-23, Fig.6-1; [INA226 datasheet](evidence/files/INA226AIDGSR_ina226_c9b67f886d4a.pdf), supply/layout guidance | Deviate: retain application-specific shunt, straps and pull-ups; optional EVM filter and extra bulk bypass are omitted. Fig.6-1 labels pull-ups 1k while its BOM says 4.7k; do not treat that inconsistency as an exact-value mandate. Validate rise time/noise. |
| U2 | 12 V buck | TI LMR51450 EVM and datasheet | EVM is 3.3/5 V; datasheet 12 V/500 kHz row uses 6.8 uH, 20 uF effective, 100k/7.15k, 33pF/1k | 6.8 uH; four 22 uF ceramics; same divider and feed-forward values; RT open | [SLUSEP7](evidence/files/LMR51450SDRRR_lmr51450_7f80073eb777.pdf), Table 9-2 and section 9.5; [SNVU838A](evidence/files/LMR51450SDRRR_snvu838a_6086805dfb70.pdf), pp.7-10 | Deviate: capacitor bank uses bias-derated margin, not nominal 20 uF. Two-layer thermal behavior requires validation; EVM copper is a layout reference, not this board's current rating. |
| U3 | 5 V buck | TI LMR51450 EVM and datasheet | 500 kHz row uses 4.7 uH, 66 uF effective, 100k/19.1k, 33pF/1k | 4.7 uH; five 22 uF ceramics and 470 uF bulk; matching divider and feed-forward values; RT open | [SLUSEP7](evidence/files/LMR51450SDRRR_lmr51450_7f80073eb777.pdf), Table 9-2; [SNVU838A](evidence/files/LMR51450SDRRR_snvu838a_6086805dfb70.pdf), pp.7-10; OUTPUT_FILTER_SELECTION.md | Deviate: retained bulk and derated ceramic bank serve the selected servo load; verify startup and loop/load-step behavior with that actual bank. |
| U4 | Approximately 22.2 V motor buck | TI LMR51450 EVM and general design equations | EVM does not demonstrate this motor voltage, load or regenerative behavior | 3.3 uH; four 10 uF ceramics plus 220 uF; 100k/3.74k; 33pF/1k starting network; switched EN | [SLUSEP7](evidence/files/LMR51450SDRRR_lmr51450_7f80073eb777.pdf), sections 8-9; [SNVU838A](evidence/files/LMR51450SDRRR_snvu838a_6086805dfb70.pdf), schematic/layout; MOTOR_FILTER_SELECTION.md and POWER_DECISIONS.md | Deviate: calculated application circuit retained as reviewed. Dropout, startup, stability, thermal performance and motor energy remain explicit validation items. |
| SKT1 | Socketed Pico 2 carrier | Raspberry Pi Pico carrier demo in Hardware design with RP2040 | Manufacturer demo documents module integration and USB device power; other carrier power options are optional | Pico 2 USB-only; carrier VBUS/VSYS NC; 3V3 powers external U1/pull-ups; selected GPIO only | [Manufacturer carrier demo](evidence/files/Raspberry_Pi_Pico_hardware-design-with-rp2040_51c4f430153f.pdf), chapter 3, pp.15-18; [exact Pico 2 datasheet](evidence/files/Pico_2_pico-2-datasheet_cbcfaf881018.pdf), sections 3 and 5.4-5.5; [socket drawing](evidence/files/254PM-1x20P-V_f0f6c3d8697d24302649e706e8fbe0d7_5778f815e84c.pdf) | Match: USB device powering and module-output 3V3 principle. The demo uses RP2040 Pico, so comparison is limited to compatible carrier interfaces; exact Pico 2 pinout/power limits and socket mechanics come from their own sources. Do not adopt the demo's optional second source or four-layer layout. |

The newly archived INA226EVM and Raspberry Pi carrier-demo pages were compared
against these existing choices on 2026-10-01. The carrier guide is indexed as a
manufacturer evaluation/demo implementation because it contains the manufacturer's
actual demo-board schematic and PCB examples; it is not relabelled as an exact
Pico 2 design or a validation of this PDB. No circuit was changed for this comparison.

The active converter is the PFM/spread-spectrum LMR51450SDRRR variant. TI
SLUSEP7 pin table (p.3) and SNVU838A EVM schematic (p.7) are the source for
`rover:LMR51450SDRRR`, whose readable symbol retains all 13 numbered pads:

| Pads | Function / captured connection |
| --- | --- |
| 1-3 | SW, inductor input and bootstrap capacitor return |
| 4 | BOOT, 100 nF capacitor to SW |
| 5 | PG, unused and explicitly NC |
| 6 | RT, explicitly NC for nominal 500 kHz |
| 7 | FB, resistor midpoint and feed-forward branch |
| 8 | AGND, local analog-return net with divider bottom |
| 9 | EN, always-on pull-up for U2/U3; switched enable for U4 |
| 10-12 | VIN, monitored VBAT and local input capacitors |
| 13 | PGND/exposed pad, GND and local NT connection to AGND |

The replacement has no VCC, BIAS, SS/TRK or SYNC/MODE terminals. Old LM73606
support connections must not be carried over by pin number. Its old library and
source evidence are historical, not authorities for the active converter circuit.

INA226AIDGSR uses the DGS 10-pin package: A1=1, A0=2, ALERT=3,
SDA=4, SCL=5, VS=6, GND=7, VBUS=8, IN-=9, IN+=10. The KiCad
MSOP-10 3 x 3 mm, 0.5 mm pitch footprint names the same package geometry
that TI calls VSSOP; final land dimensions still need the layout review.

The Pico 2 symbol uses the official 40-pin Pico 2 assignment. Its two GND
groups are modeled as power inputs, not competing power outputs. All eight
ground pins are connected. The module's debug pads are not socket contacts.
Carrier pins 39/40 are NC; GPIO18-21 go to J9. USB powers the module internally.
ADC reference, RUN, 3V3_EN and the remaining unused GPIO retain explicit NCs.

Kento's package drawing labels pin 1 as anode and pin 2 as cathode, opposite
the generic KiCad LED numbering. Both the local symbol and matching footprint
use the manufacturer's numbering; the cathode mark remains on the cathode side.

## Calculated checks

The output divider equation is VOUT = 0.8 * (1 + Rtop/Rbottom). Using independent
1% resistors and the specified 25 C feedback limits 0.792 / 0.8 / 0.808 V gives
the following arithmetic bounds. These are not all-temperature guarantees and
exclude ripple, PFM offset, dynamic overshoot, dropout and wiring loss.

| Rail | Nominal | Min / max arithmetic bound at 25 C |
| --- | ---: | ---: |
| U2 | 11.989 V | 11.650 / 12.337 V |
| U3 | 4.988 V | 4.856 / 5.124 V |
| U4 | 22.190 V | 21.549 / 22.849 V |

With VIN=25.2 V, L1=6.8 uH, L2=4.7 uH, L3=3.3 uH and f=500 kHz,
the ideal continuous-mode relation dI = VOUT*(VIN-VOUT)/(VIN*L*f) gives:

| Rail | Ripple peak-to-peak | Planning load | Calculated peak current |
| --- | ---: | ---: | ---: |
| U2 | 1.849 A | 3 A | 3.924 A |
| U3 | 1.703 A | 2.4 A | 3.251 A |
| U4 | 1.606 A | 3.5 A | 4.303 A |

These are nominal calculations, not current-limit or worst-case ratings. Include
inductor tolerance/bias, switching-frequency spread and foldback in validation.
The retained Bourns 6R8M is rated 11.5 A RMS, 18 A saturation and 11.5 mOhm
maximum DCR. Its rating does not validate converter control-loop behavior.
The selected L2 4R7M has 13.5 A Irms, 28 A Isat (20% inductance drop) and
8.4 mOhm maximum DCR at the manufacturer's stated conditions. At the 2.4 A
planning load its nominal inductor RMS current is about 2.45 A. This is a
component selection check, not a PCB thermal rating.
L3 uses Coilank APS1365M3R3DW / C54431777 (2026-10-05): 3.3 uH +/-20%,
18.3 A typical Irms, 28.75 A typical Isat and 6 mOhm maximum DCR. The supplier
PDF does not state the current-rating test thresholds; these are not guaranteed
board ratings. See the dated substitution review in `docs/design/JLCPCB.md`;
nominal RMS current is 3.531 A at the planning load. The corner screen and
retained capacitor selection are recorded in `docs/design/MOTOR_FILTER_SELECTION.md`.

The 12 V and 5 V inductors now match TI's table. The capacitor banks and the
22.2 V motor filter still need normal bench validation.
The 33 pF/1k feed-forward networks follow the 5 V/12 V table as initial values;
their use on the motor rail is a tuning starting point, not a demonstrated
stability result. Verify capacitor DC bias/ESR, load steps, loop margin and
startup. Do not treat nominal capacitance as effective capacitance.

### Motor dropout, startup and shutdown

At 500 kHz with typical 135 ns minimum off-time, ideal maximum duty before
foldback is 0.9325. Regulating 22.190 V then needs at least 23.797 V input before
conduction loss. Using typical 5 us maximum on-time gives an ideal foldback duty
of about 0.9737 and a 22.790 V input boundary. A simple 3.5 A conduction estimate
with typical 78/45 mOhm switches and maximum 6 mOhm inductor DCR raises this
to about 23.09 V. These estimates are not guaranteed thresholds; hot resistance,
layout and operating mode change them. This buck cannot maintain 22.2 V across
the 19.8-25.2 V battery range.

The nominal 260 uF motor bank needs about 1.15 A to rise to 22.190 V in 5 ms.
At a 3.2 ms ramp this becomes 1.80 A; with an already-active 3.5 A load the total
is 5.30 A, before capacitance tolerance. Confirm loaded startup and current-limit
behavior on hardware rather than claiming a guaranteed full-load start.

U2/U3's 100k EN pull-ups provide automatic start, not battery undervoltage
protection. U4 uses the local-VBAT divider: R19=100k, R24=22k before SW1,
and R15=100k from EN to AGND_4. When ON, R24 || R15 = 18.0328k, giving
VEN = 0.152778 * VBAT = 3.025-3.850 V over the planning battery range.
Independent 1% resistor corners give about 2.974-3.916 V. The unloaded
switch node remains at or below 4.619 V at 25.2 V input, below SW1's
12 V DC contact rating. R15 defines OFF without floating EN.

This removes the independent held-up +5V drive. TI's EN leakage of 0.1 uA
is typical only, not a guaranteed maximum. No intentional EN capacitor is
added. Compact wiring and normal hot-plug/shutdown measurements remain
necessary; the divider is not a guarantee for arbitrary hard shorts or
input spikes. Its thresholds are too low to be a 6S battery cutoff.
See `docs/design/POWER_DECISIONS.md` for the complete calculation and datasheet locators.
Switching EN off is not galvanic isolation or an active output discharge.

For the nominal motor capacitor sum of 260 uF, energy from 22.190 to 24 V is
only 0.5*C*(24^2 - 22.190^2) = approximately 10.9 mJ. With an initial 22.849 V
it is about 7.0 mJ. Capacitance tolerance and ceramic DC bias reduce this budget.
This calculation demonstrates why C5 is not sufficient evidence of acceptable
braking behavior. There is no designed braking clamp or dump resistor here.
The selected PFM converter is not an energy sink; assess externally driven
output and power-down conditions, including the manufacturer's VOUT/VIN limit.

Planning battery current remains approximately 6.3 A at 22.2 V, or 7.1 A at
19.8 V using 126 W / 90% efficiency. These estimates are not component or
thermal ratings. RS1 dissipates about 0.101 W at 7.1 A and 0.2 W at 10 A.
The selected IC is rated up to 5 A. Typical switch
conduction estimates at the three planning loads are about 0.55/0.30/0.91 W,
before switching loss and hot resistance. Thermal performance depends on actual
copper, vias, assembly and ambient conditions; the EVM's four-layer construction
does not establish a two-layer rover-board rating.

## Footprint and sourcing status

Both 12 V and 5 V output ceramic banks use Samsung CL32B226KAJNNNE /
C309062 / 1210. Samsung's exact curves are archived under evidence/characterization/.
The current four-part 12 V bank is about 35.8 uF typically; the five-part
5 V bank is about 87.5 uF typically. Applying initial -10% tolerance gives
32.2 uF and 78.8 uF planning estimates, not guaranteed all-condition minima.
The typical 12 V bank does not meet the earlier conservative 37.1 uF
full-load-step screen. The adopted selection uses TI-reference-based sizing
plus practical margin, not that screen as its acceptance basis.
The 0.5% ripple / 5% load-step figures remain bench goals. Startup and
transient behavior require checking with the actual loads and layout.

TI Table 9-2 gives effective reference capacitances of 20 uF at 12 V and
66 uF at 5 V, with 6.8 uH and 4.7 uH inductors respectively. The adopted
banks have useful typical margin over those references. See
`docs/design/OUTPUT_FILTER_SELECTION.md` for the selection rationale.

All three converter inputs retain two Murata 10 uF / 50 V parts plus 100 nF.
The archived exact-family graph indicates about 11.5 uF per pair at 25.2 V,
25 C / 1 Vrms, before tolerance. Initial tolerance and an independent
-15% temperature allowance reduce the screen to about 8.8 uF. That is not a
manufacturer-guaranteed combined-condition minimum. Three parts were
recommended for more margin, but that recommendation was not implemented;
the current two-part choice must not be silently replaced during layout.
See `docs/design/MOTOR_FILTER_SELECTION.md` and the archived characterization evidence.

- U2-U4 use `rover:LMR51450_DRR_WSON12_3x3`, a corrected local WSON-12/DRR
  footprint with exposed pad 13. The imported supplier source remains archived.
  The drawing-based land/stencil comparison is in `docs/review/PCB_FOOTPRINT_REVIEW.md`.
  Verify the actual reflow process and assembler rotation before manufacture;
  sourcing identity is not a substitute for assembly review.
- L1 retains SRP1265A-6R8M; L2 uses SRP1265A-4R7M / C780205. L1/L2 use the local SMD footprint
  `rover:SRP1265A_LeadFrame_13.5x12.5_P11.1`, with manufacturer-recommended
  3.1 x 5 mm lands at +/-5.55 mm and a full body/land courtyard. This replaces
  the imported value-specific footprint and its incorrect THT attribute.
  L3 uses `rover:APS1365DW_13.8x12.6_P11.5`: 3.2 x 5 mm lands at +/-5.75 mm,
  matching the Coilank drawing. Its inductance stays 3.3 uH; its MPN/LCSC fields
  and footprint change together. No unverified substitute 3D body is attached.
- F1 is removed in A10. Its earlier footprint/drawing are retained as
  historical evidence and do not imply a populated holder or fuse purchase.
- RS1 uses `rover:CSS2H_2512_6.35x3.05`: Bourns-recommended 1.8 x 3.4 mm
  lands at +/-2.6 mm, with independent inner-edge Kelvin takeoffs. Verify the
  soldered terminal path and calibration; do not sense along load-current copper.
- C1/C5: 10 mm body / 5 mm pitch; C2: 8 mm body / 5 mm pitch for the selected
  Panasonic B-suffix formed leads. Catalog FR rows confirm the bodies and
  formed-lead spacing; inspect actual ordered parts and height clearance.
- SKT1 uses `rover:Pico2_Sockets_LXWCONN_254PM_1x20`, with 1.02 mm drills,
  1.8 mm pads, two 1x20 socket rows at 17.78 mm separation and full socket/module
  outlines. Drawing review is complete; actual header engagement, body height
  and underside/USB clearance still require the purchased parts.
- P1-P4 have the authorized surface-wire footprints assigned and installed.
  P1 uses two 6 x 8 mm lands at 12 mm pitch; P2-P4 use two 5 x 6 mm lands
  at 9 mm pitch. There are no wire-through holes or paste apertures. The owner
  removed the separate NPTH retention pairs from board and libraries. Provide
  external cable strain relief and review actual harness retention and
  soldering access; circuit and pin numbering are unchanged.
- R19 uses RC0805FR-07100KL / C96346, matching the existing 100k resistor
  identity. New R24 uses 0805W8F2202T5E / C17560, 22k / 1% / 0805.
  R20 remains RC1206FR-073K9L / C137289, 3.9k / 1% / 0.25W / 1206.
- J9 remains DNP but has the optional BOOMELE 2.54-1x6P straight header /
  C37208 assigned. J8/JP1 and Q1 are absent. A purchased header is optional;
  its footprint remains available for future expansion. Its exact drawing is
  now archived and the 1 mm drill / 0.64 mm square-pin comparison is recorded
  in `docs/review/PCB_FOOTPRINT_REVIEW.md`; the earlier download limitation is resolved.
- The Pico module and two sockets are separate purchased items;
  see `docs/design/BOM_NOTES.md`. No stock, price or assembly-availability claim is made.

The earlier routed PCB was accepted through the layout workflow on 2026-10-01 with
exact native parity and two zero-error, zero-warning, zero-unconnected DRC runs.
Those historical results do not cover subsequent owner edits; current results
must be bound to the latest CAD. They establish checked CAD connectivity and geometry, not validated thermal
capacity, enclosure fit, solder quality or human release approval.
