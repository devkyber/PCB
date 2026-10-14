# PCB workspace instructions

Read [README](README.md), [Workflow](docs/WORKFLOW.md),
[Design rules](docs/DESIGN_RULES.md) and [Limitations](docs/LIMITATIONS.md).

1. Before changing a design, read its `REQUIREMENTS.md`, `DESIGN_BASIS.md`,
   `DEVIATIONS.md`, `review-profile.yaml` and `project.yaml`.
2. Root KiCad files are current. Use `pcb-copilot` and an explicit `--apply`
   for generated changes. Keep existing routed copper unless the checked
   candidate is complete. Applying a change does not approve it for fabrication.
3. Preserve exact evidence bytes and provenance. Do not invent pin maps,
   footprints, electrical limits, owner inputs or engineering conclusions.
4. Use the shared schematic/layout geometry helpers and the scoped parser in
   `src/pcb_copilot/deviations.py`. Keep netmap and native CAD parity current.
   Apply the schematic readability rules in `docs/DESIGN_RULES.md` and inspect
   every rendered sheet before handover. Preserve owner edits; generated intent
   is not authority to replace current CAD.
   For scoped edits, start from saved native CAD and use the native-candidate
   update path. Intent generation is a redraw, not a merge of owner edits.
   Save/close KiCad before external application; unsaved editor buffers are
   unavailable to the file pipeline. Apply must match a successful current preview.
5. Run relevant checks and fault tests. ERC, DRC and routing establish their
   stated scope; human visual, mechanical, RF, thermal and bench review remains.
6. Human sign-off must be named, dated and bound to current CAD, rules, evidence,
   requirements and profile. Never fabricate a sign-off or convert old checkboxes.
7. `release` is the only supported fabrication path. It runs current review and
   publishes a complete package with source/output hashes, or leaves the previous
   package intact. Do not use stale fabrication output.
8. Keep the repository limited to current designs, evidence, active code, focused
   tests and reader docs. Git is the history. Avoid agent-specific hooks,
   duplicated tool installations, generated status files and permanent draft trees.
   Do not assume untracked owner files are recoverable from Git. Before deep
   cleanup, verify an external backup and retain cited final evidence. Use
   `pcb-copilot clean PROJECT` for ordinary preview cleanup; never blanket-delete
   unknown `.pcb-copilot` contents. See the architecture retention policy.
9. Apply the shared Rover lessons in `docs/ARCHITECTURE.md` to every board.
   `review` and `release` always include the mandatory `shared.*` visual and
   layout-handover decisions. Project profiles extend these requirements;
   they cannot remove or weaken them. A policy change invalidates old sign-offs.

```powershell
uv sync
uv run pcb-copilot review projects/rover-pdb
uv run pytest -q
```

Rover is the sole retained board. Preserve its saved CAD and owner boundaries.
The owner requested recreating TMS from requirements on 2026-10-13. Start with
design-bases/tms/README.md; never use the frozen TMS fixture as a starting design.
Carry forward recorded decisions and ask only about unresolved choices.
