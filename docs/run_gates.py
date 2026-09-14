#!/usr/bin/env python3
"""Run every gate for a board and print one pass/fail table.

The rule this enforces
----------------------
Every documented step must be checkable and non-missable. A step described
only in prose is not a gate — it is a hope. This session found that out the
hard way, repeatedly:

  * "Download the datasheet for every IC" (Step 2.1) — the folder was empty,
    for eleven parts, and nothing noticed.
  * "Always consult docs/DESIGN_RULES.md" (CLAUDE.md) — nothing checked it,
    and the board broke 23 of its numbered rules while passing DRC.
  * "Every net must be routed" (Phase 4B) — the validator counted trace
    SEGMENTS, which is satisfied by any partially-routed board.
  * "Use PlacementTracker" (Phase 4A) — the generator never imported it,
    and `docs/` was not even on its sys.path.

So each gate below names the command that proves it. If a gate cannot be
automated, it is listed as a HUMAN gate and is satisfied by a signed line in
the board's SIGNOFF.md — which proves the step was DONE, not that it was
done correctly. That distinction is real and is not papered over here.

Usage:  python3 run_gates.py <board.kicad_pcb>
        python3 run_gates.py --init projects/<board>   # scaffold gate artifacts
Exit 0 only when every gate passes.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))

from pcb_copilot.toolchain import discover_toolchain  # noqa: E402

_TOOLCHAIN = discover_toolchain(REPO)
KICAD_CLI = _TOOLCHAIN.kicad_cli
KIPYTHON = _TOOLCHAIN.kipython or Path('kipython')

# ERC classes that are known-benign for EasyEDA-converted symbols. These
# carry no electrical pin-type metadata (see CLAUDE.md), so every connection
# to one reports as Unspecified/Passive. Waived by CLASS here rather than
# ignored silently, so a NEW erc class still fails the gate.
ERC_WAIVED_TYPES = {'pin_to_pin'}
# ...but only the benign SHAPE of it. Waiving the whole `pin_to_pin` class
# also waives "Pins of type Output and Output are connected" — a genuine
# short between two driving pins, and an error, not a warning. The waiver
# exists for one specific artifact: EasyEDA-converted symbols carry no
# electrical pin-type metadata, so every connection to one reports as
# Unspecified. So match that, and nothing else.
ERC_WAIVE_RE = re.compile(r'(?i)\bunspecified\b')


def _erc_waivable(v: dict) -> bool:
    return (v.get('type') in ERC_WAIVED_TYPES
            and v.get('severity') != 'error'
            and ERC_WAIVE_RE.search(v.get('description', '')) is not None)


def _run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def gate_datasheets(pcb: Path) -> tuple[bool, str]:
    r = _run([sys.executable, REPO / 'docs' / 'check_datasheets.py', pcb])
    lines = r.stdout.strip().splitlines()
    head = lines[0] if lines else 'no output'
    # Name the offending parts. The summary line alone reads as healthy
    # ("11 parts require a datasheet; 12 PDFs on file") while the gate is
    # failing on a specific part — a table that looks fine next to the word
    # FAIL teaches you to distrust the table.
    missing = [l.split('MISSING:', 1)[1].strip() for l in lines if 'MISSING:' in l]
    if missing:
        head += ' — missing: ' + ', '.join(missing[:5]) + (' …' if len(missing) > 5 else '')
    return r.returncode == 0, head


def gate_placement(pcb: Path) -> tuple[bool, str]:
    r = _run([sys.executable, REPO / 'docs' / 'validate_pcb.py', pcb])
    # Match validate_pcb's per-check lines only ("[x] FAIL  <name>"), not its
    # trailing "RESULT: n FAIL" summary — counting the summary as a finding
    # made this gate report a failure it could not name.
    fails = [l.strip() for l in r.stdout.splitlines()
             if re.search(r'FAIL\s{2,}\S', l) and not l.strip().startswith('RESULT')]
    # validate_pcb also runs the DRC-report gate; reported separately below.
    placement = [re.sub(r'^\S+\s+FAIL\s+', '', f) for f in fails if 'DRC report' not in f]
    return not placement, f'{len(placement)} placement failure(s)' + (
        ': ' + '; '.join(x[:60] for x in placement[:3]) if placement else '')


def gate_design_rules(pcb: Path) -> tuple[bool, str]:
    if not KIPYTHON.exists():
        return False, 'kipython not found — cannot check docs/DESIGN_RULES.md'
    r = _run([KIPYTHON, REPO / 'docs' / 'check_design_rules.py', pcb])
    line = next((l for l in r.stdout.splitlines() if l.startswith('RESULT:')), '')
    return r.returncode == 0, line or 'no result line'


def gate_research(pcb: Path) -> tuple[bool, str]:
    """Phase 1 + Phase 2 — the RESEARCH half, which had no gate at all until
    2026-08-25. Reference-design collection was the most valuable step in the
    workflow and the least enforced: four boards, zero stored references, on
    a step two separate documents called a "HARD GATE".

    Advisory sub-checks are surfaced but do not fail the board, so the gate
    reports on things that legitimately vary (LCSC coverage) without becoming
    the gate everyone learns to ignore."""
    r = _run([sys.executable, REPO / 'docs' / 'check_research.py', pcb, '--json'])
    try:
        res = json.loads(r.stdout)
    except Exception:                                       # noqa: BLE001
        return False, f'research check did not run: {r.stderr.strip()[:200]}'
    hard = [x for x in res if not x['ok'] and x['severity'] == 'BLOCK']
    soft = [x for x in res if not x['ok'] and x['severity'] == 'ADVISE']
    lines = [f'{len(res) - len(hard) - len(soft)}/{len(res)} research checks pass'
             + (f'; {len(soft)} advisory' if soft else '')]
    for x in hard + soft:
        tag = 'BLOCK' if x['severity'] == 'BLOCK' else 'advise'
        lines.append(f'  [{tag}] {x["name"]}')
        for ln in x['detail'].splitlines():
            lines.append(f'          {ln}')
    return not hard, '\n'.join(lines)


def gate_erc(pcb: Path) -> tuple[bool, str]:
    sch = pcb.with_suffix('.kicad_sch')
    out = pcb.parent / 'erc-report.json'
    if not sch.is_file():
        return False, 'no schematic'
    _run([KICAD_CLI, 'sch', 'erc', '--format', 'json', '-o', out, sch])
    if not out.is_file():
        return False, 'ERC produced no report'
    d = json.loads(out.read_text())
    vs = [v for s in d.get('sheets', []) for v in s.get('violations', [])]
    real = [v for v in vs if not _erc_waivable(v)]
    waived = len(vs) - len(real)
    return not real, f'{len(real)} violation(s), {waived} waived (Unspecified pin type, EasyEDA-converted symbols)'


def _drc_once(pcb: Path, out: Path):
    """One DRC run. Returns (errors, warnings, unconnected) or raises."""
    if out.exists():
        out.unlink()          # never let a previous run's report be read as this one's
    r = _run([KICAD_CLI, 'pcb', 'drc', '--format', 'json', '-o', out,
              '--refill-zones', pcb])
    if not out.is_file():
        raise RuntimeError(
            f'kicad-cli produced no DRC report (exit {r.returncode}): '
            + (r.stderr or r.stdout).strip()[:200])
    d = json.loads(out.read_text())
    errs = [v for v in d.get('violations', []) if v.get('severity') == 'error']
    warns = len(d.get('violations', [])) - len(errs)
    return len(errs), warns, len(d.get('unconnected_items', []))


def gate_drc(pcb: Path) -> tuple[bool, str]:
    """DRC, refilled and run TWICE — the only form of it that is evidence.

    Three separate defects lived in the two lines this replaced.

    1. It ignored kicad-cli's exit code and read `drc-report.json` from the
       project directory whether or not this run had written it. Pointed at
       a corrupt, unparseable board file sitting next to a stale clean
       report, the gate that decides "can JLCPCB build this?" returned
       PASS, 0 errors. The report is now deleted before the run and its
       absence is a hard failure.

    2. It did not refill zones, so DRC judged whatever fill state happened
       to be cached. Copper-pour clearance violations appeared and vanished
       between runs of an unchanged file, and the optimistic answer was the
       usual one.

    3. Even refilled, tms-v3 alternates between 1 and 2 clearance errors on
       consecutive runs of an unchanged board. That is KiCad's behaviour,
       not something this repo can fix — but a result that does not
       reproduce is not evidence, so the gate runs twice, reports the WORSE
       outcome, and says plainly when the two disagreed. A board passes
       only when both runs are clean.
    """
    out = pcb.parent / 'drc-report.json'
    runs = []
    for _ in range(2):
        try:
            runs.append(_drc_once(pcb, out))
        except Exception as exc:                            # noqa: BLE001
            return False, str(exc)
    worst = max(runs, key=lambda r: (r[0] + r[2], r[1]))
    errs, warns, unc = worst
    detail = (f'{errs} error(s), {warns} warning(s), {unc} unconnected — '
              'routing is complete only at zero unconnected')
    if runs[0] != runs[1]:
        detail += (f'\n  UNSTABLE: two runs of the same unchanged board '
                   f'disagreed ({runs[0]} vs {runs[1]}); the worse is reported. '
                   'Open it in KiCad, refill zones, and fix the pour clearance '
                   'rather than trusting the better run.')
    return (not errs and not unc), detail


SIGNATURE_RE = re.compile(r'\d{4}-\d{2}-\d{2}')


def gate_signoff(pcb: Path) -> tuple[bool, str]:
    """HUMAN gate. Proves the step was performed, not that it was correct.

    This is the LAST gate and it was the weakest thing in the workspace.
    It counted `- [x]` and nothing else, so

        sed -i '' 's/- \[ \]/- [x]/' SIGNOFF.md

    — one line, no reading, no board opened — turned "NOT READY" into
    "all gates pass" and armed the fab stage on three boards. The template
    has always said "add your initials + date"; that instruction was prose,
    and prose is not a gate. A ticked item now needs a date on it. That
    still cannot prove the check was done *well*, which is stated plainly
    and not papered over — but it does mean the tick was a deliberate act
    rather than a search-and-replace.
    """
    f = pcb.parent / 'SIGNOFF.md'
    if not f.is_file():
        return False, 'no SIGNOFF.md — human gates unrecorded'
    lines = f.read_text().splitlines()
    todo, signed, unsigned = [], [], []
    for i, l in enumerate(lines):
        # A 4-space indent is a markdown code block, not a checklist item.
        # The worked example added to the template above — an already-dated
        # `- [x]` line showing the required format — was being counted as a
        # signed item the moment it was written. That is the same
        # template-satisfies-its-own-check defect that this repo has now hit
        # four times (DEVIATIONS' example waiver, DESIGN_BASIS' <U1> row,
        # the stale template project, and now this one). Examples must be
        # inert by construction.
        if re.match(r'\s{4,}', l):
            continue
        if re.match(r'\s*-\s*\[ \]', l):
            todo.append(l)
        elif re.match(r'\s*-\s*\[[xX]\]', l):
            # the signature may sit on the item line or its continuation
            blob = ' '.join(lines[i:i + 4])
            (signed if SIGNATURE_RE.search(blob) else unsigned).append(
                re.sub(r'\s*-\s*\[[xX]\]\s*', '', l).strip('* ')[:48])
    ok = not todo and not unsigned
    detail = f'{len(signed)} signed, {len(todo)} outstanding'
    if unsigned:
        detail += (f', {len(unsigned)} ticked WITHOUT a signature — add initials '
                   'and a YYYY-MM-DD date: ' + '; '.join(unsigned[:3]))
    return ok, detail



# --------------------------------------------------------------------------
# Scaffolding
# --------------------------------------------------------------------------
# A gate that depends on a file nobody creates is a gate that always fails
# for a boring reason, and a gate that always fails for a boring reason gets
# ignored. Three of this repo's four boards had no SIGNOFF.md at all, so the
# human gate was unrecorded rather than unmet. --init closes that: it creates
# the artifacts the gates read, pre-populated with the questions no tool can
# answer. It never overwrites an existing file.

SIGNOFF_TEMPLATE = """# Human Sign-Off — {board}

