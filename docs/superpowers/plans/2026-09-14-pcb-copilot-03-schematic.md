# PCB Copilot Schematic Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate readable, evidence-backed schematic drafts with functional blocks, local wiring, hierarchy, rendered previews, netlist parity, and explicit human acceptance.

**Architecture:** A typed schematic-intent file separates circuit intent from KiCad rendering. The renderer reuses `kicad-claude-mcp`, `SymbolPlacer`, `LabelPlacer`, title-block, grid, ownership, and netmap logic, but writes only to a transactional draft workspace until the user accepts the result.

**Tech Stack:** Python 3.10+, Pydantic 2, PyYAML 6, KiCad 10 schematic format/CLI, `kicad-skip`, `kicad-claude-mcp`, pytest, and PDF rendering.

**Spec:** `docs/superpowers/specs/2026-09-14-pcb-copilot-repository-remake-design.md`

## Global Constraints

### Execution checkpoint — 2026-09-17

Tasks 1–7 have implementation commits on `main`. The current command surface
supports transactional drafts, intent validation, local wiring, hierarchy,
PDF/ERC/metrics review artifacts, and explicit schematic acceptance with
stale-file checks, backups, and rollback. Hierarchy connectivity is tested
through KiCad netlist export, including sibling sheets with separate nets.
Preview inspection exposed overlapping hierarchy labels; the renderer now
uses the existing clearance helper and separated sheet-label stubs.
An additional KiCad round-trip test exposed a local-wire short through an
unrelated pin in the two-block fixture. Local routing now considers pin and
label-stub obstacles, searches alternate grid lanes, and validates a complete
route before drawing it. Draft reports also compare the extracted netlist
against every declared intent assignment; acceptance repeats that check.

Task 8 now has intents and source-parity tests for all four real boards,
including component identities, full pin inventories and explicit no-connects.
All four have separate rendered drafts; TMS has an overview plus the six
required functional sheets. No accepted schematic, PCB or netmap was changed.
Actual previews exposed and regression-tested pin-origin mistakes, tall-symbol
row overlap, wires through symbol bodies, inward-facing left labels and fields
inside a body wider than its pins. Remaining visual limitations require human
review; structural metrics do not certify graphical polish.

Generic parts may declare a null pin-map citation only with an explicit review
note, rather than assigning unrelated source IDs. Research findings remain
advisory for draft creation and schematic acceptance, with release requirements
enforced separately. All four projects have reference-research records, but
coverage and copper-view comparison are explicitly incomplete. TMS's
unsupported external-reference claim has been corrected in its design basis;
the ADS1256 reference-voltage circuit itself still needs reconciliation.

The next checkpoint is Task 8 Step 4: human review of specific draft previews.
Do not accept drafts or start Plan 4 layout without that review. Remaining
layout, release, and cleanup work is in Plans 4 and 5.
The product target is supplementary engineering assistance as stated in the
design spec; autonomous human-level design is not an acceptance criterion.

The earlier archive migration restored three text CAD blobs' existing hashed
CRLF bytes in Git, without changing working-tree evidence or accepted designs.
LF/CRLF Git round-trip tests protect that exact-byte policy; upstream archive
whitespace is retained.

Follow-up improvements (2026-09-17): local routes now avoid conservative bounds
around generated power Value text. A bounded, multi-bend fallback handles paths
that cannot use a single alternate lane; existing component placement, stubs,
circuit intent and page boundaries are unchanged. All four drafts were
regenerated and all ten preview pages inspected. The IMU interrupt/GND text and
BMP interrupt/supply text overlaps are corrected. Existing power-glyph/stub
crowding on BMP, GNSS and TMS remains open; neither this inspection nor netlist
parity constitutes human approval or a sheet-wide graphical clearance check.

