
from pcb_copilot.schematic.preview import render_schematic_preview
from pcb_copilot.toolchain import ToolchainPaths


def test_unavailable_cli_retains_draft_and_reports_failure(rendered, tmp_path):
    toolchain = ToolchainPaths(tmp_path / 'missing-cli', None, ())
    result = render_schematic_preview(toolchain, rendered, rendered.parent)
    assert rendered.is_file()
    assert result.pdf_path is None
    assert result.erc_report_path.is_file()
    assert {f.code for f in result.findings} >= {'preview-failed', 'erc-failed'}
