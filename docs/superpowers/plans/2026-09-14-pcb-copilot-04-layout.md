# PCB Copilot Layout Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce safe, reviewable placement and routing proposals from accepted schematics while preserving measured footprint geometry and human control of the final PCB.

**Architecture:** A typed layout-intent file drives existing KiCad PCB APIs, `PlacementTracker`, coordinate transforms, route pipeline, keepout injection, stitching, annular correction, and DRC. All operations target a draft PCB; final placement and routing enter the accepted board only through stale-safe acceptance.

**Tech Stack:** Python 3.10+, Pydantic 2, PyYAML 6, KiCad 10 CLI/pcbnew, `kicad-claude-mcp`, Freerouting as an optional backend, pytest, and existing workspace helpers.

**Spec:** `docs/superpowers/specs/2026-09-14-pcb-copilot-repository-remake-design.md`

## Global Constraints

- Read the four PCB generators, `pcb_layout_helpers.py`, `validate_pcb.py`, routing scripts, and MCP PCB/routing tests before changing them.
- Never route or place directly into an accepted `.kicad_pcb`.
- Resolve the real footprint before selecting coordinates.
- Use one coordinate conversion implementation and verify it against pcbnew.
- Treat autorouting as a candidate only; DRC-clean is not equivalent to good layout.
- Preserve pad-local clearances and report Freerouting limitations.
- Do not accept layout changes without schematic/PCB parity and a human preview.
- Finish each task with a focused commit.

---

### Task 1: Characterize existing layout and validation behavior

**Files:**
- Create: `tests/layout/conftest.py`
- Create: `tests/layout/test_existing_helpers.py`
- Create: `tests/fixtures/kicad/PinHeader_1x04_P2.54mm_Vertical.kicad_mod`
- Create: `tests/fixtures/baseline/layout_metrics.json`
- Modify only for explicit bug fixes: `docs/pcb_layout_helpers.py`, `docs/validate_pcb.py`

**Interfaces:**
- Characterizes: `design_to_mcp`, `design_to_kicad`, `kicad_to_design`, `PlacementTracker.place`, `get_extents_from_file`, and validator check functions
- Produces: `capture_layout_metrics(pcb: Path) -> dict[str, object]` as a test helper

- [ ] **Step 1: Write coordinate round-trip and header-anchor tests**

```python
@pytest.mark.parametrize("point", [(0.0, 0.0), (12.7, 25.4), (100.0, 80.0)])
def test_design_kicad_round_trip(point):
    assert kicad_to_design(*design_to_kicad(*point)) == pytest.approx(point)


def test_one_by_n_header_extent_is_measured_from_pin_one(header_mod):
    pads = local_pad_positions(header_mod.read_text(encoding="utf-8"))
    assert pads["1"] != center_of(pads.values())
```

Define `header_mod` in `tests/layout/conftest.py` to return the checked-in
four-pin fixture path. Define `center_of(points)` in the test module as the
arithmetic mean of the x and y pad coordinates.

Add characterization for pad/courtyard union, rotated extents, off-board pads,
courtyard collisions, connector-class mismatch, symbol/footprint presence,
and DRC freshness.

- [ ] **Step 2: Capture current board metrics**

Record board bounds, refs, footprints, pad counts, net counts, track/via
counts, zone layers, validator statuses, and known DRC result for all four
boards in `layout_metrics.json`.

- [ ] **Step 3: Run tests without changing implementation**

Run: `uv run pytest tests/layout/test_existing_helpers.py -v`

Expected: characterization passes except for separately recorded current bugs;
do not weaken assertions to make an unexpected failure green.

- [ ] **Step 4: Commit the characterization baseline**

```bash
git add tests/layout/conftest.py tests/layout/test_existing_helpers.py tests/fixtures/kicad/PinHeader_1x04_P2.54mm_Vertical.kicad_mod tests/fixtures/baseline/layout_metrics.json
git commit -m "test: characterize PCB layout helpers"
```

### Task 2: Footprint resolution and fidelity

**Files:**
- Create: `src/pcb_copilot/layout/__init__.py`
- Create: `src/pcb_copilot/layout/footprints.py`
- Create: `tests/layout/test_footprints.py`
- Modify: `src/pcb_copilot/models.py`

