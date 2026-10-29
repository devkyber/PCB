# Project-local library lineage

Footprints and generic 3D models originate from the installed official KiCad
10.0.6 libraries. Unmodified upstream footprint/model bytes are kept separately
under `upstream/`; runtime copies are under `RS485.pretty/` and `models/`.
Only quoted model URI tokens change in the local footprint library. Distinct
MPNs sharing 0805 capacitor geometry use distinct local IDs and receipts without
changing the original footprint body name or geometry.

`PROVENANCE.json` pins exact upstream/local hashes, official source URLs,
selected MPN, manufacturer evidence and complete numbered-pad functions.
The shared strict resolver checks these facts. It does not prove download
authenticity, datasheet interpretation, symbol correctness or physical fit.
Every `physical_fit_qualified` field remains false.

`RS485.kicad_sym` contains project-local official symbol definitions. The
THVD1450D inheritance is resolved through its official MAX481E base so no external
symbol library is needed. The selected MPN on U1 is THVD1450DR; the incorrectly
VSON-assigned official THVD1450DR alias is not used. Original whole symbol-library
bytes and their hashes are retained under `upstream/symbols/` and in the receipt.
Power symbols and passive/connector bodies retain their original pin geometry.
The footprint validator's receipt scope does not include symbol derivation proof.

PCB instances retain native editable pads, copper, UUID links and fields. Their
silkscreen stroke width is raised to 0.15 mm to meet the dated fabrication
baseline; references are repositioned and non-user fields hidden. These instance
presentation edits are outside the library byte-copy comparison and are checked
by native DRC/visual review.

All STEP models are generic official KiCad visualizations. They are not exact
vendor models or fit evidence; header body/post length and capacitor height can
differ from the selected parts. The removable SNT shunt is a documented off-board
accessory and is intentionally absent from the unshunted native PCB/model.

Official library license texts are retained unchanged as
`LICENSE-kicad-footprints.md`, `LICENSE-kicad-symbols.md` and
`LICENSE-kicad-packages3D.md`, with exact source URLs and byte hashes in
`LICENSE_PROVENANCE.json`. Read those upstream terms and KiCad exception.
Manufacturer documents remain their authors' copyrighted source materials;
archiving them does not relicense them under this repository's software license.
