"""MCP9808 register tools: offline CLI; read-only MicroPython-style bus adapter.

Authority: archived Microchip DS20005095B, sections 3.5, 5.1.1-5.1.6.
No command opens hardware or claims a measured temperature/working board.
"""


def _integer(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'{label} must be an integer from 0 to {maximum}')
    return value


def address_from_shunts(a0=0, a1=0, a2=0):
    """Normal 7-bit address, not the shifted address byte sent on the wire."""
    for name, value in [('A0', a0), ('A1', a1), ('A2', a2)]:
        _integer(value, 1, name)
    return 0x18 | a0 | (a1 << 1) | (a2 << 2)


def decode_temperature(word):
    """Decode TA register 0x05; flags do not change the signed temperature."""
    _integer(word, 0xFFFF, 'temperature word')
    temperature = (word & 0x0FFF) / 16.0
    if word & 0x1000:
        temperature -= 256.0
    return {
        'raw_hex': f'0x{word:04X}', 'temperature_c': temperature,
        'at_or_above_critical': bool(word & 0x8000),
        'above_upper': bool(word & 0x4000), 'below_lower': bool(word & 0x2000),
        'within_device_operating_range': -40 <= temperature <= 125,
    }


def decode_bytes(data):
    """The sensor sends MSB first. SMBus word helpers may need byte swapping."""
    if not isinstance(data, (bytes, bytearray)) or len(data) != 2:
        raise ValueError('TA read requires exactly two bytes, MSB first')
    return decode_temperature((data[0] << 8) | data[1])


def encode_limit(temperature):
    """Exact 0.25 C threshold encoding; never silently round a trip point."""
    if (type(temperature) not in (int, float) or not -40 <= temperature <= 125
            or temperature * 4 != int(temperature * 4)):
        raise ValueError('limit must be -40..125 C in exact 0.25 C steps')
    return int(temperature * 16) & 0x1FFC


def alert_recipe(lower, upper, critical, *, current_config, hysteresis=0):
    """Plan explicit writes for a verified fresh, unlocked CONFIG=0 device.

    Returns data only. It never writes a bus, sets lock bits or acknowledges an
    interrupt. An existing configuration needs an application-specific review.
    """
    _integer(current_config, 0xFFFF, 'current CONFIG')
    if current_config != 0:
        raise ValueError('recipe requires an actually read CONFIG=0; do not reset or overwrite a configured/locked device')
    values = [encode_limit(value) for value in (lower, upper, critical)]
    if not lower < upper <= critical:
        raise ValueError('limits must satisfy lower < upper <= critical')
    if type(hysteresis) not in (int, float) or hysteresis not in (0, 1.5, 3, 6):
        raise ValueError('hysteresis must be 0, 1.5, 3 or 6 C')
    hyst_bits = (0, 1.5, 3, 6).index(hysteresis) << 9
    writes = [(0x01, b'\x00\x00', 'keep ALERT disabled while setting limits')]
    for register, value, label in zip((0x03, 0x02, 0x04), values,
                                      ('lower limit', 'upper limit', 'critical limit'), strict=True):
        writes.append((register, bytes((value >> 8, value & 0xFF)), label))
    writes.extend([(0x08, b'\x03', 'explicit 0.0625 C resolution; this register is ONE byte'),
                   (0x01, bytes((hyst_bits >> 8, 0x08)),
                    'continuous conversion; active-low comparator ALERT enabled; no locks')])
    return [{'register': f'0x{reg:02X}', 'data_hex': data.hex().upper(), 'purpose': label}
            for reg, data, label in writes]


