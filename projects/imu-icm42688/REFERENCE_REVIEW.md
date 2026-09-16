# ICM-42688-P reference research

Research date: 2026-09-17. This is an assistant research and transcription
record; circuit acceptance, layout validation and release remain human owned.

## Searches actually performed

| Query | Outcome and selection |
| --- | --- |
| `site.invensense.tdk.com ICM-42688-P evaluation board schematic layout DK-42688-P` | Found the exact-part DK-42688-P page and DS-000347 manufacturer application schematic. The DK page did not yield acquired native PCB CAD. |
| `ICM-42688-P open hardware schematic PCB layout anyshake` | Found exact-part open hardware, including SUSTAINA-OP. Its own README calls the design untested, so it was not treated as a validated implementation. |
| `site.github.com/anyshake/icm-42688-breakout ICM-42688.kicad_pcb` | Search did not itself resolve the file; opened the existing AnyShake source repository and enumerated its tree using the GitHub API. Acquired native schematic, PCB and rendered schematic at one pinned commit. |
| `site.invensense.tdk.com QCIoT ICM42688P schematic AN PCB` | Found TDK AN-000493 rev 1.0, an exact-part Pmod evaluation manual containing schematic and top/bottom layout views. Direct download returned HTTP 404. The linked Mouser PDF mirror returned HTML to the downloader, rejected by the archive API. |
| `site.tdk.com "AN-000493" pdf`; `site.invensense.tdk.com "AN-000493"` | Follow-up found a working ChipDip mirror; archived and inspected below. |

Pages inspected for source identity:

