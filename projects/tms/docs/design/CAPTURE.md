# A0 circuit decisions and calculations

> Historical A0 capture, retained for provenance. Installed A2 choices and
> calculations are in [COMPONENT_VERIFICATION.md](COMPONENT_VERIFICATION.md).
> In particular the converter, passive orders, buffering and connector polarity changed.

Date: 2026-10-13. Author: Codex. Scope: fresh schematic capture, not owner
acceptance or production qualification. Sources are the exact archives in
evidence/index.yaml. Historical CAD, netmaps, recipes, waivers and sign-offs
were not used as a starting design.

## Power domains

J1 accepts the recorded 4S electronics range, 12-16.8 V. SS54 provides series
reverse-polarity protection. TPS54302DDCR replaces the provisional LM7805.
The circuit follows TI SLVSDG6C Figure 7-1: 10 uH, two 22 uF output capacitors,
100 nF bootstrap, 511 kOhm / 105 kOhm enable divider, and 49.9 Ohm / 75 pF
feed-forward network. The lower feedback resistor is 13.6 kOhm, giving
0.596 x (1 + 100049.9/13600) = 4.981 V nominal. The 0.581-0.611 V FB limits,
plus resistor tolerances, give approximately 4.85-5.12 V before distribution
losses. Check the assembled supply, startup and load steps. Effective ceramic
capacitance, hot-loop geometry and stability are layout/component decisions.

The 511k/105k enable network is the reference implementation, not a 4S LiPo
discharge cutoff. Use an externally protected battery and a fused input harness.
Select fuse ratings from actual demand and wire ratings. At 1 A, a hypothetical
85% converter efficiency implies approximately 0.88 W conversion loss; 85% is
a thermal screening assumption, not a measured or guaranteed efficiency.
SS54 dissipation also needs the actual current, forward drop and layout.

Planning allocations at the 5 V supply are deliberately distinguished from
manufacturer maximum currents:

| Consumer | 5 V allocation | Meaning |
| --- | --- | --- |
| Teensy + on-module SD + ADC logic + LEDs | 650 mA | Reserve for simultaneous MCU/SD activity; measure selected SD card peaks |
| Radio LDO input | 100 mA | Independent RF supply allowance, including startup/transients |
| Relay coil | 47 mA | Conservative bound from 125 Ohm +/-10% coil and upper supply assumptions |
| ADC analog, bridge and buffers | 60 mA | Combined analog reserve; bridge alone is about 13 mA |
| Total | 857 mA | Below the 1 A planning envelope; not a verified peak-load guarantee |

The IC's 3 A rating is not a qualified 3 A board rating. A 3 A design cannot be
claimed from ERC, an inductor rating or this allocation table. Bench and thermal
measurements remain required.

FB1 feeds +5VA and the bridge. Its ferrite impedance is frequency-dependent;
it is not a 10 uH inductor and no ripple-rejection result is claimed. Its exact
manufacturer specification/derating must be archived and checked before order.
The part is a passive sourcing candidate, BLM21PG601SN1D.

TLV75533PDBVR supplies +3V3_RF independently. At the 100 mA allocation,
(4.981-3.3) x 0.1 = 0.168 W. Use the DBV package thermal information, not
the newer DYD exposed-pad package's lower thermal resistance. Actual copper,
ambient and module transients require validation. Teensy +3V3 supplies ADC DVDD
and pull-ups only, with a <10 mA allocation; it is never tied to +3V3_RF.

JP1 is a removable, normally fitted VIN power shunt. Remove it before battery
and USB are used together, or physically separate the Teensy VIN/VUSB pads as
PJRC describes. The post-shunt power flag explicitly assumes the shunt is
fitted. USB-only power does not power the ADC analog rails. Verify sequencing,
off-state injection and brownout behavior; the drawing does not certify them.

## Thrust channel

