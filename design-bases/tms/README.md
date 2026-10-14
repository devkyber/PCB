# TMS: restart from decisions, not old CAD

The owner requested a fresh TMS design on 2026-10-13. This folder contains
the decision and research basis, without a schematic, PCB, placement recipe,
netmap, old waivers or approval.

Start with [requirements](REQUIREMENTS.md), [decisions and conflicts](DESIGN_BASIS.md),
[reference sources](REFERENCE_REVIEW.md), then the [original PDR](PDR.md).
The PDR and [Rev D BOM](tms-v3-bom.md) are historical source documents.
Their resolved findings, stock, ratings and margin claims need verification.
This basis was transcribed from Git commit 7b8dc18's TMS records; the original
requirements, basis, deviations and review reports remain in Git history.

## A future prompt can be this short

> Recreate TMS in a new projects/tms folder using design-bases/tms as the
> requirements and decision basis. Follow the shared PCB workflow and Rover
> lessons. Carry forward the recorded choices, ask only about unresolved
> decisions that affect the next stage, and create new CAD rather than copying
> the frozen TMS regression fixture.

## Begin the new project

1. Copy templates/project to projects/tms; set its name and CAD filenames to
   tms. Copy this folder's REQUIREMENTS.md, DESIGN_BASIS.md, REFERENCE_REVIEW.md,
   review-profile.yaml, PDR.md, tms-v3-bom.md and evidence/ into the project.
2. Keep the template's empty DEVIATIONS.md. No old pin-distance waiver or
   approval transfers to a fresh design.
3. Resolve reference/input-range, power-budget and mechanical choices before
   their affected circuits are finalized.
4. Create new native CAD. The dated geometry template is under
   templates/jlcpcb-2layer-1oz. Source exact parts and inspect real pin maps.
5. Follow docs/WORKFLOW.md through research, candidate previews, review,
   views and release. An empty project cannot pass CAD review.

The indexed source archive is local so research need not be reconstructed from
chat memory. Recheck revisions and sourcing when choosing new parts. Historical
component_refs in evidence/index.yaml describe the old board; update them to
new designators without changing source bytes.

The retired TMS CAD is under tests/fixtures/boards/tms-v3 solely for hierarchy,
pin-map, geometry and failure-injection tests. It is not a recreation starting
point. Old models, fabrication output, editor history and previews were removed
after verified backup.
