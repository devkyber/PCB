# Working with a board

Open the root schematic and PCB under `projects/BOARD/`; TMS has six child sheets.
Read its requirements, design basis, reference review, deviations and review profile.

## 1. Check the current state and sources

```powershell
uv sync
uv run pcb-copilot status projects/baro-bmp390
uv run pcb-copilot research projects/baro-bmp390 --verify
uv run pcb-copilot research projects/baro-bmp390 --search-plan BMP390
uv run pcb-copilot research projects/baro-bmp390 --extract BMP390
```

Archive documents with `research PROJECT --add PART URL --role ROLE` before citing
them. Reference schematic/PCB pairs can be compared with `--inspect-reference
SCHEMATIC_ID PCB_ID`. Search plans propose queries, not live search results.
The datasheet outranks a reference circuit. Record adopted choices and disagreements
in `DESIGN_BASIS.md`. Hash verification proves archive identity, not suitability.

### LCSC parts and library import

```powershell
uv run pcb-copilot parts projects/baro-bmp390 --lookup C5124834
uv run pcb-copilot parts projects/baro-bmp390 --import C5124834 --mpn BMP390
```

Lookup fetches the exact supplier record for a C-number. Import requires a
matching manufacturer part number, converts the real symbol/footprint/models,
normalizes the footprint with native KiCad, and registers a separate `lcsc_C...`
project library. Existing imported libraries are preserved. Failed downloads or
conversion leave the project unchanged; no placeholder geometry is substituted.
Supplier JSON is archived as `cad_library` evidence with `supplier` provenance.
It does not satisfy a datasheet or reference-design requirement.

Use the returned `symbol` and `footprint` IDs in schematic intent; the optional
component `lcsc: C5124834` field verifies/preserves sourcing identity. Imported
library sourcing properties survive schematic generation. Update the PCB from
the schematic in KiCad and supply it with `--pcb`; BOM export reads its LCSC field.
Review blocks release if a selected schematic C-number differs from the PCB.
Archive the exact manufacturer datasheet using `research --add ... --role datasheet`,
then verify package dimensions and pin functions. `--lookup` is a C-number lookup,
not a live stock/price quote or a keyword catalog search.

## 2. Update the schematic

```powershell
uv run pcb-copilot update-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml
```

Inspect the PDF, native ERC and findings at the returned paths. Add `--apply` to
install a checked candidate. The command preserves the root design on failure,
updates hierarchical sheets and netmap together, and returns the lifecycle to
`DRAFT`. It requires exact PCB connectivity. `--reconcile-board-names` handles
hierarchy-qualified net renames only when pad membership and native rules agree.
For a circuit change, supply its matching, routed PCB with the new intent:

```powershell
uv run pcb-copilot update-schematic projects/baro-bmp390 --intent C:/designs/new-intent.yaml --pcb C:/designs/new-board.kicad_pcb --apply
```

This checks the PCB against the generated schematic, refills zones, runs DRC and
installs schematic, intent, netmap and PCB together. Preview first by omitting
`--apply`. This path replaces the old circuit intentionally; the old layout intent
is not used to constrain a different circuit. Update that intent before future
placement generation. Manual KiCad edits remain possible; reconcile intent and
netmap afterward.

## 3. Update the layout

```powershell
uv run pcb-copilot update-layout projects/baro-bmp390 --intent projects/baro-bmp390/layout-intent.yaml
uv run pcb-copilot update-layout projects/baro-bmp390 --candidate C:/designs/baro-bmp390.kicad_pcb
```

An intent produces placement/routing candidates. Default `human` routing does not
invoke an autorouter; incomplete candidates are previewable but blocked from apply.
`--route candidate_all` requests the optional Freerouting backend, which requires
Java and a configured `FREEROUTING_JAR`. Unsupported critical-only routing remains
blocked rather than silently routing other nets.

`--candidate` checks a board edited and routed in KiCad, using companion project
settings/custom rules when supplied. Both paths fill zones, check physical parts
and connectivity, run fresh DRC twice, compare copper/footprints/pours and render
preview artifacts. Review those artifacts, then use `--apply`. A candidate with
unconnected items, missing parts or lost routing cannot replace the current board.
Applying is a working-design update and invalidates prior release state.

## 4. Review and record human decisions

```powershell
uv run pcb-copilot review projects/baro-bmp390
uv run pcb-copilot review projects/baro-bmp390 --format json
uv run pcb-copilot prepare-signoff projects/baro-bmp390
```

Review runs ten checks against a disposable copy: research, datasheets, ERC,
netmap freshness, physical/net parity, placement, geometric house rules, DRC,
schematic quality and sign-off. Each result names its scope. A failed check does
not hide later results. Optional `--output` creates a new JSON/Markdown report
under `.pcb-copilot/reports/` without overwriting earlier reports.

`prepare-signoff` creates an unsigned `review-signoff.yaml` only when absent.
The responsible human completes each profile item with a reviewer, ISO date,
`accepted`/`rejected` decision and note after actual inspection or measurement.
Hashes bind decisions to the current inputs. If inputs change, preserve the old
record in Git, remove the stale worksheet and prepare a new one; do not merely
refresh hashes under an old signature.

## 5. Release

```powershell
uv run pcb-copilot release projects/baro-bmp390
```

Release reruns the complete review, including current human decisions. A blocked
review produces findings and no new fabrication package. Success publishes
`fabrication/` containing Gerbers, Excellon drills, BOM, native positions, JLCPCB
CPL, review, source files and `SOURCE.json`. Native exports must succeed and
produce required outputs; failed publication restores the previous package.

Sources and outputs are hashed. `status` stops reporting `RELEASED` if inputs or
package contents change. Generated Gerber timestamps can vary between runs.
Check assembler orientation and unsourced/manual-fit components in the assembly
preview. This command prepares files; it does not place an order.

Keep `netmap.json`, intent and current CAD in Git. Ignore `.pcb-copilot/` and
`fabrication/`. Neither generated output nor a green machine check replaces the
engineering work in [Limitations](LIMITATIONS.md).

## Interrupted updates

Updates and releases keep recovery originals until publication succeeds. Ctrl+C
and ordinary failures restore the prior files. If restoration itself fails, the
error identifies `.pcb-copilot/recovery-*/`; an operation lock remains to prevent
another update. Inspect its journal and restore the named originals before
removing the recovery directory and `operation.lock`. A release recovery also
retains the previous fabrication package and state. If a process is forcibly
terminated before any recovery journal exists, confirm no pipeline process is
running before removing its stale lock. Keep a copy of recovery data until the
restored design has been checked.
