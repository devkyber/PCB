# PCB Design Workspace

## Owner
Mechanical engineering student. Not EE major. Has EasyEDA experience, new to KiCad.
Takes electronics/controls roles in team projects (rocketry avionics, GNC systems).
Wants fast iteration with minimal EE friction.

## Fabrication Target
- **Primary:** JLCPCB (2-layer default, 4-layer when needed)
- **Assembly:** JLCPCB SMT assembly when needed (BOM + pick-and-place format)
- **Design rules:** JLCPCB 2-layer minimums: 0.127mm trace, 0.127mm clearance, 0.3mm via drill, 0.6mm via pad
- **Budget default (lab/project boards, not exotic EE research):** unless a spec explicitly demands otherwise, default to JLCPCB's cheapest standard options — 1.6mm board thickness, 1oz (35µm) copper, green solder mask, HASL (lead-free) surface finish, no impedance control, no gold fingers/castellated holes/blind-buried vias. These are also JLCPCB's own defaults, so they need no special config in the ordering flow. Only deviate (ENIG, thicker copper, controlled impedance, 4+ layers, non-green mask) when the circuit genuinely requires it (fine-pitch QFN/BGA soldering, high current, RF/high-speed signal integrity) — flag the tradeoff and cost bump before choosing it, don't default to it.

## Tools Installed

**Before using either MCP server in a fresh session, run the checklist in `docs/pcb-design-workflow.md` Phase 0** — venv/Freerouting/registration/compat-patch health check. Registration lives in `claude mcp list` (`claude mcp add`), not `~/.claude/settings.json` — that file is not read by this installation, confirmed 2026-08-25.

### kicad-claude-mcp (Generator)
- Location: `tools/kicad-claude-mcp/`
- MCP server registered via `claude mcp add` (see Phase 0 above)
- 105 tools: schematic capture, PCB layout, autorouting (Freerouting), DRC/ERC, Gerber export, signal integrity, SPICE
- Restart Claude Code after changes to pick up the MCP server

### kicad-jlcpcb (JLCPCB/EasyEDA Bridge)
- Location: `tools/kicad-jlcpcb/`
- MCP server registered via `claude mcp add` (see Phase 0 above)
- 13 tools: LCSC part sourcing (basic-tier preferred), EasyEDA pin-map fetching, wired .kicad_pcb generation, EasyEDA handoff for cloud autorouting, Gerber/BOM/CPL packaging
- `fetch_part_library` produces **real** libraries via easyeda2kicad: pin-accurate `.kicad_sym`, per-package `.kicad_mod`, and `.step`/`.wrl` 3D models. All land in `<project>/libs/` as one library named `jlcpcb`. **Registration in `sym-lib-table`/`fp-lib-table` is not guaranteed** — verify (grep both tables for a `jlcpcb` entry) and add manually if missing, every time, before schematic work starts.
- Real fetched symbols carry generic numeric pin names and no proper KiCad electrical pin-type metadata. Always extract the actual pin map from the fetched `.kicad_sym` before wiring — never trust a placeholder-era pin-map comment. For multi-function pins (relay COM/NO, TVS common), pull the manufacturer datasheet. See `docs/pcb-design-rules.md` §15.7.
- Check `fidelity` in the result: `"real"` = actual part geometry; `"placeholder"` = conversion failed, generic outline substituted — **must** be reviewed in KiCad before fabricating.
- LCSC metadata lookup (`lcsc_search`, `lcsc_resolve_bom`) uses the jlcparts v4 sharded JSONL format (`manifest.json` + `attributes-lut.json.gz` + `components-*.jsonl.gz`). Library fetching is unaffected (it goes straight to EasyEDA).
- Slash commands: `/pcb-new` (from description), `/pcb-from-bom` (from CSV)
- Flow: Claude sources LCSC parts → generates wired PCB → you import into EasyEDA → autoroute → order at JLCPCB

### kicad-happy (Reviewer)
- Location: `tools/kicad-happy/`
- Skills symlinked to `~/.claude/skills/`: kicad, spice, emc, datasheets, bom, digikey, mouser, lcsc, element14, jlcpcb, pcbway
- Use for design reviews, datasheet extraction, component sourcing, EMC checks