Claude can get a board to *"every automated gate passes."* It cannot get it to
*"correct."* Checking a box here records that the step was **performed** — not
that it was performed correctly. That distinction is real and is not hidden.

Sign by changing `- [ ]` to `- [x]` and appending your initials and a
`YYYY-MM-DD` date. The date is **checked** — a tick with no date does not
count, because `sed 's/\[ \]/[x]/'` is not a design review:

    - [x] **Board opened in KiCad and looked at.**  — TL 2026-08-26

- [ ] **Module socket pinouts verified against the vendor card, module in hand.**
      Highest-stakes item; no tool here can check it. A sequentially-assigned
      header netlist passes ERC, passes DRC, routes cleanly, fabricates — and
      then puts a power rail into a 3.3V GPIO. Both of TMS V3's module sockets
      were wrong in exactly this way.
- [ ] **Hand-authored footprints checked against the real part.** Print 1:1 and
      offer the component to it.
- [ ] **Passive values confirmed against the part actually bought**, not the
      generic value. Crystal load caps especially.
- [ ] **`DEVIATIONS.md` reviewed** — every declared deviation agreed or rejected.
- [ ] **Board opened in KiCad and looked at.** 3D view for mechanical fit,
      silkscreen legibility, pin-1 markers.
- [ ] **Connectors are the real connector.** A part labelled "XT60" that is a
      2.54mm header passes every automated gate in this workspace.
