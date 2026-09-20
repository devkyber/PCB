# Results and Progress

Snapshot: 2026-09-20. Last verified implementation: `a603861`.
These are review drafts, **not approved** designs or fabrication packages.

## Open the results

Start with the schematic PDF and PCB SVG. Open the KiCad files when you want
to edit. All links below refer to the selected local drafts in this workspace.

| Board | Schematic | PCB layout | Layout result |
| --- | --- | --- | --- |
| BMP390 | [PDF](../projects/baro-bmp390/.pcb-copilot/drafts/20260916T181255Z-schematic-7ad1be18/preview.pdf) · [KiCad schematic](../projects/baro-bmp390/.pcb-copilot/drafts/20260916T181255Z-schematic-7ad1be18/baro-bmp390.kicad_sch) | [SVG preview](../projects/baro-bmp390/.pcb-copilot/drafts/20260920T105547Z-layout-050ac82f/preview.svg) · [KiCad PCB](../projects/baro-bmp390/.pcb-copilot/drafts/20260920T105547Z-layout-050ac82f/baro-bmp390.kicad_pcb) | 13 placements; 0 machine blockers, 26 warnings. [Report](../projects/baro-bmp390/.pcb-copilot/drafts/20260920T105547Z-layout-050ac82f/review.json). |
| ICM-42688 | [PDF](../projects/imu-icm42688/.pcb-copilot/drafts/20260916T181255Z-schematic-b0464d86/preview.pdf) · [KiCad schematic](../projects/imu-icm42688/.pcb-copilot/drafts/20260916T181255Z-schematic-b0464d86/imu-icm42688.kicad_sch) | [SVG preview](../projects/imu-icm42688/.pcb-copilot/drafts/20260920T110417Z-layout-43b0bb86/preview.svg) · [KiCad PCB](../projects/imu-icm42688/.pcb-copilot/drafts/20260920T110417Z-layout-43b0bb86/imu-icm42688.kicad_pcb) | 13 placements; 0 machine blockers, 23 warnings. [Report](../projects/imu-icm42688/.pcb-copilot/drafts/20260920T110417Z-layout-43b0bb86/review.json). |
| NEO-M9N | [PDF](../projects/gnss-neom9n/.pcb-copilot/drafts/20260916T181255Z-schematic-c088e056/preview.pdf) · [KiCad schematic](../projects/gnss-neom9n/.pcb-copilot/drafts/20260916T181255Z-schematic-c088e056/gnss-neom9n.kicad_sch) | [SVG preview](../projects/gnss-neom9n/.pcb-copilot/drafts/20260920T105623Z-layout-213de32a/preview.svg) · [KiCad PCB](../projects/gnss-neom9n/.pcb-copilot/drafts/20260920T105623Z-layout-213de32a/gnss-neom9n.kicad_pcb) | No placement applied; source positions retained. 15 blockers, 39 warnings. [Report](../projects/gnss-neom9n/.pcb-copilot/drafts/20260920T105623Z-layout-213de32a/review.json). |
| TMS V3 | [Seven-page PDF](../projects/tms-v3/.pcb-copilot/drafts/20260916T181255Z-schematic-2b264620/preview.pdf) · [KiCad root schematic](../projects/tms-v3/.pcb-copilot/drafts/20260916T181255Z-schematic-2b264620/tms-v3.kicad_sch) | [SVG preview](../projects/tms-v3/.pcb-copilot/drafts/20260920T105734Z-layout-d9643f01/preview.svg) · [KiCad PCB](../projects/tms-v3/.pcb-copilot/drafts/20260920T105734Z-layout-d9643f01/tms-v3.kicad_pcb) | No placement applied; source positions retained. 21 blockers, 38 warnings. [Report](../projects/tms-v3/.pcb-copilot/drafts/20260920T105734Z-layout-d9643f01/review.json). |

The schematic previews were selected on September 16; layout reports were
refreshed on September 20. These are separate proposals, not an accepted
schematic-to-PCB revision pair. Layouts use the currently accepted circuit.
TMS hierarchy introduces qualified net names that still need reconciliation
before a revised schematic and PCB can be accepted together.

All human reviews remain pending. Zero machine blockers is not a visual,
electrical, mechanical, RF, or safety approval. Layout drafts are unrouted;
STEP exports in their folders are partial and do not prove component/enclosure fit.
Refresh a draft's review before considering acceptance; older draft metadata
may require generating a new proposal. Do not bypass a stale-snapshot refusal.

### If a link is unavailable

Drafts are ignored local outputs, so they do not travel with a fresh checkout
or appear on a hosted Git repository. Do not delete `.pcb-copilot` to tidy up:
it contains these results and may contain manual edits. To create a new draft,
use the commands in [Workflow](WORKFLOW.md); its ID will differ from this snapshot.
Keep TMS child sheets beside its root schematic when opening or copying it.

### See the research, not just the drawings

Each reference review distinguishes search, acquisition, inspection and
validation, and links findings to the project's archived sources:

- [BMP390 reference review](../projects/baro-bmp390/REFERENCE_REVIEW.md)
- [ICM-42688 reference review](../projects/imu-icm42688/REFERENCE_REVIEW.md)
- [NEO-M9N reference review](../projects/gnss-neom9n/REFERENCE_REVIEW.md)
- [TMS V3 reference review](../projects/tms-v3/REFERENCE_REVIEW.md)

