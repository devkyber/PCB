# JLCPCB assembly: repeatable export and manual checks

Run `uv run pcb-copilot release PROJECT --preview --quantity 5` after saving native
CAD. The pipeline checks current circuit parity, KiCad DRC, the dated JLCPCB DFM
baseline, exact sourcing identity/stock, assembly contracts and current sign-off.
It publishes one matched Gerber/drill ZIP, BOM and CPL under
`output/jlcpcb-preview/`. Only a fully passing `release` without `--preview`
publishes `fabrication/`. Never combine an older CPL or Gerber with new files.

## Why apparently correct CAD can produce wrong placement

1. A footprint's zero angle is defined by its library. JLCPCB's component library
   can use a different zero, even for parts with the same package name. Native
   coordinates can therefore be correct while the assembly body's angle is wrong.
   [JLCPCB explains the differing zero orientation and same rotation direction](https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2).
2. Footprint origin, component center and pin 1 are different locations. Through-hole
   footprints often put the origin at pin 1. Rotate a local centroid offset using
   the **native** angle, then add the vendor angle correction. Using the corrected
   angle for the centroid can move a correctly placed component off its pads.
3. KiCad models, fabrication layers and JLCPCB models are independent. Gerbers
   contain copper/mask/silk geometry; CPL contains centers/angles. Neither uploads
   a STEP model into JLCPCB's component library. Missing supplier artwork does not
   establish missing BOM selection or actual stock.
4. A generic two-terminal footprint cannot assume pin 1 is positive. DRC verifies
   electrical/geometric connections; it does not interpret printed `+` or `GND`.
   A wrong label can be especially harmful because JLCPCB says its engineers
   normally follow silk when it conflicts with placement data.
5. A false `supplier_rotation_verified` flag in a report is ineffective unless a
   release gate consumes it. The assembly result now gates release separately
   from generic engineering sign-off.

## Where to fix each problem manually

**Wrong JLC orientation, correct native footprint:** keep the routed footprint in
place. In `jlcpcb-assembly.yaml`, use a rotation rule keyed by exact LCSC C-number,
MPN, footprint name, side and `pad_geometry_sha256`. `degrees` is added to native
CPL rotation, modulo 360; positive is counterclockwise. Zero-offset parts also
need an explicit rule. Never copy a correction to every MSOP or SOT package.
Use `pcb_copilot.assembly.pad_geometry_digest()` to calculate the local pad/body
fingerprint; do not refresh a stale fingerprint before inspecting what changed.
Attach the actual preview evidence under project `evidence/` and its SHA256.
`basis` records `observed`, `derived_from_preview` or `unverified` honestly.

Export again and inspect every part in JLC Component Placements: terminal axes,
actual pin 1, polarity, connector keying, center and bottom-side mirroring. For an
on-screen correction use **individual rotation about each component's center**.
Group rotation around a common center also changes XY positions. The rotation-step
textbox is not proof of the part's present angle. A red dot is not universally pin 1.
Prefer keeping corrections in the export rule so the next upload reproduces them.

**Wrong printed polarity:** in PCB Editor hover the footprint, press E, then Edit
Footprint; select its text and press E. Use `${SHORT_NET_NAME(1)}` beside pad 1 and
`${SHORT_NET_NAME(2)}` beside pad 2 where net names are concise. KiCad resolves these
from actual pad nets. Inspect the plotted silk and keep enough text clearance.
Update the reusable library too so Update Footprints from Library does not restore
the old mistake. Battery `+` shorthand remains valid only after checking the net.
[KiCad text variable reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#text-variables).
The automated wire-pad check matches each label to its nearest pad; arbitrary
legends elsewhere on the board still need visual review.

**Missing local model:** PCB Editor → footprint Properties (E) → 3D Models → Add
the project-relative STEP/WRL. Check X/Y, Z=board surface, scale and orientation
against the manufacturer's drawing. Save the same association in the local
library, then inspect the 3D Viewer. Store provenance and fidelity in `libs/`.
Do not label a simplified dimensional envelope as manufacturer CAD. Model inventory
checks file presence, hashes and declared transforms, not every surface dimension.

## Recording actual supplier review

After the complete corrected upload has actually been checked, a responsible
reviewer records this mapping in `jlcpcb-assembly.yaml`:

```yaml
supplier_review:
  reviewer: 'Actual reviewer name'
  reviewed_on: 'YYYY-MM-DD'
  pcb_sha256: 'SHA256 of current PROJECT.kicad_pcb'
  bom_sha256: 'SHA256 of the reviewed bom.csv'
  cpl_sha256: 'SHA256 of the reviewed cpl.csv'
  evidence: 'evidence/assembly/actual-reviewed-preview.png'
  evidence_sha256: 'SHA256 of that exact evidence file'
```

Use PowerShell `Get-FileHash -Algorithm SHA256 -LiteralPath PATH` (normalize the
hex result to lowercase). Do not enter an approval based only on a generated
local image. A changed board, BOM, CPL or evidence invalidates the review. The
record does not reserve stock or certify factory acceptance. Complete the existing
engineering sign-off only after this final evidence/configuration is in place.

## Outputs and regression protection

- Upload only `gerbers.zip`, `bom.csv`, `cpl.csv` to their matching slots.
- `rotation-audit.csv` shows native angle, correction, final angle and evidence basis
  for every assembled reference. `assembly-audit.json` lists models and wire labels.
- `assembly-F.svg` and `assembly-B.svg` show fabrication outlines and pad numbers;
  they are top-view board coordinates, not a mirrored bottom assembly view.
- When local checks pass, `assembly.step` and `assembly-top.png` provide a KiCad
  mechanical preview, with exporter diagnostics in `model-export.json`.
- `stock.csv/json`, `jlcpcb-dfm.json`, `review.json` and `SOURCE.json` retain current
  findings and source/output hashes. Retail stock is distinct from PCBA allocation.

Fault tests cover wrong part, wrong side, renumbered or moved pads, changed evidence,
centroid rotation order, reversed wire labels, missing/changed model and transform,
stale supplier review and refusal to replace a good release with an unapproved one.
