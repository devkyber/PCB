"""Executable shell hooks must remain LF-only in fresh Windows checkouts."""

import subprocess


def test_git_checkout_exports_all_shell_hooks_with_lf(repo_root, tmp_path):
    fixture = tmp_path / 'fixture'
    fixture.mkdir()
    (fixture / '.gitattributes').write_bytes((repo_root / '.gitattributes').read_bytes())

    sources = sorted((repo_root / '.claude/hooks').glob('*.sh'))
    assert len(sources) == 3
    for source in sources:
        destination = fixture / '.claude/hooks' / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())

    def git(*arguments):
        return subprocess.run(
            ['git', '-c', 'core.autocrlf=true', *arguments],
            cwd=fixture,
            check=True,
            capture_output=True,
        )

    git('init', '-q')
    git('add', '--', '.gitattributes', '.claude/hooks')
    exported = tmp_path / 'exported'
    exported.mkdir()
    prefix = exported.resolve().as_posix() + '/'
    git('checkout-index', '--all', f'--prefix={prefix}')

    for source in sources:
        payload = (exported / '.claude/hooks' / source.name).read_bytes()
        assert b'\n' in payload
        assert b'\r\n' not in payload
        assert payload == source.read_bytes().replace(b'\r\n', b'\n')
