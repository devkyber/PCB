"""Prove a reviewed native schematic change on a disposable external snapshot.

First run: ``uv run python tools/demo_change.py --output NEW_EXTERNAL_DIRECTORY``.
Inspect every page of the printed PDF, then use the printed resume command with
its exact SHA-256 and your author-review identity. This is not owner sign-off.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from kicad_claude.adapters import sch_io

from pcb_copilot.layout.render import schematic_inventory
from pcb_copilot.project import load_project
from pcb_copilot.schematic.preview import schematic_files
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import contained, input_hashes

if __package__:
    from . import demo
else:
    import demo


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revise_drawing(path: Path, revision: str) -> dict:
    """Replace one revision string, preserving every other byte and parsed node."""
    original = path.read_bytes()
    expected = copy.deepcopy(sch_io.parse_file(path))
    blocks = sch_io.find_children(expected, 'title_block')
    revisions = sch_io.find_children(blocks[0], 'rev') if len(blocks) == 1 else []
    if len(revisions) != 1 or len(revisions[0]) != 2 or not isinstance(revisions[0][1], str):
        raise ValueError('demo requires exactly one existing title-block revision string')
    old = revisions[0][1]
    new = revision
    matches = list(re.finditer(rb'\(rev\s+("(?:\\.|[^"\\])*")\s*\)', original))
    if len(matches) != 1:
        raise ValueError('demo cannot identify one unambiguous revision string')
    start, end = matches[0].span(1)
    revised = original[:start] + sch_io.dumps(new).encode('utf-8') + original[end:]
    revisions[0][1] = new
    path.write_bytes(revised)
    if sch_io.parse_file(path) != expected:
        path.write_bytes(original)
        raise ValueError('revision edit changed another parsed schematic field')
    return {'file': path.name, 'before': old, 'after': new,
            'scope': 'Only the existing title-block revision string; all other bytes preserved.'}


def native_inventory(repository: Path, schematic: Path) -> dict:
    parts, nets = schematic_inventory(discover_toolchain(repository), schematic)

    def serializable(value):
        if isinstance(value, dict):
            return {key: serializable(item) for key, item in sorted(value.items())}
        if isinstance(value, set):
            return [serializable(item) for item in sorted(value)]
        if isinstance(value, (list, tuple)):
            return [serializable(item) for item in value]
        return value

    return {'parts': serializable(parts), 'nets': serializable(nets)}


def candidate_hashes(root: Path) -> dict:
    return {path.relative_to(root.parent).as_posix(): sha256(path)
            for path in schematic_files(root)}


def command(output: Path, transcript: dict, name: str, *, apply: bool = False) -> dict:
    arguments = ['update-schematic', transcript['snapshot'], '--candidate', transcript['candidate']]
    if apply:
        arguments.append('--apply')
    print(f'Running {name}...', flush=True)
    step = demo.run_command(output, name, arguments, timeout=600)
    transcript['steps'].append(step)
    if step['error']:
        raise RuntimeError(step['error'])
    if name == 'apply-stale':
        if step['exit_code'] != 2 or demo.GUARD_MESSAGE not in demo.step_output(output, step, 'stderr'):
            raise RuntimeError('expected stale-preview rejection was not observed')
        return {}
    if step['exit_code'] != 0:
        raise RuntimeError(f'{name} failed; inspect its exact stdout and stderr')
    result = json.loads(demo.step_output(output, step, 'stdout'))
    if result.get('applied') is not apply or result.get('exit_code') != 0:
        raise RuntimeError(f'{name} did not report the expected checked result')
    if any(item.get('code') == 'layout.schematic_links_added' for item in result['findings']):
        raise RuntimeError('demo requires an already linked PCB; no board metadata changes are in scope')
    return result


def preserve_source(transcript: dict) -> None:
    transcript['source_inputs_unchanged'] = False
    project = load_project(Path(transcript['source_root']))
    after = input_hashes(project)
    transcript['source_inputs_after'] = after
    transcript['source_inputs_unchanged'] = after == transcript['source_inputs_before']
    if not transcript['source_inputs_unchanged']:
        raise RuntimeError('source inputs changed; the demo will not restore or replace owner edits')


def assert_snapshot_unchanged(output: Path, transcript: dict) -> None:
    snapshot = load_project(contained(output, output / transcript['snapshot']))
    if input_hashes(snapshot) != transcript['snapshot_inputs_before']:
        raise RuntimeError('snapshot inputs changed before the reviewed apply')


def write_report(output: Path, transcript: dict) -> None:
    (output / 'transcript.json').write_text(json.dumps(transcript, indent=2) + '\n', encoding='utf-8')
    lines = ['# Scoped native-change proof', '', f"Status: **{transcript['status']}**", '',
             'All update commands target a disposable external snapshot. Exact logs are linked below.', '',
             '| Step | Actual exit code | Logs |', '| --- | ---: | --- |']
    lines.extend(f"| {step['name']} | {step['exit_code']} | [stdout]({step['stdout']}) · [stderr]({step['stderr']}) |"
                 for step in transcript['steps'])
    lines.extend(['', f"Source inputs unchanged: **{transcript.get('source_inputs_unchanged', False)}**.",
                  f"Applied to snapshot: **{transcript.get('applied', False)}**.",
                  ('The title-block revision is the only intended schematic change. Native parts, pins, '
                   'values, footprints, no-connects and net membership are compared before and after.'), '',
                  'Exact input/artifact hashes and results: [transcript.json](transcript.json).',
                  'Native electrical inventories: [before](electrical-before.json) · [candidate](electrical-candidate.json).', ''])
    if transcript.get('review_pdf'):
        lines.extend([f"Final rendered schematic: [PDF]({transcript['review_pdf']}).",
                      f"SHA-256: `{transcript['review_sha256']}`.",
                      'Sheets: ' + ', '.join(f'`{name}`' for name in transcript['reviewed_sheet_files']), ''])
    if transcript.get('author_visual_review'):
        lines.extend(['Operator-supplied author visual review: ' + json.dumps(transcript['author_visual_review']), ''])
    lines.extend([('No owner sign-off or fabrication release is created. Passing this demonstration '
                   'does not establish electrical, mechanical, thermal or manufacturing qualification.'), ''])
    if transcript.get('error'):
        lines.extend(['Error: ' + transcript['error'], ''])
    (output / 'report.md').write_text('\n'.join(lines), encoding='utf-8')


def prepare(repository: Path, source: Path, output: Path) -> dict:
    project = load_project(source)
    transcript = {'schema_version': 1, 'started_utc': datetime.now(UTC).isoformat(),
                  'source_root': str(project.root), 'status': 'failed', 'exit_code': 2,
                  'source_inputs_before': input_hashes(project), 'steps': [], 'applied': False}
    try:
        snapshot, before = demo.snapshot_project(project, output)
        transcript.update(snapshot=snapshot.root.relative_to(output).as_posix(), snapshot_inputs_before=before)
        candidate = output / 'candidate' / snapshot.schematic_path.name
        for path in schematic_files(snapshot.schematic_path):
            target = candidate.parent / path.relative_to(snapshot.schematic_path.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        transcript['candidate'] = candidate.relative_to(output).as_posix()
        before_electrical = native_inventory(repository, snapshot.schematic_path)
        (output / 'electrical-before.json').write_text(json.dumps(before_electrical, indent=2) + '\n', encoding='utf-8')
        transcript['initial_change'] = revise_drawing(candidate, 'DEMO-P1')
        first = command(output, transcript, 'preview-initial')
        review = output / 'review'
        review.mkdir()
        shutil.copy2(first['preview'], review / 'initial-schematic.pdf')
        final_revision = 'DEMO-P3' if transcript['initial_change']['before'] == 'DEMO-P2' else 'DEMO-P2'
        transcript['final_change'] = revise_drawing(candidate, final_revision)
        command(output, transcript, 'apply-stale', apply=True)
        assert_snapshot_unchanged(output, transcript)
        current = command(output, transcript, 'preview-current')
        after_electrical = native_inventory(repository, candidate)
        (output / 'electrical-candidate.json').write_text(json.dumps(after_electrical, indent=2) + '\n', encoding='utf-8')
        if before_electrical != after_electrical:
            raise RuntimeError('native component/pin/net inventory changed during the drawing-only edit')
        artifacts = {}
        for key, filename in (('preview', 'schematic.pdf'), ('erc_report', 'erc.json'), ('metrics', 'metrics.json')):
            target = review / filename
            shutil.copy2(current[key], target)
            artifacts[target.relative_to(output).as_posix()] = sha256(target)
        snapshot_report = snapshot.root / '.pcb-copilot' / 'preview' / 'schematic-review.json'
        artifacts[snapshot_report.relative_to(output).as_posix()] = sha256(snapshot_report)
        import pymupdf

        with pymupdf.open(review / 'schematic.pdf') as rendered:
            if rendered.page_count != len(schematic_files(candidate)):
                raise RuntimeError('rendered PDF page count does not match the candidate hierarchy')
        transcript.update(status='awaiting-author-visual-review', exit_code=0,
                          candidate_inputs=candidate_hashes(candidate), review_artifacts=artifacts,
                          review_pdf='review/schematic.pdf', review_sha256=sha256(review / 'schematic.pdf'),
                          reviewed_sheet_files=list(candidate_hashes(candidate)), electrical_unchanged=True)
        assert_snapshot_unchanged(output, transcript)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        transcript.update(error=str(exc), status='failed', exit_code=2)
    finally:
        try:
            preserve_source(transcript)
        except (OSError, ValueError, RuntimeError) as exc:
            transcript.update(error=str(exc), status='failed', exit_code=2)
        write_report(output, transcript)
    return transcript


def apply_reviewed(output: Path, *, reviewed_sha256: str, reviewer: str) -> dict:
    transcript = json.loads((output / 'transcript.json').read_text(encoding='utf-8'))
    if not isinstance(transcript, dict) or transcript.get('status') != 'awaiting-author-visual-review':
        raise ValueError('run is not awaiting its first author visual review')
    if not reviewer.strip() or reviewed_sha256 != transcript['review_sha256']:
        raise ValueError('supply a reviewer and the exact SHA-256 of the PDF whose every page you inspected')
    try:
        preserve_source(transcript)
        assert_snapshot_unchanged(output, transcript)
        candidate = contained(output, output / transcript['candidate'])
        if candidate_hashes(candidate) != transcript['candidate_inputs']:
            raise RuntimeError('candidate changed after the final preview; start a new proof run')
        for relative, expected in transcript['review_artifacts'].items():
            if sha256(contained(output, output / relative)) != expected:
                raise RuntimeError('preview or render changed after inspection; start a new proof run')
        transcript['author_visual_review'] = {
            'reviewer': reviewer, 'recorded_utc': datetime.now(UTC).isoformat(),
            'render_sha256': reviewed_sha256, 'sheets': transcript['reviewed_sheet_files'],
            'scope': 'Operator attests every rendered sheet was inspected; author review only, not owner sign-off.',
        }
        command(output, transcript, 'apply-reviewed', apply=True)
        transcript['applied'] = True
        snapshot = load_project(contained(output, output / transcript['snapshot']))
        after = input_hashes(snapshot)
        changed = {path for path in after if after[path] != transcript['snapshot_inputs_before'].get(path)}
        allowed = {snapshot.schematic_path.relative_to(snapshot.root).as_posix(),
                   snapshot.netmap_path.relative_to(snapshot.root).as_posix()}
        if (snapshot.schematic_path.relative_to(snapshot.root).as_posix() not in changed
                or not changed <= allowed or snapshot.schematic_path.read_bytes() != candidate.read_bytes()):
            raise RuntimeError('installed snapshot differs from the reviewed revision-only change')
        if (snapshot.root / 'fabrication').exists():
            raise RuntimeError('unexpected fabrication directory in demonstration snapshot')
        transcript.update(status='applied-to-disposable-snapshot', applied=True, exit_code=0,
                          snapshot_inputs_after=after, snapshot_changed_files=sorted(changed),
                          snapshot_board_unchanged=after[snapshot.pcb_path.relative_to(snapshot.root).as_posix()]
                          == transcript['snapshot_inputs_before'][snapshot.pcb_path.relative_to(snapshot.root).as_posix()])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        transcript.update(error=str(exc), status='failed', exit_code=2)
    finally:
        try:
            preserve_source(transcript)
        except (OSError, ValueError, RuntimeError) as exc:
            transcript.update(error=str(exc), status='failed', exit_code=2)
        write_report(output, transcript)
    return transcript


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--output', type=Path, help='new output directory outside the repository (default: temporary)')
    mode.add_argument('--resume', type=Path, help='external proof directory whose final PDF you inspected')
    parser.add_argument('--project', type=Path, default=Path('examples/gpio-indicator'))
    parser.add_argument('--apply', action='store_true', help='apply only to an existing reviewed disposable snapshot')
    parser.add_argument('--reviewed-render-sha256', help='exact PDF hash; attests inspection of every rendered sheet')
    parser.add_argument('--reviewer', help='author-review identity; this never grants owner sign-off')
    args = parser.parse_args(argv)
    if bool(args.resume) != args.apply or (args.apply and (not args.reviewed_render_sha256 or not args.reviewer)):
        parser.error('--apply requires --resume, --reviewed-render-sha256 and --reviewer together')
    if not args.apply and (args.reviewed_render_sha256 or args.reviewer):
        parser.error('author review flags are only accepted with --resume --apply')
    repository = Path(__file__).resolve().parents[1]
    try:
        if args.resume:
            output = args.resume.expanduser().resolve()
            if output == repository or output.is_relative_to(repository):
                raise ValueError('resumed proof directory must be outside the repository')
            result = apply_reviewed(output, reviewed_sha256=args.reviewed_render_sha256, reviewer=args.reviewer)
        else:
            source = (repository / args.project).resolve()
            load_project(source)
            if args.output and args.output.expanduser().resolve().is_relative_to(source):
                raise ValueError('proof output must also be outside the source project')
            if args.output is None and Path(tempfile.gettempdir()).resolve().is_relative_to(source):
                raise ValueError('temporary output would be inside the source project; select an external --output')
            output = demo.new_output_directory(args.output, repository)
            result = prepare(repository, source, output)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Change proof could not start: {exc}', file=sys.stderr)
        return 2
    print(f'Report: {output / "report.md"}')
    if result['status'] == 'awaiting-author-visual-review':
        print(f'Inspect every sheet in: {output / result["review_pdf"]}')
        print(f'Render SHA-256: {result["review_sha256"]}')
        print('After inspection, resume with --resume "' + str(output) + '" --apply '
              '--reviewed-render-sha256 ' + result['review_sha256'] + ' --reviewer "YOUR AUTHOR REVIEW IDENTITY"')
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
