# PCB Copilot

PCB Copilot is a human-controlled assistant for board development. It helps
collect and verify datasheets and reference designs, turn reviewed circuit
intent into an editable KiCad schematic, compare schematic and PCB
connectivity, and prepare layout proposals. It does not decide whether a
circuit is safe, manufacturable, or ready to release.

## Open the current designs

The KiCad files linked here—not files under `.pcb-copilot`—are the current
working designs. All four schematics were updated to functional-block
drawings. The existing routed PCBs were retained; the TMS board changed only
where hierarchy-qualified net names and their project net classes had to
follow the new schematic.

| Board | Current schematic | Current PCB | Present boundary |
| --- | --- | --- | --- |
| BMP390 | [KiCad](projects/baro-bmp390/baro-bmp390.kicad_sch) | [KiCad](projects/baro-bmp390/baro-bmp390.kicad_pcb) | Human schematic review and environmental/mechanical decisions pending. |
| ICM-42688 | [KiCad](projects/imu-icm42688/imu-icm42688.kicad_sch) | [KiCad](projects/imu-icm42688/imu-icm42688.kicad_pcb) | Axis orientation, mounting, and human layout review pending. |
| NEO-M9N | [KiCad](projects/gnss-neom9n/gnss-neom9n.kicad_sch) | [KiCad](projects/gnss-neom9n/gnss-neom9n.kicad_pcb) | Antenna, RF stack-up, and layout blockers pending. |
| TMS V3 | [Seven-sheet KiCad project](projects/tms-v3/tms-v3.kicad_sch) | [KiCad](projects/tms-v3/tms-v3.kicad_pcb) | Ignition safety, reference source, thermal, and physical-fit decisions pending. |

Open the root `.kicad_sch` in KiCad; TMS's six child sheets must remain beside
it. Each board's requirements, design basis, reference review, deviations,
project-specific `review-profile.yaml`, and archived `evidence/` are in its
project directory. No board has
complete, hash-bound human sign-off or release approval for its current design.

## Start here

Install [uv](https://docs.astral.sh/uv/) and KiCad 10, then from the repository
root run:

```powershell
uv sync
uv run pcb-copilot status projects/baro-bmp390
uv run pcb-copilot research projects/baro-bmp390 --verify
uv run pcb-copilot update-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml
uv run pcb-copilot review projects/baro-bmp390
```

The last command previews and checks a candidate without changing the root
design. Add `--apply` only when you intend to update the current schematic;
the change returns its lifecycle to `DRAFT` and requires human review. TMS's
hierarchy uses `--reconcile-board-names` when a new schematic has exactly the
same pad membership but different local net names; the command also checks
that KiCad net-class rules are preserved.

`research` can verify exact archived bytes, produce search plans, and inspect
supported reference schematic/PCB pairs. Search plans are not live searches.
The current layout tool produces proposals. `review` runs the current checks
against a disposable project copy and reports blockers and their exact scope;
it does not approve the design. The review now requires dated, named decisions
bound to the current files; none are auto-signed. A single current-file
`update-layout` and transactional `release` are still being built.
Do not replace a routed PCB with an unrouted proposal.

For commands and judgment boundaries, read [Workflow](docs/WORKFLOW.md) and
[Limitations](docs/LIMITATIONS.md). Maintainers can use
[Architecture](docs/ARCHITECTURE.md) and [Design rules](docs/DESIGN_RULES.md).
