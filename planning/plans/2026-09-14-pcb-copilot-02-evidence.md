# PCB Copilot Evidence Subsystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace separate Markdown datasheet/reference indexes with one structured, cited, multi-role evidence store while retaining the current verified-download and exact-extraction behavior.

**Architecture:** Build typed evidence models around `collect_references.py`, `fetch_reference_doc.py`, `check_datasheets.py`, and `check_research.py`. Migrate one board at a time only after the new checker produces equivalent results; keep the old scripts as compatibility entry points.

**Tech Stack:** Python 3.10+, Pydantic 2, PyYAML 6, httpx, SHA-256, pytest, and existing Eagle/PDF extraction utilities.

**Spec:** `planning/specs/2026-09-14-pcb-copilot-repository-remake-design.md`

## Global Constraints

- Read the four existing evidence scripts and their callers before changing them.
- Preserve rejection of HTML/login pages saved with document extensions.
- Preserve URL, retrieval-date, file-type, and exact-part provenance.
- A single file may have several evidence roles and component references.
- Never silently choose between conflicting revisions.
- Do not delete an old index or duplicate file until the new index verifies and all inbound references are updated.
- Network tests are marked `network`; deterministic fixture tests run offline.
- Finish each task with a focused commit.

## Reference-research follow-up (2026-09-16)

The user clarified that reference schematic and PCB research are as important
as datasheet acquisition, inspection, and validation. The package now supplies
separate search queries (not a live-search provider) and indexed Eagle
schematic/board inspection: source-hash verification, pad-net comparison,
package and explicit-value comparison, and descriptive layout metadata.
Board XML is archived as `.brd`, not `.sch`.

Actual BMP390 searches and their scoped findings are recorded in
`projects/baro-bmp390/REFERENCE_REVIEW.md`. Manufacturer and open-hardware PDFs
were archived and visually inspected; native copper review, exact revision
matching, and comparison against our own PCB remain open. Other boards still
need this research. Full research-coverage/release enforcement belongs to
Plan 5; generic reference-file presence is not proof of completed research.

---

### Task 1: Evidence models and atomic YAML index

**Files:**
- Create: `src/pcb_copilot/evidence/__init__.py`
- Create: `src/pcb_copilot/evidence/models.py`
- Create: `src/pcb_copilot/evidence/index.py`
- Create: `tests/evidence/test_index.py`

**Interfaces:**
- Produces: `EvidenceRole`, `TrustTier`, `EvidenceRecord`, `EvidenceIndex`
- Produces: `load_evidence_index(path: Path) -> EvidenceIndex`
- Produces: `save_evidence_index(index: EvidenceIndex, path: Path) -> None`
- Produces: `EvidenceIndex.for_part(part_number: str) -> tuple[EvidenceRecord, ...]`

- [ ] **Step 1: Write failing round-trip and multi-role tests**

```python
def test_one_document_can_fill_multiple_roles(tmp_path):
    record = EvidenceRecord(
        id="sha256:abc123",
        manufacturer="Digi",
        part_numbers=["XBee 3"],
        title="XBee 3 Hardware Reference",
        revision="90001543",
        source_url="https://example.test/xbee.pdf",
        retrieved_on=date(2026, 8, 25),
        path="files/xbee3_hardware_ref.pdf",
        sha256="abc123",
        media_type="application/pdf",
        roles={EvidenceRole.DATASHEET, EvidenceRole.MODULE_PINOUT},
        trust_tier=TrustTier.MANUFACTURER,
        component_refs={"J9"},
    )
    path = tmp_path / "index.yaml"
    save_evidence_index(EvidenceIndex(schema_version=1, records=[record]), path)
    loaded = load_evidence_index(path)
    assert loaded.records[0].roles == record.roles
    assert loaded.for_part("xbee 3") == (loaded.records[0],)
```

Also assert that duplicate IDs, absolute paths, `..` path escapes, missing
hashes, and unknown roles raise `EvidenceFormatError`.

- [ ] **Step 2: Run and verify missing-model failure**

Run: `uv run pytest tests/evidence/test_index.py -v`

Expected: FAIL during import because the evidence package is absent.

- [ ] **Step 3: Implement models and deterministic serialization**

Use string enums with roles `datasheet`, `integration_manual`,
`reference_design`, `application_note`, `footprint_drawing`, and
`module_pinout`. Use trust tiers `manufacturer`, `manufacturer_evm`,
`proven_open_hardware`, and `teaching_reference`.

`save_evidence_index()` writes UTF-8 to a sibling temporary file, flushes it,
then uses `Path.replace()` to publish it. Sort records by ID and sets by value
so a second save is byte-identical.