### KiCad 10.0.5
- Installed at `/Applications/KiCad/`
- kipython symlink at `~/.local/bin/kipython`
- CLI: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`

### Freerouting Autorouter
- JARs in `tools/kicad-claude-mcp/third_party/`: `freerouting-2.3.0.jar` (current) and `freerouting.jar` (2.1.0, kept as fallback)
- **2.2 and newer require Java 25** (Temurin JDK 25 at `~/Library/Java/JavaVirtualMachines/jdk-25.0.4.1+1`); 2.1.0 runs on Java 21 (also installed)
- The adapter picks the newest JAR whose JVM is actually present, so a missing JDK degrades to the old router instead of failing. Run `routing_status` to see which one you're on — **2.1.0's route optimizer is multi-threaded, upstream-broken, and cannot be disabled** (`-mt 1` and the env override were both measured not to reach it).
- Never call the JAR directly. Use `autoroute_pcb` (MCP) or `docs/route_and_fill.py` (CLI): both run one shared pipeline — DSN export → route → SES import → **zone fill** → **ground bonding** → DRC — and report `passed` only when DRC finds zero unconnected items. Raw `java -jar` skips the fill and the bonding, and an unfilled board reports every pour-connected pad as unconnected.
- Unconnected GND after autorouting is a bonding failure, not a routing failure: the router carves through pours and leaves islands. See `docs/pcb-design-workflow.md` Phase 0 gotchas.

## Project Structure
```
PCB/
├── projects/           # Each board gets its own subfolder
│   └── <board-name>/
│       ├── *.kicad_pro, *.kicad_sch, *.kicad_pcb
│       ├── fabrication/    # Gerbers, drill, BOM, PnP
│       ├── datasheets/     # Auto-downloaded PDFs
│       └── 3d-models/      # STEP exports
├── tools/              # Don't edit - cloned repos
│   ├── kicad-claude-mcp/
│   └── kicad-happy/
└── docs/               # Workspace-level docs
```

## Workflow
1. Describe the board spec in plain English with mechanical constraints
2. Claude generates schematic + PCB via kicad-claude-mcp
3. Run DRC/ERC validation
4. Run kicad-happy design review (power tree, signals, DFM, EMC)
5. Open in KiCad for visual review and manual fixes
6. Export 3D STEP model → check fit in CAD tool
7. Export Gerbers + BOM → order at JLCPCB

Full workflow: `docs/pcb-design-workflow.md` (6-phase process with gate checklists)
How the enforcement itself is built: `docs/ARCHITECTURE.md` — tiers, the three
tools, the escape hatch, and the recurring defect classes.

## PCB Design Rules (MANDATORY)
**Always consult `docs/pcb-design-rules.md` during layout and review.**

This is the expert knowledge base covering component placement, decoupling strategy, ground plane rules, trace routing, crystal layout, thermal management, via design, EMC, and JLCPCB DFM. It includes a 25-item beginner mistake checklist and a 7+1 pass layout review protocol.

The rule that overrides every other convenience: **every board must have routed traces** (placement-only is not a PCB). Fiducials are a recommendation, not a hard gate — JLCPCB auto-adds its own fiducials for assembly if a board has none, so orders are not rejected for missing them. Still add 3 self-placed fiducials in an L-pattern (1mm pad, 2mm mask opening) when the board has fine-pitch parts (<0.5mm pitch) or you want tighter placement accuracy than JLCPCB's default.

## The Gate Rule (read before starting any board)

**A step described only in prose is not a gate — it is a hope.** Every defect
this workspace has shipped was a documented step that nothing checked. So no
board is "done" on Claude's say-so. One command decides:

```bash
python3 docs/pipeline.py projects/<board>          # build: env -> sch -> erc -> pcb -> route -> gates
python3 docs/pipeline.py projects/<board> --check  # gates only, never rebuilds
python3 docs/pipeline.py --status                  # every board, one table
```

**Do not hand-run the generators.** The pipeline fixes the stage order in
code rather than prose, stops building at the first failing stage, and
*always* runs the gates so the worst run still produces the fullest evidence.
Every run writes `STATUS.md` (human) and `PIPELINE.json` (machine) recording
what ran, against which commit, and what the board hashed to.

**A completion claim without that table is not evidence.** A `Stop` hook
prints it automatically at the end of any turn that touched a board, so this
never depends on being asked.

Scaffold a new or legacy board with `python3 docs/run_gates.py --init projects/<board>`.

**Three tools, three different questions — do not confuse them:**

```bash
python3 docs/selftest_enforcement.py   # is the machinery wired and firing?
python3 docs/run_gates.py <board.pcb>  # is THIS board ready to fabricate?
python3 docs/audit_workflow.py         # was every documented step actually done, on every board?
```

`audit_workflow.py` walks the workflow phase by phase and prints DONE/OPEN
per board with the check that enforces each. It is a report, never a gate,
and it **calls the real gate functions** rather than re-implementing them —
its first version disagreed with `run_gates` about ERC and placement, and an
audit that contradicts the gate is worse than no audit.

### The datasheet outranks the reference design

Both are required and they are not equals. Order of authority:

1. **The datasheet** — the part's own specification. Tier 0.
2. **A reference design** — evidence of *practice*, not of correctness.
3. **Teaching sources** (Phil's Lab, Altium Academy) — rationale.
4. **A numbered rule** from `pcb-design-rules.md`.

Where they disagree, the datasheet wins *and the disagreement gets its own
row* in `DESIGN_BASIS.md`. On baro-bmp390 two rows had been decided the wrong
way round: the 4.7k I2C pull-ups were logged as a deviation from Adafruit's
10K when the **datasheet names 4.7 kΩ**. We were matching the manufacturer
and recording it as a departure — a Tier-0 question answered from a Tier-2
source.

The reverse also happens, and the reference is right there: the datasheet
specifies the *sensor*, assuming a stiff local rail, and says nothing about
board-level bulk. Reading only the datasheet leaves the missing bulk cap
invisible. **Read both. Cite which one each row came from.**

A datasheet is only on file if its **bytes are a PDF**. `check_datasheets.py`
sniffs the payload, because a vendor login wall saved as `.pdf` satisfied
every gate here until 2026-08-25, and every "verified against the datasheet"
claim downstream rested on a document nobody could open. Every archived
document also needs a source URL in its `INDEX.md` — un-sourced is not a
lesser problem than un-archived; it means the file cannot be re-fetched or
revision-checked.

### Reference designs come first, and they must land on disk

A PCB is designed the way code is written: by reading how credible people
solved this exact circuit, then justifying every departure. That step is the
highest-value input to a board and, until 2026-08-25, was the **least**
enforced thing here — four boards, **zero** stored reference designs, on a
step that `pcb-design-workflow.md` and `.claude/rules/pcb-schematic.md` both
labelled a HARD GATE. `fetch_reference_doc.py` was invoked by nothing.

Order of work for any new board: **requirements → part selection → datasheets
→ reference-design search → compare/justify → schematic.** Never start the
schematic from memory of a part.

```bash
python3 docs/collect_references.py suggest <PARTNO>              # Tier1/2/3 search seeds
python3 docs/collect_references.py add projects/<b> <PART> <URL> # verify + download + provenance
python3 docs/fetch_reference_doc.py eagle <archived.sch> <PART>  # EXACT values + pin-level nets
```

Rules that are enforced, not suggested:

- **Nothing counts as a reference until it is a file on this disk with a
  live-verified source URL beside it.** A link read once is not evidence, and
  a summary of a schematic is not a schematic. `add` refuses an HTML login
  wall saved as a `.pdf` — the silent failure that makes an archive worthless
  because the gate still sees a file.
- **Search Tier 1 (manufacturer EVM/app note) before Tier 2 (Adafruit,
  SparkFun, Seeed — Eagle/KiCad source, exact values) before Tier 3
  (Phil's Lab, Altium Academy — rationale and layout reasoning).** All three
  are legitimate sources to cite in `DESIGN_BASIS.md`; so is a numbered rule
  from `pcb-design-rules.md`.
- **Use `fetch_reference_doc.py`, not WebFetch, for anything you need an exact
  value or pin from.** WebFetch summarises and silently drops exactly the
  pin-level ground truth you came for.
- **Every key part** (any IC ≥8 pins, or any plug-in module socket) needs a
  `DESIGN_BASIS.md` row with a source and a verdict of `Match` or
  `Deviate: <reason>`. "Deviate" with a real reason is a *good* outcome — the
  file exists to make the choice explicit, not to force you to copy an EVM.

**This must not block you designing.** The research checks are advisory in
the pipeline's `research` stage — they report, they never halt a build — and
blocking only at the `gates` stage, where "done" is decided. Every blocking
finding also has a one-line escape hatch: name the part in `DEVIATIONS.md`
with a reason. The gate never demands a reference that does not exist; it
demands you say that it doesn't. Worked example: `projects/baro-bmp390/DESIGN_BASIS.md`
— archiving Adafruit's BMP390 Eagle source caught a **missing bulk capacitor**
that ERC, DRC and `check_design_rules.py` are all structurally blind to.



**The meta-gate.** `docs/selftest_enforcement.py` checks two different things:
that the enforcement is **wired** — hook matchers, hook scripts firing on
synthetic events, the entry points, each board's gate artifacts — and that it is
**strong**, by fault-injecting a throwaway copy of a real board and requiring
the gate to fail. Wiring is not strength: it stood at 68/68 green on 2026-08-26
while six gates could not actually fail. Every new check needs a fault-injection
test, or it only asserts its own existence. It runs as the first thing in
the pipeline's `env` stage and at session start. It exists because on
2026-08-25 the hook advertised here as automatic had never fired on a single
board — the script read `tool_input.file_path`, which `Bash` does not have.
Reviewing a rule is not running it.
`run_gates.py` remains callable on its own; the pipeline's last stage is exactly it.

| Gate | Checks | Script |
|---|---|---|
| Phase 1–2 | requirements captured (a heading with nothing under it is not a requirement); **a reference design archived for every key part**; archive integrity (real format **and** a source URL); **design basis — every key part's choices documented against the datasheet/reference actually on disk**; LCSC sourcing; **the escape hatch itself is well-formed and scoped** | `check_research.py` |
| Step 2.1 | a datasheet on file for every non-passive part, **and its bytes are actually a PDF** | `check_datasheets.py` |
| Phase 3 | schematic ERC | `kicad-cli sch erc` |
| Phase 3 | **`netmap.json` is derived from the schematic on disk** — the one schematic→PCB contract, re-checked against the sheet it claims to describe | `run_gates.gate_schematic_ownership` |
| Phase 3 | **schematic readable by a human** — components-per-sheet against page size (the documented ~25/A4 rule, counting components and *not* power symbols), and a title block with a real title and rev. Reports the drawn-connection ratio as advisory. | `check_schematic_quality.py` |
| Phase 4B | **the board describes the same circuit as the schematic** — net sets *and* per-net pin membership, compared through KiCad itself on both sides | `check_netlist_parity.py` |
| Phase 4A | placement geometry, pads on board, anchors, **symbol/footprint parity**, **connector class vs footprint** | `validate_pcb.py` |
| Phase 4A | **4 of the 42** numbered subsections of `pcb-design-rules.md` — 1.2, 2.2, 5.1, 6.1, the only ones decidable from board geometry. It prints that scope on every run; the other 38 are the Phase 5 human review. | `check_design_rules.py` |
| Phase 4C | DRC **and zero unconnected** — zones refilled, run **twice**, worse result reported | `kicad-cli pcb drc` |
| Phase 5 | human sign-off | `SIGNOFF.md` |
| Phase 6 | **fabrication package** — gerbers, drill, JLCPCB BOM (LCSC numbers, read from the **PCB**), CPL (re-origined to the board corner). Runs **only** when every gate above passes. | `export_fab.py`, pipeline `fab` stage |

DRC answers *"can JLCPCB build this?"* — never *"is this a good layout?"*.
`check_design_rules.py` is what answers the second question; a board can pass
DRC while breaking 23 numbered design rules (TMS V3 did).

### The schematic was the least-gated artifact

Seven gates, and exactly one of them looked at the schematic: ERC, which
checks connectivity and is blind to everything else. Two consequences, both
found on 2026-08-26 and both live on boards that passed every gate:

* **Connectivity was declared twice.** `gen_*_sch.py` said it in `pin_label()`
  calls; `gen_*_pcb.py` re-derived it by running a **regex over the schematic
  script's source text**. Any net assigned from a loop rather than a literal
  call was invisible to that regex, so the board got a silently incomplete
  netlist instead of an error. It shipped **five electrically dead test
  points** — `gnss` TP1/TP2 and `imu` TP1/TP2/TP3, wired in the schematic,
  netless on the board. DRC cannot see them: a pad with no net has no
  ratsnest, so it is not "unconnected", it is simply absent.
  tms-v3 had already hit this and fixed it with `netmap.json`; **the fix was
  never propagated**. All four boards now use the same authoritative file, and
  `check_netlist_parity.py` fails if the two views ever disagree again.
* **Rules stated in writing were broken by every board.** `.claude/rules/pcb-schematic.md`
  says to split past ~25 components per A4 into hierarchical sheets; all four
  boards violated it, with **zero** hierarchical sheets between them, while
  `sch_editor.py` had `add_sheet_node`/`add_hierarchical_label`/`add_sheet_pin`
  called by nothing. No board had a `title_block` at all, so every sheet
  printed with Title, Date and Rev blank.

Count **components, not symbols.** Power symbols are 60–70% of the symbols on
these boards; counting them fails baro-bmp390 at 31-on-A4 for a sheet that is
60% empty, and a gate that fires on a sheet you can see is not crowded is a
gate that gets switched off.

### The schematic can be hand-drawn now — and the guard came first

Every generated sheet in this repo measures **zero junctions**. Every pin
terminates in a stub and a label; no two components are ever joined by a drawn
wire. The rails are graphical power symbols and that part reads fine, but
nothing else on the sheet reads as a circuit — which is why review never
happened, and why sign-off stood at **0 of 38 boxes on every board**.

So a human draws them. The thing that had to land first is not the drawing:

    projects/<board>/SCHEMATIC_OWNER      one line: `generated` or `human`

`gen_*_sch.py` ends in an unconditional `sch_io.write_file(...)` and the `sch`
stage runs on **every** `pipeline.py` invocation. Before the marker, one
routine build silently destroyed an evening in Eeschema. `stage_sch` now
branches three ways, and the middle one is the point:

| owner | schematic vs. last run | what happens |
|---|---|---|
| `generated` | matches | regenerate, as before |
| `generated` | **differs** | **STOP** — hand-edited, or a generator was run outside the pipeline. `--regenerate` to discard and rebuild |
| `human` | — | never generated. `netmap.json` is **derived** from the sheet instead |

A guard that only protects boards you remembered to mark protects nothing.
`--regenerate` refuses outright on a `human` board: a flag that quietly no-ops
is how someone concludes the guard is broken and reaches for something blunter.

`docs/extract_netmap.py` derives the contract, reusing
`check_netlist_parity.schematic_nets()` rather than parsing `.kicad_sch` again
— it reproduces all four generator-declared netmaps **exactly**, 283 pin
assignments, which is what earned it the right to replace them. Parity then
changes character on purpose: it stops comparing two independent derivations
and becomes the netlist-import check every EDA flow runs. It still catches a
PCB generator that drops assignments — the defect that shipped five dead test
points — and newly catches a part added in Eeschema that nothing places.

### Three defects the guard uncovered on its way in

All three had been live for a long time, and all three are old classes:

* **The "canonical" hash was not canonical.** `pipeline.sha()` masks UUIDs so
  an unchanged board hashes the same. The mask was anchored to quotes —
  `"<uuid>"` — and KiCad writes instance paths as `(path "/<root-uuid>")`,
  with a slash inside the quotes. **31 of baro-bmp390's 148 UUIDs escaped**,
  all the root sheet UUID, minted fresh on every regeneration. So the hash
  moved on every build of an unchanged board: `--status` called fresh reports
  stale, `--verify-repeatable` could never pass. Class #8, the
  non-deterministic gate.
* **A sandbox that was not a sandbox.** Every generator hardcoded
  `PROJECT_DIR = Path('/Users/.../projects/<board>')`, so the self-test ran a
  generator inside a throwaway copy and **wrote to the live board**. The check
  meant to prove the ownership guard worked passed for that reason instead —
  removing the guard entirely did not make it fail. All eight generators are
  now `Path(__file__).resolve().parent`, and a check forbids the regression.
* **A gate that read an artifact the run had not written yet.** The first
  provenance gate compared the schematic hash against `PIPELINE.json` — which
  is written at the **end** of a run. On any run that regenerated the
  schematic it read the previous run's hash and failed. It failed
  baro-bmp390's first clean build. Class #7, inside a gate written to catch
  exactly that. Drift detection now lives in `stage_sch`, where the baseline
  genuinely is the previous run and the answer arrives before anything is
  overwritten; the gate asks a question with no ordering dependence.

The second one is worth dwelling on: **it made every fault-injection test
built on that sandbox untrustworthy**, including ones that had been green for
weeks. Wiring is not strength, and neither is a green fault-injection test if
the fault never reached the thing under test.

### A constant clearance is wrong the moment a footprint overrides it

KiCad's DSN export writes **one global clearance** and drops every pad-local
override, so Freerouting routes through keepouts it was never told about and
DRC then reports violations the router had no way to avoid. KiCad's own stock
`Fiducial_1mm_Mask3mm` carries `(clearance 1.1)` — 5.5x this workspace's
0.2 mm rule. `adapters/dsn_keepouts.py` now injects the missing keepouts.

This is the same defect in three places, twice fixed and once not propagated:
`stitch_vias.py` fixed it in its own pass, `bond_ground` still used a flat
`clearance_mm=0.2`, and the DSN export never carried it at all. **Freerouting
honours the injected keepouts for wiring but not for vias** — a tight fiducial
can still need two vias nudged by hand.

### The escape hatch is scoped

A rule you cannot meet is an engineering decision: record it under the
`## Declared` heading of the board's `DEVIATIONS.md`. Unlisted violations are
hard failures.

    <ref>.<pin>  |  <scope>  |  <reason>

