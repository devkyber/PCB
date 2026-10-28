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

## Reproduce

Install the toolchain from [Quickstart](../QUICKSTART.md), then run from the
repository root:

```sh
uv sync --group media
uv run python tools/demo.py --full
# A blocked review returns 1. The demo still prints its external transcript path.
uv run --group media python tools/render_readme_media.py --demo /path/to/transcript.json
uv run --group media python tools/render_example_media.py
```

The generator requires a real full-mode transcript for current Rover inputs,
refuses stale inputs, copies declared CAD and libraries to temporary storage,
then exports. It rechecks source hashes and writes only its named media assets.
It does not modify circuits or create sign-offs.

Add `--work-dir /path/to/new/external-directory` to retain all sheet exports and
their contact sheet for visual review. Inspect every sheet at page and circuit
scale before replacing published assets. Inspect images and animation at their
README display size as well. Export success alone is not visual review.

Images can vary with KiCad, model libraries or encoder versions. Output hashes
identify this capture; they do not promise identical video bytes on every system.

The example turntable uses 48 separate native KiCad 3D renders. It does not
invent intermediate geometry. To reproduce the scoped-change proof, run
`uv run python tools/demo_change.py`, inspect the printed preview, then use its
hash-bound resume command. [The published record](change-proof.md) describes
the exact author-inspected run; it is not owner fabrication approval.

## Visual direction: measured space

Native geometry carries the detail. Generous margins let the viewer inspect it,
while small technical markers suggest the precision of a laboratory drawing.
The composition is meticulously crafted around real source material, keeping
its shape and labels intact.

Dark slate establishes depth without competing with board materials. Pale type
and a restrained lime accent establish hierarchy; amber marks an open decision.
Painstaking attention to contrast keeps the result readable at repository scale.

Instrument Sans introduces purpose in a few words. JetBrains Mono identifies
commands, stages and recorded facts. Their carefully balanced scale keeps the
artifact central and lets details reward closer inspection.

Motion follows the inspection sequence: native CAD, source verification, an
application guard, and the actual review result. Measured holds allow reading.
The craft lies in hierarchy and honest evidence, with blockers still visible
in the final frame and every alignment refined.

Fonts are bundled for reproducible generation. Their SIL Open Font License
notices are under [fonts](fonts/).