The IMU evidence archive now includes TDK AN-000493 rev1.0. Its schematic, BOM
and placement views were inspected, but the placement images do not show routed
copper. All four evidence indexes verify (5/7/8/20 records). The initial BMP
Eagle-to-KiCad view failed on undefined layers. A later source-specific derived
copy omitted only 14 invalid dimension/fiducial-restriction objects, preserved
pad/net/track/via/placement/outline geometry through reload, and enabled visual
inspection of explicit front/back copper. Its separate KiCad-refilled view is
an approximation, not Eagle fill or reference DRC validation; the full method
and limits are in the BMP `REFERENCE_REVIEW.md`. Reference archives are unchanged.
The two superseded setup/quick-start guides were removed only after preserving
their useful commands and mutation warnings in WORKFLOW. All 42 stable rule
IDs are retained, with only four explicitly marked as partially automated.

Independent review exposed and regression-tested two fallback precision cases:
slightly off-grid targets could leave a gap, and floating-point noise could
bypass an obstacle before KiCad rounded the saved wire. The final fix checks
the backend's four-decimal geometry and rejects unrepresentable fallback
endpoints without partial drawing. The reviewer approved both corrections.
Fresh CLI drafts again pass all four board checks, with unchanged advisories
and human review pending. All ten pages render pixel-identically to the
visually inspected previews above; the project reference reviews identify the
latest draft IDs. No accepted CAD, netmap or intent was modified.

Further quality follow-up: serialized power-glyph contacts with other stock
power glyphs or visible power Value/local/hierarchical text now appear as
non-blocking review findings. Unsupported geometry, including mirrored glyphs,
is explicitly unchecked. Direct connectivity between ordinary rail glyphs does
not exempt them; only identified intentional flag/rail attachments are exempt.
Regression-first fixes for both mirror handling and overbroad exemptions passed
independent re-review. This is a bounded diagnostic, not an overlap-free claim.

The earlier power-only placement experiment was not adopted: it improved BMP
and GNSS but prevented IMU/TMS drafts from completing. Correcting that requires
coordinating signal stubs/routes or placement; the working renderer remains
unchanged. The current four draft reports identify 2/0/1/3 glyph/text contacts
(BMP/IMU/GNSS/TMS), including TMS J3's GND/LC_SIG_P contact confirmed in an
enlarged PDF view. Accepted CAD, netmaps, intents and sign-offs remain unchanged.
Human preview acceptance and Plans 4/5 remain pending.

Latest verification (e4b0ac1): `uv run pytest -q -m 'not network'` completed
with 436 passed, 49 skipped and 3 deselected in 451.41 seconds. Skipped and
network tests are not claimed as executed. The enforcement self-test passed
93/93 checks in a disposable repository snapshot; source/test Ruff and
whitespace checks passed. All four saved drafts were refreshed with
`review-draft`, returning zero with human review pending. All 61 draft input,
library and metadata hashes remain unchanged, and all ten PDF pages render
identically to the previously inspected previews. All 40 indexed archive
records verify, including committed Git blob hashes. All 20 protected
schematic, PCB, netmap, intent and sign-off hashes match the pre-run snapshot.
Independent code/documentation reviews and the final scoped fix review are
approved for this continuation, not for human acceptance or completion of
Plan 3. The combined suite exposed a fault-injection test that edited during
tool discovery rather than export; it now injects specifically at PDF export
without changing the production snapshot checks.

The CLI tests live in `tests/schematic/test_schematic_cli.py` to avoid pytest
module-name collisions with the evidence CLI tests.

Implemented manual-edit follow-up (Tasks 6/7): `review-draft PROJECT_PATH DRAFT_ID`
refreshes the existing draft's preview/checks without regenerating its CAD.
The original draft metadata and accepted-base hashes remain authoritative;
review never rebases or accepts a draft. Reuse the generation report checks,
reset human review to pending, reject stale bases and inputs changed during
checking, and test failure paths against stale successful artifacts. The
existing intent/netlist check is connectivity-scoped, not a complete check of
part identity, values, footprints or no-connect intent. Human review and the
Plan 4 gate remain unchanged.

