"""Git must preserve exact evidence bytes with Windows autocrlf enabled."""

import subprocess

import pytest


@pytest.mark.parametrize('ending', [b'\n', b'\r\n'])
def test_git_index_and_checkout_preserve_evidence_bytes(repo_root, tmp_path, ending):
    attributes = repo_root / '.gitattributes'
    assert attributes.is_file(), 'hash-addressed archives require a Git byte-preservation policy'
    (tmp_path / '.gitattributes').write_bytes(attributes.read_bytes())
    relative = 'projects/test/evidence/files/reference.sch'
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    payload = ending.join([b'<?xml version="1.0"?>', b'<eagle/>', b''])
    path.write_bytes(payload)

    def git(*args):
        return subprocess.run(['git', '-c', 'core.autocrlf=true', *args],
                              cwd=tmp_path, check=True, capture_output=True).stdout

    git('init', '-q')
    git('add', '--', '.gitattributes', relative)
    assert git('show', ':' + relative) == payload
    assert git('cat-file', '--filters', ':' + relative) == payload
