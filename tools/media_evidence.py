"""Validate recorded CLI evidence before it becomes a public media claim.

This checks internal consistency and raw log identities, not log authenticity
against a hostile author. It requires no image or native-tool dependencies.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

GUARD = 'No successful matching unconsumed preview'


def repository_binding(repository: Path, source: Path, expected: dict) -> dict:
    """Add exact HEAD blob identities only after proving checkout equivalence.

    The original capture hashes remain untouched. If sources are uncommitted,
    Git is unavailable, or any difference exceeds CRLF/LF, omit this optional
    portable binding and let the checker require the original captured bytes.
    """
    base = source.relative_to(repository).as_posix()
    blobs = {}
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository,
                                           stderr=subprocess.DEVNULL, timeout=15).decode().strip()
        for name, digest in expected.items():
            result = subprocess.run(['git', 'show', f'{revision}:{base}/{name}'], cwd=repository,
                                    capture_output=True, timeout=15, check=False)
            if digest is None:
                if result.returncode == 0:
                    return {}
                blobs[name] = None
                continue
            payload = (source / name).read_bytes()
            if hashlib.sha256(payload).hexdigest() != digest:
                raise ValueError('source changed while binding media to repository bytes')
            if result.returncode or result.stdout.replace(b'\r\n', b'\n') != payload.replace(b'\r\n', b'\n'):
                return {}
            blobs[name] = hashlib.sha256(result.stdout).hexdigest()
    except (OSError, subprocess.SubprocessError):
        return {}
    return {'source_repository_revision': revision, 'source_repository_inputs': blobs}


def _log(root: Path, name: str) -> bytes:
    if not isinstance(name, str) or '\\' in name or ':' in name:
        raise ValueError('log must be a contained relative path')
    parts = PurePosixPath(name)
    if parts.is_absolute() or not parts.parts or any(p in {'.', '..'} for p in parts.parts):
        raise ValueError('log must be a contained relative path')
    path = root
    for part in parts.parts:
        path /= part
        if path.is_symlink():
            raise ValueError('log symlinks are not accepted')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('log escapes transcript directory')
    return path.read_bytes()


def _review(raw: str, code: int) -> dict:
    review = json.loads(raw)
    if (not isinstance(review, dict) or review.get('project') != 'rover-pdb'
            or type(review.get('blocking')) is not bool
            or not isinstance(review.get('results'), list) or not review['results']):
        raise ValueError('incomplete Rover native review')
    results = review['results']
    if any(not isinstance(r, dict) or not isinstance(r.get('check_id'), str)
           or not r['check_id'] or type(r.get('passed')) is not bool for r in results):
        raise ValueError('invalid native review result')
    if len({r['check_id'] for r in results}) != len(results):
        raise ValueError('duplicate native review check')
    findings = review.get('findings', [])
    if not isinstance(findings, list) or any(not isinstance(f, dict)
                                          or type(f.get('blocking')) is not bool for f in findings):
        raise ValueError('invalid native review findings')
    blocked = any(not r['passed'] for r in results) or any(f.get('blocking') is True for f in findings)
    if review['blocking'] != blocked or code != int(blocked):
        raise ValueError('native review findings and exit code disagree')
    return review


def _normalize(value):
    if isinstance(value, str):
        return re.sub(r'[A-Za-z]:[\\/][^\n]*?pcb-copilot-review-[^\\/\s]+',
                      '<native-review-snapshot>', value)
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    return value


def demo_data(path: Path) -> dict:
    document = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(document, dict) or document.get('schema_version') != 1 or document.get('mode') != 'full'
            or document.get('source_project') != 'projects/rover-pdb' or document.get('error')):
        raise ValueError('media requires a completed full Rover demo')
    if any(document.get(flag) is not True for flag in
           ('source_inputs_unchanged', 'source_cad_unchanged', 'snapshot_inputs_unchanged')):
        raise ValueError('media requires unchanged source CAD and snapshot inputs')
    before = document.get('source_inputs_before')
    if (not isinstance(before, dict) or not before or before != document.get('source_inputs_after')
            or any(not isinstance(p, str) or (h is not None and
                   (not isinstance(h, str) or not re.fullmatch(r'[0-9a-f]{64}', h))) for p, h in before.items())):
        raise ValueError('source input hash maps are missing or inconsistent')
    cad = {p: h for p, h in before.items() if Path(p).suffix in
           {'.kicad_sch', '.kicad_pcb', '.kicad_pro', '.kicad_dru'}}
    if not cad or document.get('source_cad_before') != cad or document.get('source_cad_after') != cad:
        raise ValueError('source CAD hash maps disagree with declared inputs')
    steps = document.get('steps')
    if (not isinstance(steps, list) or [s.get('name') for s in steps if isinstance(s, dict)] !=
            ['status', 'evidence', 'missing-preview', 'review'] or len(steps) != 4):
        raise ValueError('media requires exactly the completed full-demo steps')
    snapshot = 'workspace/rover-pdb'
    commands = [
        ['pcb-copilot', 'status', snapshot],
        ['pcb-copilot', 'research', snapshot, '--verify'],
        ['pcb-copilot', 'update-schematic', snapshot, '--candidate',
         snapshot + '/rover-pdb.kicad_sch', '--apply'],
        ['pcb-copilot', 'review', snapshot, '--format', 'json'],
    ]
    logs, records = {}, []
    for step, command in zip(steps, commands, strict=True):
        if step.get('command') != command or step.get('error') or type(step.get('exit_code')) is not int:
            raise ValueError('demo command, execution error or exit code is inconsistent')
        record = {key: step[key] for key in ('name', 'command', 'exit_code')}
        for stream in ('stdout', 'stderr'):
            payload = _log(path.parent, step.get(stream))
            logs[step['name'], stream] = payload.decode('utf-8')
            record[stream + '_sha256'] = hashlib.sha256(payload).hexdigest()
        records.append(record)
    if steps[0]['exit_code'] != 0 or steps[1]['exit_code'] != 0:
        raise ValueError('media requires successful status and evidence verification')
    evidence = logs['evidence', 'stdout']
    if not evidence.splitlines() or not re.fullmatch(r'\d+ evidence record\(s\) verified', evidence.splitlines()[0]):
        raise ValueError('evidence verification did not produce its completed report')
    for heading in ('MACHINE FAILURES', 'CONFLICTS'):
        sections = list(re.finditer(r'^' + heading + r':[ \t]*(.*)$', evidence, re.MULTILINE))
        if len(sections) != 1 or sections[0].group(1).strip() != 'none':
            raise ValueError('evidence verification contains failures or conflicts')
        body = re.split(r'\n[A-Z][A-Z _]+:', evidence[sections[0].end():], maxsplit=1)[0]
        if body.strip():
            raise ValueError('evidence verification contains failures or conflicts')
    stderr = logs['missing-preview', 'stderr']
    if steps[2]['exit_code'] != 2 or GUARD not in stderr:
        raise ValueError('media requires the actual missing-preview rejection')
    review = _review(logs['review', 'stdout'], steps[3]['exit_code'])
    if document.get('review') != review:
        raise ValueError('cached review differs from the original review stdout')
    if type(document.get('exit_code')) is not int or document['exit_code'] != steps[3]['exit_code']:
        raise ValueError('demo exit code differs from the native review')
    return {
        'captured_utc': document['started_utc'], 'source_project': document['source_project'],
        'mode': 'full', 'demo_exit_code': document['exit_code'],
        'source_inputs_unchanged': True, 'snapshot_inputs_unchanged': True,
        'declared_input_count': len(before), 'source_input_hashes': before,
        'steps': records, 'evidence_excerpt': evidence.splitlines()[:5],
        'guard_excerpt': next(line for line in stderr.splitlines() if GUARD in line),
        'review': _normalize(review),
        'scope': 'Recorded CLI results with temporary absolute review paths normalized. Original log hashes '
                 'are retained. Not a screen recording, CAD edit demonstration or fabrication approval.',
    }
