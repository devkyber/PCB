# PCB Copilot Review, Release, and Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify proven checks into a complete typed review, require hash-bound project-specific human sign-off, export fabrication files transactionally, and delete only verified superseded files.

**Architecture:** Existing gate functions are adapted into one review registry rather than reimplemented. Release always executes the complete registry, validates dated human decisions against accepted design hashes, and publishes fabrication output atomically; cleanup runs last from an explicit inventory.

**Tech Stack:** Python 3.10+, Pydantic 2, KiCad 10 CLI/pcbnew, pytest, current gate and fabrication code, SHA-256, Markdown/JSON reports, and Git.

**Spec:** `planning/specs/2026-09-14-pcb-copilot-repository-remake-design.md`

## Global Constraints

- Read every current gate, audit, self-test, human-work, fabrication, hook, and caller before modification.
- A review runs every check even when earlier checks fail.
- A check states exactly what it proves and whether it is deterministic, heuristic, or human.
- Every blocking check has a fault-injection test.
- Human sign-off is project-specific, dated, and bound to accepted schematic/PCB hashes.
- Fabrication output is generated only from the accepted released revision.
- Every deletion requires an inventory rule, verified replacement, zero inbound callers, and Git recoverability.
- Do not weaken known board failures to obtain a green suite.
- Reference schematic and PCB research have equal priority with datasheets.
  The release review must distinguish search outcomes, archive integrity,
  inspection, and applicability comparison for each required reference type;
  a generic `reference_design` archive record alone is not completion.
  Missing native CAD may be documented with the searches performed and an
  explicit human disposition, never silently counted as validated layout.
  Keep incomplete research advisory while drafting; require a recorded
  disposition for unresolved research at release. This gate is planned here,
  not yet implemented by the current research CLI.
- Finish each task with a focused commit.

---

### Task 1: Typed findings and check registry

**Files:**
- Create: `src/pcb_copilot/review/__init__.py`
- Create: `src/pcb_copilot/review/models.py`
- Create: `src/pcb_copilot/review/registry.py`
- Create: `src/pcb_copilot/review/legacy.py`
- Create: `tests/review/conftest.py`
- Create: `tests/review/test_registry.py`
- Modify: `src/pcb_copilot/models.py`

**Interfaces:**
- Produces: `FindingKind`, `Finding`, `CheckScope`, `CheckResult`, and `ReviewReport`
- Produces: `ReviewReport(project: str, schematic_hash: str, pcb_hash: str, results: tuple[CheckResult, ...], findings: tuple[Finding, ...], blocking: bool)`
- Produces: `Check(Protocol)` with `check_id`, `scope`, and `run(project: Project) -> CheckResult`
- Produces: `run_checks(project: Project, checks: Sequence[Check]) -> ReviewReport`
- Consumes: existing `run_gates.GATES` through adapters

- [ ] **Step 1: Write failing complete-run and crash-isolation tests**

```python
def test_registry_runs_checks_after_failure(sample_project):
    calls = []
    checks = [FakeCheck("first", False, calls), FakeCheck("second", True, calls)]
    report = run_checks(sample_project, checks)
    assert calls == ["first", "second"]
    assert [result.check_id for result in report.results] == ["first", "second"]


def test_crashed_check_becomes_blocking_finding(sample_project):
    report = run_checks(sample_project, [CrashingCheck("broken")])
    assert report.findings[0].kind == FindingKind.MACHINE_FAILURE
    assert report.findings[0].blocking
    assert "check crashed" in report.findings[0].detail
```

