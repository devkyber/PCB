# Understand and use PCB Copilot

This repository helps you research parts and reference designs, prepare editable
schematic/PCB drafts, and review evidence. You remain the engineer: it does not
autonomously approve circuits or produce a guaranteed fabrication-ready board.

## Read in this order

| Your question | Read |
| --- | --- |
| Where are the results, and how far have we got? | [Results and progress](PROGRESS.md) |
| How do I use it on a board? | [Workflow](WORKFLOW.md) |
| What can I trust, and what needs my judgment? | [Limitations](LIMITATIONS.md) |
| How does the code fit together? | [Architecture](ARCHITECTURE.md) |
| What belongs in a board project? | [Project format](PROJECT_FORMAT.md) |
| What does a design review need to cover? | [Design rules](DESIGN_RULES.md) |

Start with the first two. The others are references, not a required reading list.
The [repository README](../README.md) covers installation and the quick start.

## Where the other files went

The versioned `docs/` files are only these reader guides. Executable helpers are in `scripts/`;
replace `python docs/<helper>.py` with `python scripts/<helper>.py` in old notes.
Maintainer plans are in `planning/`, and migration records are in `migration/`.
Board-specific requirements, evidence and decisions remain beside each board in
`projects/`. Do not delete its hidden `.pcb-copilot/` directory: it holds your
local previews, drafts and possible manual edits.