CAS BCA-100L remains the confirmed sensor. The archived CAS brochure specifies
2 mV/V +/-10%, 400 Ohm +/-20 Ohm input and 350 Ohm +/-3.5 Ohm output resistance,
and recommends 10 V excitation. A0 preserves the owner's historical 5 V
excitation, yielding about 10 mV differential at 100 kgf and lower bridge
dissipation. Noise and accuracy at this lower excitation need measurement.

J2 has EXC+, EXC-, SIG+, SIG- and shield. The 5-pin harness is a board-side
definition, not the sensor's manufacturer pin numbering. If the actual unit
has six conductors, terminate its remote sense wires correctly in the harness;
do not leave that to an assumed wire colour. The shield bonds to electronics
GND at J2; enclosure/earth bonding remains a mechanical/EMI review.

TPD2E2U06DCKR provides coarse cable ESD suppression. Two 1 kOhm resistors,
BAV199 steering diodes and a 220 nF differential capacitor precede OPA2388IDR
unity-gain buffers. The nominal input pole, including 350 Ohm sensor source
resistance, is 1/[2*pi*(2000+350)*220n] = 308 Hz. Buffer outputs use 47 Ohm
resistors and a 10 nF differential capacitor before ADS1256 AIN0/AIN1.
The 47 Ohm resistors and finite ADC input impedance produce gain error; calibrate
the assembled chain at the actual clock, PGA and data rate. No 24-bit system
accuracy or flat 500 Hz bandwidth is claimed.

ADS1256 AVDD is pin 1, DVDD 16, AGND 2 and DGND 17. RESET is pin 15, not DVDD.
Both supplies have local high-frequency and bulk bypasses. RESET/SYNC are tied
to DVDD as allowed by TI; unused analog pins return to GND, unused DIO pins are
NC. The firmware must configure unused DIO states deliberately.

The external reference is a real ratiometric source: two 10 kOhm, 0.01%,
10 ppm/degC resistors divide +5VA by two, followed by a 10 kOhm / 1 uF filter
and OPA350UA. The buffer/output bank follows ADS1256 SBAS288K Figure 26,
including 47 uF and 100 uF aluminum electrolytics plus 100 nF ceramic. Select
actual effective capacitance, ESR, package and temperature ratings; the drawing
alone does not establish stability. REF5025 research is retained as a compared
alternative; no standalone REF5025 is populated in A0.

Nominal VREF is about 2.49 V. At PGA64, the ADC differential full scale is
+/-2*VREF/64, about +/-77.8 mV. The maximum rail/reference bounds need review
against the TI 2.6 V reference limit. The divider ratio, separate buffer offsets
and temperature drift remain in the error budget. Ratiometry cancels slow
excitation changes; the different filtering paths do not guarantee dynamic
noise cancellation. Reference filter time constant is (5k+10k)*1u = 15 ms;
wait at least 150 ms before calibration/acquisition and verify settling.

Y1 is ABLS-7.680MHZ-D-4-Y-T, 18 pF load, using 30 pF C0G capacitors. The first
estimate is CL = C1*C2/(C1+C2) + Cstray = 15+3 = 18 pF. Parasitics are an
assumption; verify startup, frequency, drive level and temperature on the PCB.
Firmware intent is AIN0-AIN1, PGA64, ADC buffer OFF, 1000 SPS, SPI mode 1,
SCLK no higher than 7.68 MHz/4 = 1.92 MHz. Series SPI resistors control edges;
they are not sustained 5 V fault protection.

## Pressure channel

The confirmed IPSU-GP1K5-6 is the Sensata/Cynergy3 0-1500 psi, 0-5 V, 9-32 V
variant documented in the archived IPSU family sheet. It runs from protected
4S VBAT. The sensor's 9-32 V rating does not expand the board input rating.
Sensor DIN pins are 1 supply, 2 return, 3 signal; board J3 is deliberately
1 supply, 2 signal, 3 return. Verify the harness against the actual sensor.