Define `sample_project` in `tests/review/conftest.py` as `load_project()` over
a `tmp_path` copy of `baro-bmp390`. Define `FakeCheck` and `CrashingCheck` in
`test_registry.py`; `FakeCheck.run()` appends its ID and returns one configured
passing/failing `CheckResult`, while `CrashingCheck.run()` raises
`RuntimeError("check crashed")`.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/review/test_registry.py -v`

Expected: FAIL because review types and registry are absent.

- [ ] **Step 3: Implement immutable results and legacy adapters**

`CheckScope` contains `proves`, `does_not_prove`, `deterministic`, and
`requires_external_tool`. `run_checks()` catches exceptions per check, records
duration, continues, and derives overall blocking status without converting
warnings or human decisions into machine passes.

Wrap the existing gate callables and preserve their detail text. Do not copy
their parsing logic into `legacy.py`.

- [ ] **Step 4: Run registry and current gate tests**

Run: `uv run pytest tests/review/test_registry.py -v`

Run: `uv run python scripts/selftest_enforcement.py`

Expected: PASS and the legacy gate registry remains intact.

- [ ] **Step 5: Commit the review registry**

```bash
git add src/pcb_copilot/review src/pcb_copilot/models.py tests/review/conftest.py tests/review/test_registry.py
git commit -m "feat: add complete typed PCB review registry"
```

### Task 2: Move check primitives behind package boundaries

**Files:**
- Create from current implementations: `src/pcb_copilot/review/deviations.py`
- Create from current implementations: `src/pcb_copilot/review/netmap.py`
- Create from current implementations: `src/pcb_copilot/review/parity.py`
- Create from current implementations: `src/pcb_copilot/review/pcb_geometry.py`
- Create from current implementations: `src/pcb_copilot/review/design_rules.py`
- Create: `tests/review/test_behavior_parity.py`
- Modify into compatibility entry points: `scripts/deviations.py`, `scripts/extract_netmap.py`, `scripts/check_netlist_parity.py`, `scripts/validate_pcb.py`, `scripts/check_design_rules.py`

**Interfaces:**
- Preserves: current public functions and CLI exit behavior
- Produces: `parse_deviations(project: Path) -> DeviationSet`
- Produces: `extract_netmap(schematic: Path) -> NetMap`
- Produces: `DeviationSet(entries: tuple[Deviation, ...])`, where each `Deviation` retains rule ID, refs, rationale, approver, and date
- Produces: `NetMap(refs: dict[str, dict[str, str]], source_hash: str)`
- Produces: `compare_netlists(schematic: Path, pcb: Path) -> list[Finding]`
- Produces: `check_pcb_geometry(project: Project) -> list[Finding]`
- Produces: `check_design_rules(project: Project) -> list[Finding]`

- [ ] **Step 1: Write behavior-parity tests before moving code**

For all four boards, capture current parsed deviations, extracted netmaps,
parity result, geometry statuses, and design-rule statuses. Add exact fault
fixtures for missing net assignments, a renamed net, out-of-board header pads,
courtyard collision, connector-class mismatch, and a too-wide deviation.

- [ ] **Step 2: Run the parity tests against current code**

Run: `uv run pytest tests/review/test_behavior_parity.py -v`

Expected: PASS against the characterization fixtures before relocation.

- [ ] **Step 3: Relocate one primitive at a time**

For each source script, move its parsing/checking functions into the named
package module, keep its legacy command as a thin argument/output adapter, run
the focused parity test, and commit only after the output and exit code match.
The deviation parser remains singular: package callers import the relocated
implementation and the old path re-exports it.

- [ ] **Step 4: Run full check and fault-injection suites**

Run: `uv run pytest tests/review -q`

Run: `uv run python scripts/selftest_enforcement.py`

Run: `uv run python scripts/audit_workflow.py`

Expected: zero test failures; audit and gates agree for every adapted check.

- [ ] **Step 5: Commit relocated primitives**

```bash
git add src/pcb_copilot/review tests/review scripts/deviations.py scripts/extract_netmap.py scripts/check_netlist_parity.py scripts/validate_pcb.py scripts/check_design_rules.py
git commit -m "refactor: preserve PCB checks behind package APIs"
```

### Task 3: Enforcement strength registry

**Files:**
- Create: `src/pcb_copilot/review/faults.py`
- Create: `tests/review/test_fault_injection.py`
- Modify: `scripts/selftest_enforcement.py`

**Interfaces:**
- Produces: `FaultCase(id: str, check_id: str, mutate: Callable[[Path], None], expected_summary: str)`
- Produces: `run_fault_case(case: FaultCase, fixture_project: Path) -> FaultResult`
- Produces: `default_registry() -> tuple[Check, ...]` and `registered_fault_cases() -> tuple[FaultCase, ...]`
- Consumes: the same registered checks used by normal review

- [ ] **Step 1: Write a meta-test that rejects untested blocking checks**

```python
def test_every_blocking_check_has_a_fault_case():
    blocking = {check.check_id for check in default_registry() if check.can_block}
    covered = {case.check_id for case in registered_fault_cases()}
    assert blocking <= covered
