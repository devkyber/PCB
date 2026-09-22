# Architecture and project format

The product boundary is the `pcb-copilot` CLI in `src/pcb_copilot/`. The four
root KiCad projects in `projects/` are the current designs. Their evidence,
requirements, intent, and human decisions are inputs or review records—not a
second accepted CAD tree. Git is the durable history.

## Authority and data flow

Requirements and owner decisions define the intended behavior. Exact archived
datasheets and reference designs support it. The typed schematic/layout intent
files describe proposed changes. The root KiCad files are the working electrical
and physical designs; `netmap.json` is a versioned connectivity review diff.
Generated previews and reports under ignored `.pcb-copilot/` are local output.

```text
requirements + cited evidence + human decisions
                    ↓
            explicit design intent
                    ↓
          temporary candidate + checks
                    ↓  explicit --apply, if gates pass
              root KiCad design
                    ↓
          human review and bench work
                    ↓
          future release interlock
```

`update-schematic` uses a temporary copy, renders PDF/ERC/metrics, verifies
intent and PCB pin-net parity, then replaces the current schematic and netmap
through a rollback-capable transaction. TMS's optional net-name reconciliation
also changes PCB name fields and `.kicad_pro` class patterns in that same
transaction. It compares native before/after rule values; unchanged copper
geometry is not mistaken for a finished layout. Applying a design change
invalidates prior review/release state and leaves lifecycle `DRAFT`.

The layout package has real-footprint, placement, constraint, routing-candidate,
preview, and DRC helpers, but the public current-file `update-layout` and
transactional release are unfinished. Current `review` runs isolated checks
and validates hash-bound, board-specific human decisions. Most machine checks
still call legacy scripts until migration. The legacy script tree is not an
alternate recommended pipeline.

## A board directory

```text
projects/BOARD/
  project.yaml             path and lifecycle declaration
  BOARD.kicad_sch          current schematic; child sheets beside it
  BOARD.kicad_pcb          current board
  BOARD.kicad_pro          KiCad rules and project settings
  netmap.json              versioned connectivity comparison
  schematic-intent.yaml   reproducible proposed circuit
  layout-intent.yaml      reproducible proposed placement/rules
  REQUIREMENTS.md          human-owned purpose and limits
  DESIGN_BASIS.md          sourced design choices and disagreements
  REFERENCE_REVIEW.md      schematic and PCB reference research
  DEVIATIONS.md           narrow rule/evidence waivers
  review-profile.yaml     board-specific human questions
  review-signoff.yaml     optional dated, hash-bound decisions
  SIGNOFF.md              legacy checklist, not current approval
  evidence/index.yaml     source provenance, roles, and hashes
  evidence/files/         exact archived source bytes
```

The `project.yaml` schema is version 1. Design and evidence paths are relative
to the board directory; the loader rejects escapes and unknown fields.
Lifecycle values are `DRAFT`, `HUMAN_REVIEWED`, and `RELEASED`, but effective
state also checks recorded design hashes. KiCad UUID tokens are masked for
canonical design hashes so regenerated identifiers do not masquerade as
electrical edits. Hash equality is not semantic equivalence: native parity,
ERC/DRC, source inspection, and human review answer different questions.

Evidence files retain downloaded bytes; `.gitattributes` prevents line-ending
conversion under `evidence/files/`. Source provenance and hashes must survive
a Windows checkout. A reference schematic, reference PCB, and datasheet are
different evidence roles. Archive integrity alone does not establish coverage
or applicability.

## Code boundaries and checks

- `evidence/` verifies archives and exposes cited extraction and reference
  comparison with explicit unsupported-source findings.
- `schematic/` validates intent, renders functional blocks/hierarchy, checks
  power-symbol clearance, previews in KiCad, and compares native netlists.
- `layout/` resolves real geometry and produces placement/constraint/routing
  proposals without making them current boards.
- `state.py`, `status.py`, and `accept.py` enforce hash freshness, report the
  effective lifecycle, and roll back multi-file schematic updates.
- `tools/kicad-claude-mcp/` is a tested local KiCad dependency until its active
  APIs can be moved to a smaller package.

The existing rule checker implements only a subset of the numbered house
rules; [Design rules](DESIGN_RULES.md) marks that scope. The deviation parser
reads only declared, non-withdrawn rows and never turns a narrow exception
into blanket approval. A parity pass proves the schematic and board agree,
not that either describes the right circuit.

See [Workflow](WORKFLOW.md) for operator commands and
[Limitations](LIMITATIONS.md) for the engineering boundary.