- Accepted schematics remain byte-identical until an explicit `accept` command.
- Read `docs/schematic_layout_helpers.py`, all four schematic generators, netmap extraction, quality checks, and MCP schematic tests before changing them.
- Preserve verified symbol identity, pin coordinates, net membership, and explicit no-connects.
- Use graphical power symbols for rails, direct wires inside functional blocks, and labels at block boundaries.
- Use hierarchy rather than shrinking or crowding sheets beyond calibrated capacity.
- Every draft records the accepted base hash; stale drafts cannot be accepted.
- ERC success never substitutes for rendered visual review.
- Existing project generators remain available until board-specific draft parity passes.

---

### Task 1: Transactional draft workspace

**Files:**
- Create: `src/pcb_copilot/drafts.py`
- Create: `tests/schematic/conftest.py`
- Create: `tests/schematic/test_drafts.py`
- Modify: `src/pcb_copilot/models.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `DraftKind(str, Enum)` with `SCHEMATIC` and `LAYOUT`
- Produces: `DraftRecord(id: str, kind: DraftKind, project: str, base_schematic_hash: str, base_pcb_hash: str, created_utc: datetime, root: Path)`
- Produces: `create_draft(project: Project, kind: DraftKind, clock: Callable[[], datetime]) -> DraftRecord`
- Produces: `publish_draft(record: DraftRecord, writer: Callable[[Path], None]) -> Path`

- [ ] **Step 1: Write failing transaction tests**

```python
def test_failed_writer_leaves_no_published_draft(project_copy):
    clock = lambda: datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    record = create_draft(load_project(project_copy), DraftKind.SCHEMATIC, clock)

    def fail(path: Path) -> None:
        path.write_text("partial", encoding="utf-8")
        raise RuntimeError("renderer failed")

    with pytest.raises(RuntimeError, match="renderer failed"):
        publish_draft(record, fail)
    assert not record.root.exists()
    assert (project_copy / "baro-bmp390.kicad_sch").exists()
```

Also assert deterministic draft IDs for a fixed clock and base hashes, paths
under `PROJECT/.pcb-copilot/drafts/`, and no writes outside the draft root.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/schematic/test_drafts.py -v`

Expected: FAIL because draft services are missing.

- [ ] **Step 3: Implement temporary-directory publication**

For draft ID `20260914T120000Z-schematic-1a2b3c4d`, create sibling directory
`.building-20260914T120000Z-schematic-1a2b3c4d`, write `draft.json` plus a
copy of required project/library files, invoke the writer, fsync metadata, and
rename it to `20260914T120000Z-schematic-1a2b3c4d`. The timestamp, kind, and
eight-character base-hash prefix determine the general ID format. On exception,
remove only the validated temporary path.
Never accept a caller-supplied absolute draft root.

- [ ] **Step 4: Run transaction and path-containment tests**

Run: `uv run pytest tests/schematic/test_drafts.py -v`

Expected: PASS and no project mutation.

- [ ] **Step 5: Commit draft transactions**

```bash
git add src/pcb_copilot/drafts.py src/pcb_copilot/models.py tests/schematic/conftest.py tests/schematic/test_drafts.py .gitignore
git commit -m "feat: add transactional PCB draft workspaces"
```

### Task 2: Schematic intent schema

**Files:**
- Create: `src/pcb_copilot/schematic/__init__.py`
- Create: `src/pcb_copilot/schematic/models.py`
- Create: `src/pcb_copilot/schematic/io.py`
- Create: `tests/schematic/test_intent.py`
- Create: `projects/template/schematic-intent.yaml`