**Interfaces:**
- Produces: `FootprintCandidate(lib_id: str, path: Path, source: str, fidelity: Literal["real", "standard", "placeholder"], extents_mm: tuple[float, float, float, float], evidence_id: str | None)`
- Produces: `resolve_footprint(project: Project, ref: str, lib_id: str) -> FootprintCandidate`
- Produces: `verify_pin_pad_map(candidate: FootprintCandidate, expected_pins: set[str]) -> list[Finding]`

- [ ] **Step 1: Write failing real-part and placeholder tests**

```python
def test_bmp390_resolves_real_local_footprint(repo_root):
    project = load_project(repo_root / "projects/baro-bmp390")
    result = resolve_footprint(project, "U1", "jlcpcb:LGA-10_L2.0-W2.0-P0.50-BL")
    assert result.fidelity == "real"
    assert set(local_pad_positions(result.path.read_text(encoding="utf-8"))) == {
        str(number) for number in range(1, 11)
    }


def test_placeholder_is_blocking(tmp_path):
    footprint = tmp_path / "generic.kicad_mod"
    footprint.write_text("(footprint generic)", encoding="utf-8")
    candidate = FootprintCandidate(
        lib_id="Generated:Generic_3Pin",
        path=footprint,
        source="generated",
        fidelity="placeholder",
        extents_mm=(-1.0, -1.0, 1.0, 1.0),
        evidence_id=None,
    )
    findings = verify_pin_pad_map(candidate, {"1", "2", "3"})
    assert any(item.blocking and "placeholder" in item.detail for item in findings)
```

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/layout/test_footprints.py -v`

Expected: FAIL because the resolver is absent.

- [ ] **Step 3: Implement resolution using current library tables and helpers**

Search project-local tables first, then configured KiCad libraries. Measure
the union of courtyard and pads using existing helper behavior. A fetched
project-local footprint with provenance is `real`; a known KiCad library
footprint is `standard`; fabricated generic geometry is `placeholder` and
blocks acceptance.

- [ ] **Step 4: Run footprint and MCP sourcing tests**

Run: `uv run pytest tests/layout/test_footprints.py tools/kicad-claude-mcp/tests/test_phase4_sourcing.py -v`

Expected: PASS.

- [ ] **Step 5: Commit footprint resolution**

```bash
git add src/pcb_copilot/layout/footprints.py src/pcb_copilot/models.py tests/layout/test_footprints.py
git commit -m "feat: verify real PCB footprints before placement"
```

### Task 3: Layout intent and constraint schema

**Files:**
- Create: `src/pcb_copilot/layout/models.py`
- Create: `src/pcb_copilot/layout/io.py`
- Create: `tests/layout/test_intent.py`
- Create: `projects/template/layout-intent.yaml`

**Interfaces:**
- Produces: `LayoutIntent`, `BoardOutline`, `PlacementRegion`, `PlacementItem`, `NetClassIntent`, `CriticalNetIntent`, `ZoneIntent`, `RoutePolicy`
- Produces: `load_layout_intent(path: Path) -> LayoutIntent`
- Consumes: accepted schematic refs/nets and project manifest constraints
- Test helpers in `test_intent.py`: `minimal_layout_intent()` returns a valid
  20 mm by 20 mm two-region board with refs `U1` and `C1`; the ignition fixture
  adds net `IGN_FIRE` without `current_a` to isolate that validation failure.

- [ ] **Step 1: Write failing constraint-validation tests**

```python
def test_layout_intent_requires_every_physical_ref():
    accepted_refs = {"U1", "C1"}
    intent = minimal_layout_intent(placements=[PlacementItem(ref="U1", region="sensor")])
    with pytest.raises(LayoutIntentError, match="missing placement intent"):
        validate_layout_intent(intent, accepted_refs)


def test_critical_current_net_requires_current():
    intent_with_ignition_net = minimal_layout_intent(
        critical_nets=[CriticalNetIntent(net="IGN_FIRE", reason="igniter current")]
    )
    with pytest.raises(LayoutIntentError, match="current_a"):
        validate_layout_intent(intent_with_ignition_net, {"U1", "C1"})
```

Add tests for overlapping regions, invalid outline, unknown refs/nets,
duplicate placements, zone nets absent from the schematic, and an impedance
constraint without stackup parameters.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/layout/test_intent.py -v`

Expected: FAIL because the schema is absent.

- [ ] **Step 3: Implement the versioned layout model**

Route policies are `human`, `critical_only`, and `candidate_all`. Default to
`human`. Every critical net states its reason and the values required to
derive its rule: current/duration for power, or impedance/stackup for RF.
Mechanical refs can be marked `pcb_only` explicitly.