R40/R41 = 100 kOhm / 33.2 kOhm, 0.1%, gives k=0.249249. Thus 5 V produces
1.24625 V at AIN0, using approximately 61% of the positive 2.048 V range.
The sensor sees 133.2 kOhm. Permissible sensor load is not specified by the
retained family sheet; obtain confirmation or compare the unit's loaded and
unloaded output before accepting accuracy. RTH=24.925 kOhm and 47 nF give
approximately 136 Hz bandwidth. A 16.8 V signal-to-battery miswire would divide
to 4.1874 V while the board is powered; this is not a general fault approval.

ADS1220 uses AIN0-to-AVSS, gain1, PGA bypass, internal 2.048 V reference,
normal 1000 SPS and internal clock. AVDD pin12 and DVDD pin13 have separate
100 nF bypasses. CLK returns to DGND, unused analog/reference pins return to
GND, and both data outputs are accounted for. Calibration must include divider,
ADC reference, offset and input loading. The two ADC clocks are independent;
timestamp DRDY and validate sample alignment, filter delay and loss behavior.

## Controller and radio

The socket pads use explicit PJRC signal names rather than invented package
numbers. The two physical rows each have 24 contacts at 2.54 mm pitch and
15.24 mm row separation. See libs/README.md for row mapping and source pages.
U1 owns the module's microSD socket. SPI0 is D11/D12/D13, CS D10, DRDY D9.
SPI1 is D26/D1/D27, CS D0, DRDY D2. Serial2 is D8 TX / D7 RX, with D14 CTS
input and D15 RTS output handled by firmware. D3 is FIRE, D4/D5/D6 status LEDs.
The red LED reports command state; there is no physical ARM feedback input.

The owner selected XB3-24AST-J and A24-HASM-450 on 2026-10-13. This is the
through-hole RP-SMA variant, not U.FL. Digi's archived manual governs the
20-pin interface and mechanical projection. The antenna connects through the
appropriate RP-SMA mating interface/extension; enclosure fit is still open.
RESET and DTR are accessible, and UART/RTS/CTS support recovery/flow control.
Configure sleep and unused DIO states; prove the UART/radio throughput.
The stated 3.3 V USB adapter is assumed to be the ground-station device.
Its supply capacity and exact installation have not been verified.

## Ignition interface

The confirmed separate 2S battery, external series ARM switch, normally-open
relay and distinct IGN_GND are preserved. There is no on-board FIRE button,
continuity sensing, ARM readback or electronics-to-ignition ground connection.

AO3400A replaces the provisional MMBT3904 coil driver. The archived AOS
datasheet specifies RDS(on) at 2.5 V gate drive; a 1 kOhm gate resistor and
10 kOhm gate-source pull-down give about 3.0 V with a 3.3 V output. This avoids
depending on NPN saturation at a GPIO current near its limit. It controls
only the relay coil. 1N4148WS cathode is on +5V, anode on COIL_LOW.

The Hongfa HF46F-G/5-HS1T sources specify a 5 A resistive rating at 30 VDC.
The historical 7 A claim is not adopted. Cold nichrome resistance, actual pulse
current/duration, external switch rating, wiring, fuse selection and PCB copper
remain unmeasured/unqualified. A welded contact or stuck drive can bypass the
remote OFF command; this circuit is not a certified two-fault inhibit.

Test ARM-open, supply reset/ramp/brownout, invalid commands and single faults
with a non-energetic dummy load before any live ignition use. Release remains
blocked until the named human decisions and physical evidence are current.

## Manufacturing and scope

The eight new native sheets and local libraries are the first current design.
The PCB contains only the dated JLCPCB geometry baseline, with no outline,
placement or routing. Confirm the 100x80 versus 100x100 mm conflict before
placement. The BOM is a schematic inventory: exact resistor/capacitor orders,
electrolytic ESR/packages, socket suppliers, component derating, stock, JLCPCB
eligibility, 3D models and assembly rotation are not approved by this capture.
No old waiver or human signature transfers. Future edits must preserve saved
native CAD and use the normal checked candidate workflow.