- [ ] **Current-carrying nets sized for actual current**, not default width.
- [ ] **Mounting holes and outline checked against the mechanical assembly.**
- [ ] **BOM sourceable** — every line has an LCSC number and stock.
"""

DEVIATIONS_TEMPLATE = """# Declared Deviations — {board}

A rule you cannot meet is an engineering decision. Decisions get written down
with a reason; they do not get quietly dropped from the report. Anything
`check_design_rules.py` flags that is NOT listed here is a hard failure.

Format — one per line:

    <part.pin> | <rule number> | <reason>

Example:

    U99.3 | 2.2 | VREF_N is a reference pin, not a supply rail; the 2mm
                  decoupling rule does not apply. Bypassed at the ADC's AVDD.

(The example uses U99 on purpose: a plausible designator here would be
parsed as a real waiver. Put real entries under "## Declared" below —
nothing above that heading waives anything.)

## Declared
"""

INDEX_TEMPLATE = """# Datasheet Provenance — {board}

Every non-passive part needs a datasheet on file. This index maps parts to the
PDF that documents them, and records where each came from, so "verified"
can be told apart from "not verified" — the distinction that was missing when
eleven parts shipped with an empty datasheets/ folder and nothing noticed.

Format:  `<keys> -> <file>`  (keys = comma-separated part/value substrings)