**Interfaces:**
- Produces: `SchematicIntent`, `SheetIntent`, `BlockIntent`, `ComponentIntent`, `PinConnection`, `NoConnectIntent`
- Produces: `load_schematic_intent(path: Path) -> SchematicIntent`
- Produces: `save_schematic_intent(intent: SchematicIntent, path: Path) -> None`

- [ ] **Step 1: Write failing schema tests**

```python
def test_intent_requires_every_pin_once():
    component = ComponentIntent(
        ref="U1",
        value="BMP390",
        symbol="jlcpcb:BMP390",
        footprint="jlcpcb:LGA-10_L2.0-W2.0-P0.50-BL",
        block="sensor",
        pins={"1": PinConnection(net="+3V3", style="power")},
        no_connects=set(),
    )
    with pytest.raises(IntentValidationError, match="pin inventory"):
        validate_component_pins(component, expected_pins={str(n) for n in range(1, 11)})
```

Add tests for duplicate refs, unknown blocks, duplicate pin declarations,
unknown connection styles, invalid sheet IDs, and a net label used inside two
blocks without an explicit block-boundary declaration.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/schematic/test_intent.py -v`

Expected: FAIL because intent models are absent.

- [ ] **Step 3: Implement the versioned intent model**

Use `schema_version: 1`. Connection styles are `wire`, `label`, `power`, and
`hierarchical`. Components carry an evidence part number and pin-map evidence
ID. Blocks carry `title`, `sheet`, `flow_order`, and optional placement hints.
No-connects require a non-empty reason.

The template demonstrates a real two-resistor divider with all pins accounted
for; it must not contain angle-bracket placeholders or pass validation while
empty.

- [ ] **Step 4: Run round-trip and empty-template fault tests**

Run: `uv run pytest tests/schematic/test_intent.py -v`

Expected: PASS; deleting the template's blocks causes the validation test to fail.

- [ ] **Step 5: Commit schematic intent**

```bash
git add src/pcb_copilot/schematic projects/template/schematic-intent.yaml tests/schematic/test_intent.py
git commit -m "feat: define evidence-backed schematic intent"
```

### Task 3: UTF-8 and schematic-quality characterization

**Files:**
- Modify: `docs/check_schematic_quality.py`
- Create: `tests/schematic/test_quality.py`
- Create: `src/pcb_copilot/schematic/quality.py`

**Interfaces:**
- Produces: `SchematicMetrics(component_count: int, power_symbol_count: int, junction_count: int, sheet_count: int, drawn_connection_ratio: float, title_complete: bool)`
- Produces: `analyse_schematic(path: Path) -> SchematicMetrics`
- Preserves CLI: `python docs/check_schematic_quality.py BOARD.kicad_pcb`

- [ ] **Step 1: Add a failing Windows-encoding regression test**

```python
def test_quality_reads_utf8_independent_of_locale(tmp_path, monkeypatch):
    schematic = tmp_path / "unicode.kicad_sch"
    schematic.write_text('(title_block (title "압력 센서") (rev "A"))', encoding="utf-8")
    metrics = analyse_schematic(schematic)
    assert metrics.title_complete
