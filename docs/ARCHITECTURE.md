# Architecture

`pcb-copilot` is the public entry point. Current KiCad files live at each project
root. Intent, requirements and cited evidence describe the intended circuit;
`netmap.json` records a reviewable connectivity contract. Git provides history.

## Boundaries

- `evidence/`: exact-byte archives, provenance, coverage and cited extraction.
- `schematic/`: typed intent, drawing, hierarchy, native netmap and updates.
- `layout/`: real footprint geometry, placement constraints, routing and updates.
- `review/`: current machine checks, bounded findings and human sign-off.
- `transaction.py`: contained snapshots, current-input checks and rollback.
- `manufacturing.py` and `release.py`: native exports and complete-package publication.
- `packages/kicad-claude-mcp/`: imported file/geometry/native-routing adapters.

The support dependency keeps its Python name `kicad_claude`; it is no longer an
MCP server. Unused provider, simulation, plugin and agent integrations are removed.
There is one workspace lockfile and Python environment.

## A project

`project.yaml` declares schematic, PCB, netmap, evidence index and manufacturing
profile. Paths must stay inside the project. Hierarchical child sheets remain
beside the root schematic. Local symbol/footprint libraries, requirements, design
basis, deviations and reference reviews are inputs. The template describes the
same format without claiming to contain a finished board.

## Transactions and state

Updates create a disposable copy, build/check a candidate, publish local previews,
and replace current files only with `--apply`. Layout requires native parity,
placement checks, zone fill, repeated DRC, routing completeness and a before/after
comparison. A candidate cannot discard all routing or pours. Failures preserve
current CAD; edits during a transaction invalidate its starting snapshot.

Internal candidate helpers are shared by the update commands and tests. They do
not expose another user-facing draft/accept workflow. Only the latest previews
are retained under ignored `.pcb-copilot/preview/`.

Human decisions include exact schematic/hierarchy, PCB, profile and aggregate
input hashes. Rules, evidence, requirements and library edits therefore invalidate
sign-off as well as CAD edits. Legacy hash-only state is not approval.

Review checks a disposable copy and reports all registered results even after a
check fails. Native reports must be produced by a successful current invocation;
missing/malformed reports cannot count as zero findings.

Release snapshots inputs, runs fresh review, exports manufacturing files and embeds
the reviewed source bytes. `SOURCE.json` hashes the inputs and package outputs.
Publication replaces the complete fabrication directory and release-state record
with rollback on failure. Status checks both source freshness and output integrity.
A released state says this exact package passed the registered checks and recorded
human decisions; it cannot prove that those human judgments were correct.

Gerber tools include generated timestamps, so two runs need not be byte-identical.
Each package is independently verifiable against its recorded source and output
hashes and native tool version.

`parts` imports exact LCSC identities into separate local libraries and archives
supplier CAD provenance. `parts_converter.py` retains the MIT-licensed conversion
adapter from BeckhamLabs kicad-jlcpcb (see its adjacent license). The
[easyeda2kicad](https://github.com/uPesy/easyeda2kicad.py) dependency performs CAD
conversion; KiCad normalizes footprints. Supplier metadata is separate from
manufacturer datasheet and reference-design evidence.
