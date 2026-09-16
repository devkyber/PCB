# BMP390 reference research

Research date: 2026-09-16. Performed by the coding assistant; human acceptance
and our board's layout validation remain pending. This record distinguishes
searching, acquiring, inspecting, and validating a reference.

## Searches actually performed

| Query | Result and decision |
| --- | --- |
| `site.bosch-sensortec.com BMP390 shuttle board schematic layout` | Found the manufacturer's BMP390 shuttle board 3.0 flyer. Acquired and inspected page 2. It contains a circuit diagram, not complete PCB copper CAD. |
| `site.github.com/adafruit Adafruit BMP3xx PCB BMP390 sch brd` | Found Adafruit's official repository with both BMP390 Eagle files. These were already archived; checked their bytes and pair connectivity. |
| `site.sparkfun.com BMP390 schematic board design` | Returned a mirrored datasheet, but no selected exact-part schematic/PCB pair in this search. This is not proof that none exists. |

Primary source pages checked:

- https://www.bosch-sensortec.com/en/products/environmental-sensors/pressure-sensors/bmp390
- https://github.com/adafruit/Adafruit-BMP3xx-PCB
- https://learn.adafruit.com/adafruit-bmp388-bmp390-bmp3xx/downloads

## Acquired sources and inspection

Exact URLs, retrieval dates, and full content hashes are in `evidence/index.yaml`.

| Source | Archived file | Inspection and limits |
| --- | --- | --- |
| Bosch shuttle board 3.0 | `evidence/files/BMP390_bst-bmp390-sf000_3bf3698620c7.pdf` | Visually inspected p.2, document BST-BMP390-SF000-01, version 1.1, February 2024. The schematic shows separate 100nF capacitors on VDD and VDDIO, ground pins 3/8/9, interface signals and interrupt breakout. It does not establish our PCB placement or routing quality. |
| Adafruit native schematic | `evidence/files/BMP390_Adafruit_20BMP390.sch` | Exact gate/pin-to-pad connections and explicit component values parsed. Internal device/package is named BMP388 even though the file targets BMP390. Do not infer device compatibility from the filename alone; Bosch remains the pin/specification authority. |
| Adafruit native PCB | `evidence/files/BMP390_Adafruit_20BMP390.brd` | Inspected element placement, package identity, pad-net membership, routing primitives and polygons from native CAD. 66 connected pads compared with the schematic, zero mismatches; 178 routed wire primitives, 17 vias, copper on layers 1/16, GND polygons on both layers. These are counts and net assignments, not DRC or routing-completion proof. |
| Adafruit rendered guide | `evidence/files/BMP390_adafruit-bmp388-bmp390-bmp3xx_a12339be0afa.pdf` | Visually inspected p.40, explicitly titled for BMP390: schematic and fab/board view. Pages 41/42 are BMP388 variants and are not substituted for the BMP390 reference. The PDF and CAD are independently archived; their same revision has not been proven. |

Adafruit's repository identifies its license as CC Attribution/Share-Alike;
check its `license.txt` before redistributing adaptations. Native CAD is archived
by content hash; the existing upstream URLs target `master`, so these bytes are
reproducible locally but not pinned to an upstream commit.

## Applicability to our board

Keep the existing sourced decisions in `DESIGN_BASIS.md`: our board receives
3.3V from its host, while the Adafruit reference includes a regulator and level
shifting. Do not copy those blocks or their layout into our board indiscriminately.
Bosch's two-capacitor connection supports the existing sensor decoupling choice;
Adafruit's additional rail capacitance provides board-level context, not an
override of the Bosch datasheet.

PCB inspection priorities for the next draft are sensor-local decoupling and
return paths, connector-entry bulk capacitance, access to the sensor pressure
port, and separation from mounting/mechanical stress. Reference views inform
these questions; they do not prove that our proposed layout meets them.

## Still open

- Compare our actual placement/routing with these references and record each
  adopted rule or justified difference in the design basis.
- Inspect native copper in an EDA viewer and check reference revision identity
  before relying on exact routing or dimensions. The rendered fab view alone
  is insufficient for stackup, return-current, or manufacturing conclusions.
  A 2026-09-17 KiCad 10 Eagle-import attempt preserved all 66 mapped contacts
  in memory, but the disposable saved copy contained undefined layers and
  failed PDF export. No copper visual review is claimed from that attempt;
  the original Eagle archive was not changed.
- Full manufacturer PCB CAD was not acquired in this search.
- Human review of applicability remains pending; this is research evidence,
  not release sign-off.

## Schematic draft checkpoint

Draft `20260916T162351Z-schematic-7ad1be18` preserves the accepted circuit and
renders a dated, single-sheet PDF with functional headings and drawn passive
banks. The assistant inspected the preview; there are no machine blockers.
The new local-route text keepouts and multi-bend fallback separate the
interrupt wire from CSB supply text. Known visual limitations remain at U1:
ground/supply glyphs two pin rows apart touch. Those already-emitted stubs and
glyphs still require refinement. Accepted schematic, PCB and
netmap bytes remain unchanged; no human acceptance is recorded.
