# A1 design basis - unbuilt DRAFT

## Scope and limits

This board translates a 3.3 V UART and independent enable controls to one
half-duplex RS-485 port. It is a non-isolated educational bench design. There is
no measured link rate, industrial ESD/EFT/surge, EMC, isolation or physical-fit
qualification. The IC's published capabilities are not board-level test results.
The initial bench target is 115200 baud on a short terminated twisted pair.
THVD1450 edges remain fast at low baud rates; termination, stubs and return paths
still require measurement. No controlled impedance or maximum cable length is claimed.

## Primary reference and exact pin map

The archived TI SLLSEY3E datasheet, main revision May 2019 with its appended current
ordering information, is the circuit authority. Page 5 explicitly gives the SOIC
`D` package: 1=R/RO, 2=active-low RE, 3=DE, 4=D/DI, 5=GND, 6=A, 7=B, 8=VCC.
The selected orderable part is **THVD1450DR**, the SOIC-8 D package on reel.
The native symbol and SOIC footprint use this exact mapping. No exposed pad exists
on the selected SOIC package.

The installed official KiCad 10.0.6 `THVD1450DR` symbol alias incorrectly specifies
a VSON footprint. It was deliberately not used. The local `RS485:THVD1450D`
symbol resolves the official `THVD1450D` -> `MAX481E` inheritance without changing
its graphics, pins, numbers or electrical types, then uses the explicit selected
MPN and verified SOIC footprint on the instance. Original library bytes are
archived under `libs/upstream/symbols/`. Symbol inheritance resolution is an author
operation, not a claim that the footprint provenance validator checks symbols.

TI Figure 31 establishes the half-duplex bus/end-termination arrangement;
sections 9.4.1 and 10.2.1.4 explain enable controls and internal failsafe operation.
Section 11 requires local 100 nF decoupling. Section 12.1/Figure 40 guide local
bypass, short returns, enable pulls and connector-side placement.

## Supply, logic and startup

J1 accepts an externally regulated **3.3 V nominal, 3.0-3.6 V** supply. The IC's
specified 3.0-5.5 V range does not authorize a 5 V host for this example. The host
must use compatible 3.3 V logic and power sequencing; no powered-off signal
injection, hot-plug behavior or back-power immunity is qualified. MCU, supply,
cable and remote node are not selected by this example.

J1 pin 3 TXD drives U1 pin 4 DI; U1 pin 1 RO drives J1 pin 4 RXD. J1 pin 5 DE and
pin 6 nRE remain independent. TI specifies DE's internal pull-down and nRE's
internal pull-up; R1 and R2 add **10 kOhm, 1%** pull-downs so an otherwise floating
host makes the driver disabled and receiver enabled. TI section 12.1 recommends
1-10 kOhm enable pulls. TI logic input current is bounded at +/-6.2 uA over its
stated test conditions. With Rmax=10.1 kOhm, the worst positive input-current drop
is **62.62 mV**, below the 0.8 V input-low limit. External controller leakage,
drive thresholds and reset states must be checked separately.

C1 is 100 nF X7R, 50 V, +/-10%, placed beside U1 pin 8. Its actual supply-pad
distance to U1 pin 8 is about 2.33 mm, with a direct approximately 2.33 mm native copper
route. C2 is 1 uF X7R, 16 V, +/-10%, at the host supply entry. C2 is a board-entry
reservoir choice, **not a TI-mandated minimum**. Neither nominal MLCC value proves
effective capacitance at bias/temperature or supply transient performance.

## Bus and removable termination

J2 has 1=A, 2=B, 3=GND. Names follow TI: when DE=1 and DI=1, A is above B.
Check the other node's convention; some products use different A/B naming.
Ground is a shared reference, not an isolation barrier or protective earth.

R3 is **120 Ohm, 1%, 0.25 W** in series with the removable JP1 shunt between A
and B. JP1 pin 1 is B; pin 2 is the series node from R3 pad 2. Installing the
separately specified **SNT-100-BK-G** accessory enables termination. It is not a
permanent PCB short. Populate the shunt only at the physical end of a suitable
120 Ohm cable; remove it at middle nodes. The other physical cable end needs its
own appropriate termination. Native parity describes the open header contacts,
not the accessory's installed state.

At this example's 3.6 V supply ceiling and Rmin=118.8 Ohm, Vs^2/R gives
**109.1 mW** for one termination if the applied differential voltage is bounded
by that supply. This is below the resistor's 0.25 W rating at its stated reference
temperature. It does not cover an externally imposed bus fault, common-mode
fault, thermal derating or surge. TI's internal receiver failsafe addresses
open/short/idle bus states; no external A/B bias resistors are fitted. Mixed-node
networks need their own failsafe/loading analysis.

## Part and geometry decisions

