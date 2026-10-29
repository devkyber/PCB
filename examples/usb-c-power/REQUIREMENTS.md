# USB-C power entry requirements

## Purpose

A small educational bench board demonstrates power-only USB-C attachment,
resettable overcurrent protection, a transient shunt and a visible output-power
indicator. It is an unbuilt native KiCad example, not a certified USB product.

## Electrical

Use an externally qualified 4.75 to 5.25 V source and at most 500 mA total board
and output load at room temperature. Independent 5.1 kOhm resistors terminate
CC1 and CC2. There is no PD negotiation, current-advertisement detector, active
current limiter, output regulator or reverse-current protection. The source
must separately guarantee the allowed load budget; resistor attachment alone
does not authorize 500 mA from every host port. Do not backfeed the output.

## Mechanical

Provide a 60 x 40 mm, two-copper-layer board with two M3 clearance mounting
holes, an edge-facing USB-C receptacle and a two-pin 2.54 mm output header.
Use real official footprints and archived package models where available.
Fit, enclosure clearance and mounting hardware remain physically unqualified.

## Interfaces

J1 is the sole power input. J2 pin 1 is fused VOUT and pin 2 is GND. USB data
and SBU contacts are intentionally unused. Shield and ground are bonded on
this bench example; this does not establish EMC or system-level ESD behavior.

## Environment

Initial qualification is restricted to a dry indoor bench near 23 degrees C,
without conductive debris, an enclosure, battery energy or an energetic load.
Verify PPTC temperature derating before using the application current budget
at other temperatures. No automotive, medical or safety-critical use is claimed.

## Success criteria

Native ERC and refilled DRC report no errors or unrouted connections, selected
schematic/PCB parts and pin nets agree, every rendered schematic sheet is
actually inspected, and source/model identities are recorded. These software
results do not replace connector fit, fuse behavior, transient or load testing.
All fabrication release decisions remain unsigned until actual human review.
