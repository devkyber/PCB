#!/bin/bash
# Stop hook: when a turn ends, if any board changed recently, print its gate
# table automatically.
#
# WHY
# ---
# The user should never have to ask "did you run the gates?" or "did you check
# the lessons?". Asking is itself the bug: it makes enforcement depend on the
# user remembering to demand evidence. This hook makes the evidence appear
# whether or not Claude chose to produce it, and whether or not the user asked.
#
# It reports; it does not block. A mid-layout FAIL is expected and normal.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 0

CHANGED=$(find projects -name '*.kicad_pcb' -newermt '-45 minutes' 2>/dev/null)
[[ -z "$CHANGED" ]] && exit 0

echo "=============================================================="
echo " AUTOMATIC GATE CHECK — boards touched this session"
echo " (scripts/pipeline.py --status for the full picture)"
echo "=============================================================="
while IFS= read -r pcb; do
    [[ -f "$pcb" ]] || continue
    python3 scripts/run_gates.py "$pcb" 2>&1 | sed 's/^/  /'
done <<< "$CHANGED"
echo "=============================================================="
echo " A completion claim without the table above is not evidence."
echo "=============================================================="
exit 0
