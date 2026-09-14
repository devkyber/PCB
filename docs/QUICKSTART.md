# Quick Start — a board, start to finish

> **Superseded:** This is retained as migration history. Use
> [WORKFLOW.md](WORKFLOW.md) for the current human-controlled workflow.

This document was rewritten on 2026-08-26. The version it replaces described a
workflow that no longer existed: describe a board, ask for a review, export
Gerbers. No pipeline, no gates, no research phase, no `DEVIATIONS.md`. It was
the **first** file a newcomer would read and it contradicted `CLAUDE.md` on
every point that matters — which is exactly the drift the rest of this
workspace is built to prevent, sitting unnoticed in the onboarding doc.

---

## The one command

```bash
python3 docs/pipeline.py projects/<board>
```

That is the build. It runs `env → research → sch → erc → pcb → route → gates → fab`
in that order, stops at the first failing stage, and *always* runs the gates so
even a failed run produces the fullest evidence it can. It writes `STATUS.md`
(for you) and `PIPELINE.json` (for tools).

Do not run the generator scripts by hand. The stage order is fixed in code
rather than in prose specifically so it cannot be got wrong.

```bash
python3 docs/pipeline.py projects/<board> --check   # gates only, never rebuilds
python3 docs/pipeline.py --status                   # every board, one table
```

## Starting a new board

```bash
mkdir -p projects/my-board
python3 docs/run_gates.py --init projects/my-board
```

`--init` writes the six artifacts the gates read — `REQUIREMENTS.md`,
`DESIGN_BASIS.md`, `DEVIATIONS.md`, `SIGNOFF.md`, and an `INDEX.md` in each of
`datasheets/` and `reference-designs/`. It never overwrites a file that exists.

Then, **in this order** — the order is the point:

### 1. Requirements, before any part is chosen
Fill in `REQUIREMENTS.md`. Every section needs real content; a heading with
nothing under it fails Phase 1. Include board outline, mounting holes, supply
voltage and worst-case current, and measurable success criteria.

### 2. Parts, then datasheets
Every non-passive part needs a datasheet in `datasheets/`, listed in its
`INDEX.md` with a source URL. The gate sniffs the file's **bytes** — a vendor
login wall saved with a `.pdf` name satisfied every check here until
2026-08-25, and every "verified against the datasheet" claim downstream rested
on a document nobody could open.

### 3. Reference designs, before the schematic
```bash
python3 docs/collect_references.py suggest <PARTNO>              # search seeds
python3 docs/collect_references.py add projects/<b> <PART> <URL> # verify + archive
```
Search Tier 1 (manufacturer EVM / app note) before Tier 2 (Adafruit, SparkFun,
Seeed — Eagle or KiCad source, exact values) before Tier 3 (Phil's Lab, Altium
Academy — rationale). Nothing counts as a reference until it is a file on this
disk with a live source URL beside it.

Read exact values with `docs/fetch_reference_doc.py`, never WebFetch — the
summariser silently drops the pin-level ground truth you came for.

### 4. Compare, and write down every departure
One `DESIGN_BASIS.md` row per key part (any IC ≥8 pins, or any module socket),
each with a source and a verdict of `Match` or `Deviate: <reason>`.
**"Deviate" with a real reason is a good outcome.** The file exists to make the
choice explicit, not to make you copy the EVM.

The datasheet outranks the reference design. Where they disagree, the datasheet
wins *and the disagreement gets its own row*. Archiving Adafruit's BMP390 Eagle
source is what caught a missing bulk capacitor that ERC, DRC and
`check_design_rules.py` are all structurally blind to.

### 5. Schematic, layout, routing
All of it via the pipeline.

### 6. Open it in KiCad and look at it
Then sign `SIGNOFF.md`. Ticking a box records that a step was **performed** —
not that it was performed correctly, and that distinction is not papered over.
A tick needs your initials and a `YYYY-MM-DD` date; the date is checked,
because `sed 's/\[ \]/[x]/'` is not a design review.

### 7. Fabrication
The `fab` stage runs **only** when every gate passes, and writes
`fabrication/`: Gerbers, drill, a JLCPCB BOM (LCSC numbers read from the PCB,
where they live) and a CPL re-origined to the board's bottom-left corner.

Upload to jlcpcb.com → Instant Quote → **check the Gerber viewer** → order.

## When a rule cannot be met

That is an engineering decision, and decisions get written down:

```
<ref>.<pin>  |  <scope>  |  <reason>
```

under the `## Declared` heading of `DEVIATIONS.md`. Nothing above that heading
waives anything. The scope is a numbered rule from `pcb-design-rules.md`, or
one of `reference` / `basis` / `datasheet` to excuse a research gate — and it
is **matched**, so a waiver is never wider than the thing it excuses. An
unlisted violation is a hard failure.

## The three tools, and the three different questions

```bash
python3 docs/selftest_enforcement.py     # is the machinery wired and firing?
python3 docs/run_gates.py <board.pcb>    # is THIS board ready to fabricate?
python3 docs/audit_workflow.py           # was every documented step done, on every board?
```

Do not confuse them. The audit *calls* the gate functions rather than
re-implementing them: its first version disagreed with `run_gates` about ERC
and placement, and an audit that contradicts the gate is worse than no audit.

## Coming from EasyEDA

| EasyEDA | KiCad / here |
|---|---|
| Component library | Symbol **and** footprint libraries, kept separate |
| LCSC part picker | `lcsc` skill, or `kicad-jlcpcb`'s sourcing tools |
| Design rules | Board Setup → Design Rules — but the generator owns netclasses; edit the generator, not the `.kicad_pro` |
| Gerber export | The `fab` pipeline stage, never by hand |
| EasyEDA autorouter | Freerouting, via `autoroute_pcb` or `docs/route_and_fill.py` — never `java -jar` directly |

---

## If something in the toolchain is broken

`docs/SETUP.md` covers the install and the two traps that have actually cost
time here: which Freerouting JAR needs which JDK, and the fact that
`~/.claude/settings.json` contains an `mcpServers` block that this
installation **does not read** (registration lives in `claude mcp list`).
