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

## Derived copper inspection — 2026-09-17

The assistant inspected separate front/back copper PDF pages derived from the
archived Adafruit Eagle board, alongside the guide's page 40. The views expose
the explicit pads, traces and vias. C6 (0.1uF) is beside IC1, the sensor is near
the board centre, the QT connectors are on opposite edges, and mounting holes
are at the upper corners. These are reference placement observations, not
approved constraints or measurements of our board. The guide and native CAD
both identify revision B, but exact revision equivalence remains unproven.

KiCad 10.0.6 initially could not reload its own Eagle import: six dimensions
from Eagle layer 47 (`Measures`) and eight fiducial arcs from layer 41
(`tRestrict`, four each on FID3/FID4) became `UNDEFINED`. A disposable imported
copy omitting only those 14 imported items successfully reloads and exports
(ten source XML elements: six dimensions plus four arc definitions instantiated
on two fiducials). This is
a source-specific diagnostic workaround, not a general import repair feature.
The archived Eagle file is unchanged (SHA-256
`d732c7e871d1739e18aeccb356b2ab8c0f3e08bc8d89565dc1896740f45c3a7a`).

Import-to-reload checks found exact agreement for all 25 footprint placements,
71 pads and their geometry/net membership, 178 routed segments, 17 vias, the
two four-corner GND zone outlines and eight board-outline graphics. All 66
connected Eagle contacts still match their expected nets. This checks the
derived copy against the import; it does not prove the import reproduces
every Eagle rule or that the source board is DRC-clean.

Local diagnostic outputs (ignored, not shipped with the package) are under
`.pcb-copilot/reference-review/eagle-import/`:

- `reference-import-sanitized.kicad_pcb` and `reference-copper.pdf`: explicit
  copper without filled polygons. Use these for pad/trace/via inspection,
  not pour-continuity claims. Both pages use a top-view coordinate frame and
  front-silkscreen overlay; the back layer is not a mirrored underside view.
- `reference-import-kicad-refilled.kicad_pcb` and
  `reference-copper-kicad-refilled.pdf`: **KiCad-refilled approximations**.
  The assistant inspected both pages, but dropped `tRestrict` arcs and
  differences between fill engines may change copper around fiducials or
  elsewhere. Do not use these for manufacturing, exact clearance approval,
  reference DRC sign-off, or claims of Eagle-native polygon-fill equivalence.

Manual reproduction outline (not a packaged import command): import the
original with `PCB_IO_MGR.EAGLE` and require the invalid
items to match the exact type/reference/count whitelist above. In a disposable
Eagle XML copy only, omit the six layer-47 dimensions and four layer-41 arc
definitions from the `microbuilder:FIDUCIAL_1MM` package (instantiated twice).
Import that copy, save/reload the derived KiCad board and compare the geometry/net
invariants above; recheck the original source hash. Abort on any additional
invalid item or mismatch. Export F.Cu/B.Cu with Edge.Cuts/F.SilkS as common
layers; any zone refill must be saved separately and labeled as approximate.

## Still open

- Compare our actual placement/routing with these references and record each
  adopted rule or justified difference in the design basis.
- Confirm polygon fill and routing-restriction behavior in a native
  Eagle-compatible viewer or matching Gerber set, and establish reference
  revision identity before relying on exact routing or dimensions. The
  derived explicit-copper inspection above advances the review but does not
  close stackup, return-current, clearance or manufacturing validation.
- Full manufacturer PCB CAD was not acquired in this search.
- Human review of applicability remains pending; this is research evidence,
  not release sign-off.

## Schematic draft checkpoint

Draft `20260916T164445Z-schematic-7ad1be18` preserves the accepted circuit and
renders a dated, single-sheet PDF with functional headings and drawn passive
banks. The assistant inspected the preview; there are no machine blockers.
The new local-route text keepouts and multi-bend fallback separate the
interrupt wire from CSB supply text. Known visual limitations remain at U1:
ground/supply glyphs two pin rows apart touch. Those already-emitted stubs and
glyphs still require refinement. Accepted schematic, PCB and
netmap bytes remain unchanged; no human acceptance is recorded.