- [ ] **Step 4: Run schema and empty-template fault tests**

Run: `uv run pytest tests/layout/test_intent.py -v`

Expected: PASS; an empty template fails rather than satisfying itself.

- [ ] **Step 5: Commit layout intent**

```bash
git add src/pcb_copilot/layout/models.py src/pcb_copilot/layout/io.py projects/template/layout-intent.yaml tests/layout/test_intent.py
git commit -m "feat: define reviewable PCB layout intent"
```

### Task 4: Placement proposal engine

**Files:**
- Create: `src/pcb_copilot/layout/place.py`
- Create: `src/pcb_copilot/layout/render.py`
- Modify: `tests/layout/conftest.py`
- Create: `tests/layout/test_place.py`
- Create: `tests/fixtures/layout/sensor-layout.yaml`
- Modify only with characterization coverage: `docs/pcb_layout_helpers.py`

**Interfaces:**
- Produces: `propose_placement(project: Project, intent: LayoutIntent, draft: DraftRecord) -> PlacementReport`
- Produces: `Placement(ref: str, center: tuple[float, float], rotation_deg: float, extents_mm: tuple[float, float, float, float])`
- Produces: `PlacementReport(placed: dict[str, Placement], findings: list[Finding], pcb_path: Path)`
- Reuses: `PlacementTracker.place()` and `shelf_pack()`

- [ ] **Step 1: Write a failing near-pin placement test**

```python
def test_decoupler_is_measured_from_its_supply_pad(sensor_layout_draft):
    report = propose_placement(
        sensor_layout_draft.project,
        sensor_layout_draft.intent,
        sensor_layout_draft.record,
    )
    assert distance(report.placed["C1"].center, pad_position(report.pcb_path, "U1", "10")) <= 2.0
```

Add tests that a rotated 1xN header remains on-board, a too-small region
raises a finding naming colliding refs, and a fiducial's pad-local clearance
is included in its placement envelope.

Add `sensor_layout_draft` to `tests/layout/conftest.py`; it copies
`baro-bmp390`, loads `tests/fixtures/layout/sensor-layout.yaml`, and creates a
layout `DraftRecord`. Define `distance()` as Euclidean distance and
`pad_position()` as a thin pcbnew lookup helper in the test module.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/layout/test_place.py -v`

Expected: FAIL because placement proposals are absent.

- [ ] **Step 3: Implement region-first, dependency-aware placement**

Place fixed mechanical items first, then ICs/modules, high-frequency
decouplers, bulk capacitors, crystals, protection, connectors, and remaining
passives. For each placement, resolve and measure the actual footprint before
calling `PlacementTracker.place()`. Return findings instead of silently
relocating across functional regions.

- [ ] **Step 4: Run placement and validator tests**

Run: `uv run pytest tests/layout/test_place.py tests/layout/test_existing_helpers.py -v`

Expected: PASS with no off-board pads or courtyard collisions in fixtures.

- [ ] **Step 5: Commit placement proposals**

```bash
git add src/pcb_copilot/layout/place.py src/pcb_copilot/layout/render.py tests/layout/conftest.py tests/layout/test_place.py tests/fixtures/layout/sensor-layout.yaml docs/pcb_layout_helpers.py
git commit -m "feat: propose measured PCB placement drafts"
```

### Task 5: Net classes, zones, and critical-route preparation

**Files:**
- Create: `src/pcb_copilot/layout/constraints.py`
- Create: `tests/layout/test_constraints.py`
- Modify only when covered: `tools/kicad-claude-mcp/src/kicad_claude/adapters/dsn_keepouts.py`

**Interfaces:**
- Produces: `apply_constraints(pcb_path: Path, intent: LayoutIntent) -> ConstraintReport`
- Produces: `ConstraintReport(net_classes: dict[str, str], calculated_widths_mm: dict[str, float], findings: list[Finding])`
- Produces: `calculate_current_width(current_a: float, rise_c: float, copper_oz: float, layer: Literal["external", "internal"]) -> float`
- Produces: `calculate_microstrip_width(impedance_ohm: float, dielectric_height_mm: float, er: float, copper_mm: float) -> float`

- [ ] **Step 1: Write failing constraint tests with known calculations**

Use fixed numeric examples from `docs/DESIGN_RULES.md`. Assert the resulting
net classes are attached to the intended nets, zones reference existing nets,
and footprint/pad-local keepouts survive DSN export.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/layout/test_constraints.py -v`

