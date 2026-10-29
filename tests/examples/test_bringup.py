"""Primary-datasheet vectors and bench-recipe error boundaries, without hardware."""

import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_example(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'examples' / name / 'bringup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MCP = load_example('i2c-sensor')
RS485 = load_example('rs485-interface')


@pytest.mark.parametrize(('wire_bytes', 'celsius'), [
    (b'\x01\x94', 25.25),  # Microchip DS20005095B Figure 5-5, p26.
    (b'\x00\x00', 0), (b'\x07\xD0', 125),
    (b'\x1D\x80', -40), (b'\x1F\xFF', -0.0625), (b'\x1E\x6C', -25.25),
])
def test_mcp_signed_msb_first_samples(wire_bytes, celsius):
    result = MCP.decode_bytes(wire_bytes)
    assert result['temperature_c'] == celsius
    assert result['within_device_operating_range']


def test_mcp_flag_bits_do_not_leak_into_temperature_and_endian_error_is_visible():
    result = MCP.decode_temperature(0xE194)
    assert result['temperature_c'] == 25.25
    assert all(result[name] for name in ('at_or_above_critical', 'above_upper', 'below_lower'))
    reversed_bytes = MCP.decode_bytes(b'\x94\x01')
    assert reversed_bytes['temperature_c'] == -191.9375
    assert not reversed_bytes['within_device_operating_range']


def test_mcp_all_eight_normal_addresses_and_reject_shifted_address_inputs():
    assert {MCP.address_from_shunts(a0, a1, a2)
            for a0 in (0, 1) for a1 in (0, 1) for a2 in (0, 1)} == set(range(0x18, 0x20))
    assert MCP.address_from_shunts(1, 0, 1) == 0x1D
    with pytest.raises(ValueError):
        MCP.address_from_shunts(2, 0, 0)
    with pytest.raises(ValueError):
        MCP.address_from_shunts(True, 0, 0)


def test_mcp_limit_recipe_matches_p23_90_degree_vector_and_p20_enable_bits():
    assert MCP.encode_limit(90) == 0x05A0  # Figure 5-4 writes +90 C as 05 A0.
    assert MCP.encode_limit(-40) == 0x1D80
    recipe = MCP.alert_recipe(10, 30, 90, current_config=0, hysteresis=3)
    assert [(item['register'], item['data_hex']) for item in recipe] == [
        ('0x01', '0000'), ('0x03', '00A0'), ('0x02', '01E0'),
        ('0x04', '05A0'), ('0x08', '03'), ('0x01', '0408'),
    ]
    assert MCP.alert_recipe(10, 30, 90, current_config=0)[-1]['data_hex'] == '0008'


@pytest.mark.parametrize('value', [-40.25, 125.25, 25.0625, math.nan, math.inf, True])
def test_mcp_refuses_out_of_range_or_silently_rounded_thresholds(value):
    with pytest.raises(ValueError):
        MCP.encode_limit(value)


@pytest.mark.parametrize('config', [0x0040, 0x0080, 0x0100, 0x0008, 0x0800])
def test_mcp_bringup_recipe_does_not_overwrite_existing_or_locked_configuration(config):
    with pytest.raises(ValueError, match='actually read CONFIG=0'):
        MCP.alert_recipe(10, 30, 90, current_config=config)


@pytest.mark.parametrize(('lower', 'upper', 'critical', 'hysteresis'), [
    (30, 10, 90, 0), (10, 30, 20, 0), (10, 30, 90, 2),
])
def test_mcp_rejects_invalid_alarm_windows(lower, upper, critical, hysteresis):
    with pytest.raises(ValueError):
        MCP.alert_recipe(lower, upper, critical, current_config=0, hysteresis=hysteresis)


class ReadOnlyBus:
    def __init__(self, registers=None):
        self.registers = {0x06: b'\x00\x54', 0x07: b'\x04\x02', 0x08: b'\x03',
                          0x01: b'\x01\x00', 0x05: b'\x01\x94'}
        self.registers.update(registers or {})
        self.calls = []

    def readfrom_mem(self, address, register, length):
        self.calls.append((address, register, length))
        return self.registers[register]


def test_mcp_read_adapter_verifies_identity_and_keeps_shutdown_read_distinct_from_fresh_conversion():
    bus = ReadOnlyBus()
    result = MCP.read_sensor(bus, 0x1F)
    assert result['temperature_c'] == 25.25 and result['shutdown'] is True
    assert result['device_revision'] == 2  # Later silicon revision is accepted.
    assert bus.calls == [(0x1F, 6, 2), (0x1F, 7, 2), (0x1F, 8, 1), (0x1F, 1, 2), (0x1F, 5, 2)]


@pytest.mark.parametrize('registers', [{6: b'\x54\x00'}, {7: b'\x05\x00'},
                                      {5: b'\x01'}, {8: b'\x80'}, {1: b'\x80\x00'}])
def test_mcp_stops_on_wrong_identity_short_read_or_reserved_register_bits(registers):
    with pytest.raises(ValueError):
        MCP.read_sensor(ReadOnlyBus(registers))


@pytest.mark.parametrize('data', [b'', b'\x00', b'\x00\x00\x00', '0194', [1, 148]])
def test_mcp_requires_exact_two_wire_bytes(data):
    with pytest.raises(ValueError):
        MCP.decode_bytes(data)


def test_rs485_two_end_terminations_match_declared_tolerance_and_dc_power_bound():
    result = RS485.termination_budget(3.3, 2)
    assert result['equivalent_termination_min_ohm'] == pytest.approx(59.4)
    assert result['full_supply_differential_current_bound_ma'] == pytest.approx(55.5555556)
    assert result['each_resistor_power_bound_mw'] == pytest.approx(91.6666667)
    assert result['within_this_model']


def test_rs485_3_6_volt_bound_flags_current_uncertainty_without_claiming_measured_overcurrent():
    result = RS485.termination_budget(3.6, 2)
    assert result['full_supply_differential_current_bound_ma'] == pytest.approx(60.6060606)
    assert result['each_resistor_power_bound_mw'] == pytest.approx(109.090909)
    assert result['checks']['termination_only_load_at_least_54_ohm']
    assert not result['checks']['full_supply_current_bound_within_60_ma_recommendation']
    assert any('does not establish a real overcurrent' in note for note in result['notes'])


@pytest.mark.parametrize(('count', 'equivalent'), [(0, None), (1, 118.8), (3, 39.6)])
def test_rs485_missing_or_extra_terminations_do_not_appear_ready(count, equivalent):
    result = RS485.termination_budget(3.3, count)
    if equivalent is None:
        assert result['equivalent_termination_min_ohm'] is None
    else:
        assert result['equivalent_termination_min_ohm'] == pytest.approx(equivalent)
    assert not result['within_this_model']
    if count == 3:
        assert not result['checks']['termination_only_load_at_least_54_ohm']


def test_rs485_direction_control_never_enters_shutdown_or_releases_before_final_stop_bit():
    result = RS485.direction_sequence(1, 115200, suppress_echo=True)
    steps = result['steps']
    assert not any(step['de'] == 0 and step['nre'] == 1 for step in steps)
    assert [(step['de'], step['nre']) for step in steps] == [
        (0, 0), (1, 0), (1, 1), (1, 1), (1, 1), (1, 0), (0, 0),
    ]
    assert [step.get('wait_at_least_us') for step in steps] == [15, 2, 2, None, 2, 2, 2]
    assert 'HARDWARE TX-COMPLETE' in steps[3]['action']
    assert result['duration_is_not_a_de_release_timer']
    assert result['minimum_serial_duration_us'] == pytest.approx(86.8055556)


def test_rs485_uart_framing_and_echo_mode_are_explicit():
    result = RS485.direction_sequence(2, 9600, parity='even', stop_bits=2)
    assert result['minimum_serial_duration_us'] == pytest.approx(2500)
    assert all(step['nre'] == 0 for step in result['steps'])
    assert any('local echo' in note for note in result['notes'])


@pytest.mark.parametrize(('function', 'args'), [
    (RS485.termination_budget, (math.nan, 2)), (RS485.termination_budget, (5, 2)),
    (RS485.termination_budget, (3.3, -1)), (RS485.termination_budget, (3.3, True)),
    (RS485.direction_sequence, (0, 115200)), (RS485.direction_sequence, (1, 0)),
    (RS485.direction_sequence, (1, 1000000)),
])
def test_rs485_refuses_invalid_or_outside_initial_bench_scope_inputs(function, args):
    with pytest.raises(ValueError):
        function(*args)


@pytest.mark.parametrize(('example', 'arguments', 'exit_code'), [
    ('i2c-sensor', ['decode', '0194'], 0), ('i2c-sensor', ['decode', '194'], 2),
    ('i2c-sensor', ['alert', '--lower', '10', '--upper', '30', '--critical', '90', '--current-config', '0x40'], 2),
    ('rs485-interface', ['budget', '--terminations', '2'], 0),
    ('rs485-interface', ['budget', '--terminations', '3'], 1),
    ('rs485-interface', ['sequence', '--bytes', '2', '--suppress-echo'], 0),
])
def test_offline_cli_exit_contract(example, arguments, exit_code):
    result = subprocess.run([sys.executable, ROOT / 'examples' / example / 'bringup.py', *arguments],
                            capture_output=True, text=True, check=False)
    assert result.returncode == exit_code
    if exit_code != 2:
        assert isinstance(json.loads(result.stdout), dict)


@pytest.mark.parametrize('module', [MCP, RS485])
def test_software_demo_binds_current_primary_source_and_is_reproducible_without_hardware(module):
    import hashlib

    first, second = module.demo(), module.demo()
    assert first == second
    assert 'offline' in first['scope'] and 'no ' in first['scope']
    for name, expected in first['software_inputs'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize(('example', 'module'), [('i2c-sensor', MCP), ('rs485-interface', RS485)])
def test_retained_demo_matches_current_script_guide_test_and_datasheet_bytes(example, module):
    recorded = json.loads((ROOT / 'examples' / example / 'output/bringup-demo.json').read_bytes())
    assert recorded == module.demo()
