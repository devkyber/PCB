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
results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = '') -> None:
    results.append((ok, name, detail))


def text(p: Path) -> str:
    return p.read_text() if p.is_file() else ''


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
    r = subprocess.run(['bash', str(REPO / '.claude/hooks/validate-pcb-on-edit.sh')],
                       input=json.dumps({'tool_name': 'Bash',
                                         'tool_input': {'command': 'python3 gen_x_pcb.py'}}),
                       capture_output=True, text=True)
    check('PostToolUse hook actually fires on a synthetic Bash event',
          'validate_pcb.py result' in r.stdout, r.stdout[:80].replace('\n', ' '))
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
check('CLAUDE.md names the reference-design archive rule',
      'collect_references' in text(REPO / 'CLAUDE.md'))
check('.claude/rules/pcb-schematic.md names the archiver',
      'collect_references' in text(REPO / '.claude/rules/pcb-schematic.md'))

r = subprocess.run([sys.executable, REPO / 'docs/collect_references.py',
                    'suggest', 'SELFTEST'], capture_output=True, text=True)
check('collect_references suggest runs', r.returncode == 0 and 'Tier 1' in r.stdout)

# The archiver must REFUSE an HTML error page saved as a document. This is
# the silent failure that makes an archive worthless: the gate sees a file.
_probe = REPO / 'docs' / '.selftest_probe.pdf'
_probe.write_text('<!doctype html><html><body>Sign in</body></html>')
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
    for art in ['SIGNOFF.md', 'DEVIATIONS.md', 'build.sh', 'datasheets/INDEX.md',
                'REQUIREMENTS.md', 'DESIGN_BASIS.md', 'reference-designs/INDEX.md']:
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
_ds = _bd / 'datasheets' / 'BMP390-datasheet.pdf'
if _ds.is_file():
    _bak = REPO / '.selftest-datasheet.bak'
    try:
        _sh.copy2(_ds, _bak)
        _ds.write_text('<!doctype html><html><body>Sign in to download</body></html>')
        _r = subprocess.run([sys.executable, str(REPO / 'docs/check_datasheets.py'), 
                             str(next(_bd.glob('*.kicad_pcb')))],
                            capture_output=True, text=True)
        check('datasheet gate REJECTS an HTML login wall named .pdf',
              _r.returncode != 0 and 'NOT A DATASHEET' in _r.stdout,
              (_r.stdout or _r.stderr).strip()[:150])
    finally:
        if _bak.is_file():
            _sh.copy2(_bak, _ds)
            _bak.unlink()

    # And provenance: a document on disk with no INDEX.md row has no
    # recorded origin, so it cannot be re-fetched or revision-checked.
    # Integrity walked INDEX rows only, which made an unlisted file invisible.
    _idx = _bd / 'datasheets' / 'INDEX.md'
    _orig = _idx.read_text()
    try:
        _idx.write_text(_orig.replace('U1, BMP390, C5124834  ->', '# removed for selftest:'))
        _r = subprocess.run([sys.executable, str(REPO / 'docs/check_research.py'),
                             str(next(_bd.glob('*.kicad_pcb')))],
                            capture_output=True, text=True)
        check('archive integrity FLAGS a document with no source URL',
              'not in datasheets/INDEX.md' in _r.stdout,
              (_r.stdout or _r.stderr).strip()[-150:])
    finally:
        _idx.write_text(_orig)

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


def _sandbox():
    d = Path(_tf.mkdtemp(prefix='selftest-'))
    b = d / 'board'
    _sh.copytree(_src, b, ignore=_sh.ignore_patterns('.history', '.backups'))
    return b, next(b.glob('*.kicad_pcb'))


def _research(pcb):
    return subprocess.run([sys.executable, str(REPO / 'docs/check_research.py'), str(pcb)],
                          capture_output=True, text=True).stdout


if _pcb_src:
    # 1. a rule waiver must not excuse the reference-design gate
    _b, _p = _sandbox()
    for _f in (_b / 'reference-designs').glob('*'):
        if _f.name != 'INDEX.md':
            _f.unlink()
    _i = _b / 'reference-designs' / 'INDEX.md'
    _i.write_text(re.sub(r'^.*->.*$', '', _i.read_text(), flags=re.M))
    _o = _research(_p)
    check('a rule-2.2 pin waiver does NOT excuse the reference-design gate',
          '[FAIL] Step 2.2  reference designs' in _o,
          'waiver scope is being ignored again')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 2. ...nor the design-basis gate
    _b, _p = _sandbox()
    _d = _b / 'DESIGN_BASIS.md'
    _d.write_text(re.sub(r'^\|.*$', '', _d.read_text(), flags=re.M))
    check('a rule-2.2 pin waiver does NOT excuse the design-basis gate',
          '[FAIL] Step 2.3  design basis' in _research(_p),
          'waiver scope is being ignored again')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 3. a DEVIATIONS.md with no "## Declared" heading waives nothing, loudly
    _b, _p = _sandbox()
    _v = _b / 'DEVIATIONS.md'
    _v.write_text(_v.read_text().replace('## Declared', '## Notes'))
    check('DEVIATIONS.md without "## Declared" is reported, not silently ignored',
          '[FAIL] Escape hatch' in _research(_p),
          'containment regressed to whole-file parsing')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 4. an emptied requirements section is not a captured requirement
    _b, _p = _sandbox()
    _r_ = _b / 'REQUIREMENTS.md'
    _r_.write_text(re.sub(r'## Electrical.*?(?=\n## )', '## Electrical\n\n',
                          _r_.read_text(), flags=re.S))
    check('an emptied REQUIREMENTS section fails Phase 1',
          '[FAIL] Phase 1' in _research(_p),
          'heading presence is being counted as content')
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 5. ticking every box without a date is not a sign-off
    _b, _p = _sandbox()
    _s = _b / 'SIGNOFF.md'
    _s.write_text(re.sub(r'^- \[ \]', '- [x]', _s.read_text(), flags=re.M))
    sys.path.insert(0, str(REPO / 'docs'))
    import run_gates as _rg
    _ok, _det = _rg.gate_signoff(_p)
    check('bulk-ticked SIGNOFF.md without dates does NOT pass',
          not _ok and 'WITHOUT a signature' in _det, _det[:120])
    _sh.rmtree(_b.parent, ignore_errors=True)

    # 6. DRC must not read a stale report when kicad-cli fails
    _d2 = Path(_tf.mkdtemp(prefix='selftest-drc-'))
    _sh.copy2(_src / 'drc-report.json', _d2 / 'drc-report.json')
    (_d2 / 'fake.kicad_pcb').write_text('(not a board)')
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
