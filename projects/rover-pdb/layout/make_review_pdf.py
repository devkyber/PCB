"""Vector PCB review PDF from native KiCad SVG exports; not fabrication data."""
from pathlib import Path
import argparse
from datetime import datetime, timedelta, timezone
import io
import json
import xml.etree.ElementTree as ET
import pymupdf as fitz
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3,landscape
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from render_assembly import KIPYTHON, _run, sha256, fresh_review_views, validate_bundle, publish_views
P=Path(__file__).resolve().parents[1];O=P/'output'


def native_geometry(bundle, manifest):
    """Read dimensions and detail extents from the exact disposable CAD snapshot."""
    board = bundle / 'native' / 'rover-pdb.kicad_pcb'
    expected = manifest['source_hashes'][board.name]
    if not board.is_file() or sha256(board) != expected:
        raise RuntimeError('Review CAD snapshot does not match the source manifest')
    geometry = json.loads(_run([KIPYTHON, '-I', '-c', '''import json,pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
outline=pcbnew.SHAPE_POLY_SET()
if not b.GetBoardPolygonOutlines(outline,False):
    raise RuntimeError('A closed native board outline is required for review dimensions')
box=outline.BBox()
x0,y0=pcbnew.ToMM(box.GetLeft()),pcbnew.ToMM(box.GetTop())
width,height=pcbnew.ToMM(box.GetWidth()),pcbnew.ToMM(box.GetHeight())
parts={p.GetReference():p for p in b.GetFootprints()}
groups=[
    ['U2','L1','NT1','C10','C11','C30','C33','C39','C20','C21','C22','C23','R10','R13','R17','R21'],
    ['U3','L2','NT2','C12','C13','C31','C34','C40','C24','C25','C26','C27','C28','R11','R14','R16','R22'],
    ['U4','L3','NT3','C14','C15','C32','C35','C41','C16','C17','C18','C19','R12','R15','R18','R19','R23','R24'],
    ['U1','RS1','C3'],
]
details=[]
for refs in groups:
    missing=set(refs)-parts.keys()
    if missing:
        raise RuntimeError('Review detail references are missing: '+', '.join(sorted(missing)))
    boxes=[parts[r].GetBoundingBox(True,False) for r in refs]
    details.append([
        max(0,min(pcbnew.ToMM(r.GetLeft())-x0 for r in boxes)-2),
        max(0,min(pcbnew.ToMM(r.GetTop())-y0 for r in boxes)-2),
        min(width,max(pcbnew.ToMM(r.GetRight())-x0 for r in boxes)+2),
        min(height,max(pcbnew.ToMM(r.GetBottom())-y0 for r in boxes)+2),
    ])
holes=[[pcbnew.ToMM(parts[r].GetPosition().x)-x0,
        pcbnew.ToMM(parts[r].GetPosition().y)-y0] for r in ('H1','H2','H3','H4')]
print(json.dumps({'width':width,'height':height,'holes':holes,'details':details,
                 'revision':str(b.GetTitleBlock().GetRevision()),
                 'smt_count':sum(bool(p.GetAttributes() & pcbnew.FP_SMD) and not p.IsDNP()
                                 and not p.IsExcludedFromBOM() for p in parts.values())}))
''', board]))
    if sha256(board) != expected:
        raise RuntimeError('Review CAD snapshot changed during geometry extraction')
    # Native fit-page-to-board SVGs are board-local. Check this before mapping
    # millimetres to PDF coordinates; square-board scaling distorted P2 crops.
    for name in ('assembly', 'top-copper', 'bottom-copper'):
        root = ET.parse(bundle / f'{name}.svg').getroot()
        svg_dimensions = []
        for axis in ('width', 'height'):
            value = root.attrib.get(axis, '')
            if not value.endswith('mm'):
                raise RuntimeError('Native review SVG must declare millimetre dimensions')
            svg_dimensions.append(float(value[:-2]))
        if any(abs(actual - geometry[axis]) > 0.1
               for actual, axis in zip(svg_dimensions, ('width', 'height'))):
            raise RuntimeError('Native SVG page dimensions do not match its board outline')
    return geometry


def dimension(value):
    return f'{value:.2f}'.rstrip('0').rstrip('.')


