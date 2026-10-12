# How the pipeline fits together

`pcb-copilot` is the public entry point. Each board's saved native KiCad files
are its current design; YAML intent describes an optional generation recipe.
A candidate is a disposable edited copy, never a second authoritative board.

## L0–L2: commands, decisions and artifacts

| Command | Implementation | Reads / produces |
| --- | --- | --- |
| `status` | `status.py` | Current inputs and release hashes; no CAD writes |
| `research` | `evidence/commands.py` | Exact source archives, index, extracts/search plans |
| `parts` | `parts.py` | Exact LCSC lookup/import; isolated project libraries and supplier provenance |
| `update-schematic --candidate` | `schematic/native_candidate.py` | Saved native hierarchy → ERC/render/PCB parity → checked apply |
| `update-schematic --intent` | `schematic/update.py` | Explicit redraw from typed intent; not a merge of owner edits |
| `update-layout` | `layout/update.py` | Native candidate or generated proposal → parity/placement/refill/DRC → checked apply |
| `review` | `review/commands.py`, `review/checks.py` | Fourteen current checks, with scope and human-decision findings |
| `prepare-signoff` | `review/signoff.py` | Creates an unsigned, hash-bound worksheet |
| `release` | `release.py`, `manufacturing.py` | Fresh review → native exports → complete verified fabrication package |
| `clean` | `cleanup.py` | Explicit preview-file allowlist; preview first, `--apply` removes reproducible output |

Source paths above are relative to `src/pcb_copilot/`. Use `--help` on the public
command, not project scripts or private helpers, to discover supported options.

## L3–L4: implementation and tests

- `schematic/` contains typed intent, symbols/wires/fields, hierarchy, native
  netlist extraction and drawing checks. Native candidates preserve sheet bytes.
- `layout/` contains real footprint geometry, placement constraints and optional
  routing. These are proposals; a completed external KiCad candidate is equally
  supported. The accepted Rover used this external-candidate branch.
  `schematic_links.py` reads native netlist sheet/unit UUID paths and verifies
  forward-annotation identity separately from references and pin-net parity.
  Staged candidates can acquire missing links only after physical/electrical
  parity; conflicting links block. The binder changes path metadata only.
  Schematic-only updates use the same binder and final link check, including
  atomic publication of any required legacy PCB metadata with the schematic.
- `evidence/` checks exact archive identity, cited extraction and coverage.
  A downloaded supplier footprint is not manufacturer qualification.
- `review/` connects independent machine checks and human decisions. DRC alone
  cannot detect an electrically wrong but internally consistent pin assignment.
  `routing_topology.py` uses native pad-shape/layer contacts and straight-track
  geometry to report covered tracks, short segments and off-centre entries.
  It never rewrites copper or replaces the native DRC connectivity gate; via,
  arc and zone topology, custom/offset pad anchors and ampacity are outside its scope.
- `update_guard.py`, `transaction.py` and `preview_publication.py` bind previews
  to saved inputs, serialize writes, preserve rollback originals and prevent
  stale output from being represented as a fresh result.
- `packages/kicad-claude-mcp/` keeps the historical Python import name
  `kicad_claude`. It is a local parser/geometry/native-routing dependency, **not
  an MCP server or a separate user workflow**. Its README maps the retained APIs.
- `tests/` follows these boundaries; package tests cover the optional routing
  adapter. Native/slow and network tests are marked where applicable.

The adapters' unused alternate PCB editor, duplicate exports, static fabrication
presets and unused mutation helpers were removed after dependency tracing.
The real native exporters, schematic builders and optional routing remain.
External dependencies stay only because retained code uses them; there is one
workspace lockfile and one installed Python environment.

## Project folders: necessary inputs versus optional material

`project.yaml` declares the root schematic, PCB, connectivity snapshot, evidence
index and fabrication profile. Child sheets remain beside the root schematic.
Requirements, design basis, reference review, deviations and review profile stay
at the root because the shared pipeline reads those conventional names.
`netmap.json` is the checked connectivity snapshot; reconcile it from owner CAD.