## Known gaps

_List any part with no obtainable datasheet, and say what you did instead._
"""


REQUIREMENTS_TEMPLATE = """# Requirements — {board}

Phase 1 deliverable. Audited 2026-08-25: no board in this repo had one, so
every later "why is it like this?" had to be reconstructed from chat
scrollback. Replace every <angle bracket> — `check_research.py` fails on a
section left as a placeholder, because a half-filled spec reads as a
finished one.

## Purpose
<What the board does, in one paragraph, and what system it plugs into.>

## Electrical
- Supply: <voltage in, tolerance, max current>
- Rails generated: <e.g. 3V3 @ 500mA>
- Signal levels: <3.3V / 5V logic, any level shifting needed>
- Worst-case load / transient: <e.g. relay coil inrush, igniter current>

## Mechanical
- Board outline: <X x Y mm>
- Mounting holes: <count, diameter, positions>
- Height limit / connector-facing edges: <...>

## Interfaces
| Connector | Signal set | Mates with | Notes |
|---|---|---|---|
| <J1> | <...> | <...> | <...> |

## Environment
- Temperature: <range>
- Vibration / shock: <e.g. rocket flight loads>
- Conformal coating, potting, EMI environment: <...>

## Success criteria
- <Measurable. "Reads pressure at 50 Hz over I2C with <1 Pa noise", not "works".>
"""

DESIGN_BASIS_TEMPLATE = """# Design Basis — {board}

Every key part's circuit should name what it was learned from. PCB design,
like code, is mostly reading how credible people solved the same problem and
then justifying each departure. A departure nobody wrote down is
indistinguishable from an oversight — that is the whole reason this file
exists.

Fill one row per key part (any IC >=8 pins, or any plug-in module socket).
Archive the source first so the citation points at a file you still have:

    python3 docs/collect_references.py suggest <PART>
    python3 docs/collect_references.py add {proj} <PART> <URL>

| Ref | Part | Aspect | Ours | Reference says | Source | Verdict |
|---|---|---|---|---|---|---|
| <U1> | <PART> | decoupling | <100nF> | <10uF + 100nF> | <reference-designs/FILE + url> | <Match / Deviate: reason> |

Verdict must be `Match` or `Deviate: <reason>`. "Deviate" with a real reason
is a good outcome — this file is not here to make you copy the EVM, it is
here to make the choice explicit and re-checkable.