| References | Exact manufacturer MPN | Source decision |
| --- | --- | --- |
| U1 | TI THVD1450DR | SOIC-8 D; TI p5 pin table and mechanical/order addendum |
| R1, R2 | Vishay CRCW080510K0FKEA | 0805, 10 kOhm, 1%; 20035 p2-3 ratings/order code and dimensions |
| R3 | Vishay CRCW1206120RFKEA | 1206, 120 Ohm, 1%, 0.25 W; same archived manufacturer series |
| C1 | Yageo CC0805KRX7R9BB104 | Exact-part sheet: 100 nF, 50 V, X7R, 0805 |
| C2 | Yageo CC0805KKX7R7BB105 | Exact-part sheet: 1 uF, 16 V, X7R, 0805 |
| J1 | Samtec HTSW-106-07-G-S | Six contacts, single row, 2.54 mm, -07 lead style |
| J2 | Samtec HTSW-103-07-G-S | Three contacts, same pitch/style |
| JP1 | Samtec HTSW-102-07-G-S | Two contacts, same pitch/style; accepts separate shunt |
| Off-board accessory | Samtec SNT-100-BK-G | Manufacturer shunt table lists TSW-family mating and 0.64 mm square posts |
| H1-H4 | Fabricated NPTH | 3.2 mm unplated holes; no purchased fasteners assigned |

HTSW was chosen instead of TSW because the primary catalog explicitly lists
HTSW as lead-free solderable and TSW as lead-wave only. Header hole, pin-1,
mating depth, soldering process and actual part tolerances still need physical
review. Generic official KiCad bodies are visual aids; they are not exact vendor
STEP models. In particular nominal header body/post dimensions and MLCC heights
can differ. Official generic footprint copies have unique local IDs for distinct
MPNs sharing one package. Every electrical pad is mapped in the strict receipt.
No imported supplier identity or fabrication fit approval is fabricated.

## Layout and manufacturing assumptions

50 x 35 mm, two layers, 1.6 mm nominal FR-4. Native settings/custom rules come
from the dated `templates/jlcpcb-2layer-1oz` geometry baseline. Four M3 clearance
holes are at offsets (3.5,3.5), (46.5,3.5), (3.5,31.5), (46.5,31.5) mm.
Signals use 0.35 mm tracks, the supply trunk 0.5 mm, local bypass/return links
0.4 mm, and 0.65/0.30 mm through vias. These are scoped geometry choices, not
current ratings or a controlled-impedance design. The filled bottom GND plane
has local signal crossings; continuity/EMC still require engineering review.
The local bypass and IC returns have paired ground vias. A/B and termination
routes are short board traces; the external harness must keep stubs short.

No external TVS is fitted: the bench scope does not define an industrial surge
exposure or validated clamp network. Do not infer a board ESD rating from the
IC's datasheet. Supplier stock, placement rotation, stencil/assembly process,
component fit, enclosure/hardware and bench behavior remain unsigned.

## Evidence and release boundary

`evidence/index.yaml` preserves primary document URLs, exact bytes and SHA-256.
`libs/PROVENANCE.json` verifies footprint-copy lineage, selected MPN and pad/model
coverage; it does not authenticate the download, verify symbol interpretation
or qualify physical fit. All receipts retain `physical_fit_qualified: false`.
There is no owner approval or fabrication release. Current review and mandatory
shared human decisions remain required after every relevant source change.

## Sourced decisions

| Ref | Part | Aspect | Ours | Reference says | Source | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | THVD1450DR | Half-duplex pin map, bypass, termination | SOIC8, 100 nF local, 1 uF entry, removable 120 Ohm | TI compatible 8-pin EVM exposes RO/nRE/DE/DI/A/B, 0.1 uF bypass, 1 uF reservoir and 120 Ohm termination | evidence/files/THVD1450DR_SLLU173_2081c71247a9.pdf; https://www.ti.com/lit/pdf/SLLU173; sha256:2081c71247a960a0f4b8225459bc6b234cab979d0bac480bb6e884202d9f5488 Figure 3-1 p3; exact THVD1450 electrical authority remains SLLSEY3E | Match: interface/pin map and local plus bulk decoupling; simplify generic EVM measurement jumpers and bias for the documented bench scope |

The linked TI product page offers this generic half-duplex evaluation platform.
Its SLLU173C schematic names SN65HVD7x, not THVD1450DR: it is a compatible
eight-pin interface/decoupling/termination comparison, **not an exact THVD1450
reference implementation or proof that TI tested this board**. The exact-part
datasheet controls all device limits, enable/failsafe facts and selected package.
The EVM's optional external bias, test loads, common-mode stimulus circuitry and
measurement connectors are not copied. Their omission is deliberate in this
short educational bench interface, not an equivalent industrial evaluation setup.