Local libraries and exact evidence remain self-contained per board. Different
boards can need copies of the same part; cross-project symlinks or `..` evidence
references would couple their correctness and lifetime. Rover has one active
project, `projects/rover-pdb`; its retired predecessor is archived outside the repo.
A model or symbol that is absent from the current BOM may still support an
archived comparison or the owner's subsequent edits. Do not delete it by name.

Rover's optional material has distinct homes:

- `docs/design/`: component calculations, sourcing and layout guidance.
- `docs/review/`: review conclusions; `records/` holds the small measured reports
  that support them. Historical reports keep their original hashes and scope.
- `output/`: current human-facing schematic/PCB exports and their provenance.
- The superseded A3 teaching guide, source and citations are in the external
  2026-10-07 recovery archive; current reasoning lives in `docs/design/`.
- `simulation/`: reproducible studies plus actual measurement/model results.
- `layout/`: read-only Rover-specific audit and review-export tools. The original
  authoring recipe was reduced to an independent static copper reference and
  review lessons; it cannot rebuild over an owner-edited PCB.

## Updates, review and release

Updates capture the declared inputs and requested candidate, check disposable
copies, and require the exact successful preview before `--apply`. A new save,
changed candidate/settings, failed attempt or prior application invalidates that
authorization. GUI locks prevent applying while KiCad may hold unsaved state.
Byte comparisons and rollback address file consistency, not engineering intent.

Review also copies only declared inputs, rather than duplicating guides, PDFs,
simulations and old work directories on every run. It rechecks owner inputs
before publishing. Every registered check reports its scope, even when another
fails. Missing native reports do not count as zero findings.

Release reruns review, checks current named human decisions and uses native
exporters. It publishes the whole `fabrication/` package with source/output
hashes or restores the previous package on failure. `status` detects stale or
modified packages. Export timestamps can vary; package hashes identify the exact
output. Exporting never places an order.

## Cleanup and retention

On 2026-10-07 the owner closed Rover work, retained only `projects/rover-pdb`,
retired the 18 V / 12 V comparison and the barometer/IMU/GNSS projects, and
resumed TMS. `CODE/PCB` is the sole PCB workspace; the three dated `CODE/PCB-*`
scratch/backup folders were removed after verified archival. The separate
`CODE/Rover` and `CODE/TMS` application/data repositories are independent work.

Recovery is at `C:/Users/tae06/.codex/archives/pcb/cleanup-20261007/`:
four source ZIPs, a supplemental ZIP for nested editor Git history, per-file
SHA-256 `manifest.json`, Git history bundle and the exact deletion plan.
Archive entries were reread and compared with source bytes before deletion.
The sole Rover CAD, its libraries, indexed evidence and matched JLCPCB preview
were preserved. The final order review and assembly-preservation records were
copied byte-for-byte into Rover's `docs/review/records/` before scratch removal.
Superseded loose exports, the A3 guide, editor history and completed candidate
trees belong to that recovery archive, not the current working tree.

Retired sensor inputs needed by native/parser/failure-injection tests are fixed
fixtures under `tests/fixtures/boards`; they have no active project entry point.
Tests resolve them with `tests.board_fixtures.board_source` and mutate temporary
copies only. Do not delete coverage to make project retirement pass.

Validation after this cleanup completed all 742 collected non-network tests,
including native integrations, across checkpointed runs. All 223 protected
current CAD, library, evidence and manufacturing-preview files matched their
pre-cleanup hashes. Detailed test results and preservation hashes are in the
archive's `validation.json` and `preserved-current-files.json`. The software
tests passing does not clear the separately recorded TMS design blockers.

The ordinary `clean PROJECT` command lists only known generated preview files;
`--apply` removes those and invalidates update preview bindings. Unknown files,
source archives, native CAD, sign-offs, accepted packages and recovery data are
outside its scope. Active operations or unresolved recovery block cleanup.

Do not put unique research or review evidence in `.pcb-copilot/`. Keep a useful
final record in `docs/review/records/` and sources in `evidence/`. Interrupted
`recovery-*` data must be resolved, not cleaned. Historical owner snapshots and
acceptance originals require an explicit verified backup before one-time removal.
PSpice's vendor directory is restored on demand from its exact retained ZIP.

