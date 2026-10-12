# LMR51450 converter simulations — prepared, not run

These ten testbenches use TI's authentic encrypted **LMR51450_TRANS** model.
They are bound to the owner-controlled A9 native CAD by SHA-256. They have
**not been executed or simulator-syntax validated** because a compatible
PSpice installation is not available. No converter startup, ripple, transient,
stability or current-limit result is claimed here.

**Historical preparation:** the recorded schematic hashes predate later footprint
field edits. The frozen testbench is not automatically current. `generate.py`
will refuse to regenerate Rover decks until an explicit native-CAD comparison
and testbench reconciliation has been completed. Do not just refresh its hashes.

The owner schematic is unchanged. These are separate simulation circuits;
they neither authorize a PCB nor replace the native KiCad files.

## First reproduce TI's own example

1. Use [PSpice for TI](https://www.ti.com/tool/PSPICE-FOR-TI), or a compatible
   licensed Cadence PSpice version supporting this encrypted library.
2. Restore the exact vendor package from the retained evidence ZIP with
   `uv run python projects/rover-pdb/simulation/pspice/generate.py --vendor-only`
   from the workspace root. The command verifies the archive hash. Copy
   `vendor/LMR51450_PSPICE_TRANS` to a disposable run directory. Open
   `LMR51450_TRANS.opj` in Capture and select **START_UP / Tran1**. Run it.
   The supplied profile uses 5.5 ms and a 20 ns maximum step.
3. Check the actual run log, convergence and V(VOUT), I(L_L1), V(SW) and V(PG).
   Then run **STEADY_STATE / Tran1**, which uses MODE=1 and matching initial
   conditions. Do not infer success merely from an already-present `.out` file.
4. The `.out`, plot settings and other outputs under `vendor/` arrived in
   TI's ZIP. They are **historical vendor examples**, not local run results.

The TI example is a tool/model smoke test, not the Rover circuit: it has
different feedback, input/output passives and an RT resistor. Its success
would not yet validate our open-RT 500 kHz configuration or our power rails.

## Running the Rover cases

Keep the directory hierarchy intact so each `.cir` file's relative `.LIB`
path resolves. Use a copy of `cases` beside a copy of `vendor/` for runs;
open the `.cir` deck using the PSpice simulator's circuit-file interface.
Record the simulator/version, complete log, input hashes, waveform data and
any convergence changes. Do not edit the encrypted vendor library.

| Deck | Stimulus and useful traces |
| --- | --- |
| `12v_startup.cir` | Supply rises in 1 ms; resistive 3 A planning load at the setpoint; VIN steps through 19.8, 22.2 and 25.2 V in separate runs |
| `5v_startup.cir` | Same, with 2.4 A planning load and the retained C2 bulk capacitor |
| `motor_startup.cir` | Same, with SW1 closed and 3.5 A planning load; low-VIN dropout is expected |
| `12v_load_step.cir` | Unloaded startup; 0 → 3 A at 12 ms, then 3 → 0 A at 18 ms; 10 µs edges |
| `5v_load_step.cir` | Same, 0 ↔ 2.4 A, including C2 |
| `motor_load_step.cir` | Same, 0 ↔ 3.5 A, including C5 |
| `12v_vin_sweep.cir` | Loaded startup at 25.2 V, ramp down to 19.8 V and back up |
| `5v_vin_sweep.cir` | Same; check output regulation and inductor current |
| `motor_vin_sweep.cir` | Same; examine off-time foldback/dropout and recovery |
| `motor_enable.cir` | SW1 closes at 2 ms, opens at 12 ms and closes again at 16 ms; observe EN and output decay/restart |

All Rover decks use MODE=0 and start with zero supply. They therefore include
startup rather than initializing the output to its desired answer. The
model's prose notes call this parameter `MODEL`, but its actual `.SUBCKT`
declaration and TI example instances use **`MODE`**; the decks follow the code.

The default maximum time step is 20 ns, matching TI's example. Each case may
take substantial time. Before trusting switching ripple/peak-current results,
repeat a representative settled interval with a smaller maximum step and
check numerical convergence. Never resolve convergence trouble by silently
loosening tolerances until the plot looks acceptable.

## Electrical mapping

The explicit model interface is:

```text
.SUBCKT LMR51450_TRANS AGND BOOT EN FB GND PGOOD RT SW1 SW2 SW3 VIN1 VIN2 VIN3
+ PARAMS: MODE=0
```

| Model terminal | A9 physical pin(s) / simulated connection |
| --- | --- |
| AGND | Pin 8; zero volts in this model |
| BOOT | Pin 4; 100 nF to SW |
| EN | Pin 9; actual rail-specific enable network |
| FB | Pin 7; divider and 33 pF / 1 kΩ series feed-forward branch |
| GND | Exposed PGND pad 13; zero volts |
| PGOOD | Pin 5; isolated `PG_NC`, no pull-up fitted |
| RT | Pin 6; isolated `RT_NC`, no resistor fitted |
| SW1/SW2/SW3 | Pins 1/2/3, all tied to SW |
| VIN1/VIN2/VIN3 | Pins 10/11/12, all tied to VIN |

RT and PG are intentionally left externally open. A simulator floating-node
diagnostic must be investigated against TI's model; do not quietly add an RT
resistor or force a frequency, since that would change the selected circuit.
Verify the open-RT switching rate before interpreting the Rover results.

For U4, the enable path is VIN → R19 100 kΩ → SW_SUPPLY → closed SW1 → EN;
R24 is 22 kΩ from SW_SUPPLY to AGND and R15 is 100 kΩ from EN to AGND.
The enable-sequence case uses a voltage-controlled switch to represent SW1's
contact, not a substitute logic driver. SW1's unused third contact is absent.

## Passive models and their evidence

The purchased capacitor values are preserved in `native_component_snapshot.json`.
The simulation uses the following operating-point approximations:

| Function | A9 component selection | Default simulation model |
| --- | --- | --- |
| Every converter input | 2 × Murata 10 µF plus 100 nF | 2 × 5.75 µF, the approximate 25.2 V typical curve reading, plus 100 nF |
| 12 V output | C20–C23, 4 × Samsung 22 µF | 4 × 8.95 µF, typical near 12 V |
| 5 V output | C24–C28, 5 × Samsung 22 µF | 5 × 17.51 µF, typical near 5 V |
| Motor output | C16–C19, 4 × Murata 10 µF | 4 × 6.4 µF, approximate typical curve at 22.19 V |
| Servo bulk C2 | Panasonic EEU-FR1C471B, 470 µF | 470 µF + 56 mΩ series resistance |
| Motor bulk C5 | Panasonic EEU-FR1H221B, 220 µF | 220 µF + 30 mΩ series resistance |
| L1 | Bourns SRP1265A-6R8M | 6.8 µH + 11.5 mΩ maximum room-temperature DCR |
| L2 | Bourns SRP1265A-4R7M | 4.7 µH + 8.4 mΩ maximum room-temperature DCR |
| L3 | Bourns SRP1265A-3R3M | 3.3 µH + 6.8 mΩ maximum room-temperature DCR |

The Murata/Samsung numbers come from the archived characterization documented
in `../../docs/design/MOTOR_FILTER_SELECTION.md` and `../../docs/design/OUTPUT_FILTER_SELECTION.md`.
They are typical curve readings, not guaranteed production minima.
Capacitance is held constant in each transient: the model does **not** follow
nonlinear C(V) during startup/dropout. Its final-voltage value can understate
startup charging current because the real MLCC capacitance is higher at lower
bias. This must be resolved before claiming a loaded-startup margin.

Every ceramic's series resistance defaults to an **assumed 5 mΩ**. The bulk
resistances are **approximations based on Panasonic's 100 kHz impedance
ratings**, not verified broadband ESR values. C2's physical distance from U3
is represented by an ideal connection, which can overstate its help during
fast transients. Inductance is linear; no saturation/core loss or temperature
model is inferred from an Isat rating.

The independent source has an **assumed 50 mΩ series resistance**. These are
isolated rail tests: shared C1, battery/shunt/fuse dynamics, simultaneous
converter interaction, wiring inductance and PCB parasitics are excluded.
No claim about hot-plug spikes, EMI or layout follows from these decks.

R13/R14, feedback networks, boot capacitors and motor EN resistor values match
A9. The motor indicator is omitted (approximately 5 mA); model any exact
light-load/decay question with its actual LED I–V data. Startup loads are
resistors, not Jetson, servo or motor models. The load-step tests use a current
sink with an assumed 10 µs edge after startup. They do not simulate actual
stall current, constant-power startup, downstream UVLO or motor regeneration.

For sensitivity testing, make named run copies and change one documented
parameter at a time: `C_SCALE`, `CER_ESR`, `BULK_SCALE`, `BULK_ESR_SCALE`,
`SOURCE_R`, `L_SCALE`. Do not call an arbitrary corner a guaranteed bound.
These knobs are present for later testing; no such sweep has been run.

## How to judge an eventual run

1. First verify it completed without unexamined warnings, the waveform reached
   a settled state, and open RT produces the expected nominal 500 kHz when
   the converter is in its normal constant-frequency region. PFM/light-load
   skipping and motor dropout can reduce switching frequency.
2. Plot VIN, VOUT, EN, SW, BOOT−SW, FB and inductor current. Compare startup
   monotonicity, overshoot, settling and peak current with the datasheet and
   the actual downstream load's limits.
3. Measure ripple only in a settled window. The prepared `.MEAS` windows
   are candidates, not proof that settling occurred there. Provisional board
   goals are 0.5% peak-to-peak ripple and 5% load-step excursion, measured
   relative to settled output; they are distinct from DC accuracy.
4. A 19.8 V input cannot produce a regulated 22.19 V motor output. Record the
   dropout result instead of grading it against an impossible setpoint.
5. A clean load-step response is useful evidence, but is not a formal loop
   phase/gain-margin measurement. Thermal, layout, real component impedance,
   fault handling and motor energy still need separate work.

## Model limitations and provenance

TI's model version 1.00, dated 2022-11-27, targets PSpice 17.4. Its documented
features include output/frequency setting, fixed soft-start, minimum on/off
time and foldback, low-side zero crossing, positive overcurrent protection,
OVP, power good, UVLO and boot operation. It omits operating/shutdown current,
temperature effects and spread spectrum. Ground pins are tied internally to
0 V, so these decks cannot investigate ground bounce or the AGND/PGND layout.
The selected SDRRR variant's spread-spectrum operation is therefore absent;
do not equate the generic model with an exhaustive model of that orderable part.

`vendor/` is a regenerable, ignored extraction directory. When restored, it contains
every member's exact bytes from the archived
[TI SNVMCB2 ZIP](https://www.ti.com/lit/zip/SNVMCB2), including its unmodified
licence/copyright text and original project. `provenance.json` records the ZIP,
model, every extracted file, native CAD and prepared deck hashes. The exact
archive is also retained in the project's evidence store.

Regenerate prepared decks from the PCB workspace with:

```powershell
uv run python projects/rover-pdb/simulation/pspice/generate.py
```

This command performs no simulation. It refuses if the seven owner schematic
files differ from `cad_snapshot.json`, or if an extracted vendor file was
modified. Reconcile future CAD changes explicitly; do not refresh the hash
guard to make an obsolete testbench appear current.
