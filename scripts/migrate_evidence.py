#!/usr/bin/env python3
"""Preview or apply one project's migration to unified evidence storage."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from pcb_copilot.evidence.migrate import migrate_legacy_evidence
from pcb_copilot.project import load_project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = migrate_legacy_evidence(
        load_project(Path(args.project)), dry_run=not args.apply
    )
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"{mode}: {report.records_created} record(s), "
          f"{report.duplicates_merged} duplicate file(s) merged")
    for move in report.moves:
        print(f"  MOVE {move}")
    for rewrite in report.rewrites:
        print(f"  REWRITE {rewrite}")
    for deletion in report.deletions:
        print(f"  DELETE {deletion}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