Expected: FAIL because the constraint module is absent.

- [ ] **Step 3: Implement explicit calculations and application**

Require all physical inputs; never substitute a generic width when current or
stackup is missing. Apply board-wide rules, then retain stricter footprint and
pad rules. Serialize the calculation inputs and result in the report.

- [ ] **Step 4: Run constraint and MCP rule-sync tests**

Run: `uv run pytest tests/layout/test_constraints.py tools/kicad-claude-mcp/tests/test_phase10_rules_sync.py -v`

Expected: PASS.

- [ ] **Step 5: Commit constraints**

```bash
git add src/pcb_copilot/layout/constraints.py tests/layout/test_constraints.py tools/kicad-claude-mcp/src/kicad_claude/adapters/dsn_keepouts.py
git commit -m "feat: apply evidence-backed PCB constraints"
```

### Task 6: Optional candidate-routing backend

**Files:**
- Create: `src/pcb_copilot/layout/route.py`
- Modify: `tests/layout/conftest.py`
- Create: `tests/layout/test_route.py`
- Modify: `docs/route_and_fill.py`
- Modify: `docs/route_best_of.py`
- Modify: `docs/stitch_vias.py`
- Modify: `docs/fix_via_annular.py`
- Reuse: `tools/kicad-claude-mcp/src/kicad_claude/adapters/route_pipeline.py`

**Interfaces:**
- Produces: `route_candidate(project: Project, draft: DraftRecord, policy: RoutePolicy, attempts: int) -> RouteReport`
- Produces: `RouteAttempt(index: int, pcb_path: Path, drc_errors: int, unconnected: int, commands: tuple[str, ...])`
- Produces: `RouteReport(attempts: tuple[RouteAttempt, ...], selected: int | None, drc_errors: int, unconnected: int, limitations: tuple[str, ...])`
- Preserves legacy routing script spellings as wrappers

- [ ] **Step 1: Write failing route-policy tests**

```python
def test_human_policy_never_invokes_router(layout_draft, fake_router):
    report = route_candidate(layout_draft.project, layout_draft.record, RoutePolicy.HUMAN, 1)
    assert fake_router.calls == []
    assert report.selected is None
```

Add tests that route attempts operate on copies, the selected result uses the
fewest unconnected items then fewest DRC errors, post-processing re-runs DRC
without re-routing, stitching is skipped below two pour layers, and annular
repair widens copper without shrinking drills.

Add `layout_draft` to `tests/layout/conftest.py` by publishing the sensor-layout
fixture. Add `fake_router` there as a callable object with `calls: list[list[str]]`;
inject it through the route backend constructor so the human-policy test can
prove no external process was invoked.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/layout/test_route.py -v`

Expected: FAIL because routing orchestration is absent.

- [ ] **Step 3: Wrap the shared route pipeline**

Select a compatible router/JVM using existing measured version behavior. Run
DSN export with injected pad-local keepouts, route a draft copy, import SES,
fill zones, bond ground, conditionally stitch, repair annular rings, and run a
fresh DRC. Record all commands, versions, attempt scores, and known
Freerouting via-keepout limitations.

- [ ] **Step 4: Run offline tests and marked slow smoke test**

Run: `uv run pytest tests/layout/test_route.py tools/kicad-claude-mcp/tests/test_route_pipeline.py -v`

Run: `uv run pytest tools/kicad-claude-mcp/tests/test_phase6_routing.py -m slow -v`

Expected: unit tests pass; the slow test either passes or skips with a precise
missing-tool reason. An unexplained skip is a failure to investigate.

- [ ] **Step 5: Commit candidate routing**

```bash
git add src/pcb_copilot/layout/route.py tests/layout/test_route.py docs/route_and_fill.py docs/route_best_of.py docs/stitch_vias.py docs/fix_via_annular.py
git commit -m "refactor: expose routing as an optional PCB draft backend"
```

### Task 7: Layout preview, review, and stale-safe acceptance

**Files:**
- Create: `src/pcb_copilot/layout/preview.py`
- Create: `src/pcb_copilot/layout/commands.py`
- Modify: `src/pcb_copilot/accept.py`
- Modify: `src/pcb_copilot/cli.py`
- Create: `tests/layout/test_cli.py`
- Modify: `docs/WORKFLOW.md`

**Interfaces:**
- Adds parser positional `project_path`, required `--intent`, and optional
  `--route` choice; concrete form: `pcb-copilot draft-layout projects/baro-bmp390 --intent projects/baro-bmp390/layout-intent.yaml --route human`.
- Extends `accept` for layout draft IDs; concrete form:
  `pcb-copilot accept projects/baro-bmp390 20260914T120000Z-layout-1a2b3c4d`.
- Produces: 2D plot, STEP model when available, DRC report, placement report, route report, and accepted PCB hash

- [ ] **Step 1: Write failing non-overwrite and stale-accept tests**

Assert drafting leaves the accepted PCB hash unchanged. Modify the accepted
schematic after drafting and assert layout acceptance fails because the PCB
proposal was based on a stale circuit.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/layout/test_cli.py -v`