def read_sensor(bus, address=0x18):
    """Read an explicitly supplied bus with readfrom_mem(address, register, n).

    No bus construction, scan, pin assignment, configuration or writes occur.
    Transport errors propagate. A successful read is not calibration or fit proof.
    """
    if type(address) is not int or not 0x18 <= address <= 0x1F:
        raise ValueError('board address must be the 7-bit value 0x18..0x1F')

    def read(register, length):
        payload = bus.readfrom_mem(address, register, length)
        if not isinstance(payload, (bytes, bytearray)) or len(payload) != length:
            raise ValueError(f'short or invalid read from register 0x{register:02X}')
        return payload

    manufacturer = read(0x06, 2)
    device = read(0x07, 2)
    if manufacturer != b'\x00\x54' or device[0] != 0x04:
        raise ValueError('unexpected identity; expected manufacturer 0x0054, device ID 0x04')
    resolution = read(0x08, 1)[0]
    if resolution & 0xFC:
        raise ValueError('resolution register has nonzero reserved bits')
    config = read(0x01, 2)
    config_word = (config[0] << 8) | config[1]
    if config_word & 0xF800:
        raise ValueError('CONFIG has nonzero reserved bits')
    result = decode_bytes(read(0x05, 2))
    result.update(address_hex=f'0x{address:02X}', device_revision=device[1],
                  resolution_c=(0.5, 0.25, 0.125, 0.0625)[resolution],
                  config_hex=f'0x{config_word:04X}', shutdown=bool(config_word & 0x0100),
                  capture='supplied-bus adapter result; origin, freshness and calibration not attested')
    return result


def demo():
    """Reproduce source-bound software examples, never synthetic hardware reads."""
    import hashlib
    from pathlib import Path

    root = Path(__file__).resolve().parent
    repo = root.parents[1]
    paths = [root / name for name in ('bringup.py', 'BRINGUP.md', 'README.md',
                                      'evidence/files/mcp9808-e7b6502f744c.pdf')]
    paths.append(repo / 'tests/examples/test_bringup.py')
    return {
        'schema_version': 1, 'scope': 'offline software vectors only; no I2C or physical temperature capture',
        'reproduce': 'python examples/i2c-sensor/bringup.py demo',
        'software_inputs': {path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in paths},
        'temperature_vectors': [{'input_hex': value, 'result': decode_bytes(bytes.fromhex(value))}
                                for value in ('0194', '1E6C', 'E194', '9401')],
        'addresses': [{'a0': a0, 'a1': a1, 'a2': a2, 'address': f'0x{address_from_shunts(a0, a1, a2):02X}'}
                      for a2 in (0, 1) for a1 in (0, 1) for a0 in (0, 1)],
        'alert_recipe_inputs': {'lower_c': 10, 'upper_c': 30, 'critical_c': 90,
                                'current_config': 0, 'hysteresis_c': 3},
        'alert_recipe': alert_recipe(10, 30, 90, current_config=0, hysteresis=3),
    }


def main(argv=None):
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Offline MCP9808 decoder and checked write recipe; no hardware access')
    sub = parser.add_subparsers(dest='command', required=True)
    decode = sub.add_parser('decode', help='decode a two-byte TA register capture')
    decode.add_argument('hex_bytes', help='exactly four hex digits, MSB first, e.g. 0194')
    address = sub.add_parser('address', help='translate address shunts to a 7-bit address')
    for bit in ('a0', 'a1', 'a2'):
        address.add_argument('--' + bit, type=int, choices=(0, 1), default=0)
    alert = sub.add_parser('alert', help='print a recipe; does not perform I2C writes')
    for name in ('lower', 'upper', 'critical'):
        alert.add_argument('--' + name, type=float, required=True)
    alert.add_argument('--current-config', type=lambda value: int(value, 0), required=True)
    alert.add_argument('--hysteresis', type=float, default=0)
    sub.add_parser('demo', help='reproduce source-bound offline vectors; no hardware')
    args = parser.parse_args(argv)
    try:
        if args.command == 'decode':
            if len(args.hex_bytes) != 4:
                raise ValueError('provide exactly four hex digits in wire order')
            result = decode_bytes(bytes.fromhex(args.hex_bytes))
        elif args.command == 'address':
            value = address_from_shunts(args.a0, args.a1, args.a2)
            result = {'address_7bit': f'0x{value:02X}', 'write_address_byte': f'0x{value << 1:02X}'}
        elif args.command == 'alert':
            result = {'writes': alert_recipe(args.lower, args.upper, args.critical,
                                             current_config=args.current_config, hysteresis=args.hysteresis),
                      'scope': 'offline proposal only; identity, current CONFIG and readback require actual hardware'}
        else:
            result = demo()
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
