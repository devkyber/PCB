# Read the MCP9808 before configuring it

This board is unbuilt. The commands below run on captured or example bytes and
produce a proposed register recipe; they never open I2C or claim a hardware result.
Use Python 3.11+ from the repository root. No extra package is required.

```sh
python examples/i2c-sensor/bringup.py address --a0 1 --a1 0 --a2 1
python examples/i2c-sensor/bringup.py decode 0194
python examples/i2c-sensor/bringup.py decode 1E6C
```

These examples yield 7-bit address `0x1D`, `+25.25 C` and `-25.25 C` respectively.
The positive word is the actual bit pattern in Microchip Figure 5-5; the negative
word is derived from its signed conversion equation. They are software inputs,
not measurements. `decode E194` preserves the same temperature and reports all
three boundary flags. Flags can be set even while ALERT output is disabled.

The decoder requires exactly two bytes in **MSB-first wire order**. A host SMBus
word-read helper may reverse those bytes. For example, `9401` decodes outside the
device's operating range; a plausible-looking number alone cannot establish byte
order or identity. Out-of-range decoded values are flagged, not silently clamped.

## Connect a deliberately limited bench setup

1. Inspect assembly and the current native sheet. With power off, verify J1
   `1=3V3, 2=GND, 3=SCL, 4=SDA`; J2 `1=ALERT_N, 2=GND`. Use the board's regulated
   3.3 V +/-5% scope, a compatible same-rail host and a common ground.
2. Leave JP1/JP2/JP3 open for `0x18`. A shunt connects that header's pin 1 (3V3)
   to pin 2 (A0/A1/A2); addresses are `0x18 + A0 + 2*A1 + 4*A2`. Power off before
   changing shunts. The tool reports a **7-bit address**, separate from the shifted
   write-address byte; do not pass `0x30` as the normal bus API address.
3. Start with a short 100 kHz bus. Count the board's fixed 4.7 kOhm pullups and
   every host/remote pullup. Scope rise time and logic levels with the actual cable.
   No bus scan, cable length or 400 kHz operation is qualified here.
4. Read manufacturer register `0x06` as two bytes: `00 54`. Read device/revision
   register `0x07`: the first byte must be `04`; the second is the silicon revision
   and need not remain `00`. Stop on a mismatched identity or transfer error.
5. Read CONFIG `0x01` (two bytes), resolution `0x08` (**one byte**) and temperature
   `0x05` (two bytes). Read resolution explicitly; do not assume fractional bits
   or a fixed first-sample delay from a generic example. Resolution code 3 is
   0.0625 C with a **typical**, not maximum, 250 ms conversion time. A shutdown
   CONFIG holds the previous temperature, so a successful read need not be fresh.

`read_sensor(bus, address)` is a small read-only adapter for an explicitly supplied
bus object with `readfrom_mem(address, register, length)`, as used by MicroPython
I2C APIs. Place `bringup.py` beside the host program for import. It constructs no
bus, chooses no GPIO pins and performs no writes:

```python
# bus is your already-configured, controller-specific I2C object.
from bringup import address_from_shunts, read_sensor

sample = read_sensor(bus, address_from_shunts(0, 0, 0))
print(sample)  # includes CONFIG, shutdown, silicon revision and resolution
```

The offline tests use a scripted bus double. Neither that test nor this adapter
has been exercised on this physical board or across every MicroPython runtime.
Controller pin selection, bus locking, timeout/recovery and supply sequencing
belong to the actual host integration.

## Propose an ALERT configuration, then verify readback

Only use this initial recipe after actually reading **CONFIG=0** from the intended
device. The tool rejects existing or locked configurations instead of overwriting
application settings. Do not reset a live system simply to satisfy the example.

```sh
python examples/i2c-sensor/bringup.py alert --current-config 0x0000 --lower 10 --upper 30 --critical 90 --hysteresis 3
```

The proposed order keeps ALERT disabled, writes lower/upper/critical thresholds,
explicitly selects resolution 3, then writes CONFIG `04 08`: continuous conversion,
3 C hysteresis, active-low comparator output, no lock bits. Limits must be exact
0.25 C steps with `lower < upper <= critical`; the tool never silently rounds.
The resolution write is one byte (`03`), while threshold/CONFIG writes are two.

Before enabling output, read back all thresholds and resolution. Then verify
CONFIG's writable fields; its status bit is read-only. Compare actual ALERT_N
voltage to the configured window using a controlled temperature stimulus and a
suitable reference. CONFIG defaults to output disabled. This notification is
not a safety interlock, and no thermal accuracy, timing or measured response is
asserted by the software recipe.

## Reproduce the software checks

```sh
uv run pytest -q tests/examples/test_bringup.py
python examples/i2c-sensor/bringup.py demo
```

Tests cover the datasheet's +25.25 C read and +90 C threshold-write vectors,
negative/fractional temperatures, flag masking, all eight addresses, byte order,
identity revisions, short reads, reserved bits and rejection of locked settings.
The retained [offline demo](output/bringup-demo.json) binds example stdout to the
script/guide/test hashes. It contains no live hardware capture.

Sources: archived [Microchip DS20005095B](evidence/files/mcp9808-e7b6502f744c.pdf),
Table 3-2 p11, registers 5-2..5-7 pp18-29, Figure 5-4 p23, Equation 5-1 p25 and
Figure 5-5 p26; [manufacturer copy](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/MCP9808-0.5C-Maximum-Accuracy-Digital-Temperature-Sensor-Data-Sheet-DS20005095B.pdf).