def build_pdf(bundle, inspection_dir=None):
    bundle=Path(bundle)
    manifest=validate_bundle(P,bundle)
    geometry=native_geometry(bundle,manifest)
    digest=manifest['source_hashes']['rover-pdb.kicad_pcb']
    board_size=f"{dimension(geometry['width'])} x {dimension(geometry['height'])} mm"
    hole_positions=', '.join(f'({dimension(x)}, {dimension(y)})' for x,y in geometry['holes'])
    revision=geometry['revision'] or 'revision not set'
    R=bundle;dest=bundle/'rover-pdb-pcb-review.pdf'
    W,H=landscape(A3);buf=io.BytesIO();c=canvas.Canvas(buf,pagesize=(W,H));c.setTitle('Rover PDB - '+revision+' review');c.setAuthor('KSRC Lunar Rover / author CAD review')
    style=ParagraphStyle('body',fontName='Helvetica',fontSize=11.2,leading=16,textColor='#223442',spaceAfter=10)
    def para(s,x,y,width):
        p=Paragraph(s,style);w,h=p.wrap(width,1000);p.drawOn(c,x,y-h);return y-h-11
    def heading(title,subtitle,page):
        c.setFillColorRGB(.04,.15,.23);c.setFont('Helvetica-Bold',23);c.drawString(14*mm,H-17*mm,title)
        c.setFont('Helvetica',10.5);c.drawString(14*mm,H-24*mm,subtitle)
        c.setStrokeColorRGB(.1,.55,.56);c.setLineWidth(1.3);c.line(14*mm,H-29*mm,W-14*mm,H-29*mm)
        c.setFillColorRGB(.25,.32,.37);c.setFont('Helvetica',8);c.drawString(14*mm,8*mm,'PCB REVIEW / NOT A FABRICATION RELEASE  |  '+datetime.now(timezone(timedelta(hours=9))).date().isoformat()+'  |  CAD SHA256 '+digest[:20]);c.drawRightString(W-14*mm,8*mm,str(page))
    pages=[
    ('Assembly and interfaces',f'Fresh native views  |  {revision}  |  {board_size}',[
     f'<b>Outline and construction</b><br/>{board_size}, read from this native snapshot. M3 hole centers, measured from its upper-left corner: {hole_positions} mm. Selected construction: two copper layers, nominal 1 oz; 1.6 mm FR4; green mask; HASL. The mounting design uses 3.2 mm drills and 3.5 mm screw keepouts.',
     '<b>Wire pads</b><br/>P1: 6S battery through the shunt.<br/>P2: 12 V Jetson.<br/>P3: 12 V auxiliary.<br/>P4: 5 V auxiliary.<br/>Solid positive and GND lands remain; nearby vias connect the copper layers. F1 is removed: no onboard input fuse remains. Provide external battery protection and harness restraint.',
     '<b>Control and expansion</b><br/>Pico 2 is USB-only. Two generic KiCad female-socket models now show the existing 40-hole interface; the Pico and USB cable are not modeled. Verify actual plug clearance, socket height and header engagement. J9 exposes 3.3 V, GND and GP18-21; it is DNP. SW1 drives motor EN; it does not isolate the battery or brake the motor.',
     '<b>Review scope</b><br/>These views are freshly exported from the PCB/settings identified by the source manifest. Exporting this document does not run or certify DRC, schematic parity or engineering approval. Consult the current pipeline review.',
     f'<b>Assembly boundary</b><br/>{geometry["smt_count"]} fitted SMT components in this snapshot. SKT1 is hand fitted: two sockets plus Pico/header assembly, excluded from automated BOM/placement output, not DNP. See BOM_NOTES.md for the manual purchase list; verify actual mating polarity and socket engagement.'
     ]),
    ('Front copper','F.Cu with front silkscreen  |  Viewed from the component side',[
     '<b>Current routing</b><br/>P5 preserves the owner\'s placement, surface pads and outline. A10 removes F1 and bridges its former contacts with 4 mm copper. The P4 repair remains: a dedicated 2 mm back-layer route and four parallel vias carry 5 V load current, with a separate output sense takeoff.',
     '<b>Power distribution</b><br/>Six battery-path segments are widened. The 4 mm front VBAT trunk connects through a 3.0-4.0 mm back bridge and eight parallel vias at each end. Battery-to-shunt copper uses 3-4 mm sections; a short 2.8 mm shunt approach preserves its Kelvin takeoff. Main 12 V, 5 V and motor branches are 2.4, 2.0 and 2.5 mm respectively.',
     '<b>Current sensing</b><br/>Two thin Kelvin connections leave the inner shunt lands. Battery force copper uses the outer sides. No intentional motor/servo load current flows through the INA226 sensing traces.',
     '<b>Solder and heat</b><br/>P5 adds 42 vias beside wire pads and six near converter grounds. Each converter now has eight nearby ground vias. All new vias have 0.30 mm drills, 0.60 mm copper diameter and mask tenting on both sides; none pierces a solder land. Ground zones use direct connections, including through-hole pads. This spreads heat but also increases hand-soldering heat demand.',
     '<b>Limit</b><br/>Copper widths and clearance checks do not establish a continuous-current or temperature rating. Validate the simultaneous rail loads and cooling on hardware.'
     ]),
    ('Back copper and connector pin labels','B.Cu + B.Silkscreen  |  Viewed from underneath; mirrored relative to front',[
     '<b>Ground continuity</b><br/>Most of the back layer remains ground copper through the converter region and toward battery return. Ground stitching connects the front regions around the signal routes.',
     '<b>Pad copper and supply bridges</b><br/>Four bottom copper areas spread heat beneath the positive wire pads. Six vias per pad join them to front copper. Eighteen new GND vias serve P2-P4; P1 retains its existing seven. Preserve the repaired 5 V bank-to-load route and independent U3 sense takeoff.',
     '<b>Signals</b><br/>The parallel DYNAMIXEL data trunks run below the connector row. Pico PWM and I2C routes occupy the quiet side of the board. The final switch and LED connections use 0.25 mm traces.',
     '<b>Connector labels</b><br/>The four bottom-edge connectors have 1 mm pin legends on the back, inside the board edge: G, NC or VM, D+ and D-. Their function names are repeated on both sides. VM is the motor supply; D+/D- are the RS485 signals. This view reads as looking at the underside.',
     '<b>Independent checks</b><br/>docs/review/PCB_VERIFICATION.md records pin, power-path and routing checks against identified snapshots. Re-run checks after changes; exporting this drawing makes no fresh pass/fail claim.',
     '<b>Before fabrication release</b><br/>Complete the named, hash-bound human review required by the workspace protocol. Motor energy/backfeed, converter transients, external battery protection, thermal performance and mechanical fit remain engineering review items. No order has been placed.'
     ])]
    for i,(title,sub,notes) in enumerate(pages,1):
        heading(title,sub,i);y=H-39*mm
        for s in notes:y=para(s,278*mm,y,127*mm)
        c.showPage()
    heading('Critical copper at readable scale','Three converter cells and the shunt sensor takeoffs  |  Native vector detail',4)
    for x,title in [(14,'U2 - 12 V'),(148,'U3 - 5 V'),(282,'U4 - motor')]:
        c.setFont('Helvetica-Bold',14);c.setFillColorRGB(.04,.15,.23);c.drawString(x*mm,H-40*mm,title)
    c.setFont('Helvetica-Bold',14);c.drawString(14*mm,125*mm,'INA226 / Kelvin takeoffs')
    y=125*mm
    for s in [
     '<b>Inspect the complete path.</b> Locate VIN12, the 100 nF capacitor and PGND13; then follow SW to the inductor, BOOT to its capacitor, and the output bank back to ground.',
     '<b>Follow the feedback separately.</b> Find each local AGND tie, divider midpoint, feed-forward branch and the output-sense route. Confirm that force copper does not become a second sense return.',
     '<b>Human review remains essential.</b> These enlarged drawings support review; they do not prove converter stability, safe regenerative energy handling, temperatures or real assembly tolerances.'
    ]:y=para(s,170*mm,y,235*mm)
    c.showPage();c.save()
    out=fitz.open(stream=buf.getvalue(),filetype='pdf')
    svgs={}
    for name in ('assembly','top-copper','bottom-copper'):
        d=fitz.open(stream=(R/f'{name}.svg').read_bytes(),filetype='svg');svgs[name]=fitz.open(stream=d.convert_to_pdf(),filetype='pdf')
    for i,name in enumerate(('assembly','top-copper','bottom-copper')):
        out[i].show_pdf_page(fitz.Rect(14*mm,34*mm,266*mm,286*mm),svgs[name],0)
    source=svgs['top-copper'];sr=source[0].rect
    def clip(box):
        x1,y1,x2,y2=box
        return fitz.Rect(sr.x0+x1/geometry['width']*sr.width,
                         sr.y0+y1/geometry['height']*sr.height,
                         sr.x0+x2/geometry['width']*sr.width,
                         sr.y0+y2/geometry['height']*sr.height)
    for i,box in enumerate(geometry['details'][:3]):
        out[3].show_pdf_page(fitz.Rect((14+134*i)*mm,45*mm,(139+134*i)*mm,143*mm),source,0,clip=clip(box))
    out[3].show_pdf_page(fitz.Rect(14*mm,177*mm,155*mm,280*mm),source,0,clip=clip(geometry['details'][3]))
    dest.parent.mkdir(parents=True,exist_ok=True);out.save(dest,garbage=4,deflate=True)
    if inspection_dir is not None:
        inspection_dir=Path(inspection_dir)
        inspection_dir.mkdir(parents=True,exist_ok=True)
        for i,page in enumerate(out):
            page.get_pixmap(matrix=fitz.Matrix(1.15,1.15)).save(str(inspection_dir/f'pdf-page-{i+1}.png'))
    validate_bundle(P,bundle)
    files={O/'pdf'/dest.name:dest}
    publish_views(P,bundle,files)
    return O/'pdf'/dest.name


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspection-dir',type=Path,help='Optional directory for rendered review pages')
    args=parser.parse_args()
    with fresh_review_views(P) as bundle:
        print(build_pdf(bundle,args.inspection_dir))
