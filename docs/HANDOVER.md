# Portable review handover

Make a source-bound inspection packet from saved KiCad CAD:

```sh
uv run pcb-copilot report examples/gpio-indicator --output /path/to/new/handover
```

Use a new directory outside the source project. On Windows, for example,
`--output C:/work/gpio-handover`. Existing directories and symlinks/junctions
are rejected. Save the current design first: unsaved KiCad buffers cannot be
captured. Native generation requires the toolchain described in
[Quickstart](QUICKSTART.md).

Open `index.html` in a browser. It works offline and includes every exported
schematic page, assembly, top copper and mirrored underside, plus the complete
review findings and captured source ledger. Search checks, filter their result
or kind, enlarge a native view, or download the embedded vector schematic PDF.
The views, findings and hashes remain readable with JavaScript disabled.

The report runs the registered review on an isolated copy and exports images
from a separate input-identical snapshot. It rechecks the source before and
after publication. It applies no CAD changes and creates no human decisions.
A blocked review still produces an inspectable packet and returns **1**.
Generation errors return **2**. A report with no registered blocker returns
**0**, which is not fabrication approval.

## Verify a received packet

Verification needs the Python package, without KiCad or a browser:

```sh
uv run pcb-copilot verify-report /path/to/handover
uv run pcb-copilot verify-report /path/to/handover --project examples/gpio-indicator
```

The first command checks the complete artifact inventory, byte counts and
SHA-256 values, plus agreement between source and review records. The second
also compares the current saved project's entire declared input ledger.
It returns **1** if that saved project differs; an invalid or incomplete packet
returns **2**. Integrity verification can return **0** for a report whose
engineering review is blocked: these are separate results in the JSON output.

`index.html` is self-contained; the whole directory additionally retains the
original vector PDF, full-resolution PNGs, `review.json`, `source.json` and
`manifest.json`. Keep the entire directory for command-line verification.
The manifest is published last. A forcibly terminated process can leave a
partial directory; a missing/invalid manifest must not be treated as complete.
Handled failures remove only unchanged files created by that operation. A
concurrent owner file is retained and its directory is identified in the error.

These hashes establish recorded byte identities. They do not attest who ran
the checks, prove that a reviewer inspected correctly, or qualify the hardware.
Source paths identify evidence available in the design; the packet does not
redistribute every source document or live-update when CAD changes. See
[Limitations](LIMITATIONS.md) and the [review workflow](WORKFLOW.md#4-review-and-record-human-decisions).

## Recorded example

The [GPIO review packet](demos/gpio-review/index.html) contains a real native
KiCad capture and current review findings. Download `index.html` to inspect it
offline; GitHub's source viewer does not execute it. Its
[manifest](demos/gpio-review/manifest.json) and [review JSON](demos/gpio-review/review.json)
make the captured scope inspectable. The board remains an unbuilt DRAFT.
