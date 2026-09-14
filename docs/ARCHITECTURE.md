# PCB Copilot Architecture

PCB Copilot is an evidence-backed assistant around human-owned KiCad designs.
Its architecture follows one rule: a documented check is useful only when the
workflow invokes it and a fault test proves that it can fail.

## Authority and mutation boundary

Accepted `.kicad_sch` and `.kicad_pcb` files are the electrical and physical
sources of truth. Requirements and explicit owner decisions define intended
behavior. Evidence supports design choices; generators and reports are derived
artifacts.

Read-only operations may inspect accepted files. Generators write separate
drafts under `.pcb-copilot/drafts/`. Acceptance verifies the draft's recorded
base hashes and atomically changes only the requested accepted artifact.
Release requires current review and sign-off bound to both accepted hashes.

```text
requirements + evidence
          |
          v
   typed design intent
          |
          v
transactional draft --> preview + checks --> human acceptance
                                                 |
                                                 v
                                      accepted KiCad design
                                                 |
                                                 v
                                     full review + sign-off
                                                 |
                                                 v
                                      fabrication package
```

## Preserved implementation

The remake wraps proven behavior before relocating it:

- `docs/pipeline.py`: fixed stage order, advisory research, fabrication
  interlock, canonical hashes, repeatability, and ownership tripwire.
- `docs/run_gates.py` and checks: evidence, datasheet, ERC, geometry,
  design-rule, DRC, sign-off, and fabrication decisions.
- `docs/selftest_enforcement.py`: wiring and fault-injection philosophy.
- `docs/deviations.py`: the single scoped-waiver parser.
- `docs/extract_netmap.py` and `docs/check_netlist_parity.py`: connectivity
  derivation and schematic/PCB agreement.
- `docs/schematic_layout_helpers.py`: symbol placement, pin coordinates,
  power symbols, grid handling, and label congestion/crossing protection.
- `docs/pcb_layout_helpers.py`: coordinate transforms, measured extents,
  placement tracking, and collision checks.
- Routing and fabrication scripts: best-of attempts, zone fill, ground
  bonding, stitching, annular repair, fresh DRC, and manufacturing export.
- `tools/kicad-claude-mcp`: tested KiCad editing, hierarchy, routing, sourcing,
  rules, and manufacturing primitives.

Characterization tests and the four-board baseline protect these behaviors.
No compatibility path is removed until its package replacement has equivalent
outputs and zero live callers.

## Package boundaries

`src/pcb_copilot` becomes the stable API and CLI. Current foundation modules
are:

- `project`: safe manifest loading and path containment;
- `models`: project and lifecycle types;
- `state`: canonical hashes, effective lifecycle, ownership, and draft safety;
- `toolchain`: portable KiCad/kipython/router discovery;
- `migration`: preservation inventory and board baselines;
- `status`: read-only operator status.

Later packages own evidence, schematic drafts, layout drafts, review, and
fabrication. Legacy scripts become thin adapters during migration rather than
independent implementations.

## Enforcement tiers

| Tier | Mechanism | Role |
| --- | --- | --- |
| 0 | registered blocking checks | decides release readiness |
| 1 | package invariants | prevents unsafe writes and invalid state |
| 2 | contextual rules/hooks | timely advice and feedback |
| 3 | human documentation | explanation and judgment support |

Hooks are not trusted merely because files exist. Synthetic events must prove
that matchers and entry points fire. Every new blocking check needs a fault
case that mutates a temporary project and observes the expected failure.

## Three assurance questions

The compatibility tools answer different questions:

```powershell
uv run python docs/selftest_enforcement.py
uv run python docs/run_gates.py projects/baro-bmp390/baro-bmp390.kicad_pcb
uv run python docs/audit_workflow.py
```

1. Is the enforcement machinery wired, and can it fail?
2. Does this board pass the currently implemented checks?
3. Were promised workflow controls actually exercised across boards?

The audit calls real gate functions. It must not reimplement their logic and
produce a second answer.

## Review model

Findings are separated into machine failures, engineering warnings, and human
decisions. Each check states what it proves and does not prove. Review runs the
entire registry even after an early failure so one problem does not hide the
rest of the work.

The current compatibility pipeline order is:

```text
env -> research -> sch -> erc -> pcb -> route -> gates -> fab
```

Research is advisory while work is exploratory and blocking at release.
Fabrication runs only after all release conditions pass.

## Scoped deviations

`docs/deviations.py` is the only waiver parser until moved intact. It reads
only rows below `## Declared`, ignores withdrawn rows, and matches scope. A
waiver of decoupling rule `2.2` on one pin cannot excuse missing evidence,
parity, or another component.

## Connectivity and hashes

`netmap.json` remains versioned because a Git diff of it is a reviewable
connectivity diff. It is not deleted until an equally reviewable semantic
replacement exists. Parity asks whether schematic and PCB agree; it does not
decide which side is correct.

Canonical design hashes mask generated KiCad UUIDs before SHA-256. This avoids
false staleness while retaining content drift detection. Hash equality does
not replace semantic checks.

## Coordinates and footprint geometry

All design/MCP/KiCad conversion uses one helper implementation. Inline Y-axis
conversion repeatedly caused plausible-looking but wrong placement. Actual
footprint pads and courtyards are measured before coordinates are selected;
notably, a 1xN header's origin is pin 1 rather than its center.

## Known PCB encoding deviation

Current boards contain short pad nets such as `(net "GND")` without a numeric
net table. KiCad accepts and resolves them, but external parsers may not. A GUI
save can normalize the entire file and create a large diff. Connectivity
checks should use KiCad/pcbnew or the tested parser boundary rather than an
unreviewed regex.

## Recurring defect classes

- check that cannot fail;
- template that satisfies its own gate;
- orphaned tool with no real caller;
- waiver broader than its stated scope;
- second parser or second build path that disagrees;
- fix applied to one board but not propagated;
- gate reading stale output after a failed tool;
- nondeterministic result presented as stable.

The controls are fault injection, non-empty scaffolds, caller inventory,
single implementations, four-board regression, delete-before-generate output
handling, and repeated measurements.

See [Workflow](WORKFLOW.md), [Design rules](DESIGN_RULES.md),
[Project format](PROJECT_FORMAT.md), and [Limitations](LIMITATIONS.md).
