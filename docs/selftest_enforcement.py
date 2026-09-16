#!/usr/bin/env python3
"""Test that the enforcement fires. The meta-gate.

    python3 docs/selftest_enforcement.py

WHY THIS EXISTS
---------------
On 2026-08-25 this workspace discovered two defects of the same shape:

  * A complete gate suite was built and then referenced NOWHERE that loads
    automatically. Three of four boards had none of its artifacts. The fix
    had reproduced the bug it was written to fix.
  * The PostToolUse hook matched only `Write|Edit` and read
    `tool_input.file_path`. Every board here is generator-written through
    `Bash`, which has no `file_path` — so the validator advertised as
    "automatic" had never fired on a single board, ever.

Both passed human review for months because reviewing a rule is not the same
as running it. So the rule became: a lesson is not documented until you have
TESTED THAT THE ENFORCEMENT FIRES. This file is that test, kept honest by
being runnable.

It checks wiring, not board quality. run_gates.py judges boards.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KIPYTHON = Path.home() / '.local' / 'bin' / 'kipython'
results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = '') -> None:
    results.append((ok, name, detail))


def text(p: Path) -> str:
    return p.read_text(encoding='utf-8') if p.is_file() else ''


# --- Tier 1: CLAUDE.md is always loaded -----------------------------------
c = text(REPO / 'CLAUDE.md')
check('CLAUDE.md names the pipeline', 'docs/pipeline.py' in c)
check('CLAUDE.md states the evidence rule', 'not evidence' in c)
check('CLAUDE.md carries the Gate Rule section', 'Gate Rule' in c)

# --- Tier 2: auto-loading rules -------------------------------------------
lay = text(REPO / '.claude/rules/pcb-layout.md')
check('.claude/rules/pcb-layout.md names the pipeline', 'pipeline.py' in lay)
check('.claude/rules/pcb-layout.md has path frontmatter', 'kicad_pcb' in lay.split('---')[1] if lay.count('---') >= 2 else False)

# --- Tier 4: hooks. Both halves — matcher AND script ----------------------
settings_p = REPO / '.claude/settings.json'
try:
    s = json.loads(text(settings_p))
except Exception as e:                                   # noqa: BLE001
    s = {}
    check('settings.json parses', False, str(e))
else:
    check('settings.json parses', True)

hooks = s.get('hooks', {})
post = hooks.get('PostToolUse', [{}])[0]
matcher = post.get('matcher', '')
# THE defect of 2026-08-25: script fixed, matcher not. Both halves or neither.
check('PostToolUse matcher includes Bash (generator path)', 'Bash' in matcher,
      f'matcher={matcher!r}')
check('Stop hook registered (automatic gate evidence)', 'Stop' in hooks)
check('SessionStart hook registered (rules in context)', 'SessionStart' in hooks)

for h in ['validate-pcb-on-edit.sh', 'gate-status-on-stop.sh', 'session-start-brief.sh']:
    p = REPO / '.claude/hooks' / h
    import os
    check(f'hook {h} exists and is executable',
          p.is_file() and os.access(p, os.X_OK))

# Fire the PostToolUse hook with a synthetic Bash event. A hook that cannot
# be triggered by the event it claims to handle is documentation.
probe = REPO / 'projects'
pcbs = sorted(probe.glob('*/*.kicad_pcb'))
if pcbs:
    pcbs[0].touch()
    # Pass a POSIX-friendly relative path to Git Bash. A Windows absolute
    # path is parsed as backslash escapes and the hook is never launched.
    r = subprocess.run(['bash', '.claude/hooks/validate-pcb-on-edit.sh'],
                       input=json.dumps({'tool_name': 'Bash',
                                         'tool_input': {'command': 'python3 gen_x_pcb.py'}}),
                       capture_output=True, text=True, cwd=REPO)
    check('PostToolUse hook actually fires on a synthetic Bash event',
          'validate_pcb.py result' in r.stdout,
          f'rc={r.returncode}; stdout={r.stdout[:80]!r}; stderr={r.stderr[:120]!r}')
else:
    check('PostToolUse hook actually fires on a synthetic Bash event', False, 'no boards to probe')

# --- Tier 0: the gates and the pipeline exist and run ---------------------
for tool in ['pipeline.py', 'run_gates.py', 'check_datasheets.py',
             'check_design_rules.py', 'validate_pcb.py', 'pcb_layout_helpers.py',
             'check_research.py', 'collect_references.py', 'fetch_reference_doc.py']:
    check(f'docs/{tool} present', (REPO / 'docs' / tool).is_file())

r = subprocess.run([sys.executable, REPO / 'docs/pipeline.py', '--status'],
                   capture_output=True, text=True)
check('pipeline --status runs', r.returncode == 0, r.stderr.strip()[:100])

# --- The research half is actually WIRED, not merely present --------------
# fetch_reference_doc.py sat in docs/ for weeks, invoked by NOTHING, while
# two documents called reference-design collection a "HARD GATE". A tool
# that exists and is never called is prose with a shebang.
# Check REGISTRATION, not definition. The first version of this check
# tested `'gate_research' in run_gates.py` — which stays true when the gate
# is deleted from the GATES list, because the function body still exists.
# Fault injection caught it: unwiring the gate changed nothing. That is the
# same shape as the Write|Edit matcher bug — enforcement has two halves and
# testing one of them proves nothing.
_rg = subprocess.run([sys.executable, '-c',
                      'import sys; sys.path.insert(0, %r); import run_gates; '
                      'print([g[0] for g in run_gates.GATES])'
                      % str(REPO / 'docs')], capture_output=True, text=True)
check('research gate is REGISTERED in run_gates.GATES',
      'research' in _rg.stdout, _rg.stdout.strip()[:120] or _rg.stderr[:120])
check('research stage runs in pipeline.py',
      "'research'" in text(REPO / 'docs/pipeline.py'))
check('research stage is advisory (does not block a build)',
      'ADVISORY' in text(REPO / 'docs/pipeline.py'))
check('CLAUDE.md names the unified research command',
      'pcb-copilot research' in text(REPO / 'CLAUDE.md'))
check('.claude/rules/pcb-schematic.md names the unified research command',
      'pcb-copilot research' in text(REPO / '.claude/rules/pcb-schematic.md'))

r = subprocess.run([sys.executable, REPO / 'docs/collect_references.py',
                    'suggest', 'SELFTEST'], capture_output=True, text=True)
check('collect_references suggest runs', r.returncode == 0 and 'Tier 1' in r.stdout)

# The archiver must REFUSE an HTML error page saved as a document. This is
# the silent failure that makes an archive worthless: the gate sees a file.
_probe = REPO / 'docs' / '.selftest_probe.pdf'
_probe.write_text('<!doctype html><html><body>Sign in</body></html>', encoding='utf-8')
try:
    sys.path.insert(0, str(REPO / 'docs'))
    from collect_references import sniff
    check('archiver detects an HTML page masquerading as a document',
          sniff(_probe) == 'html')
finally:
    _probe.unlink(missing_ok=True)

# --- Entry points: slash commands must end at the gate --------------------
for cmd in ['pcb-new.md', 'pcb-from-bom.md']:
    hits = list(REPO.glob(f'tools/*/commands/{cmd}')) + \
           [Path.home() / '.claude/commands' / cmd]
    for h in hits:
        if h.is_file():
            check(f'{h.name} ({"repo" if "tools" in str(h) else "user"}) ends at the gate',
                  'pipeline.py' in text(h) or 'run_gates.py' in text(h))

# --- Per-board artifacts the gates read -----------------------------------
for proj in sorted((REPO / 'projects').iterdir()):
    if not proj.is_dir() or not list(proj.glob('*.kicad_pcb')):
        continue
    for art in ['SIGNOFF.md', 'DEVIATIONS.md', 'build.sh', 'evidence/index.yaml',
                'REQUIREMENTS.md', 'DESIGN_BASIS.md']:
        check(f'{proj.name}: {art}', (proj / art).exists(),
              'run: python3 docs/run_gates.py --init projects/' + proj.name)

# --- The DATASHEET path actually rejects a non-datasheet ------------------
# "The datasheet is the bible" was enforced by counting files whose names
# ended in .pdf. A 60-byte HTML login wall renamed BMP390-datasheet.pdf
# passed check_datasheets.py AND check_research.py's archive integrity, and
# the gate reported "every part accounted for". Every downstream claim of
# "verified against the datasheet" then rested on a document nobody could
# open. These two checks fault-inject that exact file.
import shutil as _sh
_bd = REPO / 'projects' / 'baro-bmp390'
_ds = _bd / 'evidence' / 'files' / 'BMP390-datasheet.pdf'
check('baro self-test evidence fixture exists', _ds.is_file(), str(_ds))
if _ds.is_file():
    _bak = REPO / '.selftest-datasheet.bak'
    try:
        _sh.copy2(_ds, _bak)
        _ds.write_text(
            '<!doctype html><html><body>Sign in to download</body></html>',
            encoding='utf-8',
        )
        _r = subprocess.run([sys.executable, str(REPO / 'docs/check_datasheets.py'), 
                             str(next(_bd.glob('*.kicad_pcb')))],
                            capture_output=True, text=True)
        check('datasheet gate REJECTS an HTML login wall named .pdf',
              _r.returncode != 0 and 'archive.html_payload' in _r.stdout,
              (_r.stdout or _r.stderr).strip()[:150])
    finally:
        if _bak.is_file():
            _sh.copy2(_bak, _ds)
            _bak.unlink()

    # And provenance: a document on disk with no source_url has no recorded
    # origin, so it cannot be re-fetched or revision-checked.
    _idx = _bd / 'evidence' / 'index.yaml'
    _original_index = _idx.read_bytes()
    _orig = _original_index.decode('utf-8')
    try:
        _idx.write_text(
            re.sub(r'(?m)^(  source_url:) .+$', r'\1 null', _orig, count=1),
            encoding='utf-8',
        )
        _r = subprocess.run([sys.executable, str(REPO / 'docs/check_research.py'),
                             str(next(_bd.glob('*.kicad_pcb')))],
                            capture_output=True, text=True)
        check('archive integrity FLAGS a document with no source URL',
              'archived evidence has no source URL' in _r.stdout,
              (_r.stdout or _r.stderr).strip()[-150:])
    finally:
        _idx.write_bytes(_original_index)

# --- The gates FAIL when they should ------------------------------------
# Everything above this line asks "is the machinery wired?". 68 checks said
# yes while six gates could not actually fail:
#
#   * a `<ref>.<pin> | 2.2 | reason` waiver — one numbered rule, one pin —
#     also excused that part from needing an archived reference design and a
#     design-basis row, because the scope field was parsed and then thrown
#     away. baro-bmp390 passed "every key part has an archived reference"
#     with its reference directory emptied.
#   * DEVIATIONS.md files with no "## Declared" heading fell back to
#     whole-file parsing — the mode behind four earlier false-waiver bugs.
#     Two of five projects were in that state and nothing said so.
#   * REQUIREMENTS.md sections passed as "filled" when emptied outright.
#   * SIGNOFF.md counted ticks, so one sed turned NOT READY into all-pass.
#   * gate_drc read a stale drc-report.json when kicad-cli failed, returning
#     0 errors for a file that was not a board.
#   * the ERC waiver covered the whole pin_to_pin class, including a genuine
#     Output-to-Output short, which is an error rather than a warning.
#
# Wiring is not strength. These inject the fault and require the failure, in
# a throwaway copy so no real board is ever touched.
import tempfile as _tf

_src = REPO / 'projects' / 'baro-bmp390'
_pcb_src = next(iter(_src.glob('*.kicad_pcb')), None)


def _sandbox(src: Path = None):
    """A throwaway copy of a real board.

    The copy KEEPS the project's own directory name. It used to be called
    `board/`, which left the directory disagreeing with the `<name>.kicad_pcb`
    files inside it — harmless for checks that only touch file paths, and an
    immediate crash for any check that builds a `pipeline.Board` from the
    directory, since that class derives every filename from the folder name.
    """
    src = src or _src
    d = Path(_tf.mkdtemp(prefix='selftest-'))
    b = d / src.name
    _sh.copytree(src, b, ignore=_sh.ignore_patterns('.history', '.backups'))
    return b, next(b.glob('*.kicad_pcb'))


def _research(pcb):
    return subprocess.run([sys.executable, str(REPO / 'docs/check_research.py'), str(pcb)],
                          capture_output=True, text=True).stdout


if _pcb_src:
    # 1. a rule waiver must not excuse the reference-design gate
    _b, _p = _sandbox()
    _i = _b / 'evidence' / 'index.yaml'
    _i.write_text(
        _i.read_text(encoding='utf-8').replace(
            '  - reference_design', '  - application_note'
        ),
        encoding='utf-8',
    )
    _o = _research(_p)
    check('a rule-2.2 pin waiver does NOT excuse the reference-design gate',
          '[FAIL] Step 2.2  reference designs' in _o,
          'waiver scope is being ignored again')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 2. ...nor the design-basis gate
    _b, _p = _sandbox()
    _d = _b / 'DESIGN_BASIS.md'
    _d.write_text(
        re.sub(r'^\|.*$', '', _d.read_text(encoding='utf-8'), flags=re.M),
        encoding='utf-8',
    )
    check('a rule-2.2 pin waiver does NOT excuse the design-basis gate',
          '[FAIL] Step 2.3  design basis' in _research(_p),
          'waiver scope is being ignored again')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 3. a DEVIATIONS.md with no "## Declared" heading waives nothing, loudly
    _b, _p = _sandbox()
    _v = _b / 'DEVIATIONS.md'
    _v.write_text(
        _v.read_text(encoding='utf-8').replace('## Declared', '## Notes'),
        encoding='utf-8',
    )
    check('DEVIATIONS.md without "## Declared" is reported, not silently ignored',
          '[FAIL] Escape hatch' in _research(_p),
          'containment regressed to whole-file parsing')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 4. an emptied requirements section is not a captured requirement
    _b, _p = _sandbox()
    _r_ = _b / 'REQUIREMENTS.md'
    _r_.write_text(re.sub(r'## Electrical.*?(?=\n## )', '## Electrical\n\n',
                          _r_.read_text(encoding='utf-8'), flags=re.S),
                   encoding='utf-8')
    check('an emptied REQUIREMENTS section fails Phase 1',
          '[FAIL] Phase 1' in _research(_p),
          'heading presence is being counted as content')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 5. ticking every box without a date is not a sign-off
    _b, _p = _sandbox()
    _s = _b / 'SIGNOFF.md'
    _s.write_text(
        re.sub(r'^- \[ \]', '- [x]', _s.read_text(encoding='utf-8'), flags=re.M),
        encoding='utf-8',
    )
    sys.path.insert(0, str(REPO / 'docs'))
    import run_gates as _rg
    _ok, _det = _rg.gate_signoff(_p)
    check('bulk-ticked SIGNOFF.md without dates does NOT pass',
          not _ok and 'WITHOUT a signature' in _det, _det[:120])
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 6. DRC must not read a stale report when kicad-cli fails
    _d2 = Path(_tf.mkdtemp(prefix='selftest-drc-'))
    # Build the tempting stale result in the sandbox.  Ignored reports are
    # deliberately absent from a clean checkout, so copying a live project's
    # report made this meta-test depend on untracked developer state.
    (_d2 / 'drc-report.json').write_text(
        json.dumps({'violations': [], 'unconnected_items': []}),
        encoding='utf-8',
    )
    (_d2 / 'fake.kicad_pcb').write_text('(not a board)', encoding='utf-8')
    _ok, _det = _rg.gate_drc(_d2 / 'fake.kicad_pcb')
    check('gate_drc FAILS on an unloadable board instead of reading a stale report',
          not _ok, _det[:120])
    _sh.rmtree(_d2, ignore_errors=True)

    # 7. the ERC waiver must not cover a real driver conflict
    check('ERC waiver excludes errors and non-Unspecified conflicts',
          not _rg._erc_waivable({'type': 'pin_to_pin', 'severity': 'error',
                                 'description': 'Pins of type Output and Output are connected'})
          and _rg._erc_waivable({'type': 'pin_to_pin', 'severity': 'warning',
                                 'description': 'Pins of type Unspecified and Passive are connected'}),
          'ERC waiver is back to waiving the whole pin_to_pin class')

    # 8. a FRESH scaffold must not satisfy the gates it scaffolds.
    # This class of defect has now appeared four times: DEVIATIONS' example
    # waiver, DESIGN_BASIS' `<U1>` row, a stale copy of the template project
    # carrying a pre-fix example, and the worked `- [x]` line added to
    # SIGNOFF's own instructions. A scaffold that passes is a check that
    # certifies the thing it was written to catch.
    _fresh = Path(_tf.mkdtemp(prefix='selftest-fresh-')) / 'newboard'
    _fresh.mkdir(parents=True)
    subprocess.run([sys.executable, str(REPO / 'docs/run_gates.py'), '--init', str(_fresh)],
                   capture_output=True, text=True)
    _sh.copy2(_pcb_src, _fresh / 'newboard.kicad_pcb')
    check('a fresh scaffold uses only the unified evidence archive',
          (_fresh / 'evidence' / 'index.yaml').is_file()
          and not (_fresh / 'datasheets').exists()
          and not (_fresh / 'reference-designs').exists(),
          'run_gates --init still creates a retired evidence layout')
    _fo = _research(_fresh / 'newboard.kicad_pcb')
    check('a freshly scaffolded project FAILS its own research gates',
          '[FAIL] Phase 1' in _fo and '[FAIL] Step 2.3' in _fo,
          'the scaffold satisfies the check it scaffolds')
    import deviations as _dv
    check('a freshly scaffolded DEVIATIONS.md waives nothing',
          not _dv.parse(_fresh)[0], 'the template waives by existing')
    _ok, _det = _rg.gate_signoff(_fresh / 'newboard.kicad_pcb')
    check('a freshly scaffolded SIGNOFF.md is not self-signed',
          not _ok and '0 signed' in _det, _det[:120])
    _sh.rmtree(_fresh.parent, ignore_errors=True)

# --- The workflow audit exists, runs, and AGREES with the gates -----------
# It is the third tool in this family (selftest = "is it wired?",
# run_gates = "is this board ready?", audit_workflow = "was every documented
# step actually carried out?"). It re-implemented two checks on its first
# pass and disagreed with run_gates on both — ERC (counted waived violations)
# and placement (treated WARN as failure). An audit that contradicts the gate
# is worse than no audit, so this asserts they agree.
_aw = REPO / 'docs/audit_workflow.py'
check('audit_workflow.py exists', _aw.is_file())
check('pipeline --status points at the workflow audit',
      'audit_workflow' in text(REPO / 'docs/pipeline.py'))
if _aw.is_file():
    _b = REPO / 'projects' / 'baro-bmp390'
    _p = next(iter(_b.glob('*.kicad_pcb')), None)
    if _p:
        _r = subprocess.run([sys.executable, str(_aw), 'baro-bmp390'],
                            capture_output=True, text=True)
        _g = subprocess.run([sys.executable, str(REPO / 'docs/run_gates.py'), str(_p)],
                            capture_output=True, text=True)
        # both must agree that ERC and DRC are clean on this board
        check('workflow audit agrees with run_gates on ERC',
              ('[DONE] Phase 3' in _r.stdout) == ('[PASS] Phase 3' in _g.stdout),
              'audit and gate disagree about ERC')
        check('workflow audit agrees with run_gates on placement',
              ('[DONE] Phase 4A  placement' in _r.stdout)
              == ('[PASS] Phase 4A  placement' in _g.stdout),
              'audit and gate disagree about placement')
        # DRC and sign-off drifted back into their own implementations here:
        # the audit re-read drc-report.json (no refill, no second run) and
        # reported 1 error where the gate reported 2, and it counted
        # unticked boxes so a bulk-ticked SIGNOFF.md read as DONE. Both rows
        # now call the gate; these assert they keep doing so.
        check('workflow audit agrees with run_gates on DRC',
              ('[DONE] Phase 4C' in _r.stdout) == ('[PASS] Phase 4C' in _g.stdout),
              'audit and gate disagree about DRC')
        check('workflow audit agrees with run_gates on sign-off',
              ('[DONE] Phase 5' in _r.stdout) == ('[PASS] Phase 5' in _g.stdout),
              'audit and gate disagree about sign-off')

# --- The two newest gates FAIL when they should ---------------------------
#
# Registered is not the same as working. Every check below breaks a real
# board in one specific way and requires the gate to notice; without this a
# gate only asserts its own existence, which is how this file stood at 68/68
# green while six gates could not fail at all.

def _parity(pcb):
    return subprocess.run([str(KIPYTHON), str(REPO / 'docs/check_netlist_parity.py'),
                           str(pcb)], capture_output=True, text=True)


def _schqual(pcb):
    return subprocess.run([sys.executable, str(REPO / 'docs/check_schematic_quality.py'),
                           str(pcb)], capture_output=True, text=True)


if _pcb_src and KIPYTHON.exists():
    # 11. a pad silently stripped of its net must break parity. This is the
    # exact shape of the defect that shipped: gnss TP1/TP2 and imu TP1/TP2/TP3
    # were wired in the schematic and netless on the board, and every other
    # gate passed them.
    _b, _p = _sandbox()
    _t = _p.read_text(encoding='utf-8')
    _m = re.search(r'\n(\s*)\(net "([^"]+)"\)', _t)
    if _m:
        _p.write_text(_t[:_m.start()] + _t[_m.end():], encoding='utf-8')
        _r = _parity(_p)
        check('netlist parity FAILS when a pad loses its net',
              _r.returncode != 0 and 'NOT on the board' in _r.stdout,
              'a netless pad passed parity — the dead-test-point defect is back')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 12. a net renamed on the board only must break parity.
    _b, _p = _sandbox()
    _t = _p.read_text(encoding='utf-8')
    if '(net "GND")' in _t:
        _p.write_text(
            _t.replace('(net "GND")', '(net "GNDX")', 1),
            encoding='utf-8',
        )
        _r = _parity(_p)
        check('netlist parity FAILS when a board net is renamed',
              _r.returncode != 0, 'a renamed net passed parity')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 13. parity must not pass by finding nothing. A gate that reports "0
    # nets, 0 nets, agreed" is the silent-pass failure mode.
    _b, _p = _sandbox()
    _r = _parity(_p)
    _mm = re.search(r'schematic: (\d+) net', _r.stdout)
    check('netlist parity actually reads nets (not a vacuous pass)',
          bool(_mm) and int(_mm.group(1)) > 0,
          'parity reported zero nets — it would agree with anything')
    _sh.rmtree(_b.parent, ignore_errors=True)

if _pcb_src:
    # 14. stripping the title block must fail the readability gate.
    _b, _p = _sandbox()
    _s = _p.with_suffix('.kicad_sch')
    if _s.is_file():
        _txt = _s.read_text(encoding='utf-8')
        _tb = re.search(r'\n\t\(title_block\b.*?\n\t\)', _txt, re.S)
        if _tb:
            _s.write_text(_txt[:_tb.start()] + _txt[_tb.end():], encoding='utf-8')
            _r = _schqual(_p)
            check('schematic quality FAILS with no title block',
                  _r.returncode != 0 and 'title block' in _r.stdout,
                  'a sheet with blank Title/Rev passed')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 15. the documented "~25 components per A4, then split into hierarchical
    # sheets" rule must actually fire. Shrink the page under a real board
    # rather than inventing components, so the count stays genuine — but pick
    # a board that HAS more components than the smallest page holds. The
    # first version of this check used baro-bmp390 (10 components) against
    # A5 (capacity 12) and could not fail: an injection that cannot trigger
    # tests nothing, which is the exact failure this section exists to catch.
    _dense = None
    for _cand in sorted((REPO / 'projects').glob('*/[a-z]*.kicad_sch')):
        _n = len([i for i in re.findall(r'\(lib_id "([^"]+)"\)', _cand.read_text(encoding='utf-8'))
                  if not i.startswith('power:')])
        if _n > 12:
            _dense = _cand.parent
            break
    if _dense:
        _b2, _p2 = _sandbox(_dense)
        _s2 = _p2.with_suffix('.kicad_sch')
        _s2.write_text(re.sub(r'\(paper "[^"]+"\)', '(paper "A5")',
                              _s2.read_text(encoding='utf-8'), count=1),
                       encoding='utf-8')
        _r = _schqual(_p2)
        check('schematic quality FAILS on an over-full sheet with no hierarchy',
              _r.returncode != 0 and 'hierarchical sheets' in _r.stdout,
              'the documented page-density rule still does not fire')
        _sh.rmtree(_b2.parent, ignore_errors=True)
    else:
        check('schematic quality FAILS on an over-full sheet with no hierarchy',
              False, 'no board with >12 components to test against')

    # 16. the component count must exclude power symbols. Counting all
    # symbols fails baro-bmp390 at 31-on-A4 for a sheet that is 60% empty,
    # and a gate that fires on a sheet you can see is not crowded gets
    # switched off.
    _b, _p = _sandbox()
    _r = _schqual(_p)
    _cm = re.search(r'(\d+) components \+ (\d+) power symbols', _r.stdout)
    check('schematic quality separates components from power symbols',
          bool(_cm) and int(_cm.group(2)) > 0,
          'power symbols are being counted as components')
    _sh.rmtree(_b.parent, ignore_errors=True)

# 17. both gates must be REGISTERED, not merely present on disk.
_rg = (REPO / 'docs/run_gates.py').read_text(encoding='utf-8')
check('netlist-parity gate is REGISTERED in run_gates.GATES',
      'gate_netlist_parity' in _rg.split('GATES = [')[1])
check('schematic-quality gate is REGISTERED in run_gates.GATES',
      'gate_schematic_quality' in _rg.split('GATES = [')[1])
_aw = (REPO / 'docs/audit_workflow.py').read_text(encoding='utf-8')
check('audit CALLS the parity gate rather than re-implementing it',
      'run_gates.gate_netlist_parity' in _aw)
check('audit CALLS the schematic-quality gate rather than re-implementing it',
      'run_gates.gate_schematic_quality' in _aw)

# --- Ownership guard: the seven-hours test --------------------------------
#
# `gen_*_sch.py` ends in an unconditional write and `stage_sch` runs on every
# pipeline invocation, so before the SCHEMATIC_OWNER marker one routine build
# silently destroyed any hand-drawing done in Eeschema. These require that it
# cannot. Check 18 is the one that matters: it is the whole reason the marker
# exists, and it is tested BEFORE anyone spends an evening in the editor.
sys.path.insert(0, str(REPO / 'docs'))
import pipeline as _pl  # noqa: E402
import run_gates as _rgm  # noqa: E402

if _pcb_src:
    # 18. a human-owned schematic must never reach the generator at all.
    #
    # Asserted by recording whether `_run_generator` is called, NOT by
    # comparing the sandbox schematic before and after. The first version did
    # compare bytes and was VACUOUS: every `gen_*_sch.py` hardcodes
    # `PROJECT_DIR = Path('/Users/.../projects/<board>')`, so a generator run
    # from a sandbox writes to the REAL board and leaves the copy untouched.
    # The check passed for the wrong reason — and, worse, running it modified
    # a live board. Removing the guard entirely did not make it fail, which is
    # the definition of a check that asserts nothing.
    _b, _p = _sandbox()
    _bd = _pl.Board(_b)
    (_b / _pl.OWNER_FILE).write_text('human\n', encoding='utf-8')
    _called = []
    _real_rg = _pl._run_generator
    _pl._run_generator = lambda *a, **k: (_called.append(a[0]),
                                          _pl.StageResult('sch', True, 'stub', 0.0))[1]
    try:
        _before = _bd.sch.read_bytes()
        _res = _pl.stage_sch(_bd)
    finally:
        _pl._run_generator = _real_rg
    check('a human-owned schematic never reaches the generator',
          _res.ok and not _called and _bd.sch.read_bytes() == _before,
          'the generator ran against a hand-drawn schematic — hours of work lost silently')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 19. a generated board whose schematic no longer matches the recorded run
    # must STOP the build rather than quietly overwrite it. This is the branch
    # that protects work nobody remembered to declare.
    _b, _p = _sandbox()
    _bd = _pl.Board(_b)
    (_b / _pl.OWNER_FILE).write_text('generated\n', encoding='utf-8')
    _before = _bd.sch.read_bytes()
    _bd.sch.write_bytes(_before.replace(b'(rev "', b'(rev "Z', 1))
    _edited = _bd.sch.read_bytes()
    _real_rg = _pl._run_generator
    _pl._run_generator = lambda *a, **k: _pl.StageResult('sch', True, 'stub', 0.0)
    try:
        _res = _pl.stage_sch(_bd)
    finally:
        _pl._run_generator = _real_rg
    check('an edited `generated` schematic STOPS the build',
          not _res.ok and _bd.sch.read_bytes() == _edited,
          'an out-of-sync schematic was silently regenerated')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 20. --regenerate must refuse on a human-owned board. A flag that quietly
    # no-ops is how someone concludes the guard is broken and reaches for
    # something blunter.
    _b, _p = _sandbox()
    _bd = _pl.Board(_b)
    (_b / _pl.OWNER_FILE).write_text('human\n', encoding='utf-8')
    _before = _bd.sch.read_bytes()
    _res = _pl.stage_sch(_bd, regenerate=True)
    check('--regenerate REFUSES on a human-owned board',
          not _res.ok and _bd.sch.read_bytes() == _before,
          '--regenerate rebuilt over a hand-drawn schematic')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 21. an unreadable marker must fail rather than default to something.
    _b, _p = _sandbox()
    _bd = _pl.Board(_b)
    (_b / _pl.OWNER_FILE).write_text('mostly generated\n', encoding='utf-8')
    _res = _pl.stage_sch(_bd)
    check('an invalid SCHEMATIC_OWNER marker fails the build',
          not _res.ok, 'a malformed ownership marker was silently accepted')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 22. editing the schematic's CONNECTIVITY after netmap.json was written
    # must fail the provenance gate — that is the state in which the board is
    # built from a netlist describing a drawing that no longer exists.
    # Injected as a net rename, not a title-block edit: the gate compares
    # netlists, so cosmetic edits are correctly invisible to it.
    _b, _p = _sandbox()
    _bd = _pl.Board(_b)
    (_b / _pl.OWNER_FILE).write_text('generated\n', encoding='utf-8')
    _st = _bd.sch.read_text(encoding='utf-8')
    _lbl = re.search(r'\(label "([A-Za-z0-9_]+)"', _st)
    if _lbl:
        _bd.sch.write_text(
            _st.replace(f'"{_lbl.group(1)}"', f'"{_lbl.group(1)}_X"'),
            encoding='utf-8',
        )
        _ok, _d = _rgm.gate_schematic_ownership(_p)
        check('provenance gate FAILS when the schematic is edited past its netmap',
              not _ok, 'a board built from a stale netlist passed the provenance gate')
    else:
        check('provenance gate FAILS when the schematic is edited past its netmap',
              False, 'no label found to rename in the test board')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 23. a stale netmap.json on a human-owned board must fail. netmap.json is
    # the one schematic->PCB contract; stale means the board was built from a
    # netlist describing a drawing that no longer exists.
    _b, _p = _sandbox()
    _bd = _pl.Board(_b)
    (_b / _pl.OWNER_FILE).write_text('human\n', encoding='utf-8')
    _nm = _b / 'netmap.json'
    _nmd = json.loads(_nm.read_text(encoding='utf-8'))
    _nmd['nets'] = {r: v for r, v in _nmd['nets'].items() if not r.startswith('#')}
    _nmd['nets'].pop(next(iter(_nmd['nets'])), None)
    _nm.write_text(json.dumps(_nmd, indent=2), encoding='utf-8')
    _ok, _d = _rgm.gate_schematic_ownership(_p)
    check('provenance gate FAILS on a netmap missing a reference',
          not _ok, 'a stale schematic->PCB contract passed the provenance gate')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 24. the canonical hash must be blind to UUID churn.
    #
    # `sha()` masks UUIDs so a board that regenerates identically hashes
    # identically. The first mask was anchored to surrounding quotes —
    # `"<uuid>"` — and KiCad writes instance paths as `(path "/<root-uuid>")`,
    # with a slash inside the quotes. 31 of baro-bmp390's 148 UUIDs escaped,
    # all of them the root sheet UUID, minted fresh on every regeneration. So
    # the "canonical" hash moved on every build of an unchanged board:
    # `--status` called fresh reports stale, `--verify-repeatable` could never
    # pass, and the schematic drift tripwire would have fired on every run.
    _b, _p = _sandbox()
    _bd = _pl.Board(_b)
    _h0 = _pl.sha(_bd.sch)
    _seen = {}
    _bd.sch.write_text(re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        lambda m: _seen.setdefault(m.group(0), '%08x-0000-4000-8000-%012x'
                                   % (len(_seen) + 1, len(_seen) + 1)),
        _bd.sch.read_text(encoding='utf-8')), encoding='utf-8')
    check('the canonical hash ignores UUID churn',
          _pl.sha(_bd.sch) == _h0,
          'a re-UUIDed but otherwise identical schematic hashed differently — '
          'every provenance check built on this hash is non-deterministic')
    _sh.rmtree(_b.parent, ignore_errors=True)


# 25. no generator may hardcode an absolute path.
#
# `PROJECT_DIR = Path('/Users/.../projects/<board>')` means a copy of the
# script run from anywhere writes to the ORIGINAL board. The enforcement
# self-test hit exactly that: it ran a generator inside a throwaway sandbox,
# silently modified the live project, and the check meant to prove the
# ownership guard worked passed because the sandbox copy was untouched — for
# the wrong reason. A sandbox that is not actually a sandbox makes every
# fault-injection test built on it meaningless.
_abs = [str(f.relative_to(REPO)) for f in sorted((REPO / 'projects').glob('*/gen_*.py'))
        if "'/Users/" in f.read_text(encoding='utf-8')]
check('no board generator hardcodes an absolute path',
      not _abs,
      'these write outside any sandbox: ' + ', '.join(_abs[:4]))


# 26. registration, both places.
check('provenance gate is REGISTERED in run_gates.GATES',
      'gate_schematic_ownership' in _rg.split('GATES = [')[1])
check('audit CALLS the provenance gate rather than re-implementing it',
      'run_gates.gate_schematic_ownership' in _aw)


# --- Report ---------------------------------------------------------------
fails = [r for r in results if not r[0]]
print('=== enforcement self-test ===')
for ok, name, detail in results:
    if not ok:
        print(f'  [FAIL] {name}' + (f'\n         {detail}' if detail else ''))
print(f'\n  {len(results) - len(fails)}/{len(results)} checks pass')
if fails:
    print('\nRESULT: ENFORCEMENT IS BROKEN — the gates may look present and never fire.')
else:
    print('\nRESULT: enforcement wired and firing')
sys.exit(1 if fails else 0)
