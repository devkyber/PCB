#!/bin/bash
# SessionStart hook: put the operating rules and the real board state into
# context before the first prompt, so no session begins by guessing.
#
# WHY
# ---
# Every recurring failure here started the same way: Claude began work without
# the workflow in context, and the user had to say "look at the document".
# Prose in docs/ does not load itself. This does.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 0

cat <<'TXT'
=== PCB WORKSPACE — OPERATING RULES (loaded automatically) ===

ONE command builds a board. Do not hand-run generators:
    python3 docs/pipeline.py projects/<board>
    python3 docs/pipeline.py projects/<board> --check   # gates only
    python3 docs/pipeline.py --status                   # all boards

RULES THAT ARE NOT NEGOTIABLE
 1. A board is "done" only when run_gates.py exits 0. Paste the table.
    A completion claim without it is not evidence.
 2. DRC answers "can JLCPCB build this?", never "is this a good layout?".
    check_design_rules.py answers the second. TMS V3 passed DRC while
    breaking 23 numbered rules.
 3. A rule you cannot meet is an engineering decision -> DEVIATIONS.md,
    under its "## Declared" heading, as
        <ref>.<pin> | <scope> | <reason>
    Scope is MATCHED: a rule number waives that rule on that pin;
    reference/basis/datasheet waive that research gate; nothing waives
    anything else. No "## Declared" heading = nothing is waived.
    Unlisted violations are hard failures.
 4. Routing quality is a PLACEMENT result, not a router setting.
 5. Convert coordinates ONLY via design_to_mcp / design_to_kicad /
    kicad_to_design. The same sign bug appeared three times inline.
 6. A 1xN header footprint anchors on PIN 1, not its centre.
 7. RESEARCH BEFORE SCHEMATIC. Order: requirements -> parts -> datasheets
    -> reference designs -> compare/justify -> schematic. A reference is
    only real when it is a FILE ON DISK with a live source URL:
        python3 docs/collect_references.py suggest <PART>
        python3 docs/collect_references.py add <project> <PART> <URL>
    Read exact values with fetch_reference_doc.py, never WebFetch.
    Every key part gets a DESIGN_BASIS.md row: Match or Deviate: <reason>.
    Advisory while designing; blocking at the gates; escape hatch is one
    line in DEVIATIONS.md.
 8. DATASHEET OUTRANKS THE REFERENCE DESIGN. Both required, not equals:
    datasheet (Tier 0) > reference design (practice, not correctness) >
    teaching sources > numbered rules. Where they disagree the datasheet
    wins AND the disagreement gets a DESIGN_BASIS.md row. A datasheet is
    on file only if its BYTES are a PDF, with a source URL in INDEX.md.
 9. THREE TOOLS, THREE QUESTIONS. selftest_enforcement.py = is the
    machinery wired? run_gates.py = is THIS board ready? audit_workflow.py
    = was every documented step actually done, on every board? The audit
    CALLS the gate functions; it must never re-implement and disagree.
10. New lesson? Put it at the tier that fires: a gate (Tier 0), CLAUDE.md
    (1), .claude/rules/ (2). docs/*.md alone (3) is a hope, not a rule.
    Then FAULT-INJECT it: a check you have not seen fail is a check you
    have not tested. Wiring is not strength -- the self-test was 68/68
    green while six gates could not fail at all.
11. Read docs/ARCHITECTURE.md before changing any check. It names the
    recurring defect classes, all of which have come back at least twice.
12. THE SCHEMATIC IS GATED NOW. Two new gates, both blocking:
    check_netlist_parity.py  -- the board must describe the same circuit
      as the schematic (net sets AND per-net pin membership). This is what
      caught 5 electrically dead test points that DRC is structurally blind
      to: a pad with no net has no ratsnest, so it is not "unconnected".
    check_schematic_quality.py -- components-per-sheet vs page size (the
      documented ~25/A4 rule; count COMPONENTS, power symbols are 60-70%
      of the symbols) and a real title block.
    One netmap.json per board is the ONLY schematic->PCB contract. Never
    re-derive a netlist by regexing a generator's source text.
13. A CONSTANT CLEARANCE IS WRONG once a footprint overrides it. KiCad's
    DSN export drops pad-local clearances, so the router cannot see a
    fiducial's 1.1mm keepout. Read the rule off the pad. When a route
    fails near a fiducial it is NOT a placement problem -- moving it just
    makes the router follow.

14. THE SCHEMATIC MAY BE HUMAN-OWNED. projects/<board>/SCHEMATIC_OWNER is
    one line: `generated` or `human`. On `human` the pipeline NEVER runs
    the schematic generator -- it derives netmap.json from the sheet with
    extract_netmap.py instead. On `generated`, a schematic that no longer
    matches the last recorded run STOPS the build: it was hand-edited, or
    a generator was run outside the pipeline. `--regenerate` discards and
    rebuilds; it REFUSES on a human-owned board. Never hand-run a
    generator -- that is one of the two things the tripwire is watching for.
15. A SANDBOX MUST ACTUALLY CONTAIN. Generators derive PROJECT_DIR from
    their own location. When they hardcoded an absolute path, the
    self-test's throwaway copy wrote to the LIVE board and the check meant
    to prove the ownership guard worked passed for the wrong reason. A
    green fault-injection test proves nothing if the fault never reached
    the thing under test.
16. A GATE MUST NOT READ WHAT THIS RUN HAS NOT WRITTEN. PIPELINE.json is
    written at the END of a run. The first provenance gate compared
    against it and failed every run that regenerated the schematic. Drift
    detection belongs in stage_sch (baseline = last run); the gate asks
    "does netmap.json match the schematic on disk", which has no ordering
    dependence.

Enforcement model: docs/ARCHITECTURE.md § Enforcement tiers. Wiring self-test: docs/selftest_enforcement.py
TXT

echo
python3 docs/selftest_enforcement.py 2>/dev/null | tail -3
echo
echo "=== CURRENT BOARD STATE ==="
python3 docs/pipeline.py --status 2>/dev/null || echo "(pipeline unavailable)"
exit 0
