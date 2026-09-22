# Working with a board

PCB Copilot supplies evidence, an editable starting schematic, and checks. The
engineer owns requirements, circuit choices, PCB judgment, physical tests, and
release. The current KiCad design is always the root `.kicad_sch`, child sheets,
`.kicad_pcb`, and `.kicad_pro` inside `projects/BOARD/`.

## 1. Open and understand the current design

Start at the [four current projects](../README.md#open-the-current-designs),
not a hidden draft directory. In the board folder, read `REQUIREMENTS.md`,
`DESIGN_BASIS.md`, `REFERENCE_REVIEW.md`, `DEVIATIONS.md`, `review-profile.yaml`, and
`project.yaml`. Open the root KiCad schematic and PCB. Keep any hierarchical
child sheets beside the root; TMS V3 has six.

```powershell
uv sync
uv run pcb-copilot status projects/baro-bmp390
```

`status` is read-only. `DRAFT` means no current human approval, even when a
machine check passed. An old sign-off does not survive a design change.

## 2. Research before copying a circuit

Datasheets, reference schematics, and reference PCB layouts are three separate
deliverables. Search manufacturer EVMs and integration guides, then credible
open hardware. Record query, date, exact part/variant, source URL, what was
unavailable, and the reason a reference applies or does not apply in the
board's `REFERENCE_REVIEW.md`. Archive exact source bytes and provenance in
`evidence/`; the datasheet outranks a conflicting reference design.

```powershell
uv run pcb-copilot research projects/baro-bmp390 --verify
uv run pcb-copilot research projects/baro-bmp390 --search-plan BMP390
uv run pcb-copilot research projects/baro-bmp390 --extract BMP390
uv run pcb-copilot research projects/baro-bmp390 --inspect-reference SCHEMATIC_ID PCB_ID
```

`--verify` checks indexed bytes, hashes, media types, and URLs—not source
completeness. `--search-plan` proposes queries; it does not search the web.
`--extract` reports supported cited CAD facts and items needing human review.
`--inspect-reference` compares an archived Eagle schematic/board pair's pad
membership, packages, and explicit values. It does not prove routing quality,
return paths, RF behavior, mechanical fit, or suitability for this board.
Keep “searched”, “archived”, “inspected”, and “compared” distinct. Record any
adopted design choice and its source in `DESIGN_BASIS.md`.

## 3. Preview or update the current schematic

Edit `schematic-intent.yaml` only from reviewed circuit facts. Every connected
pin, explicit no-connect, reference, value, and footprint needs a deliberate
contract. Preview first:

```powershell
uv run pcb-copilot update-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml
```

The command generates a temporary candidate, runs structural review, KiCad
ERC/PDF export, and exact schematic/PCB connectivity parity, then reports
findings and preview paths. It does not edit the root design without `--apply`.
Inspect every PDF sheet in KiCad as well as ERC; the graphical collision
diagnostic checks only supported power glyph/text geometry.

When you deliberately want the checked candidate to become the current
working schematic, rerun with `--apply`. A failed generation or validation
leaves current files unchanged. A successful apply updates the root schematic
and `netmap.json` transactionally and sets lifecycle to `DRAFT`, not human
reviewed. For a hierarchical change that only renames PCB nets while retaining
exact pad membership, add `--reconcile-board-names`; it checks native KiCad
parity and preserves project net-class settings. It refuses changed pin groups
or rule values. This is for name reconciliation, not circuit redesign.

You may also edit the current root KiCad design directly. The tool does not
infer or adopt those manual edits into intent automatically; reconcile intent,
netmap, and PCB, then rerun appropriate checks. Use Git for history and
rollback. Generated `.pcb-copilot/preview/` reports are local aids, not the
design to open or an approval record.

## 4. Layout remains a proposal workflow

The package can inspect real footprints, check placement constraints, and
generate isolated PCB proposals from `layout-intent.yaml`:

```powershell
uv run pcb-copilot draft-layout projects/baro-bmp390 --intent projects/baro-bmp390/layout-intent.yaml --route human
```

This command does not update the root PCB. The proposed boards are not
fabrication candidates merely because placement or DRC checks run. In
particular, the retained root PCBs have routing that the newer placement
proposals do not preserve. A single transactional `update-layout` command
with non-regression, routing, DRC, and visual gates is still missing. Do not
copy an unrouted proposal over a routed current PCB. Human review must cover
decoupling/return paths, connectors, mechanical access, RF, thermal, copper
widths, pours, silkscreen, and assembly.

## 5. Review and release boundary

Run the current-design review after schematic or PCB changes:

```powershell
uv run pcb-copilot review projects/baro-bmp390
uv run pcb-copilot review projects/baro-bmp390 --format json
uv run pcb-copilot review projects/baro-bmp390 --format markdown --output projects/baro-bmp390/.pcb-copilot/reports/manual.md
```

This runs all ten registered checks against a disposable copy, so KiCad report
generation cannot rewrite the current project. The optional Markdown/JSON
report may be written only as a new file under ignored `.pcb-copilot/reports/`;
it cannot overwrite a prior report or a design file. A failure does not hide later
checks. The report includes full-content fingerprints for the root schematic
and every referenced child sheet, plus the PCB, and states what each check
does and does not prove. Schematic structural quality now covers every sheet;
label-heavy sheets produce nonblocking engineering warnings, not a false
claim of readability. Legacy gate scripts still supply most checks while they
are migrated. The new human check uses board-specific `review-profile.yaml`
and optional `review-signoff.yaml` records. Each accepted decision needs a
reviewer, date, note, and the exact current schematic, PCB, and profile hashes;
old `SIGNOFF.md` ticks do not count. No decision is filled automatically.
Transactional `release` is not implemented, so review does not create
fabrication authority.

After reviewing the profile and the actual KiCad design, the human operator
can prepare an unsigned worksheet:

```powershell
uv run pcb-copilot prepare-signoff projects/baro-bmp390
```

This creates `review-signoff.yaml` only if absent and pre-fills current hashes.
It leaves reviewer, date, decision, and note blank. The responsible human must
make each decision from actual inspection or measurement; use `accepted` or
`rejected` and ISO `YYYY-MM-DD` dates. Do not let an assistant sign on the
human's behalf. Re-run `review` afterward. An edited schematic, PCB, or review
profile makes prior decisions stale; `prepare-signoff` never overwrites them.

Do not run the full legacy `scripts/pipeline.py` on a current board:
its generator stages can overwrite root CAD before its draft-only routing
boundary rejects the route. Never equate a green ERC, DRC, or parity result
with engineering approval. The board's `review-profile.yaml` lists the human
work still required; unsigned, rejected, or stale decisions block responsible
fabrication. The old `SIGNOFF.md` remains only for legacy script compatibility.

If you run `scripts/selftest_enforcement.py`, use a disposable repository
copy. It injects faults by temporarily changing evidence files and board
timestamps; interruption could leave those files changed.

See [Limitations](LIMITATIONS.md) for board-specific open questions and
[Design rules](DESIGN_RULES.md) for the implemented versus human rule scope.
