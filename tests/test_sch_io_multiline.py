from kicad_claude.adapters import sch_io
from sexpdata import Symbol


def test_multiline_owner_text_is_escaped_and_roundtrips(tmp_path):
    text = 'BATTERY\n25.2 V\tmax\r\n"Keep" \\ path'
    tree = [Symbol('gr_text'), text]
    path = tmp_path / 'text.sexp'
    sch_io.write_file(path, tree)
    assert '\\n' in path.read_text() and '\\t' in path.read_text()
    assert sch_io.parse_file(path) == tree
