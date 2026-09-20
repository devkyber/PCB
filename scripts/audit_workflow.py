#!/usr/bin/env python3
"""Walk the DOCUMENTED workflow step by step and report, per board, whether
each step actually happened — and what enforces it.

Why this exists
---------------
Every audit in this workspace has found the same shape of defect: a step
described in prose, believed to be done, enforced by nothing. Reference
designs were a "HARD GATE" in two documents and had never once been
archived. `fetch_reference_doc.py` and `stitch_vias.py` were each invoked by
nothing. `validate_pcb.py` printed "0 schematic-parity issue(s)" forever
because it read a field the pipeline never asked to be populated.

`selftest_enforcement.py` answers "is the machinery wired?".
`run_gates.py` answers "is THIS board ready?".
Neither answers the owner's actual question: **for the workflow I wrote
down, has every step really been carried out, on every board, and what
would have caught it if not?**

That is what this prints. It is a report, not a gate — it never fails a
build. `run_gates.py` remains the thing that decides "done".

Usage:  python3 scripts/audit_workflow.py [board ...]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / 'scripts'
sys.path.insert(0, str(SCRIPTS))
# Imported, not re-implemented. Every row below that has a gate calls that
# gate. Three rows here have drifted into their own copy of a check at some
# point (ERC, placement, DRC) and each time the audit disagreed with the
# gate — which makes the audit worse than useless, because it is the report
# people read.
import run_gates  # noqa: E402
KIPYTHON = Path.home() / '.local' / 'bin' / 'kipython'


def _run(cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True)


# (phase label, what the workflow says must exist, how it is verified)
def steps(proj: Path, pcb: Path):
    name = proj.name
    research = _run([sys.executable, SCRIPTS / 'check_research.py', pcb, '--json'])
    try:
        res = {r['name']: r for r in json.loads(research.stdout)}
    except Exception:
        res = {}

    def rc(frag):
        for k, v in res.items():
            if frag in k:
                return v['ok'], v['detail'].splitlines()[0][:78]
        return None, 'check did not run'

    out = []
    out.append(('Phase 1   requirements captured',
                *rc('requirements'), 'check_research.py'))
    out.append(('Step 2.1  datasheet per non-passive part, bytes verified',
                *(lambda r: (r.returncode == 0,
                             (r.stdout or '').splitlines()[0][:78]))(
                    _run([sys.executable, SCRIPTS / 'check_datasheets.py', pcb])),
                'check_datasheets.py'))
    out.append(('Step 2.2  reference design archived per key part',
                *rc('reference designs'), 'check_research.py'))
    out.append(('Step 2.2  archive integrity (real format + source URL)',
                *rc('archive integrity'), 'check_research.py'))
    out.append(('Step 2.3  design choices documented + sourced',
                *rc('design basis'), 'check_research.py'))
    out.append(('Step 2.4  LCSC sourcing',
                *rc('LCSC'), 'check_research.py'))
    # The escape hatch is part of the workflow, not an aside: every gate
    # below honours DEVIATIONS.md, so a malformed one changes what "DONE"
    # means on every row.
    out.append(('Escape hatch  DEVIATIONS.md scoped and well-formed',
                *rc('DEVIATIONS'), 'check_research.py'))

    # Call run_gates' OWN erc gate rather than re-reading the report here.
    # The first version of this counted raw violations and reported 10 where
    # the gate reports 0 — because the gate waives the EasyEDA symbol
    # pin-type class, and this did not. Two implementations of one check
    # give two answers, and the audit's whole job is to agree with the gate.
    ok, detail = run_gates.gate_erc(Path(pcb))
    out.append(('Phase 3   schematic ERC', ok, detail.splitlines()[0][:78],
                'kicad-cli sch erc'))

    # Both of these CALL the gate. Re-deriving either here is how this file
    # twice drifted into disagreeing with run_gates.py — the one thing an
    # audit must never do.
    ok, detail = run_gates.gate_schematic_ownership(Path(pcb))
    out.append(('Phase 3   schematic provenance', ok, detail.splitlines()[0][:78],
                'run_gates.gate_schematic_ownership'))

    ok, detail = run_gates.gate_schematic_quality(Path(pcb))
    out.append(('Phase 3   schematic readable', ok, detail.splitlines()[0][:78],
                'check_schematic_quality.py'))

    ok, detail = run_gates.gate_netlist_parity(Path(pcb))
    out.append(('Phase 4B  schematic == PCB netlist', ok,
                detail.splitlines()[0][:78], 'check_netlist_parity.py'))

    v = _run([sys.executable, SCRIPTS / 'validate_pcb.py', pcb])
    vt = v.stdout or ''
    for label, frag in (('Phase 4A  placement geometry', 'Courtyard collisions'),
                        ('Phase 4A  every schematic symbol is ON the board',
                         'Symbol/footprint parity'),
                        ('Phase 4A  connector class matches its footprint',
                         'Connector class vs footprint')):
        blk = [l for l in vt.splitlines() if frag in l]
        # WARN counts as done. validate_pcb.py distinguishes FAIL from WARN
        # (a sub-0.1mm bounding-box overlap on a rotated part is flagged
        # WARN, "confirm in KiCad"), and run_gates keys on FAIL only. The
        # The first version keyed on a Unicode icon and so reported
        # gnss-neom9n's
        # placement as OPEN while the gate passed it — the audit contradicting
        # the gate is the one thing this file must never do.
        ok = bool(blk) and (' PASS ' in blk[0] or ' WARN ' in blk[0])
        note = frag if ok else frag + ' — FAIL'
        if ok and blk and ' WARN ' in blk[0]:
            note = frag + ' (WARN, verify in KiCad)'
        out.append((label, ok, note, 'validate_pcb.py'))

    if KIPYTHON.exists():
        r = _run([KIPYTHON, SCRIPTS / 'check_design_rules.py', pcb])
        last = [l for l in (r.stdout or '').splitlines() if l.startswith('RESULT')]
        out.append(('Phase 4A  docs/DESIGN_RULES.md numbered rules',
                    r.returncode == 0, last[-1][:78] if last else 'no result',
                    'check_design_rules.py'))

    # Call the gate, do not re-read its output file. This block used to
    # parse drc-report.json directly, which meant: no zone refill, no
    # second run, and whatever the LAST tool to write that file had found.
    # It reported "1 error" while the gate reported 2 on the same board —
    # the audit contradicting the gate is the one thing this file must
    # never do, and it had drifted back into doing it.
    ok, detail = run_gates.gate_drc(Path(pcb))
    out.append(('Phase 4C  DRC clean AND zero unconnected', ok,
                detail.splitlines()[0][:78], 'kicad-cli pcb drc'))

    # Same reason. Counting unticked boxes missed the signature requirement
    # entirely, so a bulk-ticked SIGNOFF.md read as DONE here while the gate
    # failed it.
    ok, detail = run_gates.gate_signoff(Path(pcb))
    out.append(('Phase 5   human sign-off', ok,
                detail.splitlines()[0][:78], 'SIGNOFF.md  [HUMAN]'))
    return out


def main() -> None:
    wanted = sys.argv[1:]
    boards = []
    for p in sorted((REPO / 'projects').iterdir()):
        if not p.is_dir():
            continue
        pcbs = list(p.glob('*.kicad_pcb'))
        if pcbs and (not wanted or p.name in wanted):
            boards.append((p, pcbs[0]))

    print('=== workflow audit: is every documented step actually done? ===\n')
    grand_open = 0
    for proj, pcb in boards:
        print(f'--- {proj.name} ---')
        for label, ok, detail, by in steps(proj, pcb):
            mark = 'DONE' if ok else 'OPEN'
            if not ok:
                grand_open += 1
            print(f'  [{mark}] {label:54s} {detail}')
            if not ok:
                print(f'         enforced by: {by}')
        print()
    print(f'{grand_open} open item(s) across {len(boards)} board(s).')
    print('This is a REPORT. `run_gates.py` is what decides "done".')


if __name__ == '__main__':
    main()
