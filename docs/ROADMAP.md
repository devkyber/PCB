# Roadmap

PCB Copilot aims to make engineering work easier to reproduce: preserve source
evidence, prepare scoped KiCad changes, check the saved design and produce a
reviewable handover. The current CLI supports those stages; circuit decisions,
visual review and hardware qualification still need an engineer. See
[the workflow](WORKFLOW.md) and [current limits](LIMITATIONS.md).

Work through these implementation priorities in order, using each acceptance
condition to decide when to advance.

## 1. Make first use reproducible

Implemented: the [quickstart](QUICKSTART.md) defaults to the small GPIO board.
Its Python-only demo and explicit Rover selection were reproduced from a fresh
public-source archive with Python 3.11 on Windows. Native GPIO review separately
reported its current assembly and sign-off blockers. Software CI exercises the
demo on Windows and Linux; native qualification on those hosts is a separate step.

Next work:

- Exercise the documented first run on a clean Windows/KiCad 10 environment.
- Add Linux and macOS verification before claiming end-to-end support there.
- Test missing tools and incompatible tool versions, with actionable diagnostics.
- Check the documented commands and expected artifact names in CI where the
  required tools are available.

Done when a fresh environment can follow one documented path to current review
artifacts, with expected review blockers distinguished from environment failures.

## 2. Qualify the reference projects

Implemented: [the four-channel GPIO indicator](../examples/gpio-indicator/README.md)
has its own requirements, exact source evidence, editable native schematic and
routed PCB, local libraries and review profile. The
[scoped-change proof](media/change-proof.md) records a successful preview,
stale-preview rejection, fresh preview and visually inspected apply to a
disposable copy, with unchanged electrical inventories and PCB bytes.

Remaining: the board is an unbuilt educational `DRAFT`. Qualify purchased-part
fit, actual controller drive limits, LED current/brightness and bench behavior.
Resolve assembly rotation contracts and the project's human decisions against
the exact design being reviewed. Add a clean-environment reproduction of the
documented change proof.

Implemented next examples: [USB-C power](../examples/usb-c-power/README.md),
[I²C temperature](../examples/i2c-sensor/README.md) and
[RS-485](../examples/rs485-interface/README.md) each retain native CAD, exact
part evidence, routed copper, full-page visual review and hashed native outputs.
USB-C revision B resolves the original connector conflict with an official
six-contact power-only footprint, retaining manufacturer lands and the existing
geometry rules. All three have clean native ERC/DRC and parity. The sensor and
RS-485 guides include tested, source-backed offline bring-up tools. These remain
unbuilt prototypes with open supplier assembly, physical and human decisions.

Done when the procedure reproduces offline from the archived inputs and the
remaining engineering results have measured evidence. Owner boards and frozen
regression fixtures retain their existing scope; demo runs keep release
decisions unsigned.

## 3. Measure useful checks and engineering effort

Extend checks from a concrete failure case rather than adding broad claims.
For each new check, state the source, supported geometry or circuit pattern,
known exceptions and what remains for a reviewer to decide.

Implemented: a [reproducible fault evaluation](EVALUATION.md) exercises valid
evidence/footprint controls, corrupted inputs, identity checks and optional real
native preview invalidation. It records diagnostics, exit codes, runtime,
environment and source/implementation hashes. This hand-selected set is an
initial regression exercise; broader held-out designs are still needed to
measure missed faults and false positives over a defined population.
Separately measure engineer time for a defined task with and without the
pipeline. Archive the procedure and inputs before claiming a speedup.

Done when another engineer can rerun the evaluation and assess its limits from
the published inputs, procedure and results.

## 4. Make agent-assisted changes easier to inspect

Implemented: [portable offline handovers](HANDOVER.md) keep every native sheet
and board view together with scoped findings and the captured source ledger.
The verifier checks packet bytes, embedded native images/review consistency,
and optional current-project identity without requiring KiCad.

The [interactive example explorer](EXPLORER.md) also exposes current native
pad/net membership, selected-part identities, evidence and board views in one
standalone browser workbench. Its verifier rejects substituted embedded media,
misstated component facts and stale source ledgers.

Use the existing CLI and native-candidate workflow as the integration boundary.
Document one complete agent-assisted task: read requirements and source
evidence, prepare a scoped candidate, inspect the check results and rendered
pages, and hand the engineer the unresolved decisions.

Keep candidate application bound to the successful preview. Provide a concise
handover that names changed parts/nets, preserved CAD, check scope and the exact
review artifacts. Establish this repeatable path before extending the editing
interface.

Done when an engineer can assess a proposed edit from its native candidate and
evidence without reconstructing the assistant's conversation.