- [ ] **Step 4: Run tests twice and compare serialized bytes**

Run: `uv run pytest tests/evidence/test_index.py -v`

Expected: PASS, including byte-identical repeated serialization.

- [ ] **Step 5: Commit the evidence schema**

```bash
git add src/pcb_copilot/evidence tests/evidence/test_index.py
git commit -m "feat: add structured PCB evidence index"
```

### Task 2: Content verification and archive service

**Files:**
- Create: `src/pcb_copilot/evidence/archive.py`
- Create: `tests/evidence/test_archive.py`
- Modify: `scripts/collect_references.py`

**Interfaces:**
- Produces: `sniff_media_type(payload: bytes) -> str`
- Produces: `archive_document(project: Project, part_number: str, url: str, roles: set[EvidenceRole], payload: bytes, retrieved_on: date) -> EvidenceRecord`
- Preserves CLI: `python scripts/collect_references.py add PROJECT PART URL`

- [ ] **Step 1: Port current bad-payload cases into failing tests**

```python
@pytest.mark.parametrize("payload", [
    b"<html><title>Login</title></html>",
    b"<!doctype html><body>Access denied</body>",
])
def test_archive_rejects_html_named_pdf(project_copy, payload):
    with pytest.raises(InvalidEvidencePayload, match="HTML"):
        archive_document(
            load_project(project_copy),
            "BMP390",
            "https://example.test/BMP390.pdf",
            {EvidenceRole.DATASHEET},
            payload,
            date(2026, 9, 14),
        )
```

Add PDF (`%PDF-`), KiCad, Eagle XML, and generic text fixtures based on the
current `collect_references.sniff()` behavior.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/evidence/test_archive.py -v`

Expected: FAIL because `archive_document()` is missing.

- [ ] **Step 3: Implement hash-addressed archival with readable filenames**

Write under `PROJECT/evidence/files/`. Sanitize the URL basename, reject a
payload whose sniffed media type conflicts with a claimed PDF, compute SHA-256,
and reuse an existing record with the same hash rather than copying bytes.
Merge new roles, component refs, and part numbers into that record.

Convert `scripts/collect_references.py` into a compatibility CLI that calls the
new service. Retain `suggest`, `add`, and `verify` command spellings until the
new research CLI is documented and tested.

- [ ] **Step 4: Prove a failed archive is transactional**

Capture the evidence directory tree before an invalid payload, call
`archive_document()`, and assert the tree and index bytes remain unchanged.

Run: `uv run pytest tests/evidence/test_archive.py -v`. Expected: PASS.

- [ ] **Step 5: Run the original enforcement cases**

Run: `uv run python scripts/selftest_enforcement.py`

Expected: exit `0`, including the HTML-login-wall and provenance checks.

- [ ] **Step 6: Commit archive compatibility**

```bash
git add src/pcb_copilot/evidence/archive.py tests/evidence/test_archive.py scripts/collect_references.py
git commit -m "refactor: preserve verified evidence archival"
```

### Task 3: Exact extraction and cited facts

**Files:**
- Create: `src/pcb_copilot/evidence/extract.py`
- Create: `src/pcb_copilot/evidence/facts.py`
- Create: `tests/evidence/test_extract.py`
- Modify: `scripts/fetch_reference_doc.py`

**Interfaces:**
- Produces: `EvidenceFact(subject: str, predicate: str, value: str, unit: str | None, evidence_id: str, pages: tuple[int, ...], confidence: Literal["exact", "review_required"])`
- Produces: `extract_eagle_connections(path: Path, part: str) -> tuple[EvidenceFact, ...]`
- Produces: `render_pdf_pages(path: Path, pages: Sequence[int], output_dir: Path) -> tuple[Path, ...]`
- Preserves CLI forms: `python scripts/fetch_reference_doc.py eagle projects/baro-bmp390/evidence/files/BMP390_Adafruit_20BMP390.sch BMP390` and `python scripts/fetch_reference_doc.py pdf projects/tms-v3/evidence/files/xbee3_hardware_ref.pdf --pages 15,16`

- [ ] **Step 1: Write failing extraction characterization tests**

Use the archived Adafruit BMP390 Eagle schematic and assert that extraction
finds the known 4.7 kΩ pull-ups and VDD/VDDIO connections. Use a temporary
output directory for rendered PDF pages.

```python
def test_bmp390_eagle_extraction_keeps_source_identity(repo_root):
    source = repo_root / "projects/baro-bmp390/reference-designs/BMP390_Adafruit_20BMP390.sch"
    facts = extract_eagle_connections(source, "BMP390")
    assert any(f.value == "4.7k" and f.confidence == "exact" for f in facts)
    assert all(f.evidence_id and f.pages for f in facts)
