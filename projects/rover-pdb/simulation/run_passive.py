"""Reproducible A9 EN checks and isolated capacitor regeneration scenarios.

These are real ngspice simulations, NOT LMR51450 converter simulations.
No native schematic is written. Run with Python 3.11+ on this Windows host.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from ngspice_runner import NgSpice
from raw_results import pack_raw_cases, publish_results

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    return {p.name: sha(p) for p in sorted(PROJECT.glob('*.kicad_sch'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path,
                        default=Path('C:/Program Files/KiCad/10.0/bin/ngspice.dll'))
    args = parser.parse_args()
    before = snapshot()
    binding_file = HERE / 'cad-binding.json'
    if binding_file.exists():
        expected = json.loads(binding_file.read_text())
        if expected != before:
            raise SystemExit('CAD changed: review/rebind simulation parameters before rerunning.')
    else:
        binding_file.write_text(json.dumps(before, indent=2) + '\n')
    with tempfile.TemporaryDirectory(prefix='rover-passive-run-') as temporary:
        run_verified_batch(args, before, Path(temporary))


def run_verified_batch(args, before, result_dir):
    # Incomplete or failed batches cannot overwrite the recorded result set.
    engine = NgSpice(args.dll)
    cases = []
    def run(name, body, vectors, scope, assumptions):
        deck = result_dir / (name + '.cir')
        deck.write_text(name + '\n* ' + scope + '\n' + body +
                        '\n.options reltol=1e-6 abstol=1e-12 vntol=1e-7\n.end\n', encoding='ascii')
        data = engine.run(deck, vectors)
        cases.append({'name': name, 'scope': scope, 'assumptions': assumptions,
                      'deck_sha256': sha(deck), 'samples': len(next(iter(data.values())))})
        return data, cases[-1]

    # Actual resistor topology. SW1 is represented by an ideal voltage-controlled switch.
    # 0.1 uA leakage magnitude is TI's TYPICAL datum, not a specified maximum.
    def network(r19, r24, r15, leak, switch, cap=0):
        return (f'R19 vin sw_supply {r19:.12g}\nR24 sw_supply 0 {r24:.12g}\n'
                f'R15 en 0 {r15:.12g}\nIen en 0 {leak:.12g}\n'
                'S1 sw_supply en ctrl 0 swmodel\n'
                '.model swmodel SW(Ron=0.01 Roff=1e12 Vt=0.5 Vh=0.1)\n'
                f'Vswitch ctrl 0 {switch}\n' + (f'Cpar en 0 {cap:.12g}\n' if cap else ''))

    dc_summary = []
    for signs in itertools.product((-1, 1), repeat=3):
        r19, r24, r15 = [r*(1+0.01*s) for r, s in zip((100e3,22e3,100e3), signs)]
        for on in (0, 1):
            for leak in (-0.1e-6, 0, 0.1e-6):
                name = 'en_dc_' + ''.join('p' if s > 0 else 'm' for s in signs) + f'_{on}_{round(leak*1e7):+d}'
                data, rec = run(name,
                    'Vbat vin 0 DC 25.2\n' + network(r19,r24,r15,leak,str(on)) + '.dc Vbat 19.8 25.2 0.3\n',
                    ['v-sweep','v(en)','v(sw_supply)'], 'A9 motor-enable DC resistor-corner check',
                    {'resistors_ohm':[r19,r24,r15],'switch_on':bool(on),
                     'leak_A':leak,'leak_scope':'typical-magnitude signed sensitivity, not guaranteed bound'})
                # Independent closed-form node solution, with off-state Roff neglected.
                analytic = [((v/r19-leak)/(1/r19+1/r24+1/r15) if on else -leak*r15)
                            for v in data['v-sweep']]
                error = max(abs(a-b) for a,b in zip(analytic,data['v(en)']))
                if error > 2e-6:
                    raise RuntimeError(f'{name}: closed-form cross-check differs by {error}')
                rec['metrics'] = {'en_min_V':min(data['v(en)']), 'en_max_V':max(data['v(en)']),
                                  'switch_node_max_V':max(data['v(sw_supply)']),
                                  'analytic_max_error_V':error}
                dc_summary.append({'on':on,'leak_A':leak,**rec['metrics']})

    for cap in (100e-12, 1e-9):
        name = f'en_switch_{round(cap*1e12)}pF'
        data, rec = run(name, 'Vbat vin 0 DC 25.2\n' +
            network(100e3,22e3,100e3,0,'PWL(0 0 1m 0 1.001m 1 3m 1 3.001m 0)',cap)+
            '.tran 0.1u 4m 0 0.2u\n', ['time','v(vin)','v(ctrl)','v(en)','v(sw_supply)'],
            'A9 SW1 closure/opening with assumed EN-node parasitic capacitance',
            {'Cpar_F':cap,'Cpar_scope':'assumed wiring and pin capacitance, not measured',
             'switch_transition_s':1e-6,'leak_A':0})
        # Switch opens at ctrl = Vt - Vh = 0.4, 3.0006 ms.
        toff = 3.0006e-3
        first = next(t for t,v in zip(data['time'],data['v(en)']) if t >= toff and v <= 0.8)
        rec['metrics'] = {'delay_to_EN_below_0p8V_us':(first-toff)*1e6,
                          'expected_RC_delay_us':100e3*cap*__import__('math').log(3.85/0.8)*1e6}

    for cap in (100e-12, 1e-9):
        for fall in (10e-6,1e-3):
            name = f'en_battery_fall_{round(cap*1e12)}pF_{round(fall*1e6)}us'
            endfall=1e-3+fall
            data, rec = run(name,
                f'Vbat vin 0 PWL(0 25.2 1m 25.2 {endfall:.12g} 0 3m 0)\n'+
                network(100e3,22e3,100e3,0,'1',cap)+'.tran 0.05u 3m 0 0.2u\n',
                ['time','v(vin)','v(en)'], 'A9 EN response to an imposed local-VBAT fall',
                {'Cpar_F':cap,'fall_s':fall,'source_scope':'imposed local-VBAT waveform, not a modeled battery/cable',
                 'IC_clamps':'not modeled; this is external-network sensitivity only'})
            differences=[en-vin for en,vin in zip(data['v(en)'],data['v(vin)'])]
            rec['metrics']={'max_EN_minus_VIN_V':max(differences),
                            'exceeds_VIN_plus_0p3_in_external_network':max(differences)>0.3}

    # Isolated output-bank experiment: NO converter, reverse path, motor model or load.
    # Actual C16-C19/C5 values at initial DC bias. A fixed C approximation over the pulse.
    regen_summary=[]
    for ceramic, bulk, label in ((25.6e-6,220e-6,'typical'),
                                 (25.6e-6*0.9*0.85,176e-6,'screen')):
        for amplitude in (0.1,0.5,1.0):
            name=f'regen_{label}_{amplitude:g}A'
            data,rec=run(name,
                f'Cc out 0 {ceramic:.12g} IC=22.190374\n'
                'Rbulk out bulk 0.03\n'
                f'C5 bulk 0 {bulk:.12g} IC=22.190374\n'
                'Rleak out 0 1e12\n'
                f'Iregen 0 out PWL(0 0 1m 0 1.001m {amplitude} 2.001m {amplitude} 2.002m 0)\n'
                '.tran 0.1u 3m 0 0.5u UIC\n', ['time','v(out)','v(bulk)'],
                'Injected current into isolated motor output capacitors; NOT IC regeneration validation',
                {'ceramic_F':ceramic,'bulk_F':bulk,'bulk_series_resistance_ohm':0.03,
                 'resistance_scope':'Panasonic 100kHz impedance used only as a constant-resistance proxy',
                 'current_A':amplitude,'pulse_flat_s':0.001,'edge_s':1e-6,
                 'omitted':'converter/reverse paths, load/LED, capacitor ESL/leakage, nonlinear C, actual motor'})
            q=amplitude*0.001001
            final=data['v(out)'][-1]
            expected=22.190374+q/(ceramic+bulk)
            if abs(final-expected)>1e-4:
                raise RuntimeError(f'{name}: charge-conservation cross-check failed')
            crossing=next((t for t,v in zip(data['time'],data['v(out)']) if t>=0.001 and v>=24),None)
            rec['metrics']={'final_V':final,'peak_V':max(data['v(out)']),
                            'charge_C':q,'charge_conservation_error_V':final-expected,
                            'time_to_24V_after_pulse_start_ms':(crossing-0.001)*1e3 if crossing else None,
                            '24V_scope':'comparison marker only, not a verified actuator maximum'}
            regen_summary.append({'bank':label,'current_A':amplitude,**rec['metrics']})

    after=snapshot()
    if before!=after:
        raise RuntimeError('CAD changed during simulation; report is not bound to a single snapshot.')
    report={'generated_utc':datetime.now(timezone.utc).isoformat(),'engine':engine.identity(),
            'cad_sha256':before,'cad_unchanged':True,'case_count':len(cases),
            'scope':'A9 external passive networks only; LMR51450 simulations have NOT RUN',
            'cases':cases,'dc_summary':dc_summary,'regen_summary':regen_summary}
    (result_dir/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    pack_raw_cases(result_dir, result_dir/'results.json', result_dir/'raw-cases.zip')
    publish_results(result_dir, HERE/'results')
    print(json.dumps({'case_count':len(cases),'cad_unchanged':True,
                     'on_EN_range_V':[min(x['en_min_V'] for x in dc_summary if x['on']),
                                       max(x['en_max_V'] for x in dc_summary if x['on'])],
                     'off_EN_range_V':[min(x['en_min_V'] for x in dc_summary if not x['on']),
                                        max(x['en_max_V'] for x in dc_summary if not x['on'])],
                     'transients':[{'name':c['name'],**c['metrics']} for c in cases if c['name'].startswith(('en_switch','en_battery'))],
                     'regen':regen_summary},indent=2))


if __name__=='__main__':
    main()
