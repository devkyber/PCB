"""Offline THVD1450DR termination budget and UART direction-control recipe.

Authority: archived TI SLLSEY3E pp9-11,19 and this board's declared parts.
No GPIO, serial port, cable measurement or hardware approval is performed.
"""

import math


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{label} must be an integer from {minimum} to {maximum}')


def termination_budget(supply_v=3.3, terminations=2, *, suppress_echo=False):
    """Conservative DC termination-only model, with fixed selected 120R/1% parts.

    Assumes |VAB| <= supply. Actual transceiver drop reduces this upper bound.
    Receiver/bias/cable loading, capacitive current and resistor derating are
    excluded, so a passing model is not a complete bus/thermal/current check.
    """
    if type(supply_v) not in (int, float) or not 3.0 <= supply_v <= 3.6:
        raise ValueError('supply must be finite and within this board\'s 3.0..3.6 V scope')
    _integer(terminations, 0, 32, 'terminations')
    if type(suppress_echo) is not bool:
        raise ValueError('suppress_echo must be boolean')
    resistor_min = 120 * 0.99
    equivalent_min = resistor_min / terminations if terminations else None
    termination_current = supply_v / equivalent_min if equivalent_min else 0
    resistor_power = supply_v * supply_v / resistor_min if terminations else 0
    # TI's 3 mA max is quiescent/no-load, not a loaded total supply rating.
    enable_pulls = (2 if suppress_echo else 1) * supply_v / (10000 * 0.99)
    checks = {
        'two_physical_end_terminations': terminations == 2,
        'termination_only_load_at_least_54_ohm': equivalent_min is not None and equivalent_min >= 54,
        'each_resistor_bound_within_0_25_w_reference_rating': resistor_power <= 0.25,
        'full_supply_current_bound_within_60_ma_recommendation': termination_current <= 0.060,
    }
    notes = [
        'Only the two physical cable ends receive termination; a middle node leaves JP1 open.',
        'R3 is 120 ohm / 1% / 0.25 W; JP1 shunt is a separate accessory.',
        'The full-supply differential current is a conservative bound, not a measured current or actual fault.',
        'Receiver/bias/cable loading, dynamic current and temperature derating need separate assessment.',
        'Supply estimate omits switching/internal loaded-current effects and is not a supply-sizing guarantee.',
        'A positive result does not qualify a cable, bus speed, supply or hardware.',
    ]
    if termination_current > 0.060:
        notes.append('The bound exceeds TI\'s 60 mA recommendation; measure actual VAB/current and assess the driver. '
                     'This calculation alone does not establish a real overcurrent.')
    return {
        'scope': 'offline DC termination-only estimate; unbuilt board',
        'supply_v': supply_v, 'terminations': terminations, 'resistor_min_ohm': resistor_min,
        'equivalent_termination_min_ohm': equivalent_min,
        'full_supply_differential_current_bound_ma': termination_current * 1000,
        'each_resistor_power_bound_mw': resistor_power * 1000,
        'dc_transmit_supply_estimate_ma': (termination_current + 0.003 + enable_pulls) * 1000,
        'budget_terms': 'termination bound + 3 mA no-load quiescent bound + high enable-pin 10k pulldowns',
        'checks': checks, 'within_this_model': all(checks.values()), 'notes': notes,
    }


