# TMS A1 presentation and component audit

Date: 2026-10-14. Author: Codex. Status: A1 presentation installed under the
owner-approved schematic-only workflow exception. Electrical acceptance and
fabrication approval remain open; human review items are unsigned.

The owner rejected A0's presentation. Its prior author review did not establish
that it met the expected drawing standard. A1 was prepared from the current
saved native hierarchy, retaining physical component identities and electrical
content. The retired TMS fixture and the old capture script were not replayed.

## What changed and what was inspected

Rover's owner-adopted Gala/Gross references and docs/DESIGN_RULES.md were
reread. Every final sheet was inspected at full-page and readable circuit scale;
changed views were freshly exported and inspected after the last edits.

| Sheet | Format | Presentation work |
| --- | --- | --- |
| System overview | A3 | Consistent title, hierarchy labels, domain/target notes and revision history |
| Power and protection | A3 | Local buck support loops, vertical dividers, clear bootstrap, direct output sensing, separate analog/RF groups and correct R5 loop-test explanation |
| Teensy controller | A4 | Compact module/support layout, nearby VIN configuration, direct LED circuits with a common visible return, readable pin/NC inventory |
| Thrust acquisition | A3 | Recognizable dual buffer triangles and steering diodes; clear feedback; R22/R23/C22 spacing repaired so wires and fields do not run over capacitor plates |
| Ratiometric reference | A4 | Familiar unity-buffer loop, vertical divider, visible local bypass and output bank; explicit unused package pads |
| Pressure acquisition | A4 | Compact left-to-right scaling/filter/ADC chain, local support, explicit unused-pin audit note |
| XBee telemetry | A4 | Compact supply/UART/recovery circuit, local pulls/probes, exact antenna interface and missing-capacitor audit note |
| Ignition interface | A4 | Short local driver/flyback circuit, readable contact-domain wiring, current/ARM/return assumptions beside the relevant groups |

Intentional style exceptions: bidirectional digital interfaces use sheet labels;
fixed connector pin order is preserved. Module pad identifiers remain vendor
signal names. U6's unused package pads are drawn separately with NC marks and
an explanation. Unavoidable separate-net crossings have no dot and are away
from pin ends and text. No established signal-label scope was changed.

## Electrical preservation and source audit

- 98 physical references: same UUIDs, values, MPN/specification, datasheet
  properties and footprint assignments as the saved A0 baseline.
- Native connected pin groups: zero membership differences, allowing generated
  auto-net spelling to differ when functional pin text changes.
- 45 intentional NC pin identities preserved. All 321 physical pin records are
  accounted for; the normal netmap omits NC pins, so the audit explicitly reads
  native NC markers as well.
- Fresh candidate KiCad ERC: zero errors, zero warnings. No new exclusions or
  weakened rules were added. Candidate presentation diagnostics: no findings.
- All 38 exact evidence records verify. Revision metadata was filled from the
  archived documents; their bytes were preserved.
- No PCB copper, placement, footprint geometry or rule file was changed.

Records: records/presentation-checks-20261014.json,
presentation-erc-20261014.json and presentation-metrics-20261014.json. The
checks bind the baseline, candidate and rendered PDF by hash.

The complete component audit is ../design/COMPONENT_VERIFICATION.md and
../../output/component-verification.pdf. It contains seven circuit explanations,
every part's purpose/value basis/source/check, a required-support matrix,
device pin tables and external assembly parts. The CSV inventory lists all
98 references individually; the PDF groups identical parts with explicit refs.

F01-F10 are unresolved electrical/physical findings. In particular, Digi
90001543 W recommends 47 pF at VCC, absent in A0, and ADS1220 p50 recommends
unused AIN3 floating while A0 grounds it. The older online Digi 8.2 pF wording
is recorded as a revision conflict. These findings were not silently repaired
inside a presentation-only edit. Clean ERC does not settle them.

## Installation and scoped workflow exception

The normal `update-schematic --candidate` preview was attempted against the
empty TMS PCB. It aborts with `Cannot obtain native board outline` before a
successful apply binding is produced. The shared workflow also requires matching
routed PCB for checked application. No successful normal apply is claimed.

The owner explicitly answered "Install the polished schematic only (Recommended)"
to the scoped exception request on 2026-10-14. The exact reviewed eight sheets,
local symbol presentation, derived netmap and rendered drawing were installed
using the shared transaction lock, hash guards and rollback support. Root CAD is
now A1. `output/tms-schematic.pdf` matches the reviewed A1 PDF byte for byte.

Record: `records/presentation-install-20261014.json`. It binds the authorization,
before/after CAD hashes, unchanged project inputs and prior visual review. This
is a single approved installation exception, not a successful normal CLI apply
or a relaxation of subsequent update/release gates. PCB, footprints, rules and
project settings are unchanged. F01-F10 remain open.

The original candidate checks and component-audit record describe the pre-install
review. Current installed checks and inventory hashes are recorded separately in
`records/installed-schematic-checks-20261014.json` and
`records/installed-component-audit-20261014.json`.
