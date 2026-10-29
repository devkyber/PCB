# Reproduce the fault evaluation

Run this small software regression exercise before making claims about the
pipeline's rejection behavior. It uses the current
[GPIO indicator](../examples/gpio-indicator/README.md) as read-only source and
copies only the shared pipeline's declared inputs into new external workspaces.
The example remains an unbuilt educational DRAFT.

From the repository root, with Python 3.11+ and the dependencies installed:

```sh
uv sync
uv run python tools/evaluate.py
```

The quick mode needs no KiCad executable and should finish quickly on a normal
development machine. Measured durations belong to individual runs; the harness
does not establish performance superiority or a guaranteed runtime.

To exercise real native previews before changing a candidate, saved schematic
or saved rule file:

```sh
uv run pcb-copilot doctor
uv run python tools/evaluate.py --native
```

Native mode requires the supported KiCad 10 toolchain. It may take longer.
If native mode is not requested, its six cases are explicitly skipped. If it is
requested but cannot run, that is an execution error, not a passed case.

Both commands print the retained external directory containing `report.md`,
`evaluation.json`, raw process logs and disposable snapshots. Use
`--output NEW_EXTERNAL_DIRECTORY` to select a new directory outside the checkout.
An existing directory is rejected; the harness does not overwrite owner files.

## Recorded Windows run

The [2026-10-29 run](evaluation/2026-10-29/report.md) observed all **13 enabled
expectations** in **38.15 seconds**, using Python 3.13.14 and KiCad 10.0.6 on
Windows 11. Five valid controls passed: archive verification, footprint resolution
and three independent native previews. Eight deliberately invalid requests were
rejected with their expected diagnostics, including candidate, saved-schematic
and saved-rule changes after their respective successful previews.
All 42 declared source input entries and the evaluated implementation stayed
unchanged. This is one run of the declared cases below, not a general accuracy
or speed claim.

The published [machine-readable record](evaluation/2026-10-29/evaluation.json)
includes exact commands, source/implementation hashes, injected-fault details,
process timings and environment. Its adjacent `logs/` retain all **26 raw output
streams**, including empty streams as zero-byte files. Candidate and snapshot
input hashes were preserved after each deliberate injection. Disposable CAD
copies and generated preview trees remain external; rerun
the command to obtain a complete local packet for inspection.

## Declared cases

| Case | Interface actually exercised | Expected observation |
| --- | --- | --- |
| Evidence control | `pcb-copilot research --verify` | Current archive bytes verify; exit 0 |
| Footprint control | `pcb_copilot.layout.footprints.resolve_footprint` | All physical example references resolve with real declared geometry |
| Missing preview | `pcb-copilot update-schematic --candidate … --apply` | Specific matching-preview guard rejects; exit 2 |
| Corrupted evidence | `pcb-copilot research --verify` | `archive.hash_mismatch`; exit 1 |
| Altered footprint pad size | `resolve_footprint` | Exact upstream-copy comparison rejects even after refreshing the local receipt hash |
| Corrupted local model bytes | `resolve_footprint` | Pinned model hash rejects |
| Changed native MPN | `resolve_footprint` | Selected native part and receipt identity disagree |
| Native preview control, optional | `pcb-copilot update-schematic --candidate …` | A genuine successful unapplied native preview and binding are returned |
| Candidate changed after preview, optional | Same public command with `--apply` | Matching-preview guard rejects the changed candidate; exit 2 |
| Saved-schematic preview control, optional | A new independent native snapshot and preview | Successful preview binds the exact saved source, candidate and options |
| Saved schematic changed after preview, optional | Same public command with `--apply` | Matching-preview guard rejects the later saved source bytes; exit 2 |
| Saved-rule preview control, optional | A new independent native snapshot and preview | Successful preview binds the exact saved source, candidate and options |
| Saved `.kicad_dru` changed after preview, optional | Same public command with `--apply` | Matching-preview guard rejects the later companion-rule bytes; exit 2 |

Each independent quick case starts from a fresh exact snapshot. Each native
control and its dependent stale-input trial share one disposable workspace;
the three pairs use separate snapshots and candidates. A dependent rejection
is skipped if its own real successful matching preview was not obtained.
All three faults append one trailing newline after the actual preview. They
demonstrate byte-bound authorization without changing circuit or rule semantics.
No preview authorization or human sign-off record is fabricated.

The direct API cases are explicitly labeled `validator-api`. They establish
those validators' responses; they do not imply that full CLI review, native ERC,
DRC, visual inspection or release ran. A failed positive control cannot count
as a successful evaluation. A fault passes its expectation only when both its
actual exit code and the specific expected diagnostic match.

## Read the results

`evaluation.json` records each expected outcome, actual process exit code,
diagnostic requirement, exact executed arguments, raw-log paths, elapsed time,
fault target, environment and before/after input hashes. It also fingerprints
the evaluated Python implementation. Source inputs and implementation are
checked again at the end; a changed source or implementation invalidates the run.
The checker must preserve each snapshot's inputs after the deliberate injection.
Native controls and rejections must also preserve every declared input of their
separate candidate project. Candidate and fault-target hashes are checked after
the command; a matching rejection diagnostic cannot conceal a candidate write.

Harness exits are:

| Exit | Meaning |
| --- | --- |
| 0 | All enabled expectations were observed; skipped cases remain skipped |
| 1 | At least one observed response differed from its declared expectation |
| 2 | A process, dependency, snapshot, parsing or preservation error prevented a trustworthy run |

These cases form a small manually selected fault set, not a measured detection
rate over possible PCB failures. A correct rejection is useful software evidence.
It does not prove electrical correctness, physical fit, readability, thermal or RF
behavior, manufacturability, or suitability for an application. The harness
creates no fabrication release and completes no human decisions. See
[Limitations](LIMITATIONS.md) and the [review workflow](WORKFLOW.md#4-review-and-record-human-decisions).

Run-specific results describe their recorded hashes and environment. Rerun after
inputs or implementation change; do not attach new hashes to an old report.
