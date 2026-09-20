# PCB Copilot Foundation and Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the tested Python workspace, portable tool discovery, project model, preservation inventory, read-only CLI, and canonical documentation without removing working implementations.

**Architecture:** Add `src/pcb_copilot` beside the current scripts and keep `docs/*.py` operational. New code wraps existing behavior first; the four boards receive manifests without moving their accepted KiCad files during this plan.

**Tech Stack:** Python 3.10+, `uv`, pytest 8+, Pydantic 2, PyYAML 6, stdlib `argparse`, Git, and the vendored `kicad-claude-mcp` workspace package.

**Spec:** `planning/specs/2026-09-14-pcb-copilot-repository-remake-design.md`

## Windows helper follow-up — 2026-09-17

The original foundation tasks are implemented. A Task 2 follow-up corrects a
remaining discovery gap: Windows KiCad provides a sibling `python.exe` with
`pcbnew`, but no `kipython` executable. Preserve explicit `KIPYTHON`, then PATH
`kipython`, before considering that sibling. Require an isolated, bounded
`pcbnew` import probe; a missing or unusable optional interpreter must not hide
an otherwise available KiCad CLI. An injected environment controls helper PATH
lookup, while the shared CLI finder retains its existing environment contract.

This is a toolchain correction, not the start of layout generation or an
approval of any board. Legacy callers need individual verification under the
bundled interpreter; discovering it does not make every wrapper portable.

The parity checker also needs both repository `src` and vendored helper source
on its import path when run by KiCad Python, which lacks the workspace's
installed packages. Its bootstrap must not expose the workspace virtualenv's
native extensions to a different Python ABI. An isolated no-site-packages
regression covers that caller without requiring KiCad or opening a board.

Fresh Windows exports also need an explicit LF policy for `.claude/hooks/*.sh`;
`core.autocrlf=true` otherwise breaks Bash even when a developer's current
copy happens to use LF. A temporary-Git checkout regression protects that
boundary without changing hook logic or the exact-source evidence policy.