```

Add characterization assertions for all four current schematics: component
counts match the recorded baseline, all report zero junctions, and only TMS V3
fails the current density rule.

- [ ] **Step 2: Run and verify the locale-sensitive failure**

Run: `uv run pytest tests/schematic/test_quality.py -v`

Expected: FAIL before the quality module exists; the legacy checker case also
reproduces the default-encoding failure under a cp1252 simulation.

- [ ] **Step 3: Extract analysis and make every text read UTF-8**

Move analysis into the package without changing component-versus-power-symbol
counting. The legacy script becomes a rendering wrapper. Preserve the honest
advisory for zero junctions and the calibrated A4/A3 capacities.

- [ ] **Step 4: Run focused and self-tests**

Run: `uv run pytest tests/schematic/test_quality.py -v`

Run: `uv run python docs/selftest_enforcement.py`

Expected: PASS and the TMS density fault injection still fails when injected.

- [ ] **Step 5: Commit quality extraction**

```bash
git add src/pcb_copilot/schematic/quality.py tests/schematic/test_quality.py docs/check_schematic_quality.py
git commit -m "fix: make schematic quality portable and testable"
```

### Task 4: Functional-block renderer using existing helpers

**Files:**
- Create: `src/pcb_copilot/schematic/render.py`
- Create: `src/pcb_copilot/schematic/wiring.py`
- Modify: `tests/schematic/conftest.py`
- Create: `tests/schematic/test_render.py`
- Create: `tests/fixtures/schematic/two-block.yaml`
- Modify only when a characterization test requires it: `docs/schematic_layout_helpers.py`

**Interfaces:**
- Produces: `render_schematic_draft(project: Project, intent: SchematicIntent, draft: DraftRecord) -> Path`
- Produces: `connect_local(editor, source: PinRef, target: PinRef, corridor: WireCorridor) -> tuple[WireSegment, ...]`
- Produces immutable models `PinRef(ref: str, pin: str)`, `WireCorridor(left: float, top: float, right: float, bottom: float)`, and `WireSegment(start: tuple[float, float], end: tuple[float, float], net: str)` in `wiring.py`
- Produces `count_global_labels(path: Path, name: str) -> int` and `no_symbol_or_text_overlap(path: Path) -> bool` in `quality.py`
- Reuses: `SymbolPlacer`, `LabelPlacer`, `set_title_block_from_project()`, `get_pin_position()`, and MCP hierarchy APIs

- [ ] **Step 1: Write a failing two-block rendering test**

Build an intent fixture with a power/input block and sensor/output block. Assert:

```python
def test_renderer_uses_wires_inside_blocks_and_labels_between_blocks(rendered):
    metrics = analyse_schematic(rendered)
    assert metrics.junction_count >= 1
    assert metrics.drawn_connection_ratio >= 0.60
    assert count_global_labels(rendered, "SENSOR_OUT") == 2
    assert no_symbol_or_text_overlap(rendered)
```

Add `rendered` to `tests/schematic/conftest.py`. It copies the template
project, loads the literal two-block intent stored at
`tests/fixtures/schematic/two-block.yaml`, creates a fixed-clock schematic
draft, renders it, and returns the rendered `.kicad_sch` path.

Also assert rails use graphical power symbols, every symbol lies inside its
page frame, all endpoints are on KiCad's grid, title/revision are present, and
cross-net wire crossings raise `StubCrossingError` before publication.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/schematic/test_render.py -v`

Expected: FAIL because block rendering and local wiring are absent.

- [ ] **Step 3: Implement one-sheet functional rendering**

Sort blocks by `flow_order`, reserve a rectangular lane per block, place
symbols with the current `SymbolPlacer`, connect pins within the same block by
orthogonal wires, and use labels only for declared block boundaries. Use
`LabelPlacer` for congestion, pin-name clearance, and crossing protection.

Do not add a second coordinate conversion. All page/grid conversion routes
through existing helper functions.

- [ ] **Step 4: Run unit tests and KiCad ERC**

Run: `uv run pytest tests/schematic/test_render.py -v`

Run KiCad ERC against the generated fixture. Expected: tests pass, ERC has no
unwaived errors, and the accepted project remains unchanged.

- [ ] **Step 5: Commit one-sheet rendering**

```bash
git add src/pcb_copilot/schematic/render.py src/pcb_copilot/schematic/wiring.py tests/schematic/conftest.py tests/schematic/test_render.py tests/fixtures/schematic/two-block.yaml docs/schematic_layout_helpers.py
git commit -m "feat: render wired functional schematic blocks"
```

### Task 5: Hierarchical-sheet rendering

