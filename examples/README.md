# Native KiCad examples

These are unbuilt educational prototypes for inspecting the whole PCB workflow:
requirements, exact manufacturer evidence, native schematic, local libraries,
routed PCB, machine findings and unresolved engineering decisions.

![Three new source-bound native board renders](../docs/media/examples-gallery.png)

| Board | What to learn | Inspect |
| --- | --- | --- |
| [USB-C power entry](usb-c-power/README.md) | Independent CC terminations, PPTC/TVS limitations, and an actual connector land-pattern conflict with the manufacturing baseline | [Schematic](usb-c-power/output/schematic.pdf), [native 3D](usb-c-power/output/usb-c-power.glb), [review packet](../docs/demos/usb-c-review/index.html) |
| [I²C temperature sensor](i2c-sensor/README.md) | MCP9808 pin/package verification, address straps, open-drain ALERT, pull-up current and local bypass | [Schematic](i2c-sensor/output/schematic.pdf), [native 3D](i2c-sensor/output/i2c-sensor.glb), [review packet](../docs/demos/i2c-review/index.html) |
| [RS-485 interface](rs485-interface/README.md) | THVD1450 pin/package verification, control defaults, removable endpoint termination and clear host/bus labeling | [Schematic](rs485-interface/output/schematic.pdf), [native 3D](rs485-interface/output/rs485-interface.glb), [review packet](../docs/demos/rs485-review/index.html) |
| [GPIO indicator](gpio-indicator/README.md) | Small through-hole first run, conservative LED-current calculation and a scoped native-change demonstration | [Schematic](gpio-indicator/output/schematic.pdf), [native 3D](gpio-indicator/output/gpio-indicator.glb), [review packet](../docs/demos/gpio-review/index.html) |

Each project README describes its supply assumptions, connector pin directions,
qualification work and recorded findings. The USB-C board retains eight known
connector annular-ring/NPTH-clearance findings and lacks a PPTC body model;
it is a manufacturing-review case. The sensor and RS-485 boards have clean
recorded native ERC/DRC and parity. All retain open assembly/human decisions.

From the repository root:

```sh
uv run python tools/demo.py --project examples/rs485-interface
uv run pcb-copilot report examples/i2c-sensor --output NEW_EXTERNAL_DIRECTORY
uv run python tools/check_examples.py
```

The quick demo and offline example checker need Python without KiCad. Native
review/report generation needs the [supported toolchain](../docs/QUICKSTART.md).
The source checker verifies archives, selected-part coverage, footprint receipts
and exact captured output hashes. It preserves recorded failures and performs
no new electrical, physical or fabrication qualification.

Download a packet's `index.html` to run it offline; GitHub displays HTML source.
Keep the whole directory for [packet integrity verification](../docs/HANDOVER.md).
Native renders show saved CAD, not manufactured hardware or measured behavior.
