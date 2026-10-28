# Quickstart

Start with the small four-channel GPIO indicator, then try a checked schematic
change in a disposable copy. The example is an unbuilt educational `DRAFT`;
the demo records no owner approval or fabrication release.

## Install the tools

You need Git, Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/)
and [KiCad 10](https://www.kicad.org/download/) with its standard libraries.
KiCad must provide both `kicad-cli` and a Python interpreter that can import
`pcbnew`. `uv sync` installs this repository's Python dependencies; it does not
install KiCad or its Python bindings.

The commands below can be entered individually in PowerShell or a POSIX shell.
The current development environment is Windows with KiCad 10. Linux and macOS
tool discovery exists, but an end-to-end platform test matrix is still pending.

```sh
git clone https://github.com/devkyber/PCB.git
cd PCB
uv sync
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

## Inspect Rover and the first-use demo

Rover is the retained owner board. Its [project README](../projects/rover-pdb/README.md)
describes the current CAD and unresolved engineering decisions. Read-only use is:

```sh
uv run pcb-copilot status projects/rover-pdb
uv run pcb-copilot research projects/rover-pdb --verify
uv run pcb-copilot review projects/rover-pdb
```

Rover's captured full review blocks on missing datasheet evidence for NT1–NT3
and P1–P4, plus 0/7 current human decisions. Read every current finding rather
than treating the expected sign-off block as the only possible failure.

The separate first-use demo copies Rover's declared inputs outside the checkout.
Its quick mode runs status, evidence verification and a real rejection of an
apply request without a successful preview. It needs the Python dependencies
but can run without KiCad. Choose a destination that does not already exist.
For example, on Windows:

```powershell
uv run python tools/demo.py --output C:/work/pcb-copilot-demo
```

On Linux or macOS, an equivalent destination is `/tmp/pcb-copilot-demo`.
Omit `--output` to create a new system temporary directory automatically.
Run from the repository root, then open the printed `report.md` path.

The output contains:

- `report.md`: results and their interpretation.
- `transcript.json`: actual exit codes, timings and input/CAD hashes.
- `logs/`: stdout and stderr from each command.
- `workspace/rover-pdb/`: the disposable input copy.

With KiCad available, add `--full` to run all registered review checks, including
native ERC and DRC:

```powershell
uv run python tools/demo.py --full --output C:/work/pcb-copilot-demo-full
```

Quick mode normally exits **0** when its steps complete and evidence verifies.
Full mode preserves the review's actual blockers: expect exit **1** for the
included board's evidence and sign-off findings. Exit **2** means the demo could not complete or an
input-preservation check failed. Inspect the report and logs in each case.
Neither mode creates human sign-off or a fabrication package.

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
