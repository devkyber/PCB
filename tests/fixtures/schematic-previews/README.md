# Four-board schematic review fixtures

The versioned fixtures are each board's `schematic-intent.yaml`, accepted
schematic/netmap and evidence archive. Generated PDFs, ERC and metrics stay
under ignored `.pcb-copilot/drafts/`; they are not design authority.

Regenerate from the repository root:

```powershell
uv run pcb-copilot draft-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml
uv run pcb-copilot draft-schematic projects/imu-icm42688 --intent projects/imu-icm42688/schematic-intent.yaml
uv run pcb-copilot draft-schematic projects/gnss-neom9n --intent projects/gnss-neom9n/schematic-intent.yaml
uv run pcb-copilot draft-schematic projects/tms-v3 --intent projects/tms-v3/schematic-intent.yaml
uv run pytest tests/schematic -q
```

Read each command's exact PDF and `review.json` paths. Expect one page for each
small board and seven for TMS (overview plus six functional sheets). Tests
compare all source component identities, pin assignments and NC markers, then
exercise real KiCad export on copied projects. They do not approve visuals.

## Human review checkpoint

- Inspect every page at readable zoom: block grouping, signal flow, labels,
  power glyphs, component fields, wires, page breaks and titles.
- Remaining known limitations include power-glyph contacts and text near local
  signal wires on dense IC pin columns, plus inefficient overview whitespace.
  A zero command exit code is not a text-collision or engineering certificate.
- Review each project's `REFERENCE_REVIEW.md` for exact research coverage,
  unresolved comparisons and circuit concerns. In particular, reconcile the
  TMS ADS1256 reference-source discrepancy before treating it as a finished
  circuit. No electrical correction is implied by this drawing migration.
- Record the reviewer, exact draft ID and decisions before acceptance. Only
  accept a specific draft after the owner approves its preview. Preserve
  outstanding engineering warnings separately from visual decisions.
- Hierarchical local nets may acquire sheet prefixes. The accepted netmap must
  retain KiCad's true names; reconcile PCB names explicitly before release.

No real board has been accepted by these tests. Plan 4 layout starts only after
the Plan 3 human checkpoint; acceptance does not authorize fabrication.