```

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/evidence/test_extract.py -v`

Expected: FAIL because typed facts are absent.

- [ ] **Step 3: Wrap the current parsers rather than rewriting them**

Move or import `parse_eagle_schematic()`, `find_pins_for_part()`, and
`render_pdf_pages()` with unchanged parsing behavior. Add typed fact creation
at the boundary. PDF facts produced from OCR or visual interpretation use
`review_required`; values parsed exactly from source CAD use `exact`.

- [ ] **Step 4: Keep the old command operational and run tests**

Run: `uv run pytest tests/evidence/test_extract.py -v`

Run the existing Eagle command against the BMP390 fixture and compare its
component/net output with the pre-change output saved in the test fixture.

Expected: PASS and no output regression.

- [ ] **Step 5: Commit cited extraction**

```bash
git add src/pcb_copilot/evidence/extract.py src/pcb_copilot/evidence/facts.py tests/evidence/test_extract.py scripts/fetch_reference_doc.py
git commit -m "feat: attach citations to extracted evidence facts"
```

### Task 4: Unified evidence checks and compatibility gates

**Files:**
- Create: `src/pcb_copilot/evidence/checks.py`
- Create: `tests/evidence/test_checks.py`
- Modify: `scripts/check_datasheets.py`
- Modify: `scripts/check_research.py`
- Modify: `scripts/run_gates.py`

**Interfaces:**
- Produces: `check_evidence(project: Project, pcb_inventory: Sequence[Part]) -> list[Finding]`
- Preserves: `gate_datasheets()` and `gate_research()` tuple return interface
- Consumes: the single evidence index and the existing scoped-deviation parser

- [ ] **Step 1: Write failing behavior-parity tests**

For each board, record the current datasheet and research gate result. Build a
temporary unified index from its existing Markdown indexes and assert the new
checker reports the same blocking status and offending refs.

Add faults for a missing file, wrong hash, HTML payload, missing source URL,
missing datasheet role, missing reference role, missing design-basis row, and
a rule-scoped deviation incorrectly attempting to waive evidence.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/evidence/test_checks.py -v`

Expected: FAIL because unified checks are not implemented.

- [ ] **Step 3: Implement checks with explicit scope**

Return one `Finding` per actionable issue. A part requiring a datasheet must
match an indexed existing file carrying the `datasheet` role. A module may
also require an `integration_manual` or `module_pinout` role. Reference-design
coverage accepts manufacturer EVMs or proven open hardware, but never treats a
teaching reference as manufacturer evidence.

Modify the legacy gate functions to render these findings into their current
`tuple[bool, str]` form. Do not duplicate evidence rules in the wrappers.

- [ ] **Step 4: Run compatibility and fault-injection tests**

Run: `uv run pytest tests/evidence/test_checks.py -v`

Run: `uv run python scripts/selftest_enforcement.py`

Expected: all tests pass and every injected evidence fault blocks.

- [ ] **Step 5: Commit unified evidence gates**

```bash
git add src/pcb_copilot/evidence/checks.py tests/evidence/test_checks.py scripts/check_datasheets.py scripts/check_research.py scripts/run_gates.py
git commit -m "refactor: use one evidence checker for PCB gates"
```

### Task 5: Board-by-board evidence migration and deduplication

**Files:**
- Create: `scripts/migrate_evidence.py`
- Create: `tests/evidence/test_migration.py`
- Create: `projects/*/evidence/index.yaml`
- Move: `projects/*/datasheets/*` to `projects/*/evidence/files/`
- Move: `projects/*/reference-designs/*` to `projects/*/evidence/files/`
- Modify: project `DESIGN_BASIS.md`, `REQUIREMENTS.md`, `DEVIATIONS.md`, generators, and KiCad descriptions that link to moved evidence
- Delete after verification: old evidence `INDEX.md` files and exact duplicate TMS PDFs

**Interfaces:**
- Produces: `migrate_legacy_evidence(project: Project, dry_run: bool = True) -> MigrationReport`
- Consumes: old Markdown indexes and actual file hashes

- [ ] **Step 1: Write dry-run migration tests**

```python
def test_dry_run_does_not_change_project(project_copy, tree_hash):
    before = tree_hash(project_copy)
    report = migrate_legacy_evidence(load_project(project_copy), dry_run=True)
    assert report.records_created > 0
    assert tree_hash(project_copy) == before