```

Add a containment test that snapshots every live `projects/` file before and
after fault execution and asserts no live hash changes.

- [ ] **Step 2: Run and verify uncovered checks**

Run: `uv run pytest tests/review/test_fault_injection.py -v`

Expected: FAIL listing blocking checks without registered faults.

- [ ] **Step 3: Port and complete fault cases**

Port the current HTML-as-PDF, reference removal, narrow-waiver, stale-netmap,
parity, density, title, ownership, repeatability, stale-DRC, and sign-off
faults. Add faults for every new lifecycle, evidence, draft, and release
check. Each case copies a real fixture project into a unique temporary root.

- [ ] **Step 4: Run the registry twice**

Run: `uv run pytest tests/review/test_fault_injection.py -v`

Run the same command again. Expected: both runs pass with identical case IDs
and no changes under live `projects/`.

- [ ] **Step 5: Convert the old self-test into a compatibility wrapper**

`scripts/selftest_enforcement.py` invokes the package fault runner and preserves
its current nonzero-on-failure contract. Run it directly and assert exit `0`.

- [ ] **Step 6: Commit enforcement strength tests**

```bash
git add src/pcb_copilot/review/faults.py tests/review/test_fault_injection.py scripts/selftest_enforcement.py
git commit -m "test: require fault coverage for blocking PCB checks"
```

### Task 4: Project-specific human review profiles

**Files:**
- Create: `src/pcb_copilot/review/signoff.py`
- Create: `tests/review/test_signoff.py`
- Create: `projects/template/review-profile.yaml`
- Create: `projects/baro-bmp390/review-profile.yaml`
- Create: `projects/imu-icm42688/review-profile.yaml`
- Create: `projects/gnss-neom9n/review-profile.yaml`
- Create: `projects/tms-v3/review-profile.yaml`
- Modify: `tests/review/conftest.py`
- Modify: project `SIGNOFF.md` files

**Interfaces:**
- Produces: `ReviewItem(id: str, prompt: str, rationale: str, evidence_refs: tuple[str, ...], safety_tags: tuple[str, ...])`
- Produces: `SignoffRecord(item_id: str, reviewer: str, signed_on: date, schematic_hash: str, pcb_hash: str, decision: Literal["accepted", "rejected"], note: str)`
- Produces: `check_signoff(project: Project) -> list[Finding]`

- [ ] **Step 1: Write failing relevance and hash-binding tests**

```python
def test_barometer_profile_has_no_xt60_question(repo_root):
    profile = load_review_profile(repo_root / "projects/baro-bmp390")
    assert all("XT60" not in item.prompt for item in profile.items)


def test_signoff_for_old_hash_is_blocking(reviewed_project):
    reviewed_project.pcb_path.write_text("changed", encoding="utf-8")
    findings = check_signoff(reviewed_project)
    assert any(item.blocking and "stale" in item.detail for item in findings)
```

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/review/test_signoff.py -v`

Expected: FAIL because review profiles do not exist.

- [ ] **Step 3: Define relevant board profiles**

