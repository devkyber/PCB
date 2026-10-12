# A9 motor enable and Pico power decisions

Design decision, 2026-10-01. Prepared for the owner's requested schematic
finalization. The current native CAD and its verification report identify the
implemented revision; this note explains the selected circuit and its limits.

## Motor switch and the pasted explanation

The pasted explanation correctly separates two conditions. Opening SW1 in A8
already gave EN a return to ground through R15. It did not disconnect battery
voltage from U4 VIN. The separate weakness was deriving EN from the 5 V output:
stored charge on that output could keep EN high after U4 VIN fell.

TI specifies EN no higher than VIN in recommended operation, with an absolute
maximum of VIN + 0.3 V. TI also advises against applying an EN voltage with
VIN at zero. A9 therefore removes the independent 5 V source from this control
path. EN is derived from the same local VBAT node that supplies U4 VIN.

Do not connect the existing SW1 directly to VBAT. C&K rates the selected
OS102011MA1QN1 contacts at 0.1 A / 12 V DC; the battery reaches 25.2 V.
Low switching current alone does not justify ignoring that voltage rating.

The selected connections are:

```text
U4 local VIN / VBAT --- R19 100k --- SW_SUPPLY --- SW1 pin 1
                                         |
                                       R24 22k
                                         |
                                       AGND_4

SW1 common pin 2 --- MOTOR_EN --- U4 EN, pin 9
                         |
                       R15 100k
                         |
                       AGND_4

SW1 pin 3: intentionally unconnected
AGND_4: local connection to GND through existing NT3
```

All three resistors are 1%. R19 changes from 10k to 100k; R24 is added;
R15 remains 100k. No intentional capacitor is added to the enable divider.
The switch still enables with contacts 1-2 closed and disables in position
2-3. R15 defines EN during the switch's break-before-make interval as well.

### Voltage and power checks

With SW1 OFF, the switch supply is unloaded by R15:

    VSW = VBAT * 22 / (100 + 22)

With SW1 ON, R15 loads the divider. This loading must be included:

    Rbottom = 22k || 100k = 18.0328k
    VEN = VBAT * 18.0328 / (100 + 18.0328)
        = 0.152778 * VBAT

| Condition | At VBAT = 19.8 V | At VBAT = 25.2 V |
| --- | ---: | ---: |
| SW1 ON: nominal EN | 3.025 V | 3.850 V |
| SW1 OFF: nominal switch supply | 3.570 V | 4.544 V |
| SW1 OFF: EN | Approximately 0 V | Approximately 0 V |

Across the planning battery range and all independent 1% resistor corners,
ON-state EN is approximately 2.974-3.916 V. TI's required start level is
greater than 1.4 V, so there is substantial margin. The maximum open-switch
supply is 4.619 V. Even a 36 V DC input, the IC's recommended input ceiling,
would produce at most about 6.599 V on the open-switch supply.

TI lists 0.1 uA EN leakage at EN = 3.3 V as a **typical** value, not a
guaranteed maximum. Its nominal ON-state voltage effect is about 1.53 mV
because the source resistance is 100k || 22k || 100k = 15.278k. At the same
illustrative leakage, the open-switch EN offset through R15 is about 10 mV.
These leakage estimates must not be labelled guaranteed temperature corners.

At 25.2 V, nominal divider input current is approximately 214 uA with the
switch ON and 207 uA with it OFF. R19 dissipates approximately 4.56 mW in
the ON state; R24 and R15 each dissipate less than 1 mW. Ordinary 0.125 W
0805 resistors have ample power margin for this divider.

This circuit removes the held-up 5 V drive and makes EN follow a fraction of
local VIN during ordinary power-down. It does not establish a guarantee for
arbitrarily fast hard shorts, parasitic coupling or negative input spikes.
Keep the divider and EN wiring compact, and verify VIN/EN during the normal
hot-plug and shutdown measurements on the first board. The divider is not a
6S battery undervoltage-protection circuit: its thresholds are well below
the planning 19.8-25.2 V battery range.

