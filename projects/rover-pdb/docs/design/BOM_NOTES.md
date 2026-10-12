# BOM notes — A10 circuit / PCB P5, 2026-10-04

`../../output/schematic-bom.csv` is a component-level review list captured from the delivered
KiCad files. It is not a fabrication/assembly BOM. Re-export from the owner's
current CAD after edits. C-numbers identify selected supplier parts; a supplier
identity is not a reservation of stock or a completed assembly-order review.

All fitted discrete electrical components have selected MPNs and LCSC
C-numbers. SKT1 represents a module/socket assembly whose separate purchases
are listed below. Copper features do not need supplier numbers. Live stock,
JLCPCB assembly eligibility, quantities and rotations must be checked when an
actual assembly order is prepared.

The active converter selection is **U2–U4: LMR51450SDRRR / C6890985**,
quantity three, intended for JLCPCB assembly. All three use the local DRR
WSON-12 footprint with exposed ground pad 13. The current CAD and
`../../output/schematic-bom.csv` contain the complete component list; the table below
highlights control, indicator and expansion selections.

| Ref | Selected part | LCSC |
| --- | --- | --- |
| R19 | Yageo RC0805FR-07100KL, 100k, 0805, 1%, 0.125W | C96346 |
| R24 | Uni-Royal 0805W8F2202T5E, 22k, 0805, 1%, 0.125W | C17560 |
| R20 | Yageo RC1206FR-073K9L, 3.9k, 1206, 1%, 0.25W | C137289 |
| D2 | Kento KT-0805G, green LED; manufacturer anode=1/cathode=2 | C2297 |
| J9 | BOOMELE 2.54-1x6P直针, straight 1×6 / 2.54mm header, **DNP** | C37208 |

A9 removes Q1 and restores USB-only Pico power; SKT1 pins 39/40 are explicitly
NC on the PDB. JP1/J8 remain removed. R19/R24 derive the motor-switch supply
from VBAT, while the existing R15 holds EN low when the switch is open.
See `POWER_DECISIONS.md` for the circuit and calculations.

J9 now has an exact supplier identity despite remaining unpopulated initially.
Its footprint/pads remain on the current PCB when the header is DNP. The
previous drawing-download failure is resolved: the exact supplier-linked
BOOMELE family drawing is archived and specifies 2.54 mm pitch, 1.00 mm PCB
holes and nominal 0.64 mm square pins. The footprint drawing comparison is in
`../review/PCB_FOOTPRINT_REVIEW.md`; actual purchased-part fit remains a physical check.

Exact supplier records and the active resistor/capacitor manufacturer
specifications are archived in `../../evidence/index.yaml`.

Additional purchased/mechanical items not represented as separate circuit symbols:

| Associated ref | Item | Qty | Source identity |
| --- | --- | ---: | --- |
| SKT1 | 1x20 female sockets | 2 | LXWCONN 254PM-1x20P-V; C53202183 |
| SKT1 | Pico 2 non-W module | 1 | Raspberry Pi Pico 2; C41407547 |
| SKT1 | 1x20 male headers if module is bare | 2 | Samtec TSW-120-07-G-S; C3335373 |
| P1 | Wire, XT60 mating connector, external DC switch, strain relief | As fitted | See handover; switch selection remains open |
| P2 | 18 AWG cable to 5.5 x 2.5 mm centre-positive barrel plug | 1 | Purchased harness; verify polarity and fit |

SKT1 is one logical 40-pin module/socket interface, not one orderable socket.
The assembly plan dated 2026-10-02 is to **hand-fit SKT1 after factory assembly**:
solder two LXWCONN 254PM-1x20P-V female sockets to the carrier, then insert
one Pico 2 non-W module. If the purchased module has no male headers, solder
two Samtec TSW-120-07-G-S headers to the module first. The exact existing
purchase identities and per-board quantities are listed above; verify the
module's delivered header configuration before buying the extra headers.

For the JLCPCB assembly exports, SKT1 must have both native PCB attributes
`exclude_from_bom` and `exclude_from_pos_files`. Keep its through-hole type,
40 numbered pads, circuit nets and module/socket geometry. **Do not mark it
DNP**: the sockets and module are fitted manually in the completed board.
The schematic review BOM can still show the logical SKT1 interface; it is not
the assembler's purchase list. Never submit one generic SKT1 row and let
part matching choose one socket or a complete Pico for its single placement.

After any schematic-to-PCB update or footprint refresh, recheck both assembly
exclusion attributes. Before submitting an order, verify that SKT1 is absent
from the fresh assembly BOM and position/CPL files and that the separate
manual purchase list still includes two sockets and one module, plus two male
headers only if needed. This plan applies specifically to SKT1; assembly
eligibility and the fitting method for the other through-hole parts remain
part of the actual supplier-order review.

F1 and its holder are removed in A10 at the owner's request. There is no
onboard fuse to purchase. External battery protection remains unverified.
J9 is DNP; JP1/J8/Q1 are removed. TP1–TP6 and NT1–NT3 are PCB features,
not purchased components. NT1–NT3 are local ground net-ties, not zero-ohm
resistors to order. P1–P4 use the owner's selected surface wire-solder lands:
P1 has two 6 × 8 mm pads at 12 mm pitch; P2–P4 have two 5 × 6 mm pads at
9 mm pitch. These lands have no paste opening or wire-through holes. The owner
removed their optional NPTH retention-hole pairs from the board and footprint
libraries. Secure the actual harness externally; solder alone is not strain
relief. P3/P4 have no initial wires. Their PCB feature footprints are excluded
from purchased BOM and assembly-position output.

SKT1 now uses the selected sockets' 1.02 mm drills and two-row drawing geometry.
P5 attaches two official KiCad 1x20 female-socket STEP bodies to this footprint.
These are generic visualization models; the selected LXWCONN drawing governs
actual dimensions and fit. The sockets remain separately purchased, hand-fitted
parts even though the PCB represents both rows as one SKT1 interface.
L1–L3 and RS1 use local manufacturer-land-pattern footprints, with their original
electrical values and supplier identities preserved. See `../review/PCB_FOOTPRINT_REVIEW.md`
for the dimensions and separate drawing-versus-physical-fit verification scope.

The converter output capacitor banks are individual components, not a single
aggregate-value placeholder. C1, C2 and C5 are polarized. U2-U4 require a
reviewed reflow assembly process for the exposed-pad WSON packages, including
thermal-pad paste/via design and verification of placement rotation. Board
features and manually fitted parts must not be sent as purchased SMT components.