The barometer profile covers sensor port/coating, supply ripple measurement,
connector orientation, mounting, physical footprint, and BOM. The IMU profile
covers axis orientation, ±16 g suitability, mounting rigidity, rail noise,
header orientation, and BOM. The GNSS profile covers LDO headroom, passive
versus active antenna, RF stackup/keepout, backup cell, antenna siting, and
BOM. TMS covers measured nichrome resistance/current, relay/contact margin,
safe reset/brownout behavior, isolated-return intent, connector current and
retention, regulator thermal budget, module sockets, dummy-load test, and BOM.

Migrate valid dated signatures only when their old text unambiguously maps to
a new item and the accepted hashes still match. Leave every ambiguous item
unsigned.

Add `reviewed_project` to `tests/review/conftest.py`. It copies
`baro-bmp390`, writes accepted sign-off records for every barometer profile
item using the copied design's current canonical hashes and reviewer
`Lee Taeho`, and returns the loaded copy.

- [ ] **Step 4: Run sign-off tests and human-work rendering**

Run: `uv run pytest tests/review/test_signoff.py -v`

Expected: PASS; open-item aggregation contains no irrelevant XT60 warnings on
the three low-current boards.

- [ ] **Step 5: Commit review profiles**

```bash
git add src/pcb_copilot/review/signoff.py tests/review/conftest.py tests/review/test_signoff.py projects/*/review-profile.yaml projects/*/SIGNOFF.md
git commit -m "refactor: make PCB human sign-off project-specific"
```

### Task 5: Complete review CLI and on-demand reports

**Files:**
- Create: `src/pcb_copilot/review/commands.py`
- Create: `src/pcb_copilot/review/render.py`
- Modify: `src/pcb_copilot/cli.py`
- Create: `tests/review/test_cli.py`
- Modify: `scripts/run_gates.py`
- Modify: `scripts/audit_workflow.py`
- Modify: `scripts/human_work.py`

**Interfaces:**
- Adds parser positional `project_path`, optional `--format` choice, and
  optional `--output`; concrete form:
  `pcb-copilot review projects/tms-v3 --format markdown --output projects/tms-v3/.pcb-copilot/reports/manual-review.md`.
- Produces: `render_text(report: ReviewReport) -> str`
- Produces: `render_json(report: ReviewReport) -> str`
- Produces: `render_markdown(report: ReviewReport) -> str`
- Preserves old gate/audit/human-work commands as wrappers

- [ ] **Step 1: Write failing complete-report and read-only tests**

