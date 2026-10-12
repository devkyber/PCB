# TMS pipeline validation — 2026-10-07

The saved-native workflow was exercised through research, supplier import,
schematic and layout previews, attempted application, review, sign-off worksheet,
quotation preview, release refusal and cleanup. All 25 CLI commands returned
their expected outcomes. A separate live stock probe also passed.

The blocking paths behaved as expected: TMS still has seven failing review
checks, and neither an update nor a fabrication release was accepted. This run
does not establish a successful manufacturing export or release on TMS.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 

## Executed checks

| Stage | Observed result |
| --- | --- |
| Status and archived evidence | Passed; current design remains DRAFT and archived sources verified |
| Research search plan, extraction and reference-pair comparison | Passed for the existing ADS1220 evidence; the search plan itself is not a live search |
| Live supplier lookup and import | C48263 matched ADS1220IPWR; native symbol, footprint and models imported into a separate disposable project while preserving all existing library assets |
| Manufacturer evidence acquisition | TI ADS1220 document retrieved and verified in the separate supplier test copy |
| Import safeguards | Repeat import and deliberately mismatched MPN refused without changing inputs |
| Native schematic preview | Seven-page PDF, ERC and metrics produced; two disconnected-pin errors and board parity prevented application |
| Native layout preview | SVG, STEP, topology and DRC artifacts produced; both refilled DRC runs reported 1 error, 15 warnings and 4 unconnected items; application refused |
| Shared review | All 14 checks executed: 7 passed, 7 failed; no later checks were hidden by earlier failures |
| Sign-off worksheet | All 12 items created unsigned, including both mandatory shared items; a second creation refused to overwrite it |
| Quotation preview | Refused to finish BOM export because J1/J2 have conflicting values without an exact MPN; previous preview placeholder preserved |
| Fabrication release | Refused after the complete review; previous fabrication placeholder preserved and no release state created |
| Live stock function probe | Exact U3 identity checked successfully at quantity one, with a hashed supplier response; this was not a full-board BOM check |
| Cleanup | Planned and removed the same 12 allowlisted preview files; a second plan was empty; unknown scratch content, retained report and output placeholders survived |

The seven failing review checks are ERC, schematic ownership/netmap freshness,
schematic/PCB parity, native DRC, the independent manufacturing baseline,
assembly contracts and human sign-off. Their exact results are retained in the
[machine record](records/pipeline-validation-20261007.json). They agree with the
[earlier current-design audit](records/rework-baseline-20261007.json).

## Preservation and visual evidence

All 68 existing declared TMS input files retained their hashes. Every original
file in the active project was also unchanged at the end of the command run.
The native candidate remained byte-identical. Only the separate test copies
received imported assets, unsigned worksheets and reproducible previews.
The pipeline source code did not change during this run.

Each of the seven new PDF pages rendered identically to its corresponding page
from the already inspected saved schematic. The prior page/circuit-scale
inspection and its remaining readability findings therefore still apply; see
[visual provenance](records/visual-baseline-20261007.json). The new board SVG was
opened and inspected. KiCad reported missing J1/J2 models during STEP export;
the pipeline retained its partial-model advisory. Export success is not proof
of a complete assembly or mechanical fit.

## Coverage limits

Successful CAD application and fabrication publication were not reached on this
blocked board. J1/J2 identity also prevented completed BOM/CPL output, full-board
stock checking, assembly export and quotation-preview publication. These gates
were not bypassed to make the run green.

This run used the current native CAD workflow. It did not replay historical
intent, redraw the circuit or invoke optional autorouting. No human sign-off,
circuit decision, fabrication approval or supplier order was made.

KiCad version: **10.0.6**. The machine record includes source hashes, exact
commands, exit codes, durations and preservation checks. Full logs, both
disposable projects, native candidate and retained preview artifacts are outside
CODE in:

```text
C:\Users\tae06\.codex\archives\pcb\tms-pipeline-validation-20261007-195259
```

`metadata.json` there fingerprints the actual working Python sources; the Git
commit alone does not describe the existing uncommitted pipeline changes.
The active project received only this note, its machine record and a README link
after the run finished.
