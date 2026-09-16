"""Generate review artifacts while retaining drafts when external tools fail."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from kicad_claude.adapters import sch_editor, sch_io

from pcb_copilot.evidence.checks import Finding
from pcb_copilot.schematic.quality import analyse_schematic
from pcb_copilot.toolchain import ToolchainPaths


@dataclass(frozen=True)
class PreviewResult:
    pdf_path: Path | None
    erc_report_path: Path
    metrics_path: Path
    findings: tuple[Finding, ...]


def schematic_files(schematic: Path) -> tuple[Path, ...]:
    """Follow child references, rejecting traversal outside the draft."""
    root = schematic.parent.resolve()
    pending = [schematic.resolve()]
    found = []
    while pending:
        path = pending.pop(0)
        if path in found:
            continue
        if not path.is_relative_to(root):
            raise ValueError("schematic child escapes draft workspace")
        tree = sch_io.parse_file(path)
        found.append(path)
        pending.extend((path.parent / s['filename']).resolve()
                       for s in sch_editor.list_sheets(tree))
    return tuple(found)


def render_schematic_preview(
    toolchain: ToolchainPaths, schematic: Path, output_dir: Path,
) -> PreviewResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf = output_dir / 'preview.pdf'
    erc = output_dir / 'erc.json'
    metrics_path = output_dir / 'metrics.json'
    findings: list[Finding] = []
    metrics = []
    for path in schematic_files(schematic):
        value = analyse_schematic(path)
        metrics.append({'path': path.relative_to(schematic.parent).as_posix(), **asdict(value)})
        if not value.title_complete or value.component_count > value.page_capacity:
            findings.append(Finding('schematic-quality', f'{path.name}: incomplete title or excessive density'))
    metrics_path.write_text(json.dumps({'sheets': metrics}, indent=2) + '\n', encoding='utf-8')

    def run(arguments: list[str]) -> None:
        result = subprocess.run(
            [str(toolchain.kicad_cli), *arguments], cwd=output_dir,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f'exit {result.returncode}: {result.stderr.strip()}')

    # Remove prior outputs so a failed rerun cannot advertise stale success.
    pdf.unlink(missing_ok=True)
    erc.unlink(missing_ok=True)
    try:
        run(['sch', 'erc', '--format', 'json', '--output', str(erc), str(schematic)])
        report = json.loads(erc.read_text(encoding='utf-8'))
        if not isinstance(report.get('sheets'), list):
            raise TypeError('ERC report has no sheets')
        for sheet in report['sheets']:
            for violation in sheet.get('violations', []):
                findings.append(Finding(
                    'erc-' + violation.get('type', 'violation'),
                    violation.get('description', 'ERC violation'),
                    severity='block' if violation.get('severity') == 'error' else 'review',
                ))
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired) as exc:
        findings.append(Finding('erc-failed', str(exc)))
        erc.write_text(json.dumps({'status': 'failed', 'error': str(exc)}) + '\n', encoding='utf-8')
    try:
        run(['sch', 'export', 'pdf', '--output', str(pdf), str(schematic)])
        if not pdf.read_bytes().startswith(b'%PDF'):
            raise ValueError('PDF export did not produce a PDF')
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        findings.append(Finding('preview-failed', str(exc)))
        pdf.unlink(missing_ok=True)
    return PreviewResult(pdf if pdf.is_file() else None, erc, metrics_path, tuple(findings))
