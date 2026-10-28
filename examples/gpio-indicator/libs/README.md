# Project-local KiCad libraries

The symbols, footprints and STEP package models here come from the official KiCad library distribution installed with KiCad 10.0.6. The KiCad community is the upstream library author. Exact source file bytes/hashes, official source URLs, selected part/pad mappings and model lineage are recorded in [PROVENANCE.json](PROVENANCE.json).

The symbol library contains the selected official definitions; their geometry and pins are unchanged. Names use this project's `Demo` library namespace. The footprint library copies preserve upstream bytes except for model URIs changed to project-local `libs/models/` paths. Unmodified original footprints and separate original model bytes are retained under `upstream/`. The board's footprint instances increase silkscreen graphic strokes to the 0.15 mm workspace baseline, reposition fields and hide sourcing metadata; electrical pad geometry remains unchanged.

The upstream license texts are archived unchanged:

- [Footprints](LICENSE-kicad-footprints.md)
- [Symbols](LICENSE-kicad-symbols.md)
- [Package models](LICENSE-kicad-packages3D.md)

[LICENSE_PROVENANCE.json](LICENSE_PROVENANCE.json) records the exact official license URLs, retrieval date and SHA-256 values. These library files retain their upstream license terms; they are not covered by an invented project-wide relicensing claim.

The library receipt checks identity, byte lineage, model paths and numbered pad coverage. It does not qualify actual component fit, imported model dimensions, electrical suitability or assembly. H1/H2 are fabricated nonplated holes and intentionally have no component body model.