SW1 remains a converter-enable switch, not a galvanic battery disconnect or
a certified emergency stop. Output capacitors retain energy after disabling;
motors can also return energy to the rail. The existing rail-present LED
indicates voltage, not a guaranteed safe or fully discharged state.

## Pico: use the USB supply already required for operation

The owner clarified that USB is required for host communication and that
standalone PDB-powered Pico operation has no current purpose. USB-only power
is therefore the simpler fit. Remove the A8 external Q1 power path and leave
the carrier's Pico VBUS pin 40 and VSYS pin 39 unconnected. Do not join PDB
5 V to either pin. The Pico module retains its own internal power chain:

    USB VBUS -> onboard D1 -> VSYS -> onboard regulator -> 3V3

Raspberry Pi explicitly describes plugging in micro-USB as the simplest
powering method. The Figure 9 MOSFET circuit was a valid way to add a second
source; it was optional functionality rather than a requirement. Removing
it also removes the need to validate source handover for this carrier.

| Supply or communication condition | Expected behavior |
| --- | --- |
| Powered USB present | Pico and its 3V3 output operate from USB. The INA226 and J9 3V3 output share that supply. |
| USB power absent, PDB battery present | Pico, INA226 supply and J9 3V3 become unpowered after stored charge decays. PDB 5 V and the motor rail can remain powered. |
| Pico unpowered | Existing R3-R5, 10k, hold the three servo PWM signal lines low. The actual servo response to missing PWM still depends on the servo. |
| USB data lost but VBUS still powered | Pico can remain powered. Firmware still needs a command timeout; USB-only power does not detect every communication failure. |
| USB power restored | Pico boots and firmware must initialize outputs and communication state. A power cycle does not preserve live RAM/control state. |

The motor converter is controlled by SW1 and its local divider, independently
of Pico. Unplugging Pico USB is consequently not a hardware motor stop.
PWM pull-downs establish signal levels; they do not prove that every attached
actuator removes torque. Confirm the actual servo's missing-signal behavior
and the firmware's startup/lost-command behavior during integration.

J9 exposes GP18-GP21, Pico 3V3 and GND. Its 3V3 pin is an output from Pico,
not an alternative supply input. Future externally powered peripherals must
respect this and the GPIO voltage limits. The Pico datasheet distinguishes
the digital GP0-GP25 pins from its ADC-capable pins when discussing voltage
applied while the RP2350 is unpowered; GP18-GP21 are in the digital group.

## Datasheet locators and scope

- [TI LMR51450, SLUSEP7](https://www.ti.com/lit/ds/symlink/lmr51450.pdf):
  p. 3 Table 6-1 gives EN pin 9 and VIN pins 10-12; p. 4 sections 7.1/7.2
  give EN limits; p. 5 section 7.4 gives thresholds and typical leakage;
  p. 13 section 8.3.3/Figure 8-3 describe enable and the VIN divider.
  Archived file: `LMR51450SDRRR_lmr51450_7f80073eb777.pdf`.
- [C&K OS switch datasheet](https://www.ckswitches.com/media/1428/os.pdf):
  current manufacturer sheet p. 10 identifies OS102011MA1QN1, terminals
  1-2/2-3, non-shorting contacts, and 0.1 A / 12 V DC rating. The existing
  archived 2017 source has the same information on PDF p. 6 / printed I-42:
  `OS102011MA1QN1_9e68893bade4341f8dc17b91bf8fc979_96f8f741dec9.pdf`.
- [Raspberry Pi Pico 2 datasheet, release 5](https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf):
  printed p. 9 / PDF p. 10 gives VBUS, VSYS and 3V3 functions; printed
  p. 14 section 5.2 discusses unpowered GPIO; printed p. 15 / PDF p. 16,
  sections 5.4-5.5, explain the onboard power chain and USB-only supply;
  printed pp. 16-17 / PDF pp. 17-18 show optional second-source circuits.
  Archived file: `Pico_2_pico-2-datasheet_cbcfaf881018.pdf`.

These are schematic design decisions and arithmetic checks, not a completed
fault-safety assessment, PCB validation, actuator safety claim, or fabrication
release. Converter layout, thermal performance, startup/transient behavior,
motor regeneration and final mechanical choices retain their documented scope.
