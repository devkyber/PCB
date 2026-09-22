"""Check candidate schematic connectivity against the current PCB."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

from pcb_copilot.models import Project
from pcb_copilot.toolchain import discover_toolchain


def read_board_net_groups(pcb: Path) -> dict[str, set[tuple[str, str]]]:
    """Read KiCad's resolved pad-to-net assignments using bundled pcbnew."""
    toolchain = discover_toolchain(Path(__file__).resolve().parents[3])
    if toolchain.kipython is None:
        raise RuntimeError('KiCad Python with pcbnew is unavailable')
    helper = Path(__file__).with_name('pcb_net_inventory.py')
    run = subprocess.run(
        [str(toolchain.kipython), str(helper), str(pcb)],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=120, check=False,
    )
    if run.returncode:
        raise RuntimeError(f'KiCad board inventory failed: {run.stderr.strip()}')
    parsed = json.loads(run.stdout)
    return {net: {tuple(pin) for pin in pins} for net, pins in parsed.items()}


def derive_net_renames(
    schematic: dict[str, set[tuple[str, str]]],
    board: dict[str, set[tuple[str, str]]],
) -> dict[str, str]:
    """Map PCB net names to schematic names only for identical pin groups."""
    schematic_by_members = {frozenset(pins): name for name, pins in schematic.items()}
    board_by_members = {frozenset(pins): name for name, pins in board.items()}
    if (len(schematic_by_members) != len(schematic)
            or len(board_by_members) != len(board)
            or schematic_by_members.keys() != board_by_members.keys()):
        raise ValueError('schematic and PCB have different pin membership')
    return {
        board_by_members[members]: schematic_name
        for members, schematic_name in schematic_by_members.items()
        if board_by_members[members] != schematic_name
    }


_NET_FIELD = re.compile(rb'\((net|net_name) "([^"]+)"\)')


def rewrite_board_net_names(payload: bytes, names: dict[str, str]) -> bytes:
    """Rewrite KiCad net fields without touching copper geometry or labels."""
    encoded = {old.encode('utf-8'): new.encode('utf-8') for old, new in names.items()}
    seen: set[bytes] = set()

    def replace(match: re.Match[bytes]) -> bytes:
        old = match.group(2)
        if old not in encoded:
            return match.group(0)
        seen.add(old)
        return b'(' + match.group(1) + b' "' + encoded[old] + b'")'

    revised = _NET_FIELD.sub(replace, payload)
    missing = sorted(name.decode('utf-8') for name in encoded.keys() - seen)
    if missing:
        raise ValueError(f'PCB net fields were not found: {missing}')
    return revised


def reconcile_project_net_classes(payload: bytes, names: dict[str, str]) -> bytes:
    """Carry matching KiCad net-class patterns to hierarchy-qualified names."""
    document = json.loads(payload)
    patterns = document.get('net_settings', {}).get('netclass_patterns')
    if not isinstance(patterns, list):
        return payload
    additions = []
    for old, new in names.items():
        for entry in patterns:
            if fnmatchcase(old, entry['pattern']):
                assignment = {'netclass': entry['netclass'], 'pattern': new}
                if assignment not in patterns and assignment not in additions:
                    additions.append(assignment)
    if not additions:
        return payload
    patterns.extend(additions)
    serialized = json.dumps(document, indent=2, ensure_ascii=False)
    if payload.endswith((b'\n', b'\r')):
        serialized += '\n'
    if b'\r\n' in payload:
        serialized = serialized.replace('\n', '\r\n')
    return serialized.encode('utf-8')


def reconcile_board_net_names(
    project: Project, candidate_root: Path,
) -> tuple[bytes, bytes, dict[str, str]]:
    """Stage name-only PCB and matching project-rule changes."""
    candidate_pcb = candidate_root / project.pcb_path.relative_to(project.root)
    current = project.pcb_path.read_bytes()
    if candidate_pcb.read_bytes() != current:
        raise ValueError('candidate PCB differs from the current board before reconciliation')
    current_pro = project.pcb_path.with_suffix('.kicad_pro')
    candidate_pro = candidate_root / current_pro.relative_to(project.root)
    settings = current_pro.read_bytes()
    if candidate_pro.read_bytes() != settings:
        raise ValueError('candidate project settings differ before reconciliation')
    scripts = Path(__file__).resolve().parents[3] / 'scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from check_netlist_parity import schematic_nets

    schematic = candidate_root / project.schematic_path.relative_to(project.root)
    names = derive_net_renames(
        schematic_nets(schematic), read_board_net_groups(project.pcb_path),
    )
    revised = rewrite_board_net_names(current, names)
    if _NET_FIELD.sub(b'(net "NET")', revised) != _NET_FIELD.sub(b'(net "NET")', current):
        raise ValueError('board reconciliation changed content other than net names')
    revised_settings = reconcile_project_net_classes(settings, names)
    try:
        candidate_pcb.write_bytes(revised)
        candidate_pro.write_bytes(revised_settings)
        error = candidate_board_parity(project, candidate_root)
        if error:
            raise ValueError(f'reconciled board still differs from schematic: {error}')
        if names:
            from pcb_copilot.layout.constraints import _native

            kipython = discover_toolchain(Path(__file__).resolve().parents[3]).kipython
            if kipython is None:
                raise RuntimeError('KiCad Python with pcbnew is unavailable')
            before_rules = _native(project.pcb_path, kipython)['nets']
            after_rules = _native(candidate_pcb, kipython)['nets']
            for old, rules in before_rules.items():
                if after_rules.get(names.get(old, old)) != rules:
                    raise ValueError(f'net-class rules changed for {old}')
    except Exception:
        candidate_pcb.write_bytes(current)
        candidate_pro.write_bytes(settings)
        raise
    return revised, revised_settings, names


def candidate_board_parity(project: Project, candidate_root: Path) -> str | None:
    """Return a failure description or ``None`` for exact KiCad netlist parity."""
    repo_root = Path(__file__).resolve().parents[3]
    toolchain = discover_toolchain(repo_root)
    if toolchain.kipython is None:
        return 'KiCad Python with pcbnew is unavailable; board parity cannot be checked'
    checker = repo_root / 'scripts' / 'check_netlist_parity.py'
    pcb = candidate_root / project.pcb_path.relative_to(project.root)
    try:
        run = subprocess.run(
            [str(toolchain.kipython), str(checker), str(pcb)],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f'board parity check failed to run: {exc}'
    if run.returncode:
        return (run.stdout or run.stderr).strip()[:4000] or 'board parity check failed'
    return None
