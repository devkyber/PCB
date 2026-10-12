# JLCPCB upload files

Upload gerbers.zip in the PCB/Gerber slot, bom.csv in the BOM slot, and cpl.csv in the CPL slot. The ZIP contains both Gerbers and Excellon drills.

71 components; 25 grouped BOM rows. BOM and CPL designators match exactly. Quantities are per board.

Positions use the native KiCad coordinate origin, shared with the Gerber export.
Negative Y coordinates are intentional. Exact-part vendor angle corrections are applied after centroid calculation using the native angle. See rotation-audit.csv for every part.
Rule evidence and unresolved orientation are recorded in assembly-audit.json; derived corrections require a fresh supplier preview. Local 3D models do not upload with Gerbers and cannot repair missing models in JLCPCB’s independent library.
Explicit centroid corrections and manually fitted parts are recorded in assembly.json. assembly-F.svg and assembly-B.svg are assembly drawings, not Gerber upload files.

Check pin 1, polarity, body alignment, bottom-side orientation, matched MPN/package, stock and through-hole assembly eligibility in JLCPCB before ordering. Export checks do not establish supplier acceptance or fabrication approval.
