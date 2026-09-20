#!/usr/bin/env python3
"""The single entry point for building a board. One command, every stage, in order.

    python3 scripts/pipeline.py projects/<board>            # full run
    python3 scripts/pipeline.py projects/<board> --from pcb # resume at a stage
    python3 scripts/pipeline.py projects/<board> --check    # gates only, no rebuild
    python3 scripts/pipeline.py --status                    # every board, one table

WHY THIS FILE EXISTS
--------------------
Before it, "build the board" meant remembering: which generator to run, in
which order, which helper to import, which checks to run afterward, and which
document to consult. Every one of those was a chance to skip a step, and the
record of this workspace is that skipped steps are the ONLY defect class that
has ever shipped here.

So the pipeline is not a convenience wrapper. It is the enforcement mechanism:

  * The order is fixed in code, not in prose.
  * A stage that fails STOPS the run. You cannot route an unplaced board or
    fabricate an unrouted one by forgetting.
  * Every run writes PIPELINE.json (machine) and STATUS.md (human) recording
    what ran, when, against which git commit, and what the board hashed to.
    A completion claim without that record is not evidence.
  * The last stage is always run_gates.py. It cannot be turned off.

Stages are named so `--from` reads like the workflow document:
    env -> sch -> erc -> pcb -> route -> gates
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / 'scripts'
KICAD_CLI = Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
KIPYTHON = Path.home() / '.local' / 'bin' / 'kipython'

STAGE_ORDER = ['env', 'research', 'sch', 'erc', 'pcb', 'route', 'gates', 'fab']

# Stages that REPORT but never halt the build. The research half of the
# workflow (requirements, reference designs, sourcing, design basis) has to
# be visible from the very first run, but a board you are still exploring
# must not be un-buildable because you have not written its spec yet. So it
# is advisory HERE and authoritative at the `gates` stage, where "done" is
# actually decided. That two-speed split is deliberate: a gate that blocks
# every move is a gate people route around.
ADVISORY = {'research'}

# Who authors a board's schematic. `gen_*_sch.py` ends in an unconditional
# write, so before this marker existed one routine pipeline run silently
# destroyed any hand-editing done in Eeschema. See stage_sch().
OWNER_FILE = 'SCHEMATIC_OWNER'
OWNERS = ('generated', 'human')


class StageResult:
    def __init__(self, name, ok, detail, secs, skipped=False):
        self.name, self.ok, self.detail = name, ok, detail
        self.secs, self.skipped = secs, skipped

    def as_dict(self):
        return {'stage': self.name, 'ok': self.ok, 'skipped': self.skipped,
                'detail': self.detail, 'seconds': round(self.secs, 1)}


def run(cmd, cwd=None, timeout=None):
    return subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True,
                          text=True, timeout=timeout)


# Deliberately NOT anchored to surrounding quotes. The first version was
# `"<uuid>"`, which missed every instance path — KiCad writes those as
# `(path "/<root-uuid>")`, with a slash inside the quotes. 31 of baro-bmp390's
# 148 UUIDs escaped masking that way, all of them the root sheet UUID, which
# is minted fresh on every regeneration. So the "canonical" hash moved on
# every run of an unchanged board: `--status` called fresh reports stale,
# `--verify-repeatable` could never pass, and the schematic provenance
# tripwire would have fired on every ordinary build. Recurring defect class
# #8, the non-deterministic gate.
UUID_RE = re.compile(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def sha(path: Path) -> str:
    """CANONICAL hash: UUIDs masked before hashing.

    Measured 2026-08-25: two identical generator runs produce files differing
    on 83 lines, every one of them a regenerated `(uuid ...)`. Strip those and
    the files are byte-identical — geometry, netlist and placement are fully
    deterministic. A raw hash would therefore report every rebuild as a change
    and every board as permanently "stale", which trains you to ignore the
    field. Masking UUIDs makes the hash mean what it claims: did the DESIGN
    change. Freerouting remains genuinely non-deterministic; that is a routing
    property, not a generator one.
    """
    if not path.is_file():
        return '-'
    return hashlib.sha256(UUID_RE.sub(b'UUID', path.read_bytes())).hexdigest()[:12]


def check_repeatable(b: 'Board') -> StageResult:
    """Rebuild twice and prove the design output is identical.

    Repeatability is a claim; this measures it. Run with --verify-repeatable.
    """
    t = time.time()
    if not b.has_generators():
        return StageResult('repeat', False, 'no generators to re-run', time.time() - t)
    hashes = []
    for _ in range(2):
        for g in (b.gen_sch, b.gen_pcb):
            r = run([sys.executable, g.name], cwd=g.parent, timeout=1800)
            if r.returncode != 0:
                return StageResult('repeat', False, f'{g.name} failed', time.time() - t)
        hashes.append((sha(b.pcb), sha(b.sch)))
    ok = hashes[0] == hashes[1]
    return StageResult('repeat', ok,
                       f'pcb {hashes[0][0]} vs {hashes[1][0]}; sch {hashes[0][1]} vs {hashes[1][1]}'
                       + ('  — repeatable' if ok else '  — NOT REPEATABLE'),
                       time.time() - t)


def git_sha() -> str:
    r = run(['git', '-C', REPO, 'rev-parse', '--short', 'HEAD'])
    dirty = run(['git', '-C', REPO, 'status', '--porcelain'])
    return (r.stdout.strip() or 'no-git') + ('+dirty' if dirty.stdout.strip() else '')


# ---------------------------------------------------------------------------
# Board discovery. Conventions are enforced here rather than assumed, so a
# project laid out wrongly fails loudly at stage 0 instead of half-building.
# ---------------------------------------------------------------------------
class Board:
    def __init__(self, proj: Path):
        self.dir = proj.resolve()
        self.name = self.dir.name
        self.pcb = self.dir / f'{self.name}.kicad_pcb'
        self.sch = self.dir / f'{self.name}.kicad_sch'
        self.gen_sch = self._find('sch')
        self.gen_pcb = self._find('pcb')

    def _find(self, kind: str):
        # gen_<anything>_<kind>.py — the workspace convention.
        hits = sorted(self.dir.glob(f'gen_*_{kind}.py'))
        return hits[0] if hits else None

    def has_generators(self):
        return bool(self.gen_sch and self.gen_pcb)

    def owner(self) -> str:
        """'generated', 'human', or 'invalid'. Absent file means 'generated',
        so every board that existed before the marker keeps working."""
        f = self.dir / OWNER_FILE
        if not f.is_file():
            return 'generated'
        v = f.read_text().strip().lower()
        return v if v in OWNERS else 'invalid'

    def last_sch_sha(self):
        """The schematic hash the previous run recorded, or None on a first
        run. `sha()` masks UUIDs, so a cosmetic KiCad re-save does not move
        it — only a real content change does."""
        f = self.dir / 'PIPELINE.json'
        if not f.is_file():
            return None
        try:
            return json.loads(f.read_text()).get('sch_sha256_12')
        except (json.JSONDecodeError, OSError):
            return None


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def stage_env(b: Board) -> StageResult:
    """Phase 0 health check. Cheap, and it turns three different confusing
    downstream failures into one clear message here."""
    t = time.time()
    problems = []
    # The meta-gate: is the enforcement itself wired up? Checked FIRST,
    # because every other gate in this pipeline is worthless if the hooks,
    # matchers and entry points that invoke them have quietly come undone —
    # which is exactly what happened on 2026-08-25.
    st = run([sys.executable, SCRIPTS / 'selftest_enforcement.py'])
    if st.returncode != 0:
        bad = [l.strip() for l in st.stdout.splitlines() if '[FAIL]' in l]
        problems.append(f'enforcement self-test: {len(bad)} broken '
                        f'({"; ".join(b[7:50] for b in bad[:2])})')
    if not KICAD_CLI.exists():
        problems.append('kicad-cli missing')
    if not KIPYTHON.exists():
        problems.append('kipython missing (docs/DESIGN_RULES.md gate cannot run)')
    if not b.dir.is_dir():
        problems.append(f'no project dir {b.dir}')
    if not b.has_generators():
        problems.append('no gen_*_sch.py / gen_*_pcb.py (pipeline cannot rebuild this board)')
    for tbl in ('fp-lib-table', 'sym-lib-table'):
        if not (b.dir / tbl).is_file():
            problems.append(f'{tbl} missing')
    jars = sorted((REPO / 'tools/kicad-claude-mcp/third_party').glob('freerouting*.jar'))
    if not jars:
        problems.append('no freerouting jar (routing unavailable)')
    ok = not problems
    return StageResult('env', ok, '; '.join(problems) if problems else
                       f'kicad-cli, kipython, {len(jars)} router jar(s), lib tables OK',
                       time.time() - t)


def _run_generator(script: Path, label: str, t0) -> StageResult:
    r = run([sys.executable, script.name], cwd=script.parent, timeout=1800)
    ok = r.returncode == 0
    if ok:
        tail = [l for l in r.stdout.strip().splitlines() if l.strip()]
        detail = tail[-1][:160] if tail else f'{script.name} ok'
    else:
        err = (r.stderr.strip() or r.stdout.strip()).splitlines()
        detail = ' | '.join(err[-3:])[:300] or f'{script.name} exited {r.returncode}'
    return StageResult(label, ok, detail, time.time() - t0)


def stage_research(b: Board) -> StageResult:
    """Phase 1 + 2 — requirements, reference designs, sourcing, design basis.

    Audited 2026-08-25: this half of the workflow had NO enforcement of any
    kind. Four boards, zero archived reference designs, on a step that two
    separate documents call a "HARD GATE". Reference designs are the highest
    -value input to a board and were the least checked thing in the repo.

    Advisory here (see ADVISORY) — it tells you what research is outstanding
    without refusing to build. `gates` re-runs it as a blocking check."""
    t = time.time()
    if not b.pcb.is_file():
        return StageResult('research', True,
                           'no board file yet — research is checked at the gates stage',
                           time.time() - t, skipped=True)
    r = run([sys.executable, SCRIPTS / 'check_research.py', b.pcb])
    line = next((l for l in reversed((r.stdout or '').splitlines())
                 if l.startswith('RESULT:')), 'no result')
    detail = line.replace('RESULT: ', '').strip()
    open_items = [l.strip() for l in (r.stdout or '').splitlines()
                  if l.strip().startswith(('[FAIL]', '[WARN]'))]
    if open_items:
        detail += ' — ' + '; '.join(o.split(']', 1)[1].strip() for o in open_items)
    return StageResult('research', r.returncode == 0, detail, time.time() - t)


def stage_sch(b: Board, regenerate: bool = False) -> StageResult:
    """Build the schematic — unless a human owns it.

    WHY THIS IS NOT JUST `_run_generator`
    -------------------------------------
    Every `gen_<board>_sch.py` ends in an unconditional

        sch_io.write_file(SCH_PATH, tree)

    and this stage runs on every `pipeline.py projects/<board>` invocation.
    So before the SCHEMATIC_OWNER marker, a routine pipeline run silently
    destroyed hours of hand-editing in Eeschema. Not a hypothetical: the
    generated sheets measure ZERO junctions on all four boards — every pin
    terminates in a stub and a label, nothing reads as a circuit — so
    hand-drawing them is the plan, and this stage was the thing that made
    hand-drawing unsafe.

    Three branches:

      generated + hash matches   -> regenerate, exactly as before
      generated + hash DIFFERS   -> STOP. The schematic was edited by hand
                                    but never declared human-owned. Silently
                                    overwriting it is the failure this whole
                                    marker exists to prevent, so the run
                                    refuses rather than guessing.
      human                      -> do not generate at all. Derive
                                    netmap.json FROM the schematic instead,
                                    so the PCB is built from what was
                                    actually drawn. ERC and the parity gate
                                    then check that drawing as normal.

    The middle branch is the one that matters. A guard that only protects
    boards you remembered to mark protects nothing.
    """
    t = time.time()
    owner = b.owner()

    if owner == 'invalid':
        got = (b.dir / OWNER_FILE).read_text().strip()[:40]
        return StageResult('sch', False,
                           f'{OWNER_FILE} says {got!r} — must be one of '
                           + ', '.join(OWNERS), time.time() - t)

    if owner == 'human':
        # Refuse loudly rather than quietly ignoring the flag. A --regenerate
        # that silently no-ops is how someone concludes the guard did not work
        # and reaches for something blunter.
        if regenerate:
            return StageResult('sch', False,
                               f'--regenerate refused: {b.dir.name} is human-owned. '
                               f'To hand the schematic back to the generator, set '
                               f'{OWNER_FILE} to `generated` first — that discards '
                               f'the hand-drawn sheet, so do it deliberately.',
                               time.time() - t)
        if not b.sch.is_file():
            return StageResult('sch', False,
                               f'{OWNER_FILE} says human but {b.sch.name} does not '
                               'exist — nothing to build the board from',
                               time.time() - t)
        r = run([sys.executable, SCRIPTS / 'extract_netmap.py', b.sch])
        if r.returncode != 0:
            return StageResult('sch', False,
                               'netmap extraction failed: '
                               + (r.stderr or r.stdout).strip().splitlines()[-1][:200],
                               time.time() - t)
        detail = (r.stdout or '').strip().splitlines()
        return StageResult('sch', True,
                           'human-owned — not regenerated | '
                           + (detail[-1] if detail else 'netmap.json derived'),
                           time.time() - t, skipped=True)

    baseline = b.last_sch_sha()
    if (baseline is not None and b.sch.is_file() and sha(b.sch) != baseline
            and not regenerate):
        return StageResult('sch', False,
                           f'{b.sch.name} is not what the last recorded run produced '
                           f'({baseline} -> {sha(b.sch)}). Either it was hand-edited, '
                           f'or a generator was run outside the pipeline (which '
                           f'CLAUDE.md forbids for exactly this reason). Regenerating '
                           f'now would discard whatever is there. KEEP it: '
                           f'`echo human > {b.dir.name}/{OWNER_FILE}`. DISCARD it and '
                           f'rebuild from the generator: re-run with --regenerate.',
                           time.time() - t)

    return _run_generator(b.gen_sch, 'sch', t)


def stage_pcb(b: Board) -> StageResult:
    return _run_generator(b.gen_pcb, 'pcb', time.time())


def stage_erc(b: Board) -> StageResult:
    t = time.time()
    if not b.sch.is_file():
        return StageResult('erc', False, 'no schematic', time.time() - t)
    out = b.dir / 'erc-report.json'
    run([KICAD_CLI, 'sch', 'erc', '--format', 'json', '-o', out, b.sch], timeout=600)
    if not out.is_file():
        return StageResult('erc', False, 'ERC produced no report', time.time() - t)
    d = json.loads(out.read_text())
    vs = [v for s in d.get('sheets', []) for v in s.get('violations', [])]
    real = [v for v in vs if v.get('type') != 'pin_to_pin']
    return StageResult('erc', not real,
                       f'{len(real)} violation(s), {len(vs) - len(real)} waived',
                       time.time() - t)


def stage_route(b: Board, passes: int) -> StageResult:
    t = time.time()
    script = SCRIPTS / 'route_and_fill.py'
    if not script.is_file():
        return StageResult('route', False, 'route_and_fill.py missing', time.time() - t)

    # Route BEST-OF-N, not once. Freerouting is not deterministic — the same
    # input gives a different unconnected count run to run, because each pass
    # is bounded by wall-clock time and 2.3.0 stops at whatever local minimum
    # it reached. Keeping whichever result the last attempt produced makes
    # "ships" or "does not ship" a matter of luck.
    #
    # scripts/route_best_of.py was written for exactly this and, like
    # stitch_vias.py before it, was invoked by NOTHING — the third orphaned
    # tool found in this workspace. It re-routes from the same unrouted
    # placement each time and keeps the best board.
    best = SCRIPTS / 'route_best_of.py'
    if best.is_file():
        r = run([sys.executable, best, b.pcb, '4', passes], timeout=3600)
    else:
        r = run([sys.executable, script, b.pcb, passes], timeout=3600)
    tail = [l for l in (r.stdout or '').strip().splitlines() if l.strip()]
    ok = r.returncode == 0
    detail = tail[-1][:200] if tail else 'no output'

    # ---- Post-route passes -------------------------------------------
    #
    # Both of these can only run AFTER routing, and neither was reachable
    # from the pipeline until 2026-08-26.
    #
    # stitch_vias.py had a comment saying it "happens after routing, called
    # from build.sh" — and build.sh had since become a two-line shim to this
    # file, so nothing called it at all. tms-v3's ground design explicitly
    # depends on it (its generator declines to place stitching vias itself,
    # on the correct reasoning that pre-placed vias fight the router), which
    # meant that board's ground bonding silently stopped happening when the
    # build path was unified. A tool referenced only in a comment is not
    # wired in.
    #
    # fix_via_annular.py repairs vias the DSN/SES round trip gives a
    # mismatched pad/drill pair — 2 of 100 on tms-v3, at 0.100mm annular
    # against a 0.150mm minimum.
    #
    # Either pass changes the board, so DRC is re-run afterwards: reporting
    # route_and_fill's verdict about a board that no longer exists on disk
    # is exactly the kind of stale evidence this pipeline exists to prevent.
    notes = []
    if KIPYTHON.exists():
        stitch = SCRIPTS / 'stitch_vias.py'
        if stitch.is_file():
            sr = run([KIPYTHON, stitch, b.pcb], timeout=600)
            n = next((l.strip() for l in (sr.stdout or '').splitlines()
                      if 'stitching vias added' in l), '')
            if n and not n.startswith('0 grid + 0'):
                notes.append(n)
        fixer = SCRIPTS / 'fix_via_annular.py'
        if fixer.is_file():
            fr = run([KIPYTHON, fixer, b.pcb], timeout=300)
            n = next((l.strip() for l in (fr.stdout or '').splitlines()
                      if 'widened' in l), '')
            if n:
                notes.append(n)

    if notes:
        # Re-VERIFY, do not re-ROUTE. The first version of this re-ran
        # route_and_fill.py, which regenerates the DSN from the current
        # board and routes it again from scratch — undoing and re-doing the
        # very work the stitching pass had just added, and reporting on a
        # different board than the one on disk a moment earlier. What is
        # needed is a fresh DRC verdict, not a fresh route.
        drc_json = Path(str(b.pcb).replace('.kicad_pcb', '.postfix.drc.json'))
        dr = run([KICAD_CLI, 'pcb', 'drc', '--format', 'json',
                  '--output', drc_json, '--severity-error',
                  '--refill-zones', b.pcb], timeout=900)
        try:
            rep = json.loads(drc_json.read_text())
            errs = sum(1 for v in rep.get('violations', [])
                       if v.get('severity') == 'error')
            unc = len(rep.get('unconnected_items', []))
            ok = (errs == 0 and unc == 0)
            detail = (f'{errs} error(s), {unc} unconnected after post-route passes'
                      ' | ' + '; '.join(notes)[:120])
        except Exception as exc:
            ok = False
            detail = f'post-route DRC did not parse: {exc} | ' + '; '.join(notes)[:100]
        finally:
            drc_json.unlink(missing_ok=True)

    return StageResult('route', ok, detail, time.time() - t)


def stage_fab(b: Board, gates_ok: bool) -> StageResult:
    """Gerbers + drill + JLCPCB BOM + CPL — but ONLY for a board that passed.

    Deliberately last and deliberately conditional. A fabrication package is
    the one artifact that can be uploaded and charged for, so generating one
    for a board whose gates failed manufactures exactly the false confidence
    this pipeline exists to prevent: a folder full of Gerbers looks finished
    whatever the DRC said.
    """
    t = time.time()
    if not gates_ok:
        return StageResult('fab', True, 'skipped — gates did not pass',
                           time.time() - t, skipped=True)
    script = SCRIPTS / 'export_fab.py'
    if not script.is_file():
        return StageResult('fab', False, 'export_fab.py missing', time.time() - t)
    r = run([sys.executable, script, b.pcb], timeout=600)
    lines = [l.strip() for l in (r.stdout or '').splitlines() if l.strip()]
    bom = next((l for l in lines if 'BOM' in l), '')
    cpl = next((l for l in lines if 'CPL' in l), '')
    hand = [l for l in lines if l.startswith('- ')]
    detail = f'{bom.strip("[]ok ")}; {cpl.strip("[]ok ")}'.replace('  ', ' ')
    if hand:
        detail += f' | {len(hand)} hand-fit line(s)'
    return StageResult('fab', r.returncode == 0, detail[:190], time.time() - t)


def stage_gates(b: Board) -> StageResult:
    t = time.time()
    r = run([sys.executable, SCRIPTS / 'run_gates.py', b.pcb], timeout=1800)
    lines = r.stdout.strip().splitlines()
    result = next((l for l in reversed(lines) if l.startswith('RESULT:')), 'no result')
    return StageResult('gates', r.returncode == 0, result.strip(), time.time() - t), r.stdout


# ---------------------------------------------------------------------------
# Reporting — the evidence half. Without this the pipeline is just a script.
# ---------------------------------------------------------------------------
def write_report(b: Board, results, gate_table: str, started: str):
    rec = {
        'board': b.name,
        'started_utc': started,
        'finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'git': git_sha(),
        'pcb_sha256_12': sha(b.pcb),
        'sch_sha256_12': sha(b.sch),
        'stages': [r.as_dict() for r in results],
        'ready_for_fabrication': all(r.ok or r.skipped for r in results)
                                 and any(r.name == 'gates' and r.ok for r in results),
    }
    (b.dir / 'PIPELINE.json').write_text(json.dumps(rec, indent=2) + '\n')

    lines = [f'# Pipeline Status — {b.name}', '',
             '_Machine-generated by `scripts/pipeline.py`. Do not edit by hand._', '',
             f'- Run finished: `{rec["finished_utc"]}`',
             f'- Repo commit: `{rec["git"]}`',
             f'- Board file SHA: `{rec["pcb_sha256_12"]}`', '',
             '| Stage | Result | Detail | Seconds |', '|---|---|---|---|']
    for r in results:
        mark = 'SKIP' if r.skipped else ('PASS' if r.ok else 'FAIL')
        safe = r.detail.replace('|', '\\|')
        lines.append(f'| `{r.name}` | **{mark}** | {safe} | {r.secs:.0f} |')
    lines += ['', '## Gate detail', '', '```', gate_table.strip() or '(gates not run)', '```', '']
    verdict = ('**READY** — every automated gate passes. Human sign-off in `SIGNOFF.md` still governs.'
               if rec['ready_for_fabrication'] else
               '**NOT READY** — see failing stages above.')
    lines += ['## Verdict', '', verdict, '']
    (b.dir / 'STATUS.md').write_text('\n'.join(lines))


def cmd_status():
    """Every board, one table. Answers 'where does everything stand' without
    rebuilding anything."""
    rows = []
    for proj in sorted((REPO / 'projects').iterdir()):
        if not proj.is_dir():
            continue
        b = Board(proj)
        if not b.pcb.is_file():
            rows.append((b.name, '-', 'no board file', '-'))
            continue
        f = proj / 'PIPELINE.json'
        if f.is_file():
            d = json.loads(f.read_text())
            fails = [s['stage'] for s in d['stages'] if not s['ok'] and not s['skipped']]
            state = 'READY' if d.get('ready_for_fabrication') else 'NOT READY'
            rows.append((b.name, d['finished_utc'][:16].replace('T', ' '),
                         state + (f" ({', '.join(fails)})" if fails else ''),
                         'stale' if sha(b.pcb) != d.get('pcb_sha256_12') else 'current'))
        else:
            rows.append((b.name, 'never', 'pipeline never run', '-'))
    w = max(len(r[0]) for r in rows) if rows else 8
    print(f'{"board".ljust(w)}  {"last run".ljust(16)}  {"state".ljust(34)}  report')
    print('-' * (w + 60))
    for n, when, st, fresh in rows:
        print(f'{n.ljust(w)}  {when.ljust(16)}  {st.ljust(34)}  {fresh}')
    print('\nRebuild:  python3 scripts/pipeline.py projects/<board>')
    print('Step-by-step workflow audit:  python3 scripts/audit_workflow.py')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project', nargs='?')
    ap.add_argument('--from', dest='start', choices=STAGE_ORDER, default='env')
    ap.add_argument('--check', action='store_true', help='gates only; never rebuilds')
    ap.add_argument('--skip-route', action='store_true')
    ap.add_argument('--regenerate', action='store_true',
                    help='discard an out-of-sync schematic and rebuild it from the '
                         'generator. Required to get past the sch provenance '
                         'tripwire on a `generated` board; refuses on a `human` one.')
    ap.add_argument('--passes', type=int, default=int(os.environ.get('ROUTE_PASSES', 50)))
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--verify-repeatable', action='store_true',
                    help='rebuild twice and prove the design output is identical')
    a = ap.parse_args()

    if a.status:
        cmd_status()
        return 0
    if not a.project:
        ap.error('give a project directory, or --status')

    if a.verify_repeatable:
        bb = Board(Path(a.project))
        res = check_repeatable(bb)
        print(f'=== repeatability: {bb.name} ===')
        print(f'  [{"PASS" if res.ok else "FAIL"}] {res.detail}  ({res.secs:.0f}s)')
        return 0 if res.ok else 1

    b = Board(Path(a.project))
    started = datetime.now(timezone.utc).isoformat(timespec='seconds')
    print(f'=== pipeline: {b.name} ===')

    if a.check:
        plan = ['gates']
    else:
        plan = STAGE_ORDER[STAGE_ORDER.index(a.start):]
    results, gate_table = [], ''

    gates_ok = False
    for name in STAGE_ORDER:
        if name not in plan:
            results.append(StageResult(name, True, 'not requested', 0.0, skipped=True))
            print(f'  [SKIP] {name}')
            continue
        if name == 'route' and a.skip_route:
            results.append(StageResult('route', True, 'skipped by flag', 0.0, skipped=True))
            print('  [SKIP] route  (--skip-route)')
            continue

        print(f'  [....] {name}', flush=True)
        if name == 'env':
            res = stage_env(b)
        elif name == 'fab':
            res = stage_fab(b, gates_ok)
        elif name == 'research':
            res = stage_research(b)
        elif name == 'sch':
            res = stage_sch(b, regenerate=a.regenerate)
        elif name == 'erc':
            res = stage_erc(b)
        elif name == 'pcb':
            res = stage_pcb(b)
        elif name == 'route':
            res = stage_route(b, a.passes)
        else:
            res, gate_table = stage_gates(b)
            gates_ok = res.ok
        results.append(res)
        mark = 'PASS' if res.ok else ('WARN' if name in ADVISORY else 'FAIL')
        print(f'  [{mark}] {name}  ({res.secs:.0f}s)  {res.detail}')

        # A failing stage stops the run. Routing an unplaced board or
        # fabricating an unrouted one is exactly the class of mistake this
        # pipeline exists to make impossible.
        if not res.ok and name != 'gates' and name not in ADVISORY:
            # Stop building — but ALWAYS run the gates before reporting.
            #
            # The first version broke out here, so a failing route stage
            # produced a STATUS.md with no gate table at all. That is exactly
            # backwards: the run that went worst is the run whose evidence
            # matters most. Building further on a broken stage is forbidden;
            # measuring the damage is mandatory.
            for later in STAGE_ORDER[STAGE_ORDER.index(name) + 1:]:
                if later != 'gates':
                    results.append(StageResult(later, False, 'not reached', 0.0, skipped=True))
            print(f'\n  STOPPED building at {name} — running gates to record the state.')
            gres, gate_table = stage_gates(b)
            results.append(gres)
            print(f'  [{"PASS" if gres.ok else "FAIL"}] gates  ({gres.secs:.0f}s)  {gres.detail}')
            break

    write_report(b, results, gate_table, started)
    ok = all(r.ok for r in results if not r.skipped)
    # The register of what is waiting on a person is regenerated here, so it
    # can never be a stale hand-written list next to a fresh gate table --
    # which is exactly what BLOCKERS.md was when it was deleted.
    hw = SCRIPTS / 'human_work.py'
    if hw.is_file():
        run([sys.executable, hw, '--write'], timeout=600)

    print(f'\nreport: {(b.dir / "STATUS.md").relative_to(REPO)}  +  PIPELINE.json'
          f'  +  HUMAN_WORK.md')
    print('RESULT: ' + ('all stages pass' if ok else 'PIPELINE FAILED — board is not ready'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
