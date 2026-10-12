# PCB maintenance tools and lessons from the first Rover layout

The root KiCad files are the owner-controlled design. Start with the latest saved
files for every change. No tool in this directory reconstructs the board or writes
native CAD. The seven one-time placement/routing/finishing scripts were removed
once their independent copper intent had been captured; they were not a safe
maintenance interface for owner-edited CAD.

## Three tools, three purposes

| Tool | Input and output | What it establishes |
| --- | --- | --- |
| `audit_net_intent.py` | Current schematic export + PCB + historical reference; JSON in `.pcb-copilot/review/` | Current numbered-pad/net membership, plus net identity on surviving historical route geometry |
| `render_assembly.py` | Disposable copy of current PCB/settings; three SVG views + `review-source.json` | Views and source hashes match; no DRC or engineering approval |
| `make_review_pdf.py` | Fresh views from the preceding exporter; `output/pdf/rover-pdb-pcb-review.pdf` | Four-page review of those CAD bytes, with native dimensions and detail extents; explanatory notes describe A10/P5 routing intent |

Run the audit with KiCad's Python from the workspace root:

```powershell
& 'C:/Program Files/KiCad/10.0/bin/python.exe' projects/rover-pdb/layout/audit_net_intent.py
```

An optional positional PCB path audits a candidate instead. `--output PATH`
chooses the report destination. The schematic netlist is exported afresh to a
system temporary directory, not read from an old preview cache. Source hashes
are checked before and after. The program never saves native CAD.

`authored-copper-reference.json` is a historical reference of 373 explicitly
authored tracks and 106 vias, captured from the original P1 recipe before its
removal. Its provenance includes recipe hashes and the original board hash.
It is not the specification for all future routing. Missing/replaced segments and
new geometry are reported separately; they do not force a user to restore old
routes. A different net on surviving reference geometry is an error. Arcs and
geometry outside the original 100 x 100 mm rectangular outline are not covered
by this comparison. Always run shared native parity and DRC after an edit.

Run the review exporter with Python and the PDF tool with the existing document
runtime that supplies PyMuPDF and ReportLab. `make_review_pdf.py` refreshes all
three native views before building the PDF; do not assemble a review from cached
screenshots. Optional `--inspection-dir PATH` exports page images for visual
inspection without leaving them in the project by default. Inspect every page.
These outputs are review aids, not fabrication files.

The back-copper view includes B.SilkS and is mirrored to show the physical
underside; the connector legends therefore read normally. The manifest records
this view orientation. Front and assembly views are from the component side.

The PDF reads the closed board outline, mounting-hole positions, revision and
component detail bounds from the exact disposable native snapshot. It checks
the SVG page sizes against that outline and scales X and Y independently, so
the 80 x 100 mm P2 board is not cropped using the old square-board assumption.
Source-hash checks still bracket export and publication. The stable PDF filename
is overwritten only after successful generation; old P1 files are historical
exports, not the current review.

## What is reusable from Rover

- Read numbered pad nets from current native CAD. Before constructing a route,
  check that every intended endpoint belongs to the same net. Do not invent net
  names from a script's old assumptions. Verify again after serialization and
  native connectivity rebuilding: a touching via can be reassigned to another net.
- Treat the converter's VIN bypass, PGND return, SW/inductor and BOOT loop as a
  coupled placement problem. Short connection lengths and uninterrupted local
  returns matter more than filling every remaining area with copper.
- Keep feedback/AGND and shunt Kelvin connections distinct from load-current
  paths, even where DRC sees the same net. DRC alone cannot establish that a thin
  sense trace is not an unintended parallel power route.
- Route power cells deliberately, then remaining low-current signals. The original
  grid router completed four residual connections; it did not design the three
  converter cells. Native DRC assessed proposed geometry, not thermal performance.
- Use actual pad, body and courtyard extents for placement. Check visible labels
  against both copper openings and assembled component bodies. A 3D model is a
  visualization; its absence does not imply an absent electrical footprint.
- Locks can protect routes during authoring, but handover must state intentional
  locks and provide netclass widths/presets. Give the owner ordinary native tracks,
  not drawings that merely resemble copper. Width defaults are not ampacity proof.
- Bind each successful preview to exact saved sources and request bytes. An owner
  save invalidates the preview. Stale pictures or old construction instructions
  must never replace current CAD or imply that a fresh check passed.

The electrical, mechanical and thermal constraints remain in the project's
current design/review documents. These lessons preserve the reasoning from the
removed scripts without leaving another executable copy of the old board design.

## Making an authorized edit

Copy the current saved PCB and settings to a disposable working location. Edit
only requested objects, then use the shared pipeline:

```text
pcb-copilot update-layout PROJECT --candidate CANDIDATE
pcb-copilot update-layout PROJECT --candidate CANDIDATE --apply
```

Save and close KiCad before apply; unsaved editor state cannot be merged by the
file pipeline. Preview and apply must use identical requests and current source
hashes. For scoped schematic work use `update-schematic --candidate` on a copied
native hierarchy, not regeneration from an old intent file. Only `pcb-copilot
release` produces supported manufacturing output after its required review.
