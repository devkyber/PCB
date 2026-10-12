"""Read-only CAD audit; writes only review artifacts under .pcb-copilot/preview.

The current intent is a comparison snapshot, never a source for rewriting owner CAD.
Independent checks cover the LMR51450 pin map and adopted A10 control circuit.
Run from the PCB repo: uv run python projects/rover-pdb/check_schematic.py
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path

from kicad_claude.adapters import sch_io as io, sch_editor as ed
from pcb_copilot.project import load_project
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.schematic.preview import render_schematic_preview, schematic_files
from pcb_copilot.schematic.io import load_schematic_intent
from pcb_copilot.schematic.netlist import normalize_intent_netmap
from pcb_copilot.layout.render import schematic_inventory

P = Path(__file__).resolve().parent

def check_critical_nets(nets: dict) -> list[str]:
    failures = []
    pins = {(ref, pin): name.rsplit('/', 1)[-1]
            for name, members in nets.items() for ref, pin in members}
    def require(ref, pin, name):
        actual = pins.get((ref, str(pin)))
        if actual != name:
            failures.append(f'{ref}.{pin}: expected {name!r}, got {actual!r}')
    require('R6',1,'PWM_AUX'); require('R6',2,'GND')
    require('P1', 1, 'BAT_SWITCHED'); require('P1', 2, 'GND')
    require('RS1', 2, 'BAT_SWITCHED'); require('RS1', 1, 'VBAT')
    for pin, name in {'1':'GND','2':'GND','3':None,'4':'I2C_SDA','5':'I2C_SCL',
                      '6':'+3V3','7':'GND','8':'VBAT','9':'VBAT','10':'BAT_SWITCHED'}.items():
        require('U1', pin, name)
    for pin, name in {'1':'PWM_LIFT_A','2':'PWM_LIFT_B','4':'PWM_PAN','5':'PWM_AUX',
                      '21':'I2C_SDA','22':'I2C_SCL','24':'GP18','25':'GP19',
                      '26':'GP20','27':'GP21','36':'+3V3','39':None,'40':None}.items():
        require('SKT1', pin, name)
    for pin in (3,8,13,18,23,28,33,38): require('SKT1', pin, 'GND')
    for ref in ('J1','J5','J6','J7'):
        for pin,name in [(1,'GND'),(2,None if ref=='J1' else 'VMOTOR'),
                         (3,'DXL_D_PLUS'),(4,'DXL_D_MINUS')]: require(ref,pin,name)
    for ref,pwm in [('J2','PWM_LIFT_A'),('J3','PWM_LIFT_B'),('J4','PWM_PAN'),('J8','PWM_AUX')]:
        for pin,name in [(1,pwm),(2,'+5V'),(3,'GND')]:require(ref,pin,name)
    # TI SLUSEP7 p.3: LMR51450SDRRR has twelve edge pins and PGND/DAP 13.
    # Open RT selects nominal 500 kHz; PG is intentionally unused.
    for u,out,inductor in [(2,'+12V','L1'),(3,'+5V','L2'),(4,'VMOTOR','L3')]:
        for pin in (1,2,3):require(f'U{u}',pin,f'SW_{u}')
        require(f'U{u}',4,f'BOOT_{u}')
        for pin in (5,6):require(f'U{u}',pin,None)
        require(f'U{u}',7,f'FB_{u}')
        require(f'U{u}',8,f'AGND_{u}')
        require(f'U{u}',9,'MOTOR_EN' if u==4 else f'EN_{u}')
        for pin in (10,11,12):require(f'U{u}',pin,'VBAT')
        require(f'U{u}',13,'GND')
        require(inductor,2,f'SW_{u}');require(inductor,1,out)
        require(f'C{u+31}',1,f'BOOT_{u}');require(f'C{u+31}',2,f'SW_{u}')
        require(f'NT{u-1}',1,f'AGND_{u}');require(f'NT{u-1}',2,'GND')
        require(f'C{u+37}',1,out);require(f'C{u+37}',2,f'FF_{u}')
        require(f'R{u+19}',1,f'FF_{u}');require(f'R{u+19}',2,f'FB_{u}')
    for r,top,bot in [('R10','+12V','FB_2'),('R17','FB_2','AGND_2'),
                      ('R11','+5V','FB_3'),('R16','FB_3','AGND_3'),
                      ('R12','VMOTOR','FB_4'),('R18','FB_4','AGND_4'),
                      ('R13','VBAT','EN_2'),('R14','VBAT','EN_3'),
                      ('R15','MOTOR_EN','AGND_4')]:
        require(r,1,top);require(r,2,bot)
    for ref,n,name in [('SW1',1,'SW_SUPPLY'),('SW1',2,'MOTOR_EN'),('SW1',3,None),
                       ('R19',1,'VBAT'),('R19',2,'SW_SUPPLY'),
                       ('R24',1,'SW_SUPPLY'),('R24',2,'AGND_4'),
                       ('R20',1,'VMOTOR'),('R20',2,'LED_A'),
                       ('D2',1,'LED_A'),('D2',2,'GND')]:require(ref,n,name)
    for pin,name in [(1,'+3V3'),(2,'GP18'),(3,'GP19'),(4,'GP20'),(5,'GP21'),(6,'GND')]:require('J9',pin,name)
    for ref in ('JP1','Q1','F1'):
        if any(r==ref for r,p in pins):failures.append(f'{ref}: removed component is still connected')
    return failures


def component_metadata(paths):
    """Read instance fields without changing native CAD or cached symbols."""
    result = {}
    for path in paths:
        if path.suffix != '.kicad_sch':
            continue
        for node in ed.iter_instance_symbols(io.parse_file(path)):
            ref = ed.get_symbol_property(node, 'Reference')
            if ref.startswith('#'):
                continue
            if ref in result:
                raise ValueError(f'Duplicate component reference: {ref}')
            result[ref] = {
                'properties': {str(p[1]):str(p[2]) for p in io.find_children(node,'property')},
                'lib_id': str(io.find_child(node,'lib_id')[1]),
                'in_bom': str(io.find_child(node,'in_bom')[1]),
            }
    return result


def engineering_value(value):
    """Accept equivalent visible prefixes such as 7k15, 7.15k and 7150."""
    token = value.split('/', 1)[0].strip().replace('µ','u').replace('μ','u')
    token = re.sub(r'\s*(?:Ohm|ohm|Ω|F)$', '', token)
    try:
        return float(token)
    except ValueError:
        match = re.fullmatch(r'(\d+(?:\.\d+)?)([pnumkMGR])(\d*)',token)
        if not match:
            return None
        first,scale,tail = match.groups()
        if tail and '.' in first:
            return None
        return float(first + ('.'+tail if tail else '')) * {
            'p':1e-12,'n':1e-9,'u':1e-6,'m':1e-3,
            'R':1.0,'k':1e3,'M':1e6,'G':1e9,
        }[scale]


def check_selected_components(parts, metadata):
    """Check the adopted part/value facts independently of generated intent."""
    failures = []
    for ref in ('U2','U3','U4'):
        part = parts.get(ref,{})
        props = metadata.get(ref,{}).get('properties',{})
        for name,actual,expected in (
            ('value',part.get('value'),'LMR51450SDRRR'),
            ('MPN',props.get('MPN'),'LMR51450SDRRR'),
            ('LCSC',part.get('lcsc'),'C6890985'),
            ('symbol',metadata.get(ref,{}).get('lib_id'),'rover:LMR51450SDRRR'),
            ('footprint',part.get('footprint'),'rover:LMR51450_DRR_WSON12_3x3'),
        ):
            if actual != expected:
                failures.append(f'{ref}: expected {name} {expected!r}, got {actual!r}')
        if part.get('pins') != {str(n) for n in range(1,14)}:
            failures.append(f'{ref}: expected exactly pins 1-13 including exposed PGND pad 13')
    for ref in ('C36','C37','C38','Q1','JP1'):
        if ref in parts or ref in metadata:
            failures.append(f'{ref}: obsolete component remains in the current circuit')
    values = {
        'R6':10e3,'L3':3.3e-6,'R10':100e3,'R11':100e3,'R12':100e3,
        'R17':7150,'R16':19100,'R18':3740,
        'R13':100e3,'R14':100e3,'R15':100e3,'R19':100e3,'R20':3900,'R24':22e3,
        'C33':100e-9,'C34':100e-9,'C35':100e-9,
        'C39':33e-12,'C40':33e-12,'C41':33e-12,
        'R21':1e3,'R22':1e3,'R23':1e3,
    }
    for ref,expected in values.items():
        text = parts.get(ref,{}).get('value','')
        actual = engineering_value(text)
        if actual is None or not math.isclose(actual,expected,rel_tol=1e-9,abs_tol=0):
            failures.append(f'{ref}: expected nominal value {expected:g}, got {text!r}')
    for ref in ('C33','C34','C35'):
        if parts.get(ref,{}).get('lcsc') != 'C1711':
            failures.append(f'{ref}: expected C1711 bootstrap capacitor')
    for ref in ('NT1','NT2','NT3'):
        if parts.get(ref,{}).get('pins') != {'1','2'}:
            failures.append(f'{ref}: expected two-pin local AGND-to-PGND net-tie')
        if metadata.get(ref,{}).get('in_bom') != 'no':
            failures.append(f'{ref}: copper net-tie must be excluded from purchased BOM')
    for ref,mpn,lcsc,fp in [('R19','RC0805FR-07100KL','C96346','Resistor_SMD:R_0805_2012Metric'),
                            ('R24','0805W8F2202T5E','C17560','Resistor_SMD:R_0805_2012Metric'),
                            ('J9','2.54-1x6P直针','C37208','Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical'),
                            ('R20','RC1206FR-073K9L','C137289','Resistor_SMD:R_1206_3216Metric'),
                            ('L3','APS1365M3R3DW','C54431777','rover:APS1365DW_13.8x12.6_P11.5')]:
        props=metadata.get(ref,{}).get('properties',{})
        if props.get('MPN')!=mpn or parts.get(ref,{}).get('lcsc')!=lcsc or parts.get(ref,{}).get('footprint')!=fp:
            failures.append(f'{ref}: part/footprint identity differs from the selected manufacturer part')
    return failures

def footprint_pin_check(parts):
    libraries={}
    table=io.parse_file(P/'fp-lib-table')
    for lib in io.find_children(table,'lib'):
        libraries[str(io.find_child(lib,'name')[1])]=Path(str(io.find_child(lib,'uri')[1]).replace('${KIPRJMOD}',str(P)))
    root=Path('C:/Program Files/KiCad/10.0/share/kicad/footprints')
    pending=[]; failures=[]
    for ref,c in parts.items():
        fp=c['footprint']
        if not fp or fp=='~':pending.append(ref);continue
        library,name=fp.split(':',1)
        path=libraries.get(library,root/(library+'.pretty'))/(name+'.kicad_mod')
        if not path.is_file():failures.append(f'{ref}: missing footprint {fp}');continue
        pads={str(p[1]) for p in io.find_children(io.parse_file(path),'pad') if str(p[1])}
        if pads!=c['pins']:failures.append(f'{ref}: footprint pads {sorted(pads)} differ from symbol pins {sorted(c["pins"])}')
    return pending,failures

def main():
    project=load_project(P);tc=discover_toolchain(P.parents[1])
    files=(*schematic_files(project.schematic_path), P/'rover-pdb.kicad_pro')
    before={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    out=P/'.pcb-copilot/preview'
    preview=render_schematic_preview(tc,project.schematic_path,out)
    parts,nets=schematic_inventory(tc,project.schematic_path)
    extracted={}
    for name,members in nets.items():
        for ref,pin in members:extracted.setdefault(ref,{})[pin]=name
    mismatches=[]
    try:normalize_intent_netmap(load_schematic_intent(P/'schematic-intent.yaml'),extracted)
    except ValueError as e:mismatches.append(str(e))
    critical=check_critical_nets(nets)
    component_failures=check_selected_components(parts,component_metadata(files))
    pending,footprint_failures=footprint_pin_check(parts)
    erc=json.loads(preview.erc_report_path.read_text())
    violations=[v for sheet in erc.get('sheets',[]) for v in sheet.get('violations',[])]
    after={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if before!=after:raise RuntimeError('CAD changed during review; rerun without concurrent edits.')
    result=dict(status='SCHEMATIC REVIEW ONLY',kicad_version=erc.get('kicad_version'),
        sheets=len(files)-1,physical_symbols=len(parts),connected_nets=len(nets),
        erc_errors=sum(v['severity']=='error' for v in violations),
        erc_warnings=sum(v['severity']=='warning' for v in violations),
        initial_intent_differences=mismatches,critical_connection_failures=critical,
        component_failures=component_failures,
        footprint_pin_failures=footprint_failures,unassigned_footprints=pending,
        preview_findings=[f'{f.code}: {f.message}' for f in preview.findings],
        input_sha256=before,cad_unchanged=True,pcb_created=False,human_signoff='PENDING')
    (out/'schematic-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    if preview.pdf_path:
        preview.pdf_path.replace(out/'schematic.pdf')
    print(json.dumps(result,indent=2))
    # The historical intent comparison is advisory for owner-edited native CAD.
    # Current netmap/parity and the adopted-circuit assertions establish intent.
    return int(bool(result['erc_errors'] or critical or component_failures or footprint_failures
                    or any(f.severity == 'block' for f in preview.findings)))

if __name__=='__main__':raise SystemExit(main())
