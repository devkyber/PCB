"""Resolve frozen regression inputs separately from active owner designs."""
from pathlib import Path

RETIRED_BOARDS = frozenset({'baro-bmp390', 'imu-icm42688', 'gnss-neom9n', 'tms-v3'})


def board_source(repo_root: Path, name: str) -> Path:
    parent = repo_root / 'tests/fixtures/boards' if name in RETIRED_BOARDS else repo_root / 'projects'
    return parent / name
