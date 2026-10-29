# Start with receive, then control the final stop bit

This is an unbuilt, non-isolated 3.3 V bench example. The executable tools below
calculate an explicitly limited model and print a GPIO/UART ordering recipe.
They never open a serial port, toggle GPIO or claim a working physical link.
Use Python 3.11+ from the repository root; no extra package is needed.

```sh
python examples/rs485-interface/bringup.py budget --supply 3.3 --terminations 2
python examples/rs485-interface/bringup.py sequence --bytes 4 --baud 115200
python examples/rs485-interface/bringup.py sequence --bytes 4 --suppress-echo
```

## Wire the actual board

| Connector | Pin | Function |
| --- | --- | --- |
| J1 | 1 / 2 | Regulated 3.3 V / common GND; board range 3.0-3.6 V |
| J1 | 3 | TXD into U1 DI; compatible 3.3 V UART output |
| J1 | 4 | RXD from U1 RO; host UART input |
| J1 | 5 / 6 | DE / active-low nRE, independent host outputs |
| J2 | 1 / 2 / 3 | A / B / reference GND |
| JP1 | Shunt | Enables R3's 120 Ohm end termination when installed |

With DE high and DI high, TI defines A above B. Confirm the peer's polarity
convention rather than relying on its A/B lettering alone. Use a short twisted
pair, common reference and current-limited source for the initial setup. Ground
is not isolation or protective earth. Inspect soldering, pin 1, supply sequencing
and header/shunt fit before applying power; the software cannot establish them.

The two 10 kOhm pulldowns make the floating-host default DE=0, nRE=0: driver off,
receiver on. They do not establish the chosen MCU's reset state or prevent signal
injection into an unpowered board. This example contains no MCU, protocol or cable.

## Check termination and supply estimates

Enable appropriate termination at the **two physical cable ends**, not every node.
Leave this board's JP1 open at a middle node; the total `--terminations` count
includes the remote end(s). The separate SNT-100-BK-G shunt is not a permanent
native PCB connection. Confirm actual cable impedance and termination positions.

For this board's selected 120 Ohm / 1% / 0.25 W resistors, two worst-low values
give 59.4 Ohm in parallel. TI recommends a differential load of at least 54 Ohm.
At an assumed full-supply 3.3 V differential, the termination-current bound is
55.56 mA and each resistor's power bound is 91.67 mW. These are calculations,
not measurements. The tool adds TI's 3 mA **no-load quiescent** maximum and the
high enable pin's 10 kOhm pulldown current to show a DC supply estimate. It omits
switching/internal loaded-current effects and cannot size or qualify the supply.

```sh
python examples/rs485-interface/bringup.py budget --supply 3.6 --terminations 2
python examples/rs485-interface/bringup.py budget --terminations 3
```

Both return exit 1 because the limited model needs attention. At 3.6 V, the
full-supply bound is 60.61 mA, slightly above TI's +/-60 mA recommended driver
current; actual transceiver voltage drop may reduce it. This does **not** prove
a real overcurrent: measure VAB/current and assess the actual driver. Three
terminators give 39.6 Ohm worst-low, below the recommended load. Missing end
termination also returns exit 1. A malformed or out-of-board-range input returns
exit 2; a model with all stated checks satisfied returns 0, without approval.

The model excludes receiver/bias loading, cable resistance/capacitance, faults,
thermal derating and transients. Per-resistor power uses the selected part's
reference rating, not an environmental qualification. Check the complete bus.

## Preserve direction until hardware TX complete

The generated sequence uses TI's switching limits under the datasheet's stated
conditions, plus an explicit host margin (default 1 us, rounded up to whole us):

1. After stable supply, set DE=0, nRE=0 and UART TX idle high. Allow the receiver's
   14 us maximum enable interval at DE=0 plus the chosen host margin.
2. Obtain exclusive permission to transmit. Set DE=1 while nRE stays 0; wait the
   50 ns maximum driver enable interval plus host margin.
3. If suppressing local echo, set nRE=1 **after DE is established**. The receiver
   disable maximum is 28 ns. Otherwise keep nRE=0 and distinguish echo from peer data.
4. Write the frame and wait for the controller's **hardware TX-COMPLETE condition
   after the final stop bit**. `write()` returning, DMA completion or FIFO empty
   can happen earlier. Confirm the actual controller API's meaning.
5. Keep DE high for driver propagation (20 ns maximum) plus host margin. If echo
   was suppressed, set nRE=0 while DE remains 1, then allow receiver enable
   (110 ns maximum with DE=1) plus host margin.
6. Set DE=0, keep nRE=0, and allow driver disable (25 ns maximum) plus host margin
   before the peer/protocol's turnaround interval.

Keeping one function enabled avoids the DE=0,nRE=1 shutdown state, whose enable
times differ. The byte-count serialization estimate is a useful lower bound,
**never a timer for releasing DE**. The tool supports 8 data bits, optional parity
and one/two stop bits within this example's initial <=115200 baud planning scope.
It supplies no arbitration, collision recovery or cable/peer turnaround protocol.
Host scheduling/GPIO latency and the proposed timing margin require measurement.

Start with one deliberate sender and a non-critical known frame. Capture TXD,
DE, nRE, A/B and RXD to verify the full last stop bit, receiver return and peer
response. Record actual setup/current/waveforms if the hardware is built; no such
capture exists in this example. Fast THVD1450 edges still matter at low baud rates.

## Reproduce the software checks

```sh
uv run pytest -q tests/examples/test_bringup.py
python examples/rs485-interface/bringup.py demo
```

Tests verify resistor-tolerance/DC-power cases, missing/excess termination,
the 3.6 V conservative-current boundary, UART framing, final-stop-bit ordering,
TI enable/disable intervals and rejection of invalid inputs. The retained
[offline demo](output/bringup-demo.json) binds actual software stdout to the
script/guide/test hashes; no serial device or GPIO is used.

Sources: archived [TI SLLSEY3E](evidence/files/THVD1450DR_thvd1450_58ecc4cc07dd.pdf)
SOIC pin table p5, recommended conditions p9, quiescent current p10,
THVD145x switching table p11, functional modes p19 and bus layout pp22-29;
[manufacturer copy](https://www.ti.com/lit/ds/symlink/thvd1450.pdf).
Selected resistor and shunt identities are in [the design basis](DESIGN_BASIS.md)
and [evidence index](evidence/index.yaml).
