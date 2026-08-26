# How the enforcement works

Written 2026-08-26, after an adversarial audit of the whole workspace. The
knowledge here previously existed only as prose in `CLAUDE.md` plus whatever
you could reconstruct by reading twenty scripts. This is the map.

## The premise

> A step described only in prose is not a gate — it is a hope.

Every defect this workspace has shipped was a documented step that nothing
checked. So the design principle is not "write good rules", it is **put each
rule at a tier that fires, then prove it fires.**

## The tiers

| Tier | Where | Fires when | Can it be skipped? |
|---|---|---|---|
| 0 | a gate in `run_gates.py` | on every `--check` | no — it decides "done" |
| 1 | `CLAUDE.md` | always in context | it's advice, not a check |
| 2 | `.claude/rules/*.md` | when a matching file is touched | advice, scoped |
| 3 | `docs/*.md` | when someone reads it | **yes. this is a hope** |
| 4 | `.claude/hooks/*.sh` | on tool events / session start | yes, silently, if miswired |

A lesson recorded only at Tier 3 has not been learned. That is not rhetoric:
"download the datasheet for every IC" lived at Tier 3 while eleven parts
shipped with an empty `datasheets/` folder and nothing noticed.

Tier 4 is the treacherous one, because a miswired hook looks identical to a
working one. `docs/selftest_enforcement.py` fires each hook against a
**synthetic event** rather than checking that the file exists — written after
the `PostToolUse` hook advertised here as automatic turned out to have never
run on a single board (it read `tool_input.file_path`, which `Bash` has not
got).

## The three tools, and their three different questions

Confusing these is itself a failure mode, so they are named after the question
they answer, not after what they inspect.

```bash
python3 docs/selftest_enforcement.py   # is the machinery wired AND firing?
python3 docs/run_gates.py <board.pcb>  # is THIS board ready to fabricate?
python3 docs/audit_workflow.py         # was every documented step actually done, on every board?
```

`audit_workflow.py` **calls the real gate functions** rather than
re-implementing them. Its first version re-implemented two and disagreed with
`run_gates` on both — ERC (it counted waived violations) and placement (it
treated WARN as failure). An audit that contradicts the gate is worse than no
audit, and the self-test now asserts they agree.

`selftest_enforcement.py` tests two different things, and the distinction is
worth keeping straight:

- **wiring** — the hook matchers, the entry points, the gate registry, the
  per-board artifacts. "Is it plugged in?"
- **strength** — fault injection. It breaks a throwaway copy of a real board
  and requires the gate to fail.

Wiring was at 68 checks and fully green on 2026-08-26 while six gates could not
actually fail. Wiring is not strength. Every new check needs a fault-injection
test, or it is only asserting its own existence.

## The pipeline

```
env → research → sch → erc → pcb → route → gates → fab
```

Fixed in code (`STAGE_ORDER`), not in prose, so the order cannot be got wrong
by hand. Two properties matter:

- **`research` is advisory** (`ADVISORY = {'research'}`) — it reports, it never
  halts a build. Research blocks at `gates`, where "done" is decided. You can
  always keep designing.
- **`fab` runs only when the gates pass.** A fabrication package that exists
  for a board that failed its gates is an invitation to upload it.

Every run writes `STATUS.md` (human) and `PIPELINE.json` (machine): what ran,
against which commit, and what the board hashed to.

## The gates

| Gate | Question | Script |
|---|---|---|
| Phase 1–2 | requirements captured; a reference archived per key part; archive integrity; design basis; LCSC sourcing; **the escape hatch itself is well-formed** | `check_research.py` |
| Step 2.1 | a datasheet per non-passive part, **and its bytes are a PDF** | `check_datasheets.py` |
| Phase 3 | schematic ERC | `kicad-cli sch erc` |
| Phase 4A | placement geometry, pads on board, symbol/footprint parity, connector class vs footprint | `validate_pcb.py` |
| Phase 4A | four geometric rules from `pcb-design-rules.md` — see the honesty note below | `check_design_rules.py` |
| Phase 4C | DRC **and zero unconnected**, refilled and run twice | `kicad-cli pcb drc` |
| Phase 5 | human sign-off, with a dated signature | `SIGNOFF.md` |
| Phase 6 | fabrication package | `export_fab.py` |

### Two things the gates do not claim

**DRC answers "can JLCPCB build this?", never "is this a good layout?"**
TMS V3 passed DRC while breaking 23 numbered design rules.

**`check_design_rules.py` covers 4 of 42 numbered subsections** — 1.2, 2.2, 5.1
and 6.1, the only ones decidable from board geometry. It prints that scope on
every run. A gate whose name promises a document and whose code delivers a
tenth of it teaches people to read "0 violations" as "the rules are met". They
are not met; they are un-contradicted. The remaining 38 are the Phase 5 human
review.

## The escape hatch

Any rule you cannot meet is an engineering decision, declared in
`DEVIATIONS.md` under a `## Declared` heading:

```
<ref>.<pin>  |  <scope>  |  <reason>
```

`docs/deviations.py` is the **only** parser. Two parsers for one file is the
same defect as two build paths for one board — and the second copy, in
`check_design_rules.py`, was the looser of the two.

Two properties, each of which cost a real bug:

1. **Scope is matched, never ignored.** A numeric scope waives that numbered
   rule on that pin. `reference` / `basis` / `datasheet` waive the
   corresponding research gate. Nothing waives anything else. Before this,
   `U1.5 | 2.2 | Pad 5 is SDO, not a supply pin` — a narrow, correct waiver of
   one decoupling rule on one pin — silently excused baro-bmp390's only IC from
   needing an archived reference design *and* a design-basis row. With every
   reference file deleted, the gate still reported "every key part has an
   archived reference".

2. **Containment is mandatory.** Without a `## Declared` heading the parser used
   to fall back to reading the whole file — the mode behind four separate
   false-waiver bugs (a part value matched in the title; a rule number `U2.3`
   read as a designator; a reason paragraph mentioning `U2's pads`; and the
   scaffolded template's own `Example:` line). A file with no such heading now
   waives nothing and says so.

Struck-out (`~~...~~`) rows are withdrawn and waive nothing.

## The recurring defect classes

Named because they keep coming back in new places, not as history.

| Class | What it looks like | Caught by |
|---|---|---|
| **The check that cannot fail** | green, forever, on anything | fault injection |
| **The template that satisfies its own check** | a scaffold that passes the gate it scaffolds | fault injection on a fresh `--init` |
| **The orphaned tool** | purpose-built, invoked by nothing. Found 3× | grep for callers; "a comment naming the caller is not a caller" |
| **The escape hatch that is too wide** | a narrow waiver excusing unrelated gates | scope matching |
| **The second parser / second build path** | two readers of one file, disagreeing | one implementation, imported |
| **The fix that did not propagate** | fixed in the generator, stale in the artifact | audit both |
| **The gate that reads a stale artifact** | tool failed, gate read last run's output | delete before write; check exit codes |
| **The non-deterministic gate** | different answers on an unchanged file | run twice, report the worse |

## Coordinates, briefly

Convert only via `design_to_mcp` / `design_to_kicad` / `kicad_to_design` in
`docs/pcb_layout_helpers.py`. The same sign error appeared three times when
written inline, because two flips cancel and the board still looks plausible.
**Always measure the transform from the built board**, and remember a 1×N
header footprint anchors on **pin 1**, not its centre.
