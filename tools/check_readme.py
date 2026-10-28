"""Check local landing-page links and the byte identities of published media."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

from pcb_copilot.project import load_project
from pcb_copilot.transaction import input_hashes

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ["README.md", "docs/QUICKSTART.md", "docs/ROADMAP.md", "docs/EVALUATION.md", "docs/media/README.md",
             "docs/evaluation/2026-10-29/report.md"]
MEDIA_MANIFESTS = ('manifest.json', 'example-manifest.json', 'proof-manifest.json')
CAD_MANIFESTS = frozenset(MEDIA_MANIFESTS[:2])
EVALUATION_MANIFESTS = ('docs/evaluation/2026-10-29/manifest.json',)


def contained_path(root: Path, name: str) -> Path:
    """Use canonical relative file names on every host, including Windows paths."""
    if not isinstance(name, str) or not name:
        raise ValueError('file name must be a nonempty relative path')
    posix, windows = PurePosixPath(name), PureWindowsPath(name)
    if (posix.is_absolute() or windows.drive or '\\' in name or ':' in name
            or '..' in posix.parts or posix.as_posix() != name or name == '.'
            or any(ord(char) < 32 for char in name)):
        raise ValueError(f'file name must be a canonical contained relative path: {name!r}')
    path = (root / name).resolve()
    if path == root.resolve() or not path.is_relative_to(root.resolve()):
        raise ValueError(f'file path escapes its root: {name!r}')
    return path


def digest(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate manifest key: {key}')
        result[key] = value
    return result


def source_map(value, project_root: Path, field: str) -> dict:
    if not isinstance(value, dict) or not value:
        raise ValueError(f'{field} must be a nonempty input hash map')
    for name, value_hash in value.items():
        contained_path(project_root, name)
        if value_hash is not None and not digest(value_hash):
            raise ValueError(f'{field}: invalid SHA-256 or null for {name}')
    return value


def check_capture(manifest: dict, repository: Path) -> None:
    if manifest.get('source_cad_unchanged') is not True:
        raise ValueError('source_cad_unchanged must be exactly true')
    project_root = contained_path(repository, manifest.get('source_project'))
    relative = project_root.relative_to(repository.resolve())
    if len(relative.parts) < 2 or relative.parts[0] not in {'projects', 'examples'}:
        raise ValueError('capture source must be an active project under examples/ or projects/')
    captured = source_map(manifest.get('source_inputs'), project_root, 'source_inputs')
    canonical = None
    if 'source_repository_inputs' in manifest:
        canonical = source_map(manifest['source_repository_inputs'], project_root, 'source_repository_inputs')
        if canonical.keys() != captured.keys():
            raise ValueError('captured and repository source maps must have the same input keys')
        if any((captured[name] is None) != (canonical[name] is None) for name in captured):
            raise ValueError('captured and repository source maps must preserve null inputs')
    current = input_hashes(load_project(project_root))
    if not isinstance(current, dict) or current.keys() != captured.keys():
        raise ValueError('current project input keys differ from the captured source inputs')
    stale = [name for name, current_hash in current.items()
             if current_hash != captured[name] and (canonical is None or current_hash != canonical[name])]
    if stale:
        raise ValueError('current project input hashes differ from captured/repository bytes: ' + ', '.join(sorted(stale)))


def check_manifest(path: Path, media: Path, repository: Path, *, capture: bool,
                   complete_bundle: bool = False) -> int:
    manifest = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    if not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('media manifest needs schema_version 1')
    outputs = manifest.get('outputs')
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError('media manifest outputs must be a nonempty mapping')
    minimum_bytes = 0 if complete_bundle else 1  # Retained raw command streams may be empty.
    for name, record in outputs.items():
        output = contained_path(media, name)
        if (not isinstance(record, dict) or not digest(record.get('sha256'))
                or type(record.get('bytes')) is not int or record['bytes'] < minimum_bytes):
            raise ValueError(f'invalid media SHA-256/byte count record: {name}')
        if not output.is_file():
            raise ValueError(f'missing media {name}')
        payload = output.read_bytes()
        if len(payload) != record['bytes']:
            raise ValueError(f'media byte count mismatch {name}')
        if hashlib.sha256(payload).hexdigest() != record['sha256']:
            raise ValueError(f'media hash mismatch {name}')
    if complete_bundle:
        present = {item.relative_to(media).as_posix() for item in media.rglob('*') if item.is_file()}
        if present != {*outputs, path.name}:
            raise ValueError('retained evaluation artifacts differ from the complete manifest output list')
    if capture:
        check_capture(manifest, repository)
    return len(outputs)


def anchors(path: Path) -> set[str]:
    found = set()
    for heading in re.findall(r"^#{1,6}\s+(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE):
        plain = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        found.add(plain)
    return found


def main() -> int:
    failures = []
    count = 0
    repository = ROOT.resolve()
    for name in DOCUMENTS:
        document = repository / name
        try:
            content = re.sub(r"```[^\n]*\n.*?```", "", document.read_text(encoding="utf-8"), flags=re.DOTALL)
        except (OSError, UnicodeError) as exc:
            failures.append(f'{name}: cannot read required document: {exc}')
            continue
        for target in re.findall(r"\]\(([^)\n]+)\)", content):
            target = target.strip().strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            destination = (document.parent / unquote(url.path)).resolve() if url.path else document
            count += 1
            if not destination.is_relative_to(repository) or not destination.exists():
                failures.append(f"{name}: missing local target {target}")
            elif url.fragment and destination.suffix == ".md" and unquote(url.fragment) not in anchors(destination):
                failures.append(f"{name}: missing Markdown heading {target}")
    output_count = 0
    try:
        media = contained_path(repository, 'docs/media')
    except ValueError as exc:
        failures.append(str(exc))
    else:
        for name in MEDIA_MANIFESTS:
            try:
                manifest_path = contained_path(media, name)
                output_count += check_manifest(manifest_path, media, repository, capture=name in CAD_MANIFESTS)
            except (OSError, ValueError, UnicodeError) as exc:
                failures.append(f'{name}: {exc}')
    for name in EVALUATION_MANIFESTS:
        try:
            relative = PurePosixPath(name)
            bundle = contained_path(repository, relative.parent.as_posix())
            manifest_path = contained_path(bundle, relative.name)
            output_count += check_manifest(manifest_path, bundle, repository, capture=False, complete_bundle=True)
        except (OSError, ValueError, UnicodeError) as exc:
            failures.append(f'{name}: {exc}')
    if failures:
        print("\n".join(failures))
        return 1
    total_manifests = len(MEDIA_MANIFESTS) + len(EVALUATION_MANIFESTS)
    print(f"Landing-page checks passed: {count} local links; {total_manifests} required evidence manifests; {output_count} published byte/hash identities match.")
    print("Scope: local links, exact captured/repository input identities and published output bytes; not external URLs, capture authenticity or CAD qualification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
