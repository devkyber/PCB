# PCB Project Format

Each board lives below `projects/BOARD_NAME/`. The accepted KiCad schematic
and PCB remain in that directory and are named by the board. A versioned
`project.yaml` declares paths and lifecycle metadata without moving legacy
files during migration.

## Manifest

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
safety_tags:
  - pressure_sensor
  - i2c
```

All configured paths are relative to the project directory. The loader
resolves them to absolute paths and rejects any value that escapes the project
root. Unknown manifest fields are rejected so misspellings do not silently
change behavior.

`lifecycle` accepts `DRAFT`, `HUMAN_REVIEWED`, or `RELEASED`. Effective state
is stricter than the manifest: reviewed or released status is valid only while
recorded schematic and PCB hashes match the accepted files. Any design change
returns the effective lifecycle to `DRAFT`.

## Accepted and derived files

```text
projects/BOARD_NAME/
├── project.yaml
├── BOARD_NAME.kicad_sch       accepted electrical source of truth
├── BOARD_NAME.kicad_pcb       accepted physical source of truth
├── BOARD_NAME.kicad_pro       KiCad project configuration
├── netmap.json                versioned connectivity review contract
├── REQUIREMENTS.md            owner requirements and measurable success
├── DESIGN_BASIS.md            evidence comparison and design decisions
├── DEVIATIONS.md              narrowly scoped waivers
├── SIGNOFF.md                 compatibility human-review record
├── schematic-intent.yaml      reproducible schematic intent, not acceptance
├── layout-intent.yaml         planned reproducible layout intent
├── evidence/
│   ├── index.yaml             structured provenance, roles, trust and hashes
│   └── files/                 archived exact source bytes
└── .pcb-copilot/              ignored local drafts, reports, and state
```

The evidence migration is complete: `datasheets/` and `reference-designs/`
have been replaced by the unified, hash-addressed archive. All four schematic
intents are present; layout intents remain planned. Legacy `STATUS.md`, `PIPELINE.json`, generators,
and build wrappers remain until their replacement gates pass.

Evidence files retain their exact downloaded bytes. `.gitattributes` disables
Git text/line-ending conversion under `evidence/files/`; do not format those
sources, including upstream whitespace. Hash verification must work after a
Windows checkout as well as in the acquisition workspace.

## Ownership and drafts

`SCHEMATIC_OWNER` is a compatibility tripwire. Missing means `generated`, as
before. `generated` permits regeneration only when the current canonical
schematic hash equals the last pipeline hash. `human` refuses generator
overwrite. Invalid values fail loudly.

New generation writes only under `.pcb-copilot/drafts/`. A target equal to an
accepted schematic/PCB or outside that directory is rejected before opening
the file. Each draft records its kind, project, timestamp, and accepted
base hashes. Acceptance checks those hashes again to prevent stale work from
overwriting newer human edits.

## Canonical hashes

KiCad regenerates UUIDs during semantically identical writes. The canonical
hash masks UUID tokens before SHA-256 and stores the first 12 hexadecimal
characters, preserving the established pipeline behavior. This detects design
content drift without treating UUID churn as an electrical change.

Canonical hashing is not a semantic circuit equivalence proof. Netmap parity,
ERC/DRC, previews, and human review remain separate checks.

## Safety tags

Tags select relevant checks and review prompts; they do not certify a board.
Current examples include `rf`, `battery_backup`, `inertial_sensor`,
`pressure_sensor`, `high_current`, and `pyrotechnic`. TMS V3 carries both
high-consequence tags and must never inherit a generic low-current sign-off.

## Manufacturing profiles

The profile names a versioned set of fabrication defaults and limits. It does
not override part datasheets, current calculations, RF stackup decisions, or
explicit project constraints. Fabrication outputs are derived from accepted
design files and must identify the hashes they describe.

See [Workflow](WORKFLOW.md), [Architecture](ARCHITECTURE.md), and
[Limitations](LIMITATIONS.md) for lifecycle and authority rules.
