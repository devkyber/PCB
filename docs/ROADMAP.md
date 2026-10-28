# Roadmap

PCB Copilot aims to make engineering work easier to reproduce: preserve source
evidence, prepare scoped KiCad changes, check the saved design and produce a
reviewable handover. The current CLI supports those stages; circuit decisions,
visual review and hardware qualification still need an engineer. See
[the workflow](WORKFLOW.md) and [current limits](LIMITATIONS.md).

Work through these implementation priorities in order, using each acceptance
condition to decide when to advance.

## 1. Make first use reproducible

Keep the [quickstart](QUICKSTART.md), environment diagnostics and temporary-copy
demo runnable from a fresh clone. The first result should show the actual
schematic/board, machine findings and unsigned human decisions together.

Next work:

- Exercise the documented first run on a clean Windows/KiCad 10 environment.
- Add Linux and macOS verification before claiming end-to-end support there.
- Test missing tools and incompatible tool versions, with actionable diagnostics.
- Check the documented commands and expected artifact names in CI where the
  required tools are available.

Done when a fresh environment can follow one documented path to current review
artifacts, with expected review blockers distinguished from environment failures.

## 2. Qualify the small reference project

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

Done when the procedure reproduces offline from the archived inputs and the
remaining engineering results have measured evidence. Owner boards and frozen
regression fixtures retain their existing scope; demo runs keep release
decisions unsigned.

## 3. Measure useful checks and engineering effort

Extend checks from a concrete failure case rather than adding broad claims.
For each new check, state the source, supported geometry or circuit pattern,
known exceptions and what remains for a reviewer to decide.

Build a focused evaluation set of valid candidates and injected faults. Report
detected faults, missed faults, false positives, runtime and the environment.
Separately measure engineer time for a defined task with and without the
pipeline. Archive the procedure and inputs before claiming a speedup.

Done when another engineer can rerun the evaluation and assess its limits from
the published inputs, procedure and results.

## 4. Make agent-assisted changes easier to inspect

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
