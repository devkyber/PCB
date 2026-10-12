# Coilank APS1365DW model

This is a locally authored, datasheet-derived **maximum clearance envelope** for
APS1365M3R3DW / C54431777. It is not original manufacturer CAD or a detailed
representation of the molded body. No model was returned by EasyEDA's exact-part
API on 2026-10-06. KiCad uses this STEP; JLCPCB uses its own independent library.

Source: Coilank APS1365DW drawing, page 1, archived in
`evidence/files/APS1365M3R3DW_68d4a03c5920925210785d7848183ed4_a794e72576cd.pdf`.
[Supplier-hosted manufacturer PDF](https://datasheet.lcsc.com/datasheet/pdf/68d4a03c5920925210785d7848183ed4.pdf?productCode=C54431777).

Dimensions in mm: X=13.8 maximum (B), Y=12.9 maximum (A=12.6 +/-0.3),
Z=6.5 maximum (C). Two bottom terminations use E=2.4 and D=4.7 typical.
The 0.25 terminal thickness/underside relief is a visualization assumption:
the drawing does not dimension it. Corner relief, lead wrap, molding details
and markings are deliberately omitted. This conservative body must not be used
to infer solderability or exact enclosure contact geometry.

Origin: center between terminals, board surface at Z=0, terminals on the X axis.
KiCad scale 1, offset 0, rotation 0. The recommended PCB land pattern remains
14.7 outside, 8.3 inside and 5.0 wide; a 3D model does not define copper pads.
`build_model.py` reproduces the colored STEP with CadQuery 2.6.1 and asserts bounds.