Verified on the local Windows KiCad installation: shared discovery selects
the bundled interpreter, and the existing read-only geometry and schematic/PCB
parity checks run successfully on all four accepted boards. The enforcement
self-test passes 93/93 in a fresh Git-exported snapshot with UTF-8 propagated
to child processes. A snapshot is important because this legacy self-test
temporarily replaces evidence files during fault injection. These results do
not establish full board readiness; the combined test counts are recorded in
the [schematic execution checkpoint](2026-09-14-pcb-copilot-03-schematic.md#execution-checkpoint--2026-09-17).

## Global Constraints

- Read each current file, callers, tests, and documentation before changing it.
- Preserve all current CLI entry points throughout this plan.
- Do not move or regenerate accepted KiCad files.
- Do not delete project evidence, engineering decisions, generators, or gate code.
- Tests must use temporary projects and cannot write into `projects/`.
- Support Windows paths containing spaces and KiCad directory names such as `10.0`.
- Use UTF-8 explicitly for every repository text read and write.
- Finish each task with a clean, focused commit.

---

### Task 1: Root Python workspace and smoke test

**Files:**
- Create: `pyproject.toml`
- Create: `src/pcb_copilot/__init__.py`
- Create: `src/pcb_copilot/cli.py`
- Create: `tests/conftest.py`
- Create: `tests/test_package_smoke.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `pcb_copilot.__version__: str`
- Produces: `pcb_copilot.cli.main(argv: list[str] | None = None) -> int`
- Consumes: vendored `kicad-claude-mcp` as a `uv` workspace dependency

- [ ] **Step 1: Write the failing package smoke test**

```python
from pcb_copilot import __version__
from pcb_copilot.cli import main


def test_package_and_cli_are_importable(capsys):
    assert __version__ == "0.1.0"
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "pcb-copilot 0.1.0"
```

- [ ] **Step 2: Run the test and verify the missing package failure**

Run: `uv run pytest tests/test_package_smoke.py -v`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'pcb_copilot'`.

- [ ] **Step 3: Add the root project and minimal CLI**

Use this project configuration:

```toml
[project]
name = "pcb-copilot"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "kicad-claude-mcp",
  "pydantic>=2,<3",
  "PyYAML>=6,<7",
]

[project.scripts]
pcb-copilot = "pcb_copilot.cli:entrypoint"

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.uv.workspace]
members = ["tools/kicad-claude-mcp"]

[tool.uv.sources]
kicad-claude-mcp = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pcb_copilot"]

[tool.pytest.ini_options]
testpaths = ["tests", "tools/kicad-claude-mcp/tests"]
markers = [
  "slow: invokes KiCad or Freerouting",
  "network: accesses external services",
]
```

Implement `main()` with `argparse`, returning `0` for `--version`, and add an
`entrypoint()` that raises `SystemExit(main())`. Add `.pcb-copilot/` and
`.pytest_cache/` to `.gitignore`.

Create the shared repository fixture in `tests/conftest.py`:

```python
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
```

- [ ] **Step 4: Run the smoke test and existing fast MCP tests**

Run: `uv run pytest tests/test_package_smoke.py tools/kicad-claude-mcp/tests -m "not slow and not network" -q`

Expected: the new smoke test passes and the existing fast suite has zero failures.

- [ ] **Step 5: Commit the workspace scaffold**

```bash
git add pyproject.toml uv.lock .gitignore src/pcb_copilot tests/conftest.py tests/test_package_smoke.py
git commit -m "build: add pcb copilot workspace"
```

### Task 2: Portable KiCad and helper discovery

**Files:**
- Modify: `tools/kicad-claude-mcp/src/kicad_claude/utils/kicad_paths.py`
- Modify: `tools/kicad-claude-mcp/tests/test_phase2_indexer.py`
- Create: `src/pcb_copilot/toolchain.py`
- Create: `tests/test_toolchain.py`

**Interfaces:**
- Produces: `ToolchainPaths(kicad_cli: Path, kipython: Path | None, freerouting_jars: tuple[Path, ...])`
- Produces: `discover_toolchain(repo_root: Path, environ: Mapping[str, str] | None = None) -> ToolchainPaths`
- Reuses: `kicad_claude.utils.kicad_paths.find_kicad_cli()`
- Reuses: `find_symbol_lib_dirs()` and `find_footprint_lib_dirs()`

- [ ] **Step 1: Add failing dotted-version Windows tests**

```python
def test_windows_version_directories_accept_dotted_names(tmp_path, monkeypatch):
    root = tmp_path / "KiCad"
    symbols = root / "10.0" / "share" / "kicad" / "symbols"
    symbols.mkdir(parents=True)
    monkeypatch.setattr(kicad_paths.platform, "system", lambda: "Windows")
    monkeypatch.setattr(kicad_paths, "_windows_kicad_root", lambda: root)
    assert symbols in kicad_paths.find_symbol_lib_dirs()


def test_windows_cli_is_found_below_dotted_version(tmp_path, monkeypatch):
    root = tmp_path / "KiCad"
    cli = root / "10.0" / "bin" / "kicad-cli.exe"
    cli.parent.mkdir(parents=True)
    cli.touch()
    monkeypatch.setattr(kicad_paths.platform, "system", lambda: "Windows")
    monkeypatch.setattr(kicad_paths, "_windows_kicad_root", lambda: root)
    monkeypatch.setattr(kicad_paths.shutil, "which", lambda _: None)
    assert kicad_paths.find_kicad_cli() == cli
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `uv run pytest tools/kicad-claude-mcp/tests/test_phase2_indexer.py -k "windows" -v`

Expected: FAIL because only hard-coded integer versions are probed and Windows CLI fallback is absent.

- [ ] **Step 3: Implement directory enumeration instead of a fixed Windows version tuple**

Add `_windows_kicad_root()` returning `Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "KiCad"`. Add `_windows_install_dirs()` that sorts child directories by parsed numeric segments, so `10.0` sorts above `9.0`. Use those directories for symbols, footprints, and `bin/kicad-cli.exe`. Retain environment-variable and PATH priority.

Implement `discover_toolchain()` as the single workspace wrapper. It must use `KIPYTHON` when supplied, otherwise `shutil.which("kipython")`, and enumerate `tools/kicad-claude-mcp/third_party/freerouting*.jar` without selecting an incompatible JVM yet.

- [ ] **Step 4: Add and run root toolchain tests**

```python
def test_discover_toolchain_uses_shared_kicad_finder(tmp_path, monkeypatch):
    cli = tmp_path / "kicad-cli.exe"
    cli.touch()
    monkeypatch.setattr("pcb_copilot.toolchain.find_kicad_cli", lambda: cli)
    paths = discover_toolchain(tmp_path, {})
    assert paths.kicad_cli == cli
    assert paths.freerouting_jars == ()
```

Run: `uv run pytest tests/test_toolchain.py tools/kicad-claude-mcp/tests/test_phase2_indexer.py -v`

Expected: PASS.

- [ ] **Step 5: Run a real Windows discovery smoke check**

Run: `uv run python -c "from pathlib import Path; from pcb_copilot.toolchain import discover_toolchain; print(discover_toolchain(Path.cwd()))"`

Expected: output names the installed KiCad executable under `C:\Program Files\KiCad\10.0` and does not report an empty toolchain.

- [ ] **Step 6: Commit portable discovery**

```bash
git add tools/kicad-claude-mcp/src/kicad_claude/utils/kicad_paths.py tools/kicad-claude-mcp/tests/test_phase2_indexer.py src/pcb_copilot/toolchain.py tests/test_toolchain.py
git commit -m "fix: discover dotted KiCad installs on Windows"
```

### Task 3: Preservation inventory and four-board baseline

**Files:**
- Create: `migration/inventory.yaml`
- Create: `src/pcb_copilot/migration.py`
- Create: `tests/test_migration_inventory.py`
- Create: `tests/fixtures/baseline/boards.json`
- Create: `scripts/capture_board_baseline.py`

**Interfaces:**
- Produces: `InventoryRule(pattern: str, action: Literal["KEEP", "REFACTOR", "MERGE", "GENERATED", "DELETE"], rationale: str, replacement: str | None)`
- Produces: `load_inventory(path: Path) -> tuple[InventoryRule, ...]`
- Produces: `classify_path(path: PurePosixPath, rules: Sequence[InventoryRule]) -> InventoryRule`
- Produces: `capture_board(project: Project) -> dict[str, object]`

- [ ] **Step 1: Write the failing inventory coverage test**

```python
def test_every_tracked_path_has_one_inventory_rule(repo_root):
    rules = load_inventory(repo_root / "migration" / "inventory.yaml")
    tracked = subprocess.check_output(
        ["git", "ls-files"], cwd=repo_root, text=True, encoding="utf-8"
    ).splitlines()
    for name in tracked:
        assert classify_path(PurePosixPath(name), rules).rationale
```

Also test that a path matching two equally specific rules raises
`AmbiguousInventoryRule` rather than choosing silently.

- [ ] **Step 2: Run the test and verify the missing inventory failure**

Run: `uv run pytest tests/test_migration_inventory.py -v`

Expected: FAIL because the inventory loader does not exist.

- [ ] **Step 3: Implement ordered glob classification and write the inventory**

Use explicit rules for root docs, `.claude`, each `docs/*.py` capability,
project records, accepted KiCad files, evidence, libraries, generated reports,
project generators, each vendored tool tree, and the approved spec/plan files.
Every `DELETE` or `MERGE` rule must name a non-empty `replacement`.

- [ ] **Step 4: Capture the immutable comparison baseline**

`capture_board()` must record, for each existing board:

```json
{
  "schematic_hash": "canonical 12-character hash",
  "pcb_hash": "canonical 12-character hash",
  "schematic_refs": ["sorted references"],
  "pcb_refs": ["sorted references"],
  "netmap": {"reference": {"pin": "net"}},
  "pcb_nets": {"net": ["reference.pin"]}
}
```

Run: `uv run python scripts/capture_board_baseline.py --output tests/fixtures/baseline/boards.json`

Then run it again to a temporary file and compare hashes. Expected: byte-identical output.

- [ ] **Step 5: Run inventory and baseline tests**

Run: `uv run pytest tests/test_migration_inventory.py -v`

Expected: PASS for every tracked path with no ambiguous classifications.

- [ ] **Step 6: Commit the preservation baseline**

```bash
git add migration/inventory.yaml src/pcb_copilot/migration.py scripts/capture_board_baseline.py tests/test_migration_inventory.py tests/fixtures/baseline/boards.json
git commit -m "test: record migration inventory and board baseline"
```

### Task 4: Project manifest and compatibility loader

**Files:**
- Create: `src/pcb_copilot/models.py`
- Create: `src/pcb_copilot/project.py`
- Create: `tests/test_project.py`
- Create: `projects/template/project.yaml`
- Create: `projects/baro-bmp390/project.yaml`
- Create: `projects/imu-icm42688/project.yaml`
- Create: `projects/gnss-neom9n/project.yaml`
- Create: `projects/tms-v3/project.yaml`
- Modify: `tests/conftest.py`

**Interfaces:**
- Produces: `Lifecycle`, `ProjectManifest`, `DesignFiles`, `ManufacturingProfile`, and `Project`
- Produces: `load_project(path: Path) -> Project`
- Produces: `Project.schematic_path`, `Project.pcb_path`, `Project.netmap_path`, `Project.evidence_index_path`
- Consumes: current flat project layout without moving any file

- [ ] **Step 1: Write manifest validation tests**

```python
def test_load_existing_flat_project(repo_root):
    project = load_project(repo_root / "projects" / "baro-bmp390")
    assert project.manifest.name == "baro-bmp390"
    assert project.schematic_path.name == "baro-bmp390.kicad_sch"
    assert project.pcb_path.name == "baro-bmp390.kicad_pcb"
    assert project.manifest.lifecycle == Lifecycle.DRAFT


def test_manifest_rejects_path_escape(tmp_path):
    (tmp_path / "project.yaml").write_text(
        """schema_version: 1
name: escape-test
lifecycle: DRAFT
design:
  schematic: ../outside.kicad_sch
  pcb: board.kicad_pcb
  netmap: netmap.json
evidence:
  index: evidence/index.yaml
manufacturing:
  profile: jlcpcb_2layer_default
safety_tags: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ProjectFormatError, match="outside project root"):
        load_project(tmp_path)
```

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/test_project.py -v`

Expected: FAIL because the project model is not implemented.

- [ ] **Step 3: Implement Pydantic models and safe path resolution**

Use this manifest shape for existing boards:

```yaml
schema_version: 1
name: baro-bmp390
lifecycle: DRAFT
design:
  schematic: baro-bmp390.kicad_sch
  pcb: baro-bmp390.kicad_pcb
  netmap: netmap.json
evidence:
  index: evidence/index.yaml
manufacturing:
  profile: jlcpcb_2layer_default
safety_tags: []
```

Use `safety_tags: [pyrotechnic, high_current]` for TMS V3 and relevant tags
for RF, battery, and inertial boards. Resolve every manifest path and require
it to remain under `Project.root`.

Extend `tests/conftest.py` with the reusable copy and byte-tree hash used by
read-only command tests:

```python
import hashlib
import shutil


@pytest.fixture
def project_copy(tmp_path: Path, repo_root: Path) -> Path:
    destination = tmp_path / "baro-bmp390"
    shutil.copytree(repo_root / "projects" / "baro-bmp390", destination)
    return destination


@pytest.fixture
def tree_hash():
    def calculate(root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

    return calculate
```

- [ ] **Step 4: Run the four-board loader test**

Add a parametrized test loading every non-template project and asserting its
accepted schematic and PCB exist. Run: `uv run pytest tests/test_project.py -v`.

Expected: PASS for all four boards.

- [ ] **Step 5: Commit project manifests**

```bash
git add src/pcb_copilot/models.py src/pcb_copilot/project.py tests/conftest.py tests/test_project.py projects/*/project.yaml
git commit -m "feat: add versioned PCB project manifests"
```

### Task 5: Lifecycle and ownership compatibility

**Files:**
- Create: `src/pcb_copilot/state.py`
- Create: `tests/test_state.py`
- Modify: `src/pcb_copilot/models.py`
- Read before modifying later: `scripts/pipeline.py`, `scripts/extract_netmap.py`, `scripts/run_gates.py`

**Interfaces:**
- Produces: `canonical_design_hash(path: Path) -> str`
- Produces: `effective_lifecycle(project: Project) -> Lifecycle`
- Produces: `assert_draft_target_safe(project: Project, target: Path) -> None`
- Consumes: legacy `SCHEMATIC_OWNER` and `PIPELINE.json` without rewriting them

- [ ] **Step 1: Write failing canonical-hash and ownership tests**

```python
def test_uuid_only_change_keeps_canonical_hash(tmp_path):
    first = tmp_path / "a.kicad_sch"
    second = tmp_path / "b.kicad_sch"
    first.write_text('(uuid 11111111-1111-4111-8111-111111111111)', encoding="utf-8")
    second.write_text('(uuid 22222222-2222-4222-8222-222222222222)', encoding="utf-8")
    assert canonical_design_hash(first) == canonical_design_hash(second)


def test_changed_released_design_returns_to_draft(released_project):
    released_project.schematic_path.write_text("changed", encoding="utf-8")
    assert effective_lifecycle(released_project) == Lifecycle.DRAFT
```

In the same test file, define the fixture with the concrete compatibility
record consumed by `state.py`:

```python
@pytest.fixture
def released_project(project_copy: Path) -> Project:
    project = load_project(project_copy)
    state_dir = project.root / ".pcb-copilot"
    state_dir.mkdir()
    record = {
        "schema_version": 1,
        "lifecycle": "RELEASED",
        "schematic_hash": canonical_design_hash(project.schematic_path),
        "pcb_hash": canonical_design_hash(project.pcb_path),
    }
    (state_dir / "release.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return project
```

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/test_state.py -v`

Expected: FAIL because state compatibility is absent.

- [ ] **Step 3: Move the existing UUID-mask behavior without changing it**

Implement the same UUID token regex currently used by `pipeline.sha()`. Read
legacy ownership as follows: `human` forbids regeneration; `generated` permits
draft creation only when its last recorded canonical hash still matches;
missing ownership retains the current `generated` compatibility behavior.

Lifecycle is `RELEASED` only when both accepted hashes match the release
record, `HUMAN_REVIEWED` only when the accepted-review hashes match, and
otherwise `DRAFT`.

- [ ] **Step 4: Prove accepted targets cannot be overwritten**

Add tests where draft output equals the accepted schematic path, the accepted
PCB path, or a path outside `.pcb-copilot/drafts/`; each must raise
`UnsafeDraftTarget` before opening the file.

Run: `uv run pytest tests/test_state.py -v`. Expected: PASS.

- [ ] **Step 5: Commit lifecycle compatibility**

```bash
git add src/pcb_copilot/models.py src/pcb_copilot/state.py tests/test_state.py
git commit -m "feat: protect accepted PCB design state"
```

### Task 6: Read-only status CLI

**Files:**
- Modify: `src/pcb_copilot/cli.py`
- Create: `src/pcb_copilot/status.py`
- Create: `tests/test_status_cli.py`

**Interfaces:**
- Produces: `collect_status(project: Project) -> ProjectStatus`
- Produces: `render_status(status: ProjectStatus) -> str`
- Adds parser positional `project_path`; concrete form:
  `pcb-copilot status projects/baro-bmp390`.
- Consumes: `load_project()` and `effective_lifecycle()`

- [ ] **Step 1: Write a failing read-only contract test**

```python
def test_status_does_not_modify_project(project_copy, tree_hash, capsys):
    before = tree_hash(project_copy)
    assert main(["status", str(project_copy)]) == 0
    assert tree_hash(project_copy) == before
    assert "DRAFT" in capsys.readouterr().out
```

- [ ] **Step 2: Run and verify the missing subcommand failure**

Run: `uv run pytest tests/test_status_cli.py -v`

Expected: FAIL because `status` is not registered.

- [ ] **Step 3: Implement status without invoking generators or gates**

Report manifest validity, effective lifecycle, accepted schematic/PCB paths,
toolchain availability, evidence-index presence, last review/release hashes,
and a single recommended next command. Do not read or write `STATUS.md` or
`PIPELINE.json` in this command.

- [ ] **Step 4: Run status tests and a real project smoke check**

Run: `uv run pytest tests/test_status_cli.py -v`

Run: `uv run pcb-copilot status projects/baro-bmp390`

Expected: tests pass; the command reports the project without changing `git status --short`.

- [ ] **Step 5: Commit the status command**

```bash
git add src/pcb_copilot/cli.py src/pcb_copilot/status.py tests/test_status_cli.py
git commit -m "feat: add read-only project status"
```

### Task 7: Canonical documentation skeleton and link checks

**Files:**
- Create: `README.md`
- Create: `docs/WORKFLOW.md`
- Create: `docs/DESIGN_RULES.md`
- Create: `docs/LIMITATIONS.md`
- Create: `docs/PROJECT_FORMAT.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `CLAUDE.md`
- Create: `tests/test_documentation.py`

**Interfaces:**
- Produces: one authoritative destination for purpose, workflow, architecture, rules, limitations, and project format
- Consumes: current `QUICKSTART.md`, `SETUP.md`, `pcb-design-workflow.md`, `pcb-design-rules.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `.claude/rules`, and all project records

- [ ] **Step 1: Write documentation ownership tests**

```python
CANONICAL = {
    "purpose": Path("README.md"),
    "workflow": Path("docs/WORKFLOW.md"),
    "architecture": Path("docs/ARCHITECTURE.md"),
    "rules": Path("docs/DESIGN_RULES.md"),
    "limitations": Path("docs/LIMITATIONS.md"),
    "project_format": Path("docs/PROJECT_FORMAT.md"),
}


def test_canonical_docs_exist_and_have_no_placeholder(repo_root):
    for path in CANONICAL.values():
        text = (repo_root / path).read_text(encoding="utf-8")
        assert len(text.strip()) >= 200
        assert "T" + "BD" not in text
        assert "T" + "ODO" not in text
```

Add a relative-link test that resolves local Markdown links and reports the
source document and broken target.

- [ ] **Step 2: Run and verify missing canonical documents**

Run: `uv run pytest tests/test_documentation.py -v`

Expected: FAIL because the new canonical documents do not yet exist.

- [ ] **Step 3: Write the canonical documents by consolidation**

Preserve these current ideas explicitly: evidence tiers; integration-manual
exception; advisory research versus release blocking; the three assurance
questions; fault injection; scoped deviations; ownership tripwire; netmap
parity; honest 4-of-42 rule coverage; coordinate and anchor rules; placement
before routing; fabrication interlock; and all current human limitations.

Keep `CLAUDE.md` as a short operational index that links to the canonical
documents and commands. Do not delete old documents in this task; add a clear
supersession notice at their top only after every inbound link has moved.

- [ ] **Step 4: Run documentation tests and search for stale links**

Run: `uv run pytest tests/test_documentation.py -v`

Run: `rg -n "docs/(QUICKSTART|SETUP|pcb-design-workflow|pcb-design-rules)\.md" --glob '!planning/**'`

Expected: tests pass; remaining references occur only inside the superseded documents themselves or migration inventory.

- [ ] **Step 5: Run the full foundation verification**

Run: `uv run pytest -m "not slow and not network" -q`

Run: `uv run python scripts/selftest_enforcement.py`

Expected: zero pytest failures and the enforcement self-test exits `0`.

- [ ] **Step 6: Commit canonical documentation**

```bash
git add README.md CLAUDE.md docs/ARCHITECTURE.md docs/WORKFLOW.md docs/DESIGN_RULES.md docs/LIMITATIONS.md docs/PROJECT_FORMAT.md tests/test_documentation.py
git commit -m "docs: define the human-controlled PCB copilot"
```

## Plan 1 Completion Check

- [ ] `uv run pytest -m "not slow and not network" -q` exits `0`.
- [ ] `uv run python scripts/selftest_enforcement.py` exits `0`.
- [ ] `uv run pcb-copilot status projects/baro-bmp390` leaves that project byte-identical.
- [ ] All four manifests load and point to the current accepted KiCad files.
- [ ] The migration inventory classifies every tracked path exactly once.
- [ ] No existing implementation or project evidence has been deleted.
- [ ] Stop for human review before starting the evidence plan.
