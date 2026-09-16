import json

from pcb_copilot.cli import main
from pcb_copilot.schematic.preview import render_schematic_preview
from pcb_copilot.toolchain import ToolchainPaths


def test_draft_command_preserves_accepted_files(project_copy, repo_root, capsys):
    accepted = {p: p.read_bytes() for p in project_copy.glob('*.kicad_*')}
    code = main(['draft-schematic', str(project_copy), '--intent',
                 str(repo_root / 'tests/fixtures/schematic/parent-child.yaml')])
    result = json.loads(capsys.readouterr().out)
    assert code == 1  # Fixture citations are deliberately absent from the archive.
    root = project_copy / '.pcb-copilot/drafts' / result['draft_id']
    assert (root / 'preview.pdf').read_bytes().startswith(b'%PDF')
    assert json.loads((root / 'erc.json').read_text(encoding='utf-8'))['sheets']
    assert len(json.loads((root / 'metrics.json').read_text())['sheets']) == 2
    assert (root / 'schematic-intent.yaml').is_file()
    assert all(p.read_bytes() == data for p, data in accepted.items())


def test_unavailable_cli_retains_draft_and_reports_failure(rendered, tmp_path):
    toolchain = ToolchainPaths(tmp_path / 'missing-cli', None, ())
    result = render_schematic_preview(toolchain, rendered, rendered.parent)
    assert rendered.is_file()
    assert result.pdf_path is None
    assert result.erc_report_path.is_file()
    assert {f.code for f in result.findings} >= {'preview-failed', 'erc-failed'}