**Files:**
- Modify: `src/pcb_copilot/schematic/render.py`
- Create: `src/pcb_copilot/schematic/hierarchy.py`
- Modify: `tests/schematic/conftest.py`
- Create: `tests/schematic/test_hierarchy.py`
- Create: `tests/fixtures/schematic/parent-child.yaml`
- Read and reuse: `tools/kicad-claude-mcp/tests/test_phase8_hierarchy_layers.py`

**Interfaces:**
- Produces: `render_hierarchy(editor, intent: SchematicIntent) -> tuple[Path, ...]`
- Produces: `HierarchyDraft(root_schematic: Path, child_paths: tuple[Path, ...])`
- Consumes: MCP `add_sheet_node`, `add_sheet_pin`, and `add_hierarchical_label` behavior

- [ ] **Step 1: Write a failing parent/child connectivity test**

```python
def test_hierarchical_net_survives_round_trip(hierarchical_draft):
    extracted = extract(hierarchical_draft.root_schematic)
    assert extracted["nets"]["U1"]["7"] == "DATA_READY"
    assert hierarchical_draft.child_paths == (Path("sensor.kicad_sch"),)
```

Add failures for duplicate sheet filenames, a hierarchical label without a
matching parent pin, page capacity exceeded without another sheet, and two
different nets assigned to one hierarchical pin.

Add `hierarchical_draft` to `tests/schematic/conftest.py`; it renders
`tests/fixtures/schematic/parent-child.yaml`, whose child `sensor.kicad_sch`
connects `U1.7` to parent net `DATA_READY`, and returns `HierarchyDraft`.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/schematic/test_hierarchy.py -v`

Expected: FAIL because hierarchy orchestration is absent.

- [ ] **Step 3: Implement hierarchy through tested MCP primitives**

Create child sheets before parent symbols, give sheet pins stable names from
the intent, place matching hierarchical labels in each child, and extract the
result through the existing netmap parser. Do not manipulate raw hierarchy
S-expressions outside the MCP adapter.

- [ ] **Step 4: Run hierarchy tests and MCP hierarchy tests**

Run: `uv run pytest tests/schematic/test_hierarchy.py tools/kicad-claude-mcp/tests/test_phase8_hierarchy_layers.py -v`

Expected: PASS.

- [ ] **Step 5: Commit hierarchy support**

```bash
git add src/pcb_copilot/schematic/render.py src/pcb_copilot/schematic/hierarchy.py tests/schematic/conftest.py tests/schematic/test_hierarchy.py tests/fixtures/schematic/parent-child.yaml
git commit -m "feat: render hierarchical KiCad schematic drafts"
```

### Task 6: Preview, review report, and draft-schematic CLI

**Files:**
- Create: `src/pcb_copilot/schematic/preview.py`
- Create: `src/pcb_copilot/schematic/commands.py`
- Modify: `src/pcb_copilot/cli.py`
- Create: `tests/schematic/test_cli.py`
- Modify: `docs/WORKFLOW.md`

**Interfaces:**
- Produces: `render_schematic_preview(toolchain: ToolchainPaths, schematic: Path, output_dir: Path) -> PreviewResult`
- Produces: `PreviewResult(pdf_path: Path | None, erc_report_path: Path, metrics_path: Path, findings: tuple[Finding, ...])`
- Adds parser positional `project_path` plus required `--intent` path; concrete
  form: `pcb-copilot draft-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml`.
- Output: draft ID, schematic path, PDF path, ERC summary, metrics, and unresolved evidence findings

- [ ] **Step 1: Write a failing CLI non-overwrite test**

Copy a small project to a temporary directory, hash its accepted schematic,
run `draft-schematic`, and assert the accepted hash is unchanged while a draft
schematic, PDF, ERC report, and metrics JSON exist under the returned draft ID.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/schematic/test_cli.py -v`

Expected: FAIL because the command is absent.

- [ ] **Step 3: Implement preview and command orchestration**

Run KiCad ERC and PDF export through `ToolchainPaths.kicad_cli`. If PDF export
fails, retain the validated draft but mark preview as a machine failure. If
schematic rendering itself fails, publish nothing.

