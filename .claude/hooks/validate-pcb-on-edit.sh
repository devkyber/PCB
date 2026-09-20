#!/bin/bash
# PostToolUse hook: after anything that could have written a .kicad_pcb,
# run validate_pcb.py and surface the result. Never blocks the turn —
# this is feedback, not a gate (routing happens incrementally, so
# mid-layout FAILs are expected).
#
# WHY IT MATCHES Bash AS WELL AS Write/Edit
# -----------------------------------------
# The original version only read tool_input.file_path, which exists for
# Write/Edit and NOT for Bash. But every board in this repo is produced by
# a Python generator invoked through Bash — so on the one path that
# actually creates boards, this hook silently did nothing, for months,
# while CLAUDE.md advertised it as automatic. A hook that cannot fire on
# the real path is documentation, not enforcement.
#
# So: for Write/Edit use the declared file_path; for Bash, find any
# .kicad_pcb modified in the last 120 seconds and validate that.

INPUT=$(cat)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VALIDATOR="$REPO_ROOT/scripts/validate_pcb.py"
[[ -f "$VALIDATOR" ]] || exit 0

read -r TOOL FILE_PATH <<<"$(echo "$INPUT" | python3 -c '
import json,sys
d=json.load(sys.stdin)
print(d.get("tool_name",""), d.get("tool_input",{}).get("file_path",""))
' 2>/dev/null)"

TARGETS=()
if [[ "$FILE_PATH" == *.kicad_pcb ]]; then
    TARGETS+=("$FILE_PATH")
elif [[ "$TOOL" == "Bash" ]]; then
    while IFS= read -r f; do TARGETS+=("$f"); done < <(
        python3 - "$REPO_ROOT" <<'PY'
from pathlib import Path
import sys
import time

cutoff = time.time() - 120
for board in sorted((Path(sys.argv[1]) / "projects").glob("*/*.kicad_pcb")):
    if board.stat().st_mtime >= cutoff:
        print(board)
PY
    )
fi

for f in "${TARGETS[@]}"; do
    [[ -f "$f" ]] || continue
    OUT=$(python3 "$VALIDATOR" "$f" 2>&1)
    echo "--- validate_pcb.py result for $(basename "$f") ---"
    echo "$OUT" | grep -E '(FAIL|WARN) ' -A1
    echo "$OUT" | tail -3
done

exit 0
