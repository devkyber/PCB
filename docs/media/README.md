# Media sources and reproduction

These assets use saved native KiCad CAD and actual CLI results. Board images are
renders, not photographs. The animation is a visual walkthrough of recorded
results, not a screen recording or proof of autonomous circuit design.

| Asset | Contents |
| --- | --- |
| `hero.png` | Product introduction and a fresh native Rover 3D render |
| `social-preview.png` | 1280 × 640 image prepared for GitHub social sharing |
| `native-cad.png` | Fresh native schematic and PCB copper/silkscreen exports |
| `rover-3d.png` | Transparent native 3D render |
| `workflow.gif` | 16-second, 960 × 540 in-README walkthrough |
| `workflow.mp4` | Same walkthrough at 1280 × 720 / 24 fps |
| `demo-results.json` | Recorded command outcomes, findings and input hashes |
| `manifest.json` | Native commands, source hashes and output hashes |
| `gpio-demo.png` | One-sheet GPIO example beside its native 3D render |
| `gpio-turntable.gif` / `.mp4` | 48 actual native views of the unbuilt example |
| `gpio-3d.png` | Transparent native GPIO board render |
| `example-manifest.json` | Exact example CAD inputs and turntable outputs |
| `change-proof.md` / `.json` | Completed preview, stale rejection and inspected apply |
| [Evaluation graphic](../evaluation/2026-10-29/evaluation.png) | Three valid controls and six expected rejections from one recorded Windows run |

## Reproduce

Install the toolchain from [Quickstart](../QUICKSTART.md), then run from the
repository root:

```sh
uv sync --group media
uv run python tools/demo.py --project projects/rover-pdb --full
# A blocked review returns 1. The demo still prints its external transcript path.
uv run --group media python tools/render_readme_media.py --demo /path/to/transcript.json
uv run --group media python tools/render_example_media.py
```

The generator requires a real full-mode transcript for current Rover inputs,
refuses stale inputs, copies declared CAD and libraries to temporary storage,
then exports. It stages the complete bundle before publication, rechecks source
hashes, and installs its named assets with the manifest last. An encoding,
publication or source-check failure restores the previous bundle. If filesystem
errors prevent recovery, it retains a backup and prints its recovery path.
Individual replacements are atomic; simultaneous readers can observe a mixed
bundle during publication and should verify the manifest after it completes.
It does not modify circuits or create sign-offs.

Add `--work-dir /path/to/new/external-directory` to retain all sheet exports and
their contact sheet for visual review. Inspect every sheet at page and circuit
scale before replacing published assets. Inspect images and animation at their
README display size as well. Export success alone is not visual review.

Images can vary with KiCad, model libraries or encoder versions. Output hashes
identify this capture; they do not promise identical video bytes on every system.
The capture's `source_inputs` retain the exact original bytes.
`source_repository_inputs` separately identify the published Git blob bytes:
some pre-existing Rover text files change CRLF/LF during checkout. The landing
page checker accepts either recorded byte identity, and rejects changed content,
missing inputs, extra declared inputs or false preservation flags. This portable
check does not rerun native exports or establish new CAD qualification.

The example turntable uses 48 separate native KiCad 3D renders. It does not
invent intermediate geometry. To reproduce the scoped-change proof, run
`uv run python tools/demo_change.py`, inspect the printed preview, then use its
hash-bound resume command. [The published record](change-proof.md) describes
the exact author-inspected run; it is not owner fabrication approval.

Reproduce the evaluation graphic from its retained record and raw logs:

```sh
uv run --group media python tools/render_evaluation_media.py --record docs/evaluation/2026-10-29/evaluation.json --output /path/to/new/external-evaluation.png
```

The graphic embeds the record, raw-log, generator and font hashes in its PNG
metadata. It verifies the declared case outcomes and rechecks evidence bytes
before creating the new file. Its [bundle manifest](../evaluation/2026-10-29/manifest.json)
binds the published graphic, report, JSON and raw logs together.

## Visual direction: measured space

Native geometry carries the detail. Generous margins let the viewer inspect it,
while small technical markers suggest the precision of a laboratory drawing.
The composition keeps the source geometry and labels intact.

Dark slate establishes depth without competing with board materials. Pale type
and a restrained lime accent establish hierarchy; amber marks an open decision.
Contrast keeps the result readable at repository scale.

Instrument Sans introduces purpose in a few words. JetBrains Mono identifies
commands, stages and recorded facts. Their scale keeps the
artifact central and lets details reward closer inspection.

Motion follows the inspection sequence: native CAD, source verification, an
application guard, and the actual review result. Measured holds allow reading.
Blockers remain visible in the final frame.

Fonts are bundled for reproducible generation. Their SIL Open Font License
notices are under [fonts](fonts/).
