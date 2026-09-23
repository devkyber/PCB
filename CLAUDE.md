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

```powershell
uv sync
uv run pcb-copilot review projects/baro-bmp390
uv run pytest -q
```

TMS ignition decisions and GNSS RF/antenna questions remain owner work. Consult
project profiles before claiming any board is ready.
