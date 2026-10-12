"""Datasheet-derived clearance envelope, NOT manufacturer-supplied detailed CAD.

Run: uv run --with cadquery==2.6.1 python build_model.py
See README.md for dimensional sources and explicit simplifications.
"""
from pathlib import Path

import cadquery as cq

output = Path(__file__).resolve().parent
assembly = cq.Assembly(name="APS1365DW_datasheet_envelope")
# Conservative overall package limits: A=12.6 +/-0.3, B max=13.8, C max=6.5.
# The un-dimensioned underside relief / terminal thickness is simplified to 0.25.
body = cq.Workplane("XY").box(13.8, 12.9, 6.25, centered=(True, True, False)).translate((0, 0, 0.25))
assembly.add(body, name="maximum_body_envelope", color=cq.Color(0.22, 0.23, 0.24))
for side, x in (("left", -5.7), ("right", 5.7)):
    terminal = cq.Workplane("XY").box(2.4, 4.7, 0.25, centered=(True, True, False)).translate((x, 0, 0))
    assembly.add(terminal, name=f"{side}_terminal_typical", color=cq.Color(0.72, 0.73, 0.75))
assembly.save(str(output / "APS1365DW-envelope.step"))
bounds = assembly.toCompound().BoundingBox()
assert all(abs(a-b) < 1e-6 for a,b in zip((bounds.xlen,bounds.ylen,bounds.zlen),(13.8,12.9,6.5)))
assert abs(bounds.zmin) < 1e-6
print("STEP bounds (mm):", bounds.xlen, bounds.ylen, bounds.zlen, "zmin:", bounds.zmin)
