# TMS v3: rework starting point

Open [tms-v3.kicad_pro](tms-v3.kicad_pro). The saved seven-sheet schematic and
PCB are the owner's current files. The 2026-10-07 workspace cleanup preserved
their bytes and established the audit below; no circuit or routing repair was
applied. Read [requirements](REQUIREMENTS.md), [design basis](DESIGN_BASIS.md),
[deviations](DEVIATIONS.md), [reference review](REFERENCE_REVIEW.md) and
[review profile](review-profile.yaml) before choosing the next change.

## Current audit: 2026-10-07

The [full shared review](docs/review/records/rework-baseline-20261007.json)
reports seven passing checks and seven blockers. The
[native ERC report](docs/review/records/erc-20261007.json) preserves the individual
findings. These reports describe saved CAD, not an approved design.

| Check | Result |
| --- | --- |
| Source integrity | Research and archived datasheets pass |
| ERC | 2 disconnected-pin errors and 3 dangling-wire warnings; 37 unspecified-pin warnings excluded by the existing policy |
| Saved connectivity snapshot | Stale for two components; current schematic and PCB disagree |
| Forward annotation | PCB schematic links are absent; ordinary F8 updating is not yet a safe handover |
| Native DRC | 1 error, 15 warnings and 4 unconnected items in both refilled runs |
| Independent manufacturing baseline | 244 errors and 4 unconnected items against the dated JLCPCB profile; includes settings, annular-ring, clearance and silk findings |
| Assembly contract | J1/J2 have conflicting values without exact MPN identity |
| Routing topology | 55 short-track and 3 covered-track advisories; these require local inspection, not automatic deletion |
| Human decisions | 0/12 current decisions, including the two mandatory shared items |

## Visual inspection of the saved schematic

All seven native PDF pages were inspected at full-page and circuit scale on
2026-10-07. This is author inspection, not an owner's release decision.
The exact render and its source hashes are recorded in
[visual provenance](docs/review/records/visual-baseline-20261007.json).

| Sheet | Remaining presentation issues |
| --- | --- |
| Overview | Six small hierarchy boxes occupy a narrow column on a mostly empty A1 page; there is no readable system-level power/interface flow or load summary |
| Power and protection | Power assertions are detached; some wiring visually approaches terminals without agreeing with native connectivity; assumptions are absent |
| Load cell / ADS1256 | Bypass, reference, clock and interface groups rely on matching detached labels; pin arrangement follows the package rather than the signal flow |
| Pressure / ADS1220 | Input and interface parts are remote from the IC; bypass parts use detached rail groups; most of the sheet is unused |
| Controller and telemetry | Long socket pin lists and labels dominate; bypass parts and the power assertion are detached; module/interface roles need clearer grouping |
| Ignition control | Sparse groups and labels make page flow difficult to follow; native ERC reports an unresolved disconnected terminal; no functional change was made |
| External connectors and test | Connectors and test points are separated into label lists; destination context and documented electrical assumptions are missing |

Titles and hierarchy are present. That does not establish readability or
electrical agreement. Follow the shared Gala/Gross conventions for any authorized
presentation work, and prove unchanged native pin/net and explicit-NC membership.

## Continue from this state

The [2026-10-07 pipeline validation](docs/review/pipeline-validation-20261007.md)
ran 25 CLI commands on disposable copies through research, import, native
previews, blocked application, review, sign-off preparation, release and cleanup.
The expected blocking and preservation checks passed. TMS remains blocked;
J1/J2 part identity prevents even a completed quotation preview. The report
states which successful export/publication paths could not be reached.

First reconcile which saved circuit is intended before updating the netmap or
PCB links. A drawing-only edit cannot silently repair a circuit discrepancy.
Then prepare a scoped native candidate and inspect every changed sheet using
the [shared workflow](../../docs/WORKFLOW.md). Do not replay the old intent over
owner edits, discard routing or silence findings by broadening deviations.

The original PDR and Rev D BOM remain historical requirements evidence, not
current production instructions. The open engineering decisions remain in the
existing requirements/profile; the cleanup and this audit resolve none of them.
Layout, assembly and release stay blocked pending their respective checks.

```powershell
uv run pcb-copilot status projects/tms-v3
uv run pcb-copilot research projects/tms-v3 --verify
uv run pcb-copilot review projects/tms-v3
```