Expected: FAIL because layout CLI/acceptance is absent.

- [ ] **Step 3: Implement previews and acceptance**

Generate visual artifacts in the draft, run placement validation and DRC, and
show machine failures separately from engineering warnings. Acceptance
requires matching schematic and PCB base hashes, parity, no placeholder
footprints, and recorded human preview approval. It does not require routing
completion until release.

- [ ] **Step 4: Run CLI tests and inspect a real small-board draft**

Run: `uv run pytest tests/layout/test_cli.py -v`

Run `draft-layout` for `baro-bmp390` with route policy `human`, open its plot
and STEP preview, and confirm `git diff` shows no accepted PCB change.

- [ ] **Step 5: Commit layout workflow**

```bash
git add src/pcb_copilot/layout/preview.py src/pcb_copilot/layout/commands.py src/pcb_copilot/accept.py src/pcb_copilot/cli.py tests/layout/test_cli.py docs/WORKFLOW.md
git commit -m "feat: review and accept PCB layout drafts"
```

### Task 8: Existing-board layout intents and regression

**Files:**
- Create: `projects/baro-bmp390/layout-intent.yaml`
- Create: `projects/imu-icm42688/layout-intent.yaml`
- Create: `projects/gnss-neom9n/layout-intent.yaml`
- Create: `projects/tms-v3/layout-intent.yaml`
- Create: `tests/layout/test_board_migration.py`
- Modify only after human approval: accepted project `.kicad_pcb` files

**Interfaces:**
- Produces: reproducible placement proposals for all four boards
- Consumes: accepted schematic/netmap, evidence, current PCB generators, and layout baseline

- [ ] **Step 1: Encode current mechanical and layout intent**

Transcribe current outline, fixed items, functional regions, real footprints,
net classes, zones, and known critical nets. Preserve unresolved owner inputs:
TMS igniter current, GNSS RF stackup/antenna constraints, IMU orientation and
mounting rigidity, and barometer standoff pattern.

- [ ] **Step 2: Write baseline comparison tests**

Assert every accepted schematic physical ref has placement intent, PCB-only
mechanical refs are explicit, footprint IDs match current accepted boards,
and known unresolved constraints remain human decisions rather than fabricated
numbers.

- [ ] **Step 3: Generate draft placements for all four boards**

Run `pcb-copilot draft-layout` separately for each literal project path with
route policy `human`, then run `uv run pytest tests/layout/test_board_migration.py -v`.

Expected: no accepted PCB changes; no off-board pads or courtyard overlaps;
reports retain current known warnings and open decisions.

- [ ] **Step 4: Human placement review checkpoint**

Open each draft in KiCad and 3D view. Review connectors, mounting holes,
component access, decoupling, crystal/RF paths, current paths, silkscreen, and
functional flow. Accept only explicitly approved drafts.

- [ ] **Step 5: Commit intent and approved changes per board**

Use four literal commit messages:

```text
refactor: add assisted layout intent for baro-bmp390
refactor: add assisted layout intent for imu-icm42688
refactor: add assisted layout intent for gnss-neom9n
refactor: add assisted layout intent for tms-v3
```

## Plan 4 Completion Check

- [ ] `uv run pytest tests/layout -q` exits `0`.
- [ ] MCP PCB, routing, rule-sync, and manufacturing fast tests pass.
- [ ] Relevant slow tests pass or provide a verified external-tool skip reason.
- [ ] All proposals preserve accepted schematic/PCB parity.
- [ ] No accepted PCB changed outside explicit acceptance.
- [ ] Autorouting remains optional and reports its limitations.
- [ ] Stop for human review before release and cleanup work.
