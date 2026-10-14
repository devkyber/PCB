# PCB workspace instructions

Read [CLAUDE.md](CLAUDE.md) for the shared workspace protocol, then follow the
project's own `AGENTS.md` and design documents. The same protocol applies to
Codex and other schematic authors.

For every new or revised schematic, follow
[Schematic readability](docs/DESIGN_RULES.md#schematic-readability) and the
[schematic update workflow](docs/WORKFLOW.md#2-update-the-schematic). Inspect
every rendered sheet before handover; a successful export or clean ERC is not
visual review. Preserve owner-edited CAD and the user's requested scope.

The schematic readability section includes the owner's adopted Tiago Gala and
Gregor Gross references. Apply these conventions to all future schematic work,
including functional pin arrangement and on-sheet design assumptions. These
style rules do not authorize circuit changes or replacement of manual edits.

Rover's reusable lessons are enforced through the shared update/release gates
and the mandatory `shared.*` review items, described in
[Architecture](docs/ARCHITECTURE.md#rover-lessons-used-by-the-shared-pipeline).
Apply them to all boards. The sole retained board is projects/rover-pdb. Recreate TMS from
design-bases/tms decisions and research. Frozen regression inputs under
tests/fixtures/boards are never projects to develop or restore.
