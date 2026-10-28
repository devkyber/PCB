"""Check local landing-page links and the byte identities of published media."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ["README.md", "docs/QUICKSTART.md", "docs/ROADMAP.md", "docs/media/README.md"]


def anchors(path: Path) -> set[str]:
    found = set()
    for heading in re.findall(r"^#{1,6}\s+(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE):
        plain = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        found.add(plain)
    return found


def main() -> int:
    failures = []
    count = 0
    for name in DOCUMENTS:
        document = ROOT / name
        content = re.sub(r"```[^\n]*\n.*?```", "", document.read_text(encoding="utf-8"), flags=re.DOTALL)
        for target in re.findall(r"\]\(([^)\n]+)\)", content):
            target = target.strip().strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            destination = (document.parent / unquote(url.path)).resolve() if url.path else document
            count += 1
            if not destination.is_relative_to(ROOT) or not destination.exists():
                failures.append(f"{name}: missing local target {target}")
            elif url.fragment and destination.suffix == ".md" and unquote(url.fragment) not in anchors(destination):
                failures.append(f"{name}: missing Markdown heading {target}")
    media = ROOT / "docs" / "media"
    for manifest_path in sorted(media.glob("*manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, record in manifest["outputs"].items():
            path = (media / name).resolve()
            if not path.is_relative_to(media) or not path.is_file():
                failures.append(f"{manifest_path.name}: missing media {name}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                failures.append(f"{manifest_path.name}: media hash mismatch {name}")
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Landing-page checks passed: {count} local links; published media hashes match.")
    print("Scope: local links and captured output bytes; not external URLs or CAD qualification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
