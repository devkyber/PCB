# Follow a signal through the examples

The [interactive explorer](https://devkyber.github.io/PCB/) combines the three
native KiCad examples in one browser workbench. It uses saved PCB pad and track
coordinates, actual schematic/3D/copper captures and archived manufacturer
evidence. It works without KiCad or a hardware connection.

Choose a board and search for a reference, part number, pin or net. Selecting a
component opens its exact MPN, native numbered pads and source documents.
Select a pin's net to highlight its contacts and routed segments. For example,
the sensor's SDA network connects J1 pin 4, R1 pin 2 and U1 pin 1. The pin labels
and net memberships come from saved CAD, checked against the project netmap.

The connectivity map simplifies pad shapes and omits filled zones and arcs.
Dashed routes are on the bottom copper layer; the map remains oriented from the
top. Use the native top/bottom copper images for full geometry. The bottom image
is mirrored as viewed from the underside. Neither surface replaces editable
CAD or a mechanical drawing. Download the embedded vector schematic for
readable circuit-scale inspection.

All boards remain unbuilt DRAFTs. The displayed ERC/DRC counts are retained
native reports; opening or verifying the explorer does not rerun them. Board
behavior, physical fit, supplier assembly and current human release decisions
remain open. The [complete handovers](HANDOVER.md) retain the full review.

## Run the saved explorer offline

Download [index.html](demos/example-explorer/index.html) using GitHub's raw-file
download control, then open the saved HTML in a browser. Images, vector PDFs,
scripts and circuit data are embedded; the workbench makes no network requests.
Clicking a manufacturer or review link opens the explicitly selected source.

For a local checkout, serve the same saved bundle with standard Python:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory docs/demos/example-explorer
```

Open `http://127.0.0.1:8765/`. No dependency installation is needed to view it.

## Rebuild and verify

```sh
uv run python tools/build_example_explorer.py --verify
# Requires KiCad Python and current example capture/review packets:
uv run python tools/build_example_explorer.py
```

The builder reads an isolated copy of the declared inputs with KiCad Python. It
reconciles every numbered electrical pad against the netmap, checks current
artifact/handovers, and embeds the captured native views with the complete input
ledger. It rechecks sources around transactional publication. Native extraction, verification or source
failures preserve the previous complete bundle.

Verification needs no KiCad. It checks the retained HTML hash, required source
artifact inventory, all embedded image/PDF bytes, component identities, evidence
metadata and URLs, native finding counts, pin-net maps and current input ledgers.
It rejects stale sources, linked paths and packet files replaced during the
check. Hashes establish recorded identities, not capture authenticity or the
quality of the engineering review.

GitHub Pages publishes only this verified standalone bundle after successful
main-branch software/package checks. Its [workflow](../.github/workflows/pages.yml)
uses GitHub's [custom Pages deployment actions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