Rules and lectures count as sources too: a `docs/DESIGN_RULES.md` rule number,
a manufacturer app note, Phil's Lab or Altium Academy layout guidance. Cite
which one.
"""

REF_INDEX_TEMPLATE = """# Reference Design Archive — {board}

Provenance record for reference designs, EVM schematics, app notes and
vendor source files. `docs/check_research.py` reads the `->` rows.

Format:  PART[, PART...]  ->  filename  # source-url | fetched YYYY-MM-DD | note

Nothing counts as a reference until it is a FILE ON THIS DISK with a live
source URL beside it. A link read once and not saved cannot be re-checked,
and a summary of a schematic is not a schematic.

Add entries with:
    python3 docs/collect_references.py add {proj} <PART> <URL>
"""


def init_project(proj: Path) -> int:
    if not proj.is_dir():
        print(f'no such project directory: {proj}')
        return 1
    board = proj.name
    made, kept = [], []
    targets = [
        (proj / 'SIGNOFF.md', SIGNOFF_TEMPLATE),
        (proj / 'DEVIATIONS.md', DEVIATIONS_TEMPLATE),
        (proj / 'datasheets' / 'INDEX.md', INDEX_TEMPLATE),
        (proj / 'REQUIREMENTS.md', REQUIREMENTS_TEMPLATE),
        (proj / 'DESIGN_BASIS.md', DESIGN_BASIS_TEMPLATE),
        (proj / 'reference-designs' / 'INDEX.md', REF_INDEX_TEMPLATE),
    ]
    for path, tpl in targets:
        if path.exists():
            kept.append(path.name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        rel = proj.relative_to(REPO) if proj.is_relative_to(REPO) else proj
        path.write_text(tpl.format(board=board, proj=rel))
        made.append(str(path.relative_to(REPO)))
    print(f'=== init: {board} ===')
    for m in made:
        print(f'  created  {m}')
    for k in kept:
        print(f'  kept     {k} (already present)')
    print(f'\nNext: python3 docs/run_gates.py {proj}/{board}.kicad_pcb')
    return 0


def gate_netlist_parity(pcb: Path) -> tuple[bool, str]:
    """Does the board describe the same circuit as the schematic?

    Nothing asked this until 2026-08-26, and three of four boards were
    declaring connectivity twice — `pin_label()` in the schematic generator
    and a separately-derived NET_MAP in the PCB generator. It shipped five
    electrically dead test points that every other gate passed: DRC cannot
    see a pad with no net, because a pad with no net has no ratsnest.
    """
    if not KIPYTHON.exists():
        return False, 'kipython not found — cannot compare netlists'
    r = _run([KIPYTHON, REPO / 'docs' / 'check_netlist_parity.py', pcb])
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    head = next((l for l in lines if l.startswith('schematic:')), '')
    bad = [l.strip() for l in lines if 'MISMATCH:' in l or 'NOT on the board' in l
           or 'NOT in the schematic' in l]
    detail = head or (lines[0] if lines else 'no output')
    if bad:
        detail += '\n  ' + '\n  '.join(b[:110] for b in bad[:6])
    return r.returncode == 0, detail


def gate_schematic_quality(pcb: Path) -> tuple[bool, str]:
    """Is the schematic a document a human can read?

    ERC checks connectivity and nothing else, so two rules this repo states
    in writing went unenforced on every board: the ~25-components-per-A4
    hierarchy rule, and having a title block at all.
    """
    r = _run([sys.executable, REPO / 'docs' / 'check_schematic_quality.py', pcb])
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    head = lines[0] if lines else 'no output'
    notes = [l.strip() for l in lines if l.strip().startswith(('FAIL:', 'advise:'))]
    if notes:
        head += '\n  ' + '\n  '.join(n[:110] for n in notes[:4])
    return r.returncode == 0, head


def gate_schematic_ownership(pcb: Path) -> tuple[bool, str]:
    """Is `netmap.json` actually derived from the schematic on disk right now?

    netmap.json is the ONE schematic->PCB connectivity contract (CLAUDE.md
    rule 12) and the PCB generator builds the board from it. If it goes stale,
    the board is built from a netlist describing a drawing that no longer
    exists — and nothing else notices: ERC only reads the schematic, DRC only
    reads the board, and parity compares those two without ever asking where
    the netlist between them came from.

    That matters much more now that a human draws these sheets. The contract
    used to be *declared* by `gen_*_sch.py` alongside the schematic it was
    describing; for a hand-drawn board it is *derived* from the schematic.
    Deriving it is only trustworthy if something checks it was re-derived
    after the last edit.

    Deliberately NOT a comparison against PIPELINE.json. The first version of
    this gate compared the schematic hash to the one recorded there — and
    PIPELINE.json is written at the END of a run, so on any run that
    regenerated the schematic the gate read the PREVIOUS run's hash and failed.
    It failed baro-bmp390 on its first clean build. Recurring defect class #7,
    "the gate that reads a stale artifact", inside a gate written to catch
    stale artifacts.

    Drift detection — a schematic hand-edited, or a generator run outside the
    pipeline — lives in `pipeline.stage_sch` instead, where the baseline
    genuinely is the previous run and the answer arrives BEFORE anything gets
    overwritten. Two questions, two places, neither reading an artifact the
    current run has not finished writing.
    """
    sys.path.insert(0, str(REPO / 'docs'))
    import pipeline
    import extract_netmap

    b = pipeline.Board(pcb.parent)
    owner = b.owner()

    if owner == 'invalid':
        got = (b.dir / pipeline.OWNER_FILE).read_text().strip()[:40]
        return False, (f'{pipeline.OWNER_FILE} says {got!r} — must be one of '
                       + ', '.join(pipeline.OWNERS))
    if not b.sch.is_file():
        return False, 'no schematic'

    netmap = b.dir / 'netmap.json'
    if not netmap.is_file():
        return False, 'no netmap.json — no schematic->PCB contract to build the board from'

    on_disk = json.loads(netmap.read_text()).get('nets', {})
    # `#PWR`/`#FLG` pseudo-refs carry no footprint, so nothing derived from a
    # netlist can name them and gen_*_pcb.py filters them out anyway.
    on_disk = {r: v for r, v in on_disk.items() if not r.startswith('#')}
    fresh = extract_netmap.extract(b.sch)['nets']

    if on_disk != fresh:
        differing = sorted(r for r in set(on_disk) | set(fresh)
                           if on_disk.get(r) != fresh.get(r))
        return False, (f'netmap.json disagrees with {b.sch.name} on '
                       f'{len(differing)} reference(s): {", ".join(differing[:8])} — '
                       f'the board was built from a stale netlist. Re-run the pipeline.')

    n = sum(len(v) for v in fresh.values())
    return True, (f'{owner}-owned; netmap.json matches {b.sch.name} '
                  f'({n} pin-net assignments)')


GATES = [
    ('Phase 1-2 research + references', gate_research, 'auto'),
    ('Step 2.1  datasheets on file', gate_datasheets, 'auto'),
    ('Phase 3   schematic ERC', gate_erc, 'auto'),
    ('Phase 3   schematic provenance', gate_schematic_ownership, 'auto'),
    ('Phase 3   schematic readable', gate_schematic_quality, 'auto'),
    ('Phase 4B  schematic == PCB netlist', gate_netlist_parity, 'auto'),
    ('Phase 4A  placement geometry', gate_placement, 'auto'),
    ('Phase 4A  docs/DESIGN_RULES.md', gate_design_rules, 'auto'),
    ('Phase 4C  DRC + full routing', gate_drc, 'auto'),
    ('Phase 5   human sign-off', gate_signoff, 'HUMAN'),
]


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    if args[0] == '--init':
        if len(args) < 2:
            print('usage: run_gates.py --init projects/<board>')
            sys.exit(2)
        sys.exit(init_project(Path(args[1]).resolve()))
    pcb = Path(args[0]).resolve()
    print(f'=== gates: {pcb.name} ===')
    failed = 0
    for name, fn, kind in GATES:
        try:
            ok, detail = fn(pcb)
        except Exception as exc:                       # noqa: BLE001
            ok, detail = False, f'gate crashed: {exc}'
        mark = 'PASS' if ok else 'FAIL'
        tag = '' if kind == 'auto' else '  [HUMAN]'
        print(f'  [{mark}] {name}{tag}\n         {detail}')
        failed += not ok
    print()
    if failed:
        print(f'RESULT: {failed} gate(s) FAILED — not ready for fabrication')
    else:
        print('RESULT: all gates pass')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
