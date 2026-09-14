"""Capture deterministic comparison data for every accepted board."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pcb_copilot.migration import capture_board, legacy_project_paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    projects_root = repo_root / "projects"
    board_names = ("baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3")
    document = {
        name: capture_board(legacy_project_paths(projects_root / name))
        for name in board_names
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