- [ ] **Step 4: Run tests and manually inspect the fixture PDF**

Run: `uv run pytest tests/schematic/test_cli.py -v`

Open the generated PDF and confirm readable left-to-right flow, no clipped
text, no symbol overlaps, visible local wires, and a complete title block.

- [ ] **Step 5: Commit drafting interface**

```bash
git add src/pcb_copilot/schematic/preview.py src/pcb_copilot/schematic/commands.py src/pcb_copilot/cli.py tests/schematic/test_cli.py docs/WORKFLOW.md
git commit -m "feat: generate reviewable schematic drafts"
```

### Task 7: Stale-safe schematic acceptance

**Files:**
- Create: `src/pcb_copilot/accept.py`
- Modify: `tests/schematic/conftest.py`
- Create: `tests/schematic/test_accept.py`
- Modify: `src/pcb_copilot/cli.py`
- Modify: `src/pcb_copilot/state.py`

**Interfaces:**
- Produces: `accept_schematic(project: Project, draft: DraftRecord) -> AcceptanceResult`
- Produces: `AcceptanceResult(kind: DraftKind, accepted_path: Path, accepted_hash: str, netmap_path: Path, lifecycle: Lifecycle)` and `StaleDraftError`
- Adds parser positionals `project_path` and `draft_id`; concrete form:
  `pcb-copilot accept projects/baro-bmp390 20260914T120000Z-schematic-1a2b3c4d`.
- Consumes: draft base hashes, ERC/quality result, and `extract_netmap.extract()`

- [ ] **Step 1: Write failing stale-base and successful-accept tests**

```python
def test_accept_rejects_stale_base(project_copy, schematic_draft):
    accepted = project_copy / "baro-bmp390.kicad_sch"
    accepted.write_text(accepted.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(StaleDraftError):
        accept_schematic(load_project(project_copy), schematic_draft)
```

The success test must assert atomic schematic replacement, refreshed
`netmap.json`, lifecycle `HUMAN_REVIEWED`, accepted hash recorded, and a diff
containing no PCB change.

Add `schematic_draft` to `tests/schematic/conftest.py`; it renders the
two-block fixture against the copied project and returns the published
`DraftRecord` before any accepted-file mutation.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/schematic/test_accept.py -v`

Expected: FAIL because acceptance is absent.

- [ ] **Step 3: Implement explicit acceptance**

Require a current base hash and successful structural validation. Show the
paths and hashes before modifying anything. Replace the schematic atomically,
derive `netmap.json` from the accepted file, record review state, and retain
the draft for audit until a later cleanup command.

- [ ] **Step 4: Run acceptance and ownership compatibility tests**

Run: `uv run pytest tests/schematic/test_accept.py tests/test_state.py -v`

Expected: PASS, including refusal to accept a stale draft.

- [ ] **Step 5: Commit schematic acceptance**

```bash
git add src/pcb_copilot/accept.py src/pcb_copilot/cli.py src/pcb_copilot/state.py tests/schematic/conftest.py tests/schematic/test_accept.py
git commit -m "feat: accept schematic drafts without silent overwrite"
```

### Task 8: Four-board schematic migration and visual gate

**Reference-research prerequisite (user clarification, 2026-09-16):** For each
board, search both manufacturer and credible open-hardware references for
schematics and PCB layouts. Record queries/outcomes and exact source identity
in `REFERENCE_REVIEW.md`; archive the selected sources, inspect relevant
schematic and layout views, and compare applicability against datasheets and
our design basis. Pair-consistency checks supplement this review. Missing
sources remain advisory findings in drafts, not invented successful research.
All four reviews now exist. Their stated gaps remain open; an archived or
pair-consistent CAD source is not proof of completed PCB visual comparison.

**Files:**
- Create: `projects/baro-bmp390/schematic-intent.yaml`
- Create: `projects/imu-icm42688/schematic-intent.yaml`
- Create: `projects/gnss-neom9n/schematic-intent.yaml`
- Create: `projects/tms-v3/schematic-intent.yaml`
- Create: `tests/schematic/test_board_migration.py`
- Create: `tests/fixtures/schematic-previews/README.md`
- Modify only after approval: accepted project `.kicad_sch` files and `netmap.json`

**Interfaces:**
- Produces: reproducible drafts for all four boards
- Consumes: approved requirements, design bases, evidence indexes, existing generators, and baseline netmaps

- [x] **Step 1: Encode current circuit intent without inventing new design decisions**

For each board, transcribe components, pins, nets, and no-connects from the
accepted schematic/netmap and verify part choices against its design basis.
Do not resolve `[OWNER]` items in intent.

Use these TMS V3 sheets:

1. `power-and-protection`
2. `load-cell-ads1256`
3. `pressure-ads1220`
4. `controller-and-telemetry`
5. `ignition-control`
6. `external-connectors-and-test`

- [x] **Step 2: Write board parity tests before rendering**

For each intent, assert its ref/pin/net map equals the saved baseline except
for `#PWR`/`#FLG` pseudo-references. Assert every physical component belongs to
one block and every cross-sheet net is declared hierarchical.

