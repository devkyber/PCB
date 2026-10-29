# USB-C 5 V bench power entry — revision A

This is an **unbuilt educational DRAFT**, authored 2026-10-29. It accepts a
separately qualified 4.75–5.25 V bench source and a total board-plus-load budget
of at most 500 mA near 23 °C. It does not establish USB compliance, negotiated
power, physical fit, fault protection for a system, or permission to fabricate.

## Circuit and selected identities

| Function | Selected part / source | Adopted facts and interpretation |
| --- | --- | --- |
| J1 USB-C input | GCT USB4105-GF-A, drawing B4, pp1–2 | The blank stake option is 0.95 mm. A4/A9/B4/B9 are VBUS; A1/A12/B1/B12 and shell are GND; A5 is CC1 and B5 CC2. Contact positions and unused data/SBU pins follow the drawing. Connector current ratings do not grant a USB load budget. |
| R1/R2 attachment | Yageo MFR-25FBF52-5K1, MFR datasheet pp2–3; USB Type-C R2.0 (August 2019), §§4.5–4.6 | Separate 5.1 kOhm, 1% pull-downs connect CC1 and CC2 to GND. This passive sink has no PD controller or Rp-current detector. Its application budget must be guaranteed outside the board; attachment alone does not authorize 500 mA from every host. The archived 2019 specification is a dated design reference, not a current certification assessment. |
| F1 resettable fuse | Bourns MF-MSMF075-2, MF-MSMF pp1,5,7,13 | At 23 °C: hold 0.75 A, trip 1.50 A, rated voltage 13.2 V; R1 maximum 0.45 Ohm. The 500 mA application budget is below hold current, but F1 is not a 500 mA current limiter. At 500 mA, the stated resistance bound gives 0.225 V drop and 0.1125 W dissipation before routing losses; no thermal performance is measured. Reflow is required by the selected assembly plan; the manufacturer discourages hand soldering this PPTC. |
| D1 transient shunt | Vishay SMAJ6.0A, document 88390, pp1–2 | Unidirectional: pin1 cathode to VOUT, pin2 anode to GND. Standoff 6.0 V; breakdown 6.67–7.37 V at 10 mA; maximum listed leakage 800 uA at 6.0 V; listed maximum clamp 10.3 V at 38.8 A for the specified 10/1000 us pulse. These are component pulse conditions, not a board surge/ESD rating. A downstream part with a 5.5 V maximum can still be damaged. This is not sustained 5 V overvoltage protection. |
| R3 / D2 indicator | Same 5.1 kOhm resistor; Kingbright WP710A10ID, pp1–3 | D2 pin1 is cathode, pin2 anode. The conservative zero-forward-voltage current bound is 5.25 / (5100 × 0.99) = 1.040 mA. Resistor power is at most 5.25² / 5049 = 5.46 mW. Brightness at this current remains unqualified. |
| J2 output | Samtec HTSW-102-07-G-S, TSW/HTSW family sheet p1 and ordering grid | Two single-row 2.54 mm positions: pin1 VOUT, pin2 GND. HTSW is deliberately selected because the family sheet lists lead-free solderability; TSW is not substituted. The generic KiCad header body is a visualization aid. |
| H1/H2 | Fabricated 3.2 mm nonplated holes | No purchased fastener or insulating hardware is selected. Mounting/enclosure fit is unqualified. |

All exact downloaded bytes, origin URLs and SHA-256 values are retained in
[evidence/index.yaml](evidence/index.yaml). Manufacturer facts were checked
against the selected part rows and drawings; archive coverage alone does not
perform that interpretation.

The shared research gate reads the following explicit decision row. The
archived Adafruit 4090 rev-B schematic/board pair supplies a separate proven
open-hardware comparison for the passive attachment pattern. The USB
specification remains a dated integration reference, not a manufacturer EVM.
No reference waiver is recorded.