```

Add a test proving the two byte-identical TMS XBee PDFs become one record with
both roles, and the same for the Teensy front pinout card.

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/evidence/test_migration.py -v`

Expected: FAIL because migration is absent.

- [ ] **Step 3: Implement deterministic dry-run and apply modes**

Require every legacy `->` row to resolve to an existing file and a source URL.
Group by SHA-256, merge roles and references, and report every planned move,
merge, rewritten link, and deletion. `--apply` writes the new index first,
verifies it, updates textual references, and only then removes duplicate paths.

- [ ] **Step 4: Migrate one board per commit**

Run the following PowerShell loop. It uses literal project names, verifies each
board, and creates one migration commit per board:

```powershell
foreach ($board in @("baro-bmp390", "imu-icm42688", "gnss-neom9n", "tms-v3")) {
    uv run python scripts/migrate_evidence.py "projects/$board"
    uv run python scripts/migrate_evidence.py "projects/$board" --apply
    uv run pytest tests/evidence -q
    uv run python scripts/run_gates.py "projects/$board/$board.kicad_pcb"
    git add "projects/$board"
    git commit -m "refactor: migrate $board evidence"
}
```

Expected: the dry-run and apply reports agree; evidence-related gate results
match the recorded pre-migration baseline. Other known board failures remain
visible and are not treated as migration failures.

The loop must yield four commits named for the literal board migrated.

- [ ] **Step 5: Verify repository-wide evidence integrity**

Run: `uv run pytest tests/evidence -q`

Run: `uv run python scripts/audit_workflow.py`

Run a SHA-256 duplicate scan over `projects/*/evidence/files/`.

Expected: zero unexplained duplicate hashes, all evidence indexes valid, and
the workflow audit uses the unified gates.

- [ ] **Step 6: Commit migration tooling and final cross-reference fixes**

```bash
git add scripts/migrate_evidence.py tests/evidence projects docs CLAUDE.md .claude
git commit -m "refactor: unify project evidence archives"
```

### Task 6: Research CLI and evidence documentation

**Files:**
- Create: `src/pcb_copilot/evidence/commands.py`
- Modify: `src/pcb_copilot/cli.py`
- Create: `tests/evidence/test_cli.py`
- Modify: `docs/WORKFLOW.md`
- Modify: `docs/PROJECT_FORMAT.md`
- Modify: `docs/LIMITATIONS.md`

**Interfaces:**
- Adds parser positional `project_path` and mutually exclusive operations
  `--verify`, `--add PART URL --role ROLE`, and `--extract PART`.
- Concrete smoke forms: `pcb-copilot research projects/baro-bmp390 --verify`
  and `pcb-copilot research projects/baro-bmp390 --extract BMP390`.

- [ ] **Step 1: Write failing CLI tests with a fake downloader**

Assert `--verify` is read-only, `--add` archives and indexes exactly one file,
and `--extract` prints facts with file and page citations. Inject the downloader
function; do not access the network in these tests.

- [ ] **Step 2: Run and verify missing-command failure**

Run: `uv run pytest tests/evidence/test_cli.py -v`

Expected: FAIL because research options are absent.

- [ ] **Step 3: Implement the thin CLI layer**

The command delegates to the archive, extract, and check modules. It prints
machine failures, review-required facts, and conflicts separately. It never
edits `REQUIREMENTS.md` or `DESIGN_BASIS.md`; it prints proposed rows for human
review.

- [ ] **Step 4: Run tests and document the workflow**

Run: `uv run pytest tests/evidence/test_cli.py -v`

Run: `uv run pcb-copilot research projects/baro-bmp390 --verify`

Expected: PASS and a cited, read-only evidence report.

- [ ] **Step 5: Commit the research interface**

```bash
git add src/pcb_copilot/evidence/commands.py src/pcb_copilot/cli.py tests/evidence/test_cli.py docs/WORKFLOW.md docs/PROJECT_FORMAT.md docs/LIMITATIONS.md
git commit -m "feat: add cited PCB research assistant"
```

## Plan 2 Completion Check

- [ ] `uv run pytest tests/evidence -q` exits `0`.
- [ ] `uv run python scripts/selftest_enforcement.py` exits `0`.
- [ ] Evidence-related gates match the baseline for all four boards.
- [ ] Every evidence record resolves to existing bytes with a matching hash.
- [ ] Exact duplicate evidence bytes have one canonical path and multiple roles.
- [ ] Existing collection and extraction command spellings still work.
- [ ] Stop for human review before starting schematic work.
