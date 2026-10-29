# Local libraries

`USBC` contains selected official KiCad symbol/footprint definitions from the
installed 10.0.6 distribution. Footprint bytes change only declared model URIs;
separate exact upstream footprints and model files remain under `upstream/`.
[PROVENANCE.json](PROVENANCE.json) records hashes, pin functions, exact selected
MPNs, source URLs and manufacturer evidence. Local copies do not authenticate
the installed distribution or independently qualify fit.

`BournsDerived` is a separate, explicitly drawing-derived library. Its F1
footprint implements the MF-MSMF075 style-1 recommended pads from the archived
manufacturer drawing. The [receipt](footprint-provenance.yaml) records dimensions
and limitations. No F1 body model is provided; none was invented.

The saved PCB instances widen silkscreen graphic strokes to 0.15 mm and place
reference text for readability. Electrical pads are not changed. Exact J1
geometry retains eight DRC findings documented in DESIGN_BASIS.md; there is no
claim that an official library file automatically satisfies a fabricator.

Upstream [symbol](LICENSE-kicad-symbols.md), [footprint](LICENSE-kicad-footprints.md)
and [package-model](LICENSE-kicad-packages3D.md) license notices are retained.
[LICENSE_PROVENANCE.json](LICENSE_PROVENANCE.json) records their origins and
hashes. Those files retain upstream terms; the project does not relicense them.
