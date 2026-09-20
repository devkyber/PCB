#!/bin/bash
# Thin shim. The real build lives in scripts/pipeline.py, for every board.
#
# This file used to contain its own five-step sequence. That made two code
# paths for "build a board" — one here, one in the workflow document — and
# two paths that can drift is precisely the failure mode this workspace keeps
# paying for. There is now one path. This shim exists only so that muscle
# memory and any old reference to ./build.sh still lands in the right place.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 ../../scripts/pipeline.py "$PWD" "$@"
