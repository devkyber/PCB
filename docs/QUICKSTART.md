# Quickstart

To inspect the examples before installing tools, open the
[interactive browser workbench](https://devkyber.github.io/PCB/). Search native
parts and pins, trace saved nets, and inspect the schematic/copper/3D views beside
their source evidence. It also works as a [downloaded offline file](EXPLORER.md).

Start with the small four-channel GPIO indicator, then try a checked schematic
change in a disposable copy. The example is an unbuilt educational `DRAFT`;
the demo records no owner approval or fabrication release.

## Get a first result without KiCad

For the quick demo, you need Git, Python 3.11+ and
[uv](https://docs.astral.sh/uv/getting-started/installation/). KiCad is optional
for this first step. Run these commands individually in PowerShell or a POSIX
shell:

```sh
git clone https://github.com/devkyber/PCB.git
cd PCB
uv sync
uv run python tools/demo.py
```

The default is the small [GPIO indicator](../examples/gpio-indicator/README.md).
The demo copies its declared inputs to a new external temporary directory, runs
status and archive verification, and exercises a real rejection of an apply
request without a successful preview. **Quick mode does not run native ERC/DRC
or apply a change.** The source design stays untouched.

Open the printed `report.md` path. Its directory contains:

- `report.md`: what each result means and which checks were run.
- `transcript.json`: actual process exit codes, timings and input/CAD hashes.
- `logs/`: each command's exact stdout and stderr.
- `workspace/gpio-indicator/`: the disposable input copy.

| Demo exit code | Meaning |
| --- | --- |
| `0` | Quick steps completed and archived evidence verified. In full mode, no registered blocker was reported. |
| `1` | Archive verification or the optional full review reported blockers. Read the findings; this is separate from a runtime failure. |
| `2` | The demo could not complete, its output was inconsistent, or saved inputs changed during the run. Inspect its exact logs. |

Choose a new destination with `--output NEW_EXTERNAL_DIRECTORY`, or omit it to
get a new system temporary directory. The destination must not already exist
and must be outside the checkout. For example, use
`--output C:/work/pcb-copilot-demo` on Windows or
`--output /tmp/pcb-copilot-demo` on Linux/macOS.

Neither mode creates human sign-off or a fabrication package. The recorded
Rover walkthrough in the repository's media is a historical Rover run; the
current default demo selects GPIO and reports its actual project name.

## Enable native CAD checks

Install [KiCad 10](https://www.kicad.org/download/) with its standard libraries
for native review and checked changes. The pipeline needs both `kicad-cli` and
a Python interpreter that can import KiCad's `pcbnew` bindings. `uv sync`
installs this repository's Python dependencies; it does not install KiCad or
its Python bindings.

For an offline visual handover after setup, run
`uv run pcb-copilot report examples/gpio-indicator --output NEW_EXTERNAL_DIRECTORY`.
Open its `index.html` to inspect native views and filter actual review findings.
The [handover guide](HANDOVER.md) explains generation, blocked results and
verification without KiCad.

The current development environment is Windows with KiCad 10. Linux and macOS
tool discovery exists, but an end-to-end platform test matrix is still pending.

```sh
uv run pcb-copilot doctor
```

Resolve any required-tool failures reported by `doctor` before running a CAD
review. Java and Freerouting are only needed for optional autorouting; the
quickstart does not use them.

### If KiCad Python is missing

The pipeline uses a separate KiCad Python process for native board operations.
Discovery checks `KIPYTHON`, then a `kipython` executable on `PATH`. On Windows,
it also tests `python.exe` beside the discovered `kicad-cli.exe`.

If discovery misses your installation, set `KIPYTHON` to an interpreter that
can import `pcbnew` in isolated mode. For a standard Windows KiCad 10 install,
the PowerShell commands are:

```powershell
$env:KIPYTHON = 'C:/Program Files/KiCad/10.0/bin/python.exe'
& $env:KIPYTHON -I -c "import pcbnew; print(pcbnew.GetBuildVersion())"
uv run pcb-copilot doctor
```

Use your actual installation path. On Linux or macOS, select the interpreter
provided by your KiCad installation and use
`export KIPYTHON=/absolute/path/to/interpreter`. Verify the same isolated import.
Setting `KIPYTHON` to the uv environment's Python does not install `pcbnew` there.
If `kicad-cli` is missing, install KiCad or put its binary directory on `PATH`.

## Inspect the small example

The [GPIO indicator](../examples/gpio-indicator/README.md) is a complete,
single-sheet KiCad design with four 0 to 3.3 V LED inputs, a routed two-layer
PCB, archived manufacturer evidence and project-local libraries. Run these
read-only commands from the repository root:

```sh
uv run pcb-copilot status examples/gpio-indicator
uv run pcb-copilot research examples/gpio-indicator --verify
uv run pcb-copilot review examples/gpio-indicator
```

What to look for:

| Command | Expected result |
| --- | --- |
| `status` | The project name, `DRAFT` lifecycle, saved CAD paths and discovered KiCad CLI. A fresh clone has no local review or release record. |
| `research --verify` | Verified archived evidence records and `MACHINE FAILURES: none` when the included archive is intact. This checks source bytes, not the circuit's engineering validity. |
| `review` | A result for each registered check, with its stated scope. The example's saved A1 review blocks on missing exact-part assembly rotation rules and 0/5 current human decisions. Expect `assembly_contracts` and `signoff` failures, with `RESULT: BLOCKED`. |

`review` returns exit code **1** when any check blocks. Read every failed check:
a missing tool, an altered input or a CAD finding is additional work, even when
the human sign-off block is expected. An unsigned review is not an installation
failure, and a clean ERC or DRC does not grant fabrication approval.

Review runs against a temporary copy and does not rewrite the source CAD.
For structured output, use:

```sh
uv run pcb-copilot review examples/gpio-indicator --format json
```

The [saved review](../examples/gpio-indicator/output/review-a1.json) records
clean native ERC/DRC, exact schematic/PCB parity and the remaining blockers for
that snapshot. Actual GPIO loading, LED behavior, fit and assembly still need
qualification. After any edit, rerun checks on the new bytes.

## Try a scoped native change

With the KiCad toolchain ready, run one command:

```sh
uv run python tools/demo_change.py
```

This creates a new external temporary workspace from the GPIO example. It
changes only the title-block revision, runs a successful preview, changes that
revision again and demonstrates rejection of the stale preview. It then runs a
fresh preview, compares native component/pin/net inventories and **stops for
visual inspection**. Exit 0 at this stage means the preview is ready; the
candidate has not been applied.

Open the printed `review/schematic.pdf`. Inspect every sheet at page and circuit
scale against [schematic readability](DESIGN_RULES.md#schematic-readability).
After inspection, use the printed directory and exact PDF hash to resume:

```sh
uv run python tools/demo_change.py --resume "/path/to/printed-directory" --apply --reviewed-render-sha256 "PRINTED_PDF_SHA256" --reviewer "Your author-review identity"
```

Replace the path and hash with your run's values. This records your author
inspection and applies the candidate only to the disposable snapshot. It checks
that the inspected PDF, candidate and saved inputs still match the preview,
and that the PCB remains unchanged. This author review is separate from the
five human release decisions. Exit 2 means the proof could not complete;
inspect its report and exact logs.

The printed directory retains `report.md`, `transcript.json`, `logs/`, the
candidate, the review PDF, native inventories and disposable workspace.
Use `--output NEW_EXTERNAL_DIRECTORY` to choose a new destination outside the
checkout. The [recorded proof](media/change-proof.md) publishes the actual
preview/rejection/apply results and hashes from one completed run.

## Select another project

Use `--project` to choose a declared project under `examples/` or `projects/`.
Selection is relative to this checkout. Test fixtures and paths outside the
checkout are rejected; fixtures never become projects through this demo.

Rover remains available explicitly. Its
[project README](../projects/rover-pdb/README.md) describes the retained owner CAD
and unresolved engineering decisions:

```sh
uv run python tools/demo.py --project projects/rover-pdb
uv run python tools/demo.py --project projects/rover-pdb --full
uv run pcb-copilot status projects/rover-pdb
uv run pcb-copilot research projects/rover-pdb --verify
```

With the native toolchain ready, full review of the default GPIO example is:

```sh
uv run python tools/demo.py --full
```

Full mode adds the registered review checks, including native ERC and DRC, on
the disposable copy. Expect exit **1** for GPIO's missing assembly contracts
and unsigned human decisions. Rover's captured full review blocks on missing
datasheet evidence for NT1–NT3 and P1–P4, plus 0/7 current human decisions. Read
every current finding rather than treating an expected sign-off block as the
only possible failure.

Each report uses the selected project's actual name and links to
`workspace/<project folder>/`. Run `uv run python tools/demo.py --help` for
project/output options and exit semantics.

## Make your first scoped change

Follow the [working workflow](WORKFLOW.md) before editing a board. It explains
how to start from saved native CAD, prepare a separate candidate, inspect fresh
renders, preview the exact change and then apply it explicitly. Read the
[design rules](DESIGN_RULES.md) and [limitations](LIMITATIONS.md) before drawing
or interpreting check results.

For a new project, start with the template and captured requirements described
in [Start a new board](WORKFLOW.md#start-a-new-board). Test fixtures are regression
inputs and must not be used as starting designs. See the [roadmap](ROADMAP.md)
for the next implementation priorities.