Copy TMS V3 to a temporary project, run review, and assert the report contains
research, datasheet, ERC, ownership, schematic quality, parity, placement,
design rules, DRC, and human sign-off even though several fail. Snapshot the
project before and after and assert it is unchanged unless `--output` names a
path under `.pcb-copilot/reports/`.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/review/test_cli.py -v`

Expected: FAIL because the review command is absent.

- [ ] **Step 3: Implement registry orchestration and renderers**

Use stable check IDs, show scope beside every result, and keep the three
finding categories separate. JSON output is schema-versioned and sorted;
Markdown includes accepted design hashes and tool versions.

- [ ] **Step 4: Convert legacy commands to the same registry**

`run_gates.py`, `audit_workflow.py`, and `human_work.py` delegate to package
review APIs. Preserve their current command-line exits and human-readable
headings during compatibility. Add tests asserting they agree with
`pcb-copilot review` on blocking check IDs.

- [ ] **Step 5: Run review, audit, and self-tests**

Run: `uv run pytest tests/review -q`

Run: `uv run python scripts/selftest_enforcement.py`

Run: `uv run python scripts/audit_workflow.py`

Expected: zero test failures; all three interfaces agree.

- [ ] **Step 6: Commit complete review**

```bash
git add src/pcb_copilot/review src/pcb_copilot/cli.py tests/review scripts/run_gates.py scripts/audit_workflow.py scripts/human_work.py
git commit -m "feat: produce complete scoped PCB review reports"
```

### Task 6: Transactional release and fabrication export

**Files:**
- Create: `src/pcb_copilot/fabrication/__init__.py`
- Create: `src/pcb_copilot/fabrication/export.py`
- Create: `src/pcb_copilot/release.py`
- Create: `tests/fabrication/test_export.py`
- Create: `tests/fabrication/test_release.py`
- Create: `tests/fabrication/conftest.py`
- Modify: `src/pcb_copilot/cli.py`
- Modify: `scripts/export_fab.py`

**Interfaces:**
- Produces: `export_fabrication(project: Project, destination: Path, toolchain: ToolchainPaths) -> FabricationManifest`
- Produces: `release_project(project: Project, reviewer: str) -> ReleaseResult`
- Produces: `FabricationManifest(schematic_hash: str, pcb_hash: str, git_commit: str, tool_versions: dict[str, str], files: dict[str, str])`
- Produces: `ReleaseResult(lifecycle: Lifecycle, fabrication_dir: Path, manifest_path: Path, review: ReviewReport)`
- Adds parser positional `project_path` and required `--reviewer`; concrete
  form: `pcb-copilot release projects/baro-bmp390 --reviewer "Lee Taeho"`.
- Preserves CLI: `python scripts/export_fab.py BOARD.kicad_pcb`

- [ ] **Step 1: Write failing release-interlock tests**

```python
@pytest.mark.parametrize("condition", [
    "blocking_machine_finding",
    "unsigned_human_item",
    "stale_schematic_hash",
    "stale_pcb_hash",
])
def test_release_refuses_unready_project(release_fixture, condition):
    release_fixture.apply(condition)
    with pytest.raises(ReleaseBlocked):
        release_project(release_fixture.project, "Lee Taeho")
    assert not release_fixture.fabrication_dir.exists()
```

Add fabrication characterization tests for Gerber/drill set, BOM LCSC values
read from PCB footprints, CPL positions re-originated within board bounds, and
manifest hashes matching actual output files.

Define `ReleaseFixture` in `tests/fabrication/conftest.py` with fields
`project`, `fabrication_dir`, and `apply(condition: str)`. Its fixture copies
the end-to-end sample project, creates current accepted sign-offs, and mutates
exactly one of the four parametrized conditions without touching live projects.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/fabrication -v`

Expected: FAIL because package release/export is absent.

- [ ] **Step 3: Move existing fabrication behavior and add atomic publication**

Generate into `.pcb-copilot/release-building/`, run the complete review first,
write a manifest containing accepted hashes, Git commit, KiCad/tool versions,
review results, reviewer, UTC time, and output hashes, then rename to
`fabrication/`. On any failure, remove only the validated temporary directory
and publish nothing.

- [ ] **Step 4: Prove output belongs to the released design**

After a successful fixture release, mutate the schematic or PCB and assert
`status` reports `DRAFT` and the existing fabrication manifest reports stale.
Do not automatically delete the old package; make its stale status explicit.

- [ ] **Step 5: Run fabrication and MCP manufacturing tests**

Run: `uv run pytest tests/fabrication tools/kicad-claude-mcp/tests/test_phase9_manufacturing.py -v`

Expected: PASS.

- [ ] **Step 6: Commit release workflow**

```bash
git add src/pcb_copilot/fabrication src/pcb_copilot/release.py src/pcb_copilot/cli.py tests/fabrication scripts/export_fab.py
git commit -m "feat: bind PCB fabrication output to reviewed releases"
```

### Task 7: Portable hooks and compatibility shutdown

**Files:**
- Create: `src/pcb_copilot/hooks.py`
- Create: `tests/test_hooks.py`
- Create: `tests/fixtures/hooks/post-edit-pcb.json`
- Modify: `.claude/settings.json`
- Replace: `.claude/hooks/session-start-brief.sh`
- Replace: `.claude/hooks/validate-pcb-on-edit.sh`
- Replace: `.claude/hooks/gate-status-on-stop.sh`
- Modify: `.claude/rules/*.md`