- [TDK ICM-42688-P](https://www.invensense.tdk.com/en-us/products/consumer/icm-42688-p)
- [TDK DK-42688-P](https://www.invensense.tdk.com/en-us/products/6-axis/dk-42688-p)
- [AnyShake source repository](https://github.com/anyshake/icm-42688-breakout)
- [SUSTAINA-OP candidate](https://github.com/SUSTAINA-OP/ICM-42688-P-Module)
- [Mouser evaluation-board page linking the TDK manual](https://eu.mouser.com/en/new/tdk/tdk-invensense-qciot-icm42688p-board/)

## Archived and inspected sources

Full hashes, exact URLs and retrieval dates are in `evidence/index.yaml`.
The three newly acquired AnyShake files are pinned to commit
`b4f35e0759763c8e6bcaafed687799e2f0148c36`. This pins repository identity; it
does not establish that the PDF was regenerated from that commit's schematic.

| Source | Archive file | Inspection and limits |
| --- | --- | --- |
| TDK DS-000347 rev 1.6, existing AnyShake mirror | `evidence/files/ICM-42688-P_ds-000347-icm-42688-p-v1.6.pdf` | Rendered and visually inspected pp.20-21 using the evidence PDF helper. Table 10 provides the pin definitions and allowed reserved-pin connections; Figure 7 is the SPI circuit with 100nF and 2.2uF on VDD and 10nF on VDDIO. This is the manufacturer circuit reference. |
| TDK AN-000493 rev 1.0, ChipDip mirror | `evidence/files/ICM-42688-P_DOC056673507_44e5201b843b.pdf` | Inspected schematic p.12 Figure 4, BOM p.13 and layout p.14 Figures 5–6. The layout views show placement/pads, not routed copper or filled planes. |
| AnyShake pinned native schematic | `evidence/files/ICM-42688-P_ICM-42688_5b2b5ac9a5f0.kicad_sch` | Acquired alongside PCB. Its hash differs from the older existing `ICM-42688-P_ICM-42688.kicad_sch`; the older bytes and original provenance are preserved. No claim of KiCad pair parity is made. |
| AnyShake rendered schematic | `evidence/files/ICM-42688-P_ICM-42688_8cdcc0d19fe3.pdf` | Visually inspected page 1. Sensor U2 is ICM-42688-P; C3 is 2.2uF, C5 is 0.1uF and C7 is 0.01uF. It also contains a regulator, diodes, power-selection header and TXB0104 level translator absent from our circuit. |
| AnyShake native PCB | `evidence/files/ICM-42688-P_ICM-42688_57a947b32217.kicad_pcb` | Inspected source pad nets and KiCad exports of F.Cu/B.Cu with Edge.Cuts and F.SilkS overlay. The two views show central sensor U2, nearby decoupling, peripheral header and mounting holes, and routes interrupting poured copper. Source counts: 25 footprints, 133 segments, 38 vias and 61 zone records (includes small filled/teardrop regions; not 61 independent ground planes). This is placement/routing reference coverage, not a reference-board DRC or return-current proof. |

Native pad inspection confirms AnyShake U2.5 and C7.1 share `/Vout`, while
U2.8, C3.1 and C5.1 share `/+3V3`; their returns use GND. U2.7 is grounded,
U2.9 is exposed as `/INT2`, and U2.11 is grounded. These are exact source net
assignments, not electrical recommendations or evidence that its copper is
fully connected.

`research --inspect-reference` was attempted on the pinned KiCad pair. The
current inspector supports Eagle XML only and returned `invalid Eagle XML`.
Therefore pair consistency is **not verified**. The project archive integrity
check passed for all six records; that check proves bytes/provenance consistency,
not the design's electrical correctness.

## Manufacturer follow-up and remaining coverage

The original manufacturer/Mouser download attempts failed. The follow-up
[ChipDip mirror](https://static.chipdip.ru/lib/673/DOC056673507.pdf) supplied
AN-000493 rev 1.0 (2024-10-02), now archived with its actual retrieval URL.
Python's default TLS trust store rejected the chain; a verified connection
using the installed certifi CA bundle succeeded. TLS verification was not
disabled. No byte identity with an unavailable manufacturer-hosted file is
claimed.

Figure 4 agrees on 2.2uF/100nF VDD and 10nF VDDIO bypass. It adds selectable
SPI/I2C jumpers and pull-ups; its Pmod wiring is not our fixed-SPI interface.
Figure 5 places bypass parts beside U1, unlike a schematic's separated power
block. This informs physical review but supplies no trace/return-path proof.
Full manufacturer PCB CAD and routed-copper views remain unacquired.
The existing DS-000347 rev 1.6 archive remains the selected manufacturer
application schematic; no newest-datasheet revision claim is made. A direct
TDK Product Center attempt for that revision returned HTTP 403.

## Applicability and discrepancies

Our host supplies one 3.3V rail directly and uses four-wire SPI. AnyShake's
separate power-selection and translation circuits and its header numbering
must not be copied into this board. Its exposed INT2 differs from our grounded
unused FSYNC/INT2 pin. The manufacturer pin table permits our accepted NCs on
pins 2, 3, 10 and 11; mandatory ground on pin 7 is preserved. These comparisons
do not decide the owner's axis orientation, mounting rigidity, supply ramp,
rail-noise performance or high-g sensor requirement.

The archived rev 1.6 PDF exposes citation errors in the existing
`DESIGN_BASIS.md`: the signal table is **Table 10, p.20**, the pin/axis drawing
is **Figure 5**, and the SPI circuit is **Figure 7, p.21**. Figure 6 is I2C/I3C.
Its cited capacitor values and reserved-pin text agree, but the figure/table
locators were corrected in the 2026-09-17 documentation follow-up. The prior
absolute claim that capacitance alone proves failure to meet 10mVpp was not
established by this research and was removed; actual supply performance needs
measurement. The archival revision is now distinguished from any current/latest
revision claim. These documentation corrections do not validate the circuit.

The new intent preserves all ten accepted physical components plus the two
existing power flags, exact physical symbol IDs/footprints/values, netmap
connections and all six explicit NC markers checked against the schematic.
Generic-part pin evidence remains null with concrete pending-review notes;
the sensor uses its matching indexed datasheet. No owner choices or accepted
electrical/PCB changes are made by this transcription.

Next review must compare our actual decoupling placement and return paths,
sensor/mechanical stress and orientation, connector pinout and host behavior
against the selected evidence. Native reference DRC, latest datasheet review,
manufacturer native/routed-copper acquisition and human suitability review
remain open. The newly acquired manual closes schematic and placement-view
inspection, not complete PCB-layout validation.

## Latest draft inspection

Draft `20260916T162351Z-schematic-b0464d86` has a one-page PDF, no machine
blockers, 10 ERC pin-type warnings and 11 unresolved pin-map evidence reviews.
Assistant visual inspection confirms dated titles, functional headings, local
wiring and four junctions. The INT1 vertical wire now clears U1.6 GND text;
a real KiCad PDF regression checks that separation. Local routes avoid
generated power Value text, but this is not a sheet-wide glyph-collision
guarantee or human approval. Accepted schematic,
PCB and netmap bytes remain unchanged.