`docs/deviations.py` is the **only** parser — `check_design_rules.py` used to
carry a second, looser copy. Two properties, each of which cost a real bug:

* **Scope is matched, never ignored.** A numeric scope (`2.2`) waives that
  numbered rule on that pin. `reference` / `basis` / `datasheet` waive the
  corresponding research gate. Nothing waives anything else. Until 2026-08-26
  the scope was parsed and discarded, so `U1.5 | 2.2 | Pad 5 is SDO, not a
  supply pin` — a narrow, correct waiver of one decoupling rule on one pin —
  silently excused baro-bmp390's only IC from needing an archived reference
  design *and* a design-basis row. With every reference file deleted, the gate
  still reported *"every key part has an archived reference"*.
* **Containment is mandatory.** Without a `## Declared` heading the parser fell
  back to reading the whole file — the mode behind four separate false-waiver
  bugs. A file with no such heading now waives nothing and says so. Struck-out
  (`~~...~~`) rows are withdrawn and waive nothing.

Full lessons table (95 rows, each a defect that actually shipped and the check
that now catches it): `docs/pcb-design-workflow.md` § The Gate Rule.

Detailed layout/schematic/fabrication rules auto-load from `.claude/rules/` whenever Claude touches a matching file (`.kicad_pcb`, `.kicad_sch`, `fabrication/**`) — no need to re-paste them here. A `PostToolUse` hook also runs `docs/validate_pcb.py` automatically — on `Write`/`Edit` of a `.kicad_pcb`, and on any `Bash` call that leaves a `.kicad_pcb` newer than 120s (the generator path, which the hook silently missed until 2026-08-25). It is feedback, not a gate; `run_gates.py` is the gate.

Two more tools, both mandatory where they apply: `docs/pcb_layout_helpers.py` checks a real footprint's courtyard size *before* you pick a placement coordinate (placeholder-era coordinates never survive a real footprint — this is a recurring, structural defect, not a one-off mistake); `docs/fetch_reference_doc.py` fetches exact reference-design data (real part values, pin-level net connections from Eagle `.sch`/`.brd`, PDF pages rendered for visual reading) instead of relying on WebFetch's summarizer, which is fine for prose and unreliable for exact pin/value ground truth.

## Conventions
- Always include board dimensions and mounting hole positions in the spec
- Prefer through-hole for prototypes when hand-soldering
- Use LCSC part numbers for JLCPCB assembly compatibility
- Save datasheets in the project's datasheets/ folder
- Name revisions: rev1, rev2, etc.
- Put your name and rev on the silkscreen