**Interfaces:**
- Adds CLI: `pcb-copilot hook session-start`
- Adds CLI: `pcb-copilot hook post-edit --event-json tests/fixtures/hooks/post-edit-pcb.json`
- Adds CLI: `pcb-copilot hook stop`
- Consumes: status and review APIs rather than invoking old scripts directly

- [ ] **Step 1: Write failing synthetic-event tests**

Port current Bash-event fixtures. Assert a PCB edit triggers geometry feedback,
a non-PCB edit does not, session start prints the short operating contract and
status, and stop prints review status only for touched boards. Run tests on
Windows without requiring Bash.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/test_hooks.py -v`

Expected: FAIL because portable hook commands are absent.

- [ ] **Step 3: Implement Python hook commands and update settings**

Parse event JSON from a file or stdin, use explicit UTF-8, and delegate to the
package status/review functions. Configure `.claude/settings.json` to invoke
`uv run pcb-copilot hook session-start`, `uv run pcb-copilot hook post-edit`,
or `uv run pcb-copilot hook stop`. Keep minimal shell shims only if the host cannot
invoke the Python entry point directly.

- [ ] **Step 4: Run hook and fault-injection tests**

Run: `uv run pytest tests/test_hooks.py tests/review/test_fault_injection.py -v`

Expected: PASS, including synthetic event delivery rather than file-existence-only checks.

- [ ] **Step 5: Commit portable integrations**

```bash
git add src/pcb_copilot/hooks.py tests/test_hooks.py tests/fixtures/hooks/post-edit-pcb.json .claude
git commit -m "refactor: make PCB workflow hooks portable"
```

### Task 8: Generated-state transition

**Files:**
- Modify: `src/pcb_copilot/state.py`
- Modify: `src/pcb_copilot/status.py`
- Modify: `scripts/pipeline.py`
- Modify: `.gitignore`
- Create: `tests/test_generated_state.py`
- Delete after parity: `HUMAN_WORK.md`, `projects/*/STATUS.md`, `projects/*/PIPELINE.json`

**Interfaces:**
- Produces local state: `PROJECT/.pcb-copilot/state.json`
- Produces on-demand reports: `PROJECT/.pcb-copilot/reports/REVIEW_ID.{json,md}`
- Preserves drift detection and canonical hashes previously read from `PIPELINE.json`

- [ ] **Step 1: Write state-migration and staleness tests**

For each board, load its current `PIPELINE.json`, migrate the last accepted
hashes/results to local state, and assert old and new status agree. Mutate a
copied schematic/PCB and assert both systems report stale before deletion.

- [ ] **Step 2: Run and verify missing migration failure**

Run: `uv run pytest tests/test_generated_state.py -v`

Expected: FAIL because local state migration is absent.

- [ ] **Step 3: Implement state migration and compatibility writes**

Add parser positional `project_path`; concrete form:
`pcb-copilot migrate-state projects/baro-bmp390`. During one compatibility commit,
write both old and new state and assert semantic equality. Then switch status,
ownership drift, and report consumers to the local state implementation.

- [ ] **Step 4: Verify no current caller needs tracked reports**

Run:

```bash
rg -n "HUMAN_WORK\.md|STATUS\.md|PIPELINE\.json" --glob '!planning/**'
uv run pytest tests/test_generated_state.py tests/test_state.py tests/test_status_cli.py -v
```

Expected: remaining references are migration/compatibility code scheduled for
removal in this task; tests show equal status and drift behavior.

- [ ] **Step 5: Stop tracking reproducible state**

Add `HUMAN_WORK.md`, `projects/*/STATUS.md`, and `projects/*/PIPELINE.json` to
`.gitignore`, remove their tracked copies, and delete the legacy writes from
`pipeline.py`. Run state and fault tests again before commit.

- [ ] **Step 6: Commit generated-state cleanup**

```bash
git add .gitignore src/pcb_copilot/state.py src/pcb_copilot/status.py scripts/pipeline.py tests/test_generated_state.py
git rm HUMAN_WORK.md projects/*/STATUS.md projects/*/PIPELINE.json
git commit -m "refactor: generate PCB status locally on demand"
```

### Task 9: Documentation and obsolete-file deletion

**Files:**
- Modify: maintained root/project documentation and `migration/inventory.yaml`
- Move: `docs/tms-v3-pdr.md` to `projects/tms-v3/PDR.md`
- Delete after fact migration: `docs/QUICKSTART.md`, `docs/SETUP.md`, `docs/pcb-design-workflow.md`, `docs/pcb-design-rules.md`, `docs/archive/`
- Delete after fact migration: `projects/baro-bmp390/EVALUATION.md`, `projects/imu-icm42688/EVALUATION.md`, `projects/gnss-neom9n/EVALUATION.md`
- Delete after BOM parity: `projects/tms-v3/tms-v3-bom.md`
- Delete after CLI parity: all four `projects/*/build.sh`
- Delete after accepted-intent parity: all eight project `gen_*_sch.py` and `gen_*_pcb.py`
- Delete compatibility Python entry points only when inventory reports zero callers and package/CLI replacements pass
- Create: `tests/test_cleanup.py`

**Interfaces:**
- Produces: `assert_cleanup_ready(repo_root: Path, inventory: Inventory) -> CleanupReport`
- Produces: `CleanupReport(missing_replacements: tuple[str, ...], live_callers: tuple[str, ...], unmigrated_facts: tuple[str, ...], behavior_regressions: tuple[str, ...])`
- Consumes: replacement paths, Git-tracked callers, doc links, board baselines, and generated BOM comparison

- [ ] **Step 1: Write a failing cleanup-readiness test**

```python
def test_delete_candidates_have_verified_replacements(repo_root):
    report = assert_cleanup_ready(repo_root, load_inventory(repo_root / "migration/inventory.yaml"))
    assert report.missing_replacements == ()
    assert report.live_callers == ()
    assert report.unmigrated_facts == ()
    assert report.behavior_regressions == ()
```

The checker must fail if a candidate is referenced by Python imports,
subprocess commands, hooks, Markdown links, project descriptions, or tests.

- [ ] **Step 2: Run and verify current candidates are not ready**

Run: `uv run pytest tests/test_cleanup.py -v`

Expected: FAIL with exact remaining callers/references; this proves deletion
is gated rather than assumed.

- [ ] **Step 3: Migrate unique facts from obsolete documentation**

For each `EVALUATION.md` and archive document, compare every current claim to
`REQUIREMENTS.md`, `DESIGN_BASIS.md`, `DEVIATIONS.md`, `PDR.md`, maintained
rules, limitations, and regression tests. Move a fact only when it is current;
do not carry superseded 22 pF, connector, missing-switch, or placement-only
claims into canonical documentation.

Generate the TMS BOM from the accepted design and compare refs, quantities,
values, footprints, and LCSC fields with every still-current manual row. Fix
the design/evidence source for genuine differences; do not edit generated BOM
output by hand.

- [ ] **Step 4: Update all code and documentation references**

Move the PDR with `git mv`, replace links to canonical docs, replace build
wrappers with documented `pcb-copilot` commands, and ensure accepted intent
plus regression fixtures cover each project generator's unique behavior.

- [ ] **Step 5: Run cleanup readiness until it passes**

Run: `uv run pytest tests/test_cleanup.py -v`

Run: `rg -n "EVALUATION\.md|tms-v3-bom\.md|docs/archive|docs/QUICKSTART\.md|docs/SETUP\.md|pcb-design-workflow\.md|pcb-design-rules\.md|gen_.*_(sch|pcb)\.py|build\.sh" --glob '!planning/**'`

Expected: cleanup test passes and search returns no live references to deletion
candidates.

- [ ] **Step 6: Delete only the verified candidates**

Use explicit `git rm` paths from this task, not a broad recursive pattern.
Before deletion, resolve every target under the repository root and print the
list. After deletion, rerun the cleanup test, documentation-link test,
four-board parity tests, generated BOM test, and fault-injection suite.

- [ ] **Step 7: Remove obsolete compatibility entry points individually**

For each old `docs/*.py` wrapper classified `DELETE`, confirm `rg` finds zero
callers, delete that one file, run its replacement tests, and commit. Keep any
wrapper whose compatibility value remains real; reclassify it as `KEEP` with
a reason instead of forcing the target tree shape.

- [ ] **Step 8: Commit documentation and file cleanup**

```bash
git add README.md CLAUDE.md docs projects migration/inventory.yaml tests/test_cleanup.py
git commit -m "refactor: remove superseded PCB workflow files"
```

### Task 10: Final four-board and release verification

**Files:**
- Create: `tests/test_end_to_end.py`
- Modify: `docs/WORKFLOW.md`, `docs/LIMITATIONS.md`, and `README.md` only for verified final commands/results

**Interfaces:**
- Verifies: research, schematic draft, layout draft, review, acceptance, release blocking, and fabrication against the final package APIs

- [ ] **Step 1: Add a temporary end-to-end fixture project**

Use a small two-resistor/sensor fixture with local evidence, a valid schematic
intent, layout intent, signed review profile, and fake deterministic KiCad
command adapter. Run the complete lifecycle and assert exact state transitions:
`DRAFT`, `HUMAN_REVIEWED`, then `RELEASED`.

- [ ] **Step 2: Prove release invalidation**

After fixture release, change one schematic net and assert lifecycle returns
to `DRAFT`, old fabrication output is reported stale, and another release is
blocked until review/sign-off is repeated.

- [ ] **Step 3: Run the complete automated suite**

Run:

```bash
uv run pytest -m "not network" -q
uv run python -m ruff check src tests tools/kicad-claude-mcp/src tools/kicad-claude-mcp/tests
uv run pcb-copilot status projects/baro-bmp390
uv run pcb-copilot status projects/imu-icm42688
uv run pcb-copilot status projects/gnss-neom9n
uv run pcb-copilot status projects/tms-v3
```

Expected: tests and lint exit `0`; status is read-only and reports honest
current lifecycle/findings for every board.

- [ ] **Step 4: Run real KiCad review on all boards**

Run `pcb-copilot review` for each of the four literal project paths. Compare
schematic and PCB refs/nets with the stored baseline. Open every accepted
schematic and board in KiCad, plus schematic PDF and 3D preview.

Expected: no unexplained connectivity loss; current unresolved engineering and
human findings remain visible.

- [ ] **Step 5: Run documentation and cleanup verification**

Run: `uv run pytest tests/test_documentation.py tests/test_cleanup.py -v`

Run: `git status --short`

Expected: documentation/cleanup tests pass and only intended final-doc edits
are present.

- [ ] **Step 6: Commit final verified documentation**

```bash
git add tests/test_end_to_end.py README.md docs/WORKFLOW.md docs/LIMITATIONS.md
git commit -m "test: verify the human-controlled PCB copilot lifecycle"
```

## Plan 5 Completion Check

- [ ] The complete non-network test suite and linter exit `0`.
- [ ] Every blocking check has a passing fault-injection case.
- [ ] Review always reports all checks, including after failures.
- [ ] Human sign-off is relevant, dated, and hash-bound.
- [ ] Release refuses blocking findings, missing decisions, and stale hashes.
- [ ] Fabrication artifacts and manifest match the accepted released design.
- [ ] All four boards open in KiCad and retain accounted-for connectivity.
- [ ] Cleanup readiness has no missing replacement, live caller, unmigrated fact, or behavior regression.
- [ ] Deleted files remain recoverable from Git and the final worktree is clean.