- [x] **Step 3: Render all four drafts and run automated checks**

Run:

```bash
uv run pcb-copilot draft-schematic projects/baro-bmp390 --intent projects/baro-bmp390/schematic-intent.yaml
uv run pcb-copilot draft-schematic projects/imu-icm42688 --intent projects/imu-icm42688/schematic-intent.yaml
uv run pcb-copilot draft-schematic projects/gnss-neom9n --intent projects/gnss-neom9n/schematic-intent.yaml
uv run pcb-copilot draft-schematic projects/tms-v3 --intent projects/tms-v3/schematic-intent.yaml
uv run pytest tests/schematic/test_board_migration.py -v
```

Expected: every draft has physical-net-group parity; the three small boards
meet their single-sheet capacity; TMS uses six functional child sheets plus an
overview; each board has nonzero junctions and complete title blocks. A child
containing only connectors need not invent junctions to satisfy a metric.
KiCad-qualified local net names remain visible in review and must be reconciled
with PCB names before release; equivalence requires exact complete pin groups.

- [ ] **Step 4: Human visual review checkpoint**

Open all rendered PDFs and KiCad drafts. Record decisions for block grouping,
signal flow, labels, page breaks, and visual polish in the draft review JSON.
Do not accept any board until the user approves its preview.

- [ ] **Step 5: Accept only approved board drafts**

Run `pcb-copilot accept` separately for each approved draft ID. Then run the
existing ERC, schematic-quality, ownership, and parity gates for that board.

Expected: accepted connectivity matches the baseline and any remaining gate
failure is an existing PCB/human-review issue, not schematic drift.

- [ ] **Step 6: Commit each approved board separately**

Use these four literal commit messages, one after each approved acceptance:
`refactor: migrate baro-bmp390 schematic to assisted workflow`,
`refactor: migrate imu-icm42688 schematic to assisted workflow`,
`refactor: migrate gnss-neom9n schematic to assisted workflow`, and
`refactor: migrate tms-v3 schematic to assisted workflow`.

## Plan 3 Completion Check

- [ ] `uv run pytest tests/schematic -q` exits `0`.
- [ ] Existing MCP schematic and hierarchy tests pass.
- [x] `uv run python docs/selftest_enforcement.py` exits `0`.
- [ ] Every accepted schematic's extracted netmap matches its baseline or has a separately approved electrical change.
- [ ] TMS V3 is hierarchical and all boards have nonzero drawn connectivity.
- [x] Accepted files change only through explicit acceptance.
- [ ] Stop for human review before starting layout work.