def direction_sequence(payload_bytes=1, baud=115200, *, parity='none', stop_bits=1,
                       suppress_echo=False, host_margin_us=1):
    """Plan UART/GPIO order, never timer-release DE based on the byte estimate.

    Keep the receiver enabled until after DE is high. Before releasing DE,
    re-enable it while DE is still high. This avoids the DE=0,nRE=1 shutdown
    state. Datasheet timing limits are under its stated electrical conditions.
    """
    _integer(payload_bytes, 1, 4096, 'payload bytes')
    _integer(baud, 1, 115200, 'initial bench baud')
    _integer(stop_bits, 1, 2, 'stop bits')
    if parity not in ('none', 'even', 'odd'):
        raise ValueError('parity must be none, even or odd')
    if type(suppress_echo) is not bool:
        raise ValueError('suppress_echo must be boolean')
    if (type(host_margin_us) not in (int, float) or not math.isfinite(host_margin_us)
            or host_margin_us < 1 or host_margin_us > 1000000):
        raise ValueError('host timing margin must be finite, 1..1000000 us; verify the actual host')

    def guard(device_us):
        return math.ceil(device_us + host_margin_us)

    steps = [
        {'action': 'After stable supply, set DE=0, nRE=0 and UART TX idle high',
         'de': 0, 'nre': 0, 'wait_at_least_us': guard(14),
         'reason': 'receiver enable from disabled state: 14 us max with DE=0; host margin added'},
        {'action': 'Acquire exclusive bus ownership; set DE=1 while nRE remains 0',
         'de': 1, 'nre': 0, 'wait_at_least_us': guard(0.050),
         'reason': 'driver enable: 50 ns max when nRE=0; receiver stays active'},
    ]
    if suppress_echo:
        steps.append({'action': 'Set nRE=1 only after DE=1 is established',
                      'de': 1, 'nre': 1, 'wait_at_least_us': guard(0.028),
                      'reason': 'receiver disable: 28 ns max; driver stays active'})
    steps.extend([
        {'action': 'Write the UART frame; wait for the HARDWARE TX-COMPLETE flag after the final stop bit',
         'de': 1, 'nre': int(suppress_echo),
         'reason': 'write()/DMA complete/FIFO empty may precede the last shifted bit; do not release DE yet'},
        {'action': 'Keep DE high after hardware TX complete', 'de': 1, 'nre': int(suppress_echo),
         'wait_at_least_us': guard(0.020),
         'reason': '20 ns max driver data propagation plus host margin; protocol may require more'},
    ])
    if suppress_echo:
        steps.append({'action': 'Set nRE=0 while DE is still 1',
                      'de': 1, 'nre': 0, 'wait_at_least_us': guard(0.110),
                      'reason': 'receiver enable: 110 ns max with DE=1; avoid entering shutdown'})
    steps.append({'action': 'Set DE=0; keep nRE=0 for receive', 'de': 0, 'nre': 0,
                  'wait_at_least_us': guard(0.025),
                  'reason': 'driver disable: 25 ns max plus host margin, then obey peer/protocol turnaround'})
    frame_bits = 1 + 8 + int(parity != 'none') + stop_bits
    return {
        'scope': 'offline ordering recipe; timing margin is a host assumption, not a measured guarantee',
        'uart': {'baud': baud, 'data_bits': 8, 'parity': parity, 'stop_bits': stop_bits},
        'payload_bytes': payload_bytes, 'minimum_serial_duration_us': payload_bytes * frame_bits * 1e6 / baud,
        'duration_is_not_a_de_release_timer': True, 'steps': steps,
        'notes': ['No GPIO/serial calls are performed. Confirm TX-COMPLETE semantics on the actual controller.',
                  'With nRE=0 during transmit, RX sees local echo; separate it from peer responses.',
                  'No protocol arbitration, collision recovery, cable propagation or remote timing is implemented.'],
    }


def demo():
    """Reproduce calculations and control recipes, not measured UART waveforms."""
    import hashlib
    from pathlib import Path

    root = Path(__file__).resolve().parent
    repo = root.parents[1]
    paths = [root / name for name in ('bringup.py', 'BRINGUP.md', 'README.md',
                                      'evidence/files/THVD1450DR_thvd1450_58ecc4cc07dd.pdf')]
    paths.append(repo / 'tests/examples/test_bringup.py')
    return {
        'schema_version': 1, 'scope': 'offline DC estimates and ordering recipes; no serial/GPIO/hardware capture',
        'reproduce': 'python examples/rs485-interface/bringup.py demo',
        'software_inputs': {path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in paths},
        'termination_cases': [termination_budget(voltage, count)
                              for voltage, count in ((3.3, 2), (3.6, 2), (3.3, 3), (3.3, 0))],
        'direction_cases': [direction_sequence(4, 115200, suppress_echo=echo) for echo in (False, True)],
    }


def main(argv=None):
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Offline RS-485 bring-up calculations; no serial/GPIO access')
    sub = parser.add_subparsers(dest='command', required=True)
    budget = sub.add_parser('budget', help='calculate the selected termination resistor network')
    budget.add_argument('--supply', type=float, default=3.3)
    budget.add_argument('--terminations', type=int, default=2)
    budget.add_argument('--suppress-echo', action='store_true')
    sequence = sub.add_parser('sequence', help='print explicit DE/nRE and UART order')
    sequence.add_argument('--bytes', type=int, default=1, dest='payload_bytes')
    sequence.add_argument('--baud', type=int, default=115200)
    sequence.add_argument('--parity', choices=('none', 'even', 'odd'), default='none')
    sequence.add_argument('--stop-bits', type=int, default=1)
    sequence.add_argument('--suppress-echo', action='store_true')
    sequence.add_argument('--host-margin-us', type=float, default=1)
    sub.add_parser('demo', help='reproduce source-bound offline examples; no hardware')
    args = parser.parse_args(argv)
    try:
        if args.command == 'budget':
            result = termination_budget(args.supply, args.terminations, suppress_echo=args.suppress_echo)
        elif args.command == 'sequence':
            result = direction_sequence(args.payload_bytes, args.baud, parity=args.parity,
                                        stop_bits=args.stop_bits, suppress_echo=args.suppress_echo,
                                        host_margin_us=args.host_margin_us)
        else:
            result = demo()
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return int(result.get('within_this_model') is False)


if __name__ == '__main__':
    raise SystemExit(main())