The 2026-10-01 deep cleanup was backed up outside this repo at
`C:/Users/tae06/.codex/archives/pcb/repo-cleanup-20261001-042706/`.
`before-cleanup.zip` and `manifest.json` preserve all non-environment inputs,
including untracked Rover history. The backup is recovery history, not an active
pipeline dependency. No current CAD or owner decision was replaced by cleanup.
The `retired-work/` sibling also retains the old pipeline work trees and editor
histories outside the repository. Automatic approval blocked their bulk deletion,
so this part of cleanup used a reversible move rather than permanent removal.
Excluding Git, the environment and regenerating caches, the working tree went
from 1,507 files / 384.7 MB to about 620 files / 224.8 MB. The active Rover root
went from 42 files to 24. This is reduced working-tree clutter, not a claim that
the external recovery archive occupies no disk space.

Later on 2026-10-01, the owner requested one Rover project. The current
`rover-pdb-readable` directory became `projects/rover-pdb`. The earlier
LM73606 comparison project, including all 68 files, was moved intact to
`C:/Users/tae06/.codex/archives/pcb/rover-consolidation-20261001-114628/original-rover/`.
The moves preserved file bytes, including the owner's newly saved CAD edits;
they did not merge circuits or establish a fresh CAD review. Current commands
and project identity use `rover-pdb`. Historical reports and the A3 guide retain
their original names, source hashes and revision scope.

## Rover lessons used by the shared pipeline

These requirements apply to all current and future boards. The enforcement
column distinguishes automatic gates from recorded human inspection.

| Lesson | Enforcement |
| --- | --- |
| Preserve owner saves and exact evidence; redraw only when requested | Native candidate paths, preview/input hashes, GUI locks, transactional rollback and exact evidence hashes |
| Check pin numbers, real pads, sourcing and F8 identity separately | Native schematic/PCB parity, physical-part comparison and schematic UUID-link checks |
| ERC/export success is insufficient for a readable drawing | Mandatory `shared.schematic-readability` human release item; inspect every rendered sheet at page and circuit scale under the Gala/Gross rules |
| Connected thin sense paths do not establish a usable power path | Refilled DRC plus topology advisory; mandatory `shared.layout-handover` inspection of critical power/return/sense paths and physical limits |
| Handover must remain editable | Routing settings/lock advisories and the shared layout item; intentional owner locks require explanation |
| Supplier origin, rotation, pin 1 and local 3D models are distinct | Geometry-bound exact-part assembly rules, centroid-order tests, net-linked wire-pad labels and separate current supplier review |
| Retail stock differs from assembly allocation | Exact C-number/MPN/quantity checks; supplier allocation and placement remain separate review evidence |
| Fresh source hashes cannot renew stale exports | Fresh preview publication, output/source manifests and atomic release; never mix BOM/CPL/Gerbers from different runs |
| Remove obsolete work without losing the proof | Allowlisted ordinary cleanup; verified external archive and retained final evidence for deep cleanup |

`review/signoff.py` appends both shared items to every loaded project profile.
Local YAML may add board-specific decisions but cannot use the reserved
`shared.*` IDs. `prepare-signoff` includes the shared items unsigned; `review`
and `release` block until current named decisions cover them. The profile hash
includes the shared policy text, so a policy change invalidates prior decisions.
Existing assembly, DFM, stock and update gates remain in force. Automation
checks recorded evidence and consistency; it cannot perform a human inspection.

Rover demonstrated why native edit preservation, datasheet pin-map checks,
separate power-loop review, selectable routing defaults, unlocked handover copper
and source-bound rendered views matter. These are now in the update guards,
routing-settings review and shared design/workflow rules. Only four residual
low-current Rover connections used grid routing; its power layout was explicit
scripted geometry, followed by native parity/DRC and author review. This history
does not establish thermal, EMI, mechanical or regenerative-energy performance.

The manual fourth-servo update exposed a separate omission: matching references
and pin nets did not establish schematic UUID links for F8. Link verification
and candidate-only missing-link binding now cover that case. The routing audit
also surfaces overlaid fragments and pad entries for local review; these were
not covered by ordinary continuity checks. It does not claim to repair or
validate the whole historical Rover layout.

The parts conversion adapter retains its adjacent third-party license;
`easyeda2kicad` performs supplier conversion and KiCad normalizes footprints.
License and provenance files are required source material, not unused clutter.
