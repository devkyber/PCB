# PCB Design Rules

This is the canonical rules index. It distinguishes machine-enforced checks
from engineering judgment so a green command is never mistaken for a complete
design review. Exact values come from the selected manufacturer documents,
fabricator capability, stackup, and operating requirements—not from this file.

## Authority order

1. Captured board requirements and explicit owner decisions.
2. Manufacturer datasheets and integration manuals for the exact part/revision.
3. Manufacturer EVMs and reference designs.
4. Proven open-hardware CAD.
5. General rules and teaching references.

Where sources conflict, record the conflict and its resolution in
`DESIGN_BASIS.md`. Never silently choose the convenient value.

## Pre-schematic completeness

- Archive a datasheet for every non-passive part and any integration manual
  required for a module/socket.
- Verify exact symbol identity, pin numbers, electrical types, and footprint
  pad mapping. A fetched part is not automatically correct.
- Account for every pin exactly once as connected or intentionally unused.
- Check supply limits, logic levels, absolute maximums, address/mode straps,
  reset behavior, startup state, and required external components.
- Compare key circuits with at least one appropriate reference implementation.

## Schematic readability

- Organize around functional blocks and left-to-right signal/power flow.
- Use direct wires inside a block and labels at deliberate boundaries.
- Use graphical power symbols for standard rails.
- Attach wires and labels to actual symbol pin coordinates on the KiCad grid.
- Prevent cross-net wire crossings, overlapping symbols/text, clipped content,
  and ambiguous label placement.
- Split crowded designs into hierarchy instead of shrinking until unreadable.
- Use a complete title, revision, date, and project identity.

The existing helpers `SymbolPlacer`, `LabelPlacer`, coordinate conversion,
title-block setup, and pin-position lookup are preserved because they already
encode lessons from real failures.

## Placement order

1. Board outline, mounting holes, keepouts, connectors, and fixed mechanics.
2. Major ICs, modules, sensors, regulators, and relays.
3. High-frequency decoupling at the relevant supply pad.
4. Crystals/oscillators and their load network.
5. Protection and filtering at entry points.
6. Remaining passives, test points, and assembly features.

Measure the actual footprint’s pads and courtyard before placement. A 1×N
header anchors on pin 1, not its geometric center. Include footprint-specific
and pad-local clearance in the collision envelope.

## Power integrity and decoupling

- Place each high-frequency bypass capacitor at the supply pin it serves;
  measure pad-to-pad distance, not center-to-center distance.
- Minimize the supply–capacitor–ground loop and avoid a via between capacitor
  and pin where practicable.
- Add bulk capacitance where cable/connector inductance or load steps require
  it; an IC datasheet may assume a stiff board rail and omit board-entry bulk.
- Size power traces from current, duration, copper thickness, layer, and
  allowed temperature rise. Do not invent a generic width when inputs are
  unknown.
- Check regulator dropout/headroom, dissipation, transient response, and
  thermal copper for worst-case conditions.

## Ground and return paths

- Prefer an uninterrupted reference plane. Do not split analog and digital
  ground reflexively; control current paths and join domains according to the
  converter/vendor guidance.
- Keep high-current, relay, motor, and ignition returns away from precision
  analog paths.
- A stitching via helps only when it joins copper on at least two layers.
- Inspect filled zones for islands, starved thermals, unintended slots, and
  broken high-frequency return paths.

## Signals, clocks, and RF

- Route clocks/crystals short, close to their device, away from aggressors,
  with the datasheet’s keepout and grounding guidance.
- Route analog inputs away from switching nodes and noisy digital edges.
- Evaluate crosstalk, edge rate, return continuity, series termination, and
  differential geometry where relevant.
- Controlled impedance requires the actual stackup, dielectric properties,
  copper thickness, geometry, and fabricator calculation. A nominal width in a
  document is a starting hypothesis, not proof.
- Antenna type, matching, siting, ground clearance, and enclosure effects are
  human RF decisions backed by the module integration manual.

## Protection and high consequence outputs

- Put ESD/transient protection near the connector it protects with a short
  return path.
- Verify clamp voltage, working voltage, pulse energy, polarity, and fault
  current against the protected interface.
- For relays, solenoids, heaters, and igniters, verify driver SOA, flyback path,
  contact ratings, connector ratings, copper heating, safe reset state, and
  credible fault modes using measured load information.
- Pyrotechnic and high-current designs require independent human review and
  staged dummy-load testing. Automation cannot authorize energization.

## Routing and vias

- Route critical power, clocks, analog, RF, and safety-related signals first.
- Minimize unnecessary layer changes and place a nearby return via when a
  signal changes reference layers.
- Verify via drill, annular ring, current capacity, aspect ratio, and local
  clearance against the selected fabricator.
- Autorouting output is a candidate. Refill zones, restore grounding, inspect
  topology, and rerun DRC after every post-processing change.

## DFM and assembly

- Apply the selected fabricator’s current minimum trace, spacing, drill,
  annular-ring, edge-clearance, solder-mask, and silkscreen rules.
- Check courtyard and body collisions, component access, polarity/orientation,
  assembly process, connector retention, fiducials where appropriate, and
  panel/mechanical constraints.
- Verify BOM part numbers from the accepted PCB properties and inspect CPL
  origins, rotations, and layers against the assembly preview.

## Review protocol

Review in passes: completeness, power integrity, signal integrity, thermal,
EMC, fabrication/assembly, mechanical, then post-route verification. ERC and
DRC are inputs to these passes, not substitutes.

The current geometric checker implements only 4 of the former knowledge
base’s 42 numbered subsections: placement clearance, decoupling proximity,
crystal proximity, and regulator-cap placement. The remaining rules require
human review or future typed checks. This limitation must stay visible in
reports; see [Limitations](LIMITATIONS.md).