## Progress against our purpose

The goal is less repetitive work for the engineer, not autonomous design.
Reliable tooling is demonstrated more strongly than actual time saved.

| Essential value | Implemented | Still missing or unproven |
| --- | --- | --- |
| Find and verify sources | Acquisition, exact-byte archives, citations and integrity checks; assistant-led searches | Broad PDF fact extraction and verification of electrical conditions; CLI search plans are not a live search provider |
| Learn from reference schematics and PCBs | Separate records, native connectivity comparisons and scoped copper inspections | Complete variant, return-path, RF, mechanical and applicability review |
| Start from a useful schematic | Functional blocks, local wiring, power symbols, TMS hierarchy | Human readability review and measured cleanup effort; explicit intent must still be prepared |
| Get a PCB starting point | Real-footprint checks, placement proposals, constraints, previews and optional routing interface | Existing circuit parts must already be on the PCB; fresh-board initialization, GNSS rule areas/RF-zone notch and TMS J9 decisions remain open |
| Edit without losing work | Isolated drafts, stale-base checks, review refresh and explicit acceptance | Rule/zone changes require a new proposal; a placement blocker currently prevents all proposed moves |
| Trust the scope of checks | Regression/fault tests and explicit unresolved findings | Tests do not establish circuit performance, manufacturability or engineering suitability |

Latest full non-network verification at `a603861`: **670 passed, 48 skipped,
3 deselected**. The skips were 44 library-index-dependent tests and four
Java/Freerouting dependency checks. The real optional-router run remains unverified.
Accepted designs and the selected layout PCB/settings bytes were unchanged.

Plans 1–2 are implemented. Plan 3 has schematic tooling and drafts, with human
review pending. Plan 4 has reviewed layout tooling and four intents; the
human checkpoint and clean GNSS/TMS placements are unfinished. Plan 5 unified
review, release and replacement-dependent cleanup is not complete.

## Next priorities

1. Use one small board with the human owner and measure research, correction,
   review and editing effort—not just generated files or passing tests.
2. Support a fresh PCB from an accepted schematic and reduce manual intent
   preparation; preserve manual CAD when constraints change.
3. Make findings actionable with affected refs, source citations, proposed
   corrections and specific owner decisions. Consider block-scoped proposals
   without weakening whole-board acceptance.
4. Finish unified review/release tooling against fixtures. This does not
   approve or release the real boards. Delete remaining compatibility files
   only when their replacements and current facts are verified.

See [Limitations](LIMITATIONS.md) for detailed boundaries and the
[roadmap](superpowers/plans/2026-09-14-pcb-copilot-remake-roadmap.md) for task history.

## What belongs in the repository

For daily work, use this page, [Workflow](WORKFLOW.md), and your board under
`projects/`. You do not need to read the implementation plans or tool internals.

| Location | Why it remains |
| --- | --- |
| `projects/` | Accepted KiCad files, evidence, libraries, requirements, decisions and draft inputs |
| `src/`, `tests/`, `tools/` | Implementation, regression protection and still-used or not-yet-migrated KiCad capabilities |
| `docs/` | Canonical guidance; Python helpers here are still imported and are not disposable prose |
| `migration/`, `scripts/` | Preservation inventory and tested migration commands |
| `.git/`, `.gitattributes`, `.gitignore` | History/recovery, exact evidence bytes and generated-file policy |
| `.venv/`, `pyproject.toml`, `uv.lock` | Working runtime and reproducible dependencies; `.venv` is local, not tracked |
| `.claude/`, `CLAUDE.md` | Configured hooks and agent operating rules; hook migration is unfinished |
| `projects/*/.pcb-copilot/` | Local drafts, previews, manual edits, research diagnostics and state—not a cache |
| `.superpowers/` | Ignored implementation review evidence and unfinished-checkpoint recovery records; not product source |
| `docs/superpowers/` | Approved specification and plans, kept separate from daily instructions |

`HUMAN_WORK.md`, project `STATUS.md`/`PIPELINE.json`, generators, build wrappers
and the manual TMS BOM are legacy material, not the current results entry point.
They still have callers or unverified replacement behavior. Removing them now
would not be a safe documentation-only cleanup. Disposable test/lint caches
can be removed and may be recreated by the tools.

### Cleanup in this revision

Seven superseded documents were removed: the old workflow chronology, two TMS
V2 history records, the archive index, the duplicate relay/ADC tutorial, and
the BMP390/IMU evaluations. Current findings remain in the canonical workflow,
architecture and project records; obsolete chronology is available in Git,
not duplicated in new archive folders.

The TMS PDR now lives beside its board. The detailed legacy rule reference is
the one retained document under `docs/history/`: existing review/deviation
identifiers still rely on it, and detailed fact migration is unfinished.
Both retained records carry warnings about stale or non-authoritative claims.
No accepted CAD, evidence, libraries, intent, settings or sign-off was changed.

Local test/lint/Python caches, empty temporary folders and two KiCad `.history`
folders were audited as disposable (the histories contain zero saved snapshots).
The environment blocked the removal command, so those local folders remain.
Draft folders and both Python environments were deliberately preserved.

Cleanup verification: 54 focused tests passed; lint passed for the changed
tests; all 37 protected-file hashes matched; all 40 evidence archive records
verified. The three generator edits leave executable syntax unchanged.
This is not another full-suite run or an engineering approval.