| Ref | Topic | Source fact | Board choice | Verification boundary | Source | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| J1 | Pin allocation / power attachment | GCT p1 CC1=A5, CC2=B5, VBUS/GND groups; USB R2.0 sink attachment; Adafruit4090 revB independent 5.1k CC resistors | Independent 5.1 kOhm Rd; unused data/SBU; externally guaranteed 5 V / 500 mA total budget | Different reference connector; electrical pattern comparison only; USB source compatibility and manufacturing open | GCT USB4105 drawing B4 p1; USB Type-C R2.0 sections 4.5–4.6; Adafruit4090 commit1484ecb56b369e177848e69de4b7b7e513399590 | Match pin allocation and passive sink pattern; no PD/current sensing or compliance claim |

## Power and protection boundaries

J1 is the sole input. J2 must not be backfed. The board has no reverse-current
blocking, regulator, inrush controller, output capacitor or active overvoltage
disconnect. Begin with a current-limited source and a non-sensitive resistive
dummy load. Determine the actual source advertisement, cable capability,
startup behavior and load capacitance before changing that setup.

The 500 mA total budget includes the LED and leakage. It is not a guarantee of
500 mA at J2 or a regulated 5 V output. Taking the fuse resistance bound alone,
4.75 V input can produce only 4.525 V before connector/copper losses. PPTC
derating, recovery resistance, transient behavior and actual heating need bench
measurements. A source limited below F1's trip current may never trip it.

D1 is after F1, near the entry protection group, with a short top-layer shunt
to two ground vias and a continuous bottom GND pour. That placement is a design
choice, not validated protection coordination. The fuse does not establish
that a prolonged TVS event is safe. The cable/source and board pulse loop need
their own qualified test conditions.

## Layout and library decisions

The fresh 60 × 40 mm board has two copper layers. USB fine-pitch escapes use
0.20 mm CC and 0.40 mm VBUS/GND stubs; most power routing is 0.80 mm. Those are
editable routing choices for the declared bench budget, not measured ampacity
or a thermal qualification. The bottom layer carries a continuous GND pour and
the short VBUS bridge. R1 and R2 remain independent. All native schematic paths
are retained for forward annotation. Useful Power/CC netclasses, track widths,
and via presets are saved in the project.

Most local footprints are exact official KiCad 10.0.6 library copies, changing
only model URIs. [PROVENANCE.json](libs/PROVENANCE.json) pins separate upstream
and local bytes, pad functions, exact part evidence and package models. Source
URLs identify official library locations; the installed distribution version
and hashes do not authenticate a particular upstream Git commit. Board
instances adjust silkscreen stroke widths/field positions only; pads are intact.

F1 is the explicit exception: the generic official 1812 footprint uses
1.125 × 3.40 mm pads with a 3.15 mm inner gap. The selected Bourns style-1
recommended layout is 1.50 × 3.20 mm pads with a 2.70 mm inner gap. The separate
`BournsDerived` footprint follows those recommended lands (centers 4.20 mm),
the maximum 4.73 × 3.41 mm body outline, and a declared assembly courtyard.
Its [drawing receipt](libs/footprint-provenance.yaml) records the derivation.
There is **no F1 3D body**; no substitute or invented package geometry is used.

## Unresolved connector manufacturing findings

Native DRC deliberately retains eight errors in the unchanged official J1
footprint: four shell-pad annular rings are 0.20 mm against the workspace's
0.25 mm recommendation; four GND-pad/peg-hole clearances are 0.1944 mm against
the 0.25 mm baseline. No rule was relaxed and no finding was excluded.

The GCT p1 drawing explicitly specifies the 0.60 × 1.15 mm GND solder lands,
0.65 mm peg holes and their fixed centers. Increasing the clearance to 0.25 mm
would remove specified solder land or change the holes/centers. That change
was rejected during author review. The [JLCPCB capability page](https://jlcpcb.com/capabilities/pcb-capabilities/),
checked 2026-10-29, lists 0.20 mm NPTH-to-copper spacing and a recommended
0.25 mm PTH annular ring (0.18 mm absolute minimum for the stated 1 oz two-layer
case). The existing 0.1944 mm clearance therefore needs an explicit fabrication
resolution, rather than an unsupported claim that the official footprint is
manufacturable under this profile. Select and qualify another connector or
obtain a documented fabrication/connector land decision before release.

Native ERC, exact pin-net/part/link parity and routing completeness are separate
checks. They can pass while this manufacturing gate correctly remains blocked.
