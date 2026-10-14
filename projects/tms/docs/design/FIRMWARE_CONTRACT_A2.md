# TMS A2 firmware contract

Author design contract, 2026-10-14. These settings follow the archived TI
register tables and PJRC pin table. They have not been tested on hardware.
They are part of the electrical design assumptions, not optional library
defaults. The A2 schematic-stage installation is authorized; this contract describes the
installed circuit. Firmware and hardware behavior remain untested.

| Device / register | Proposed value | Meaning and source |
| --- | --- | --- |
| ADS1256 STATUS, address00h |02h writable bits | MSB first, manual calibration, **buffer ON**. ID and DRDY are read-only. TI SBAS288K p30. |
| ADS1256 MUX,01h |01h | AIN0 positive, AIN1 negative. Unused analog pins are NC. p31. |
| ADS1256 ADCON,02h |06h | CLKOUT disabled, sensor-detect current disabled, PGA64. pp31-32. |
| ADS1256 DRATE,03h |A1h | Nominal1000SPS at7.68MHz. p32. |
| ADS1256 IO,04h |00h | Unused DIO pins are outputs held low; CLKOUT is disabled. p33. |
| ADS1220 configuration0 |81h | AIN0-to-AVSS, gain1, **PGA bypass**. TI SBAS501D p43. |
| ADS1220 configuration1 |C4h | Normal mode, nominal1000SPS, continuous conversion, temperature sensor and burnout sources off. p44. |
| ADS1220 configuration2 |00h | Internal2.048V reference, low-side switch open, IDAC current off. p45. |
| ADS1220 configuration3 |00h | Both IDAC routes disabled, dedicated DRDY only, reserved bit zero. p46. |

Use separate SPI0 and SPI1 buses as drawn. SPI mode1 (CPOL0/CPHA1), initially
1MHz on each, is the proposed bring-up configuration. ADS1256 SCLK must remain
at or below fCLKIN/4 =1.92MHz. Observe each device's command spacing,
read-data delay, CS setup/hold and calibration timing; bus frequency alone
does not satisfy these timings.

Initialize FIRE GPIO3 low before enabling its output. Keep both chip selects
high during startup. USB-only operation leaves analog power off: do not
interpret conversions as valid until the analog supply and reference are valid.
Allow at least150ms after stable rails as an initial reference-settling screen,
then verify the actual settling and calibration duration.

For ADS1256, stop continuous read before writing configuration, read back the
writable settings, run SELFCAL at the selected gain/rate/buffer setting, and
wait for completion through DRDY. Keep the resulting calibration state with
the measurement configuration. A reset or configuration change requires
reinitialization and appropriate recalibration. Do not use an older driver
that silently leaves BUFEN disabled.

For ADS1220, reset, write/read back all four configuration bytes, then start
continuous conversion. Use the dedicated DRDY pin for timestamps. The internal
oscillator has specified tolerance; the two channels are not synchronously
clocked. Record actual sample timestamps, filter delay, missed-sample counters
and power/reset events. A nominal1kSPS stream does not prove a flat500Hz band.

Radio: `Serial3.begin(115200)`, followed by `Serial3.attachCts(19)` and
`Serial3.attachRts(18)`. TX14 goes to XBee DIN, RX15 receives DOUT; XBee CTS12
feeds Teensy CTS19 and RTS18 drives XBee RTS16. Pin19 supports direct Serial3
CTS, avoiding the inverted polarity associated with PJRC XBAR routing.
Configure the XBee's flow-control and sleep/DIO settings deliberately.

For USB-adapter firmware recovery, remove socketed U8 from the board and use
the module adapter. TP8/TP9 expose reset/sleep for diagnostics; they are not a
complete programming header. U9 outputs remain driven when both supplies are
present and OE is high, so an external adapter must not contend with its RF-side
UART/RTS outputs. Specify/inspect XBee SoC revisionC or later; Digi manualW p101
describes revisionB brownout failures and complete-powercycle recovery.

Keep ignition off through reset, invalid commands, stale commands and logging
failures according to the agreed firmware protocol. The actual pulse/current
contract must be qualified with a non-energetic dummy load. This document does
not implement, test or approve ignition firmware.

Sources: [ADS1256](https://www.ti.com/lit/ds/symlink/ads1256.pdf),
[ADS1220](https://www.ti.com/lit/ds/symlink/ads1220.pdf),
[PJRC UART](https://www.pjrc.com/teensy/td_uart.html),
[Digi hardware manual](https://docs.digi.com/resources/documentation/digidocs/pdfs/90001543.pdf).
Revision-specific facts refer to the local hash-verified archives.
