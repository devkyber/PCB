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

The current geometric checker implements parts of only 4 of the former
knowledge base’s 42 numbered subsections: heat-source separation, decoupling
proximity, crystal proximity, and regulator-cap placement. A partial check
does not establish that the whole subsection is satisfied. This limitation
must stay visible in reports; see [Limitations](LIMITATIONS.md).

## Stable rule identifiers

Reports and `DEVIATIONS.md` still use these historical IDs. They are retained
here so consolidation does not silently change what a waiver or finding means.
The old generic rule collection is available in Git history. Its absolute
prescriptions are not current project requirements.
Use the authority order above and the board's cited design basis.

The scope column describes **only `pcb_copilot.review.design_rules_native`**. `Partial`
means a geometric proxy exists, not full coverage. `Human` means this checker
does not decide that subsection; another gate may check a related fact.

| ID | Preserved topic | Checker scope |
| --- | --- | --- |
| `1.1` | Placement order | Human |
| `1.2` | Placement rules, including heat-source separation | Partial |
| `1.3` | Functional grouping | Human |
| `2.1` | Decoupling proximity rationale | Human |
| `2.2` | Decoupling placement | Partial |
| `2.3` | Bypass loop area | Human |
| `2.4` | Part-specific decoupling examples | Human |
| `3.1` | Ground-plane principle | Human |
| `3.2` | Ground-plane rules | Human |
| `3.3` | Mixed-signal ground connections | Human |
| `3.4` | High-current/star returns | Human |
| `4.1` | General routing | Human |
| `4.2` | Trace width and current | Human |
| `4.3` | Analog routing | Human |
| `4.4` | Digital routing | Human |
| `5.1` | Crystal and load-cap layout | Partial |
| `6.1` | Linear-regulator layout | Partial |
| `6.2` | Switching-regulator layout | Human |
| `6.3` | LDO regulators | Human |
| `6.4` | Power trace routing | Human |
| `6.5` | Voltage-reference layout | Human |
| `7.1` | Relay and high-current layout | Human |
| `8.1` | Via geometry | Human |
| `8.2` | Ground stitching | Human |
| `9.1` | Thermal management | Human |
| `10.1` | Fabrication constraints | Human |
| `10.2` | Assembly constraints | Human |
| `11.1` | Connector ESD protection | Human |
| `11.2` | ADC input protection | Human |
| `12.1` | Copper pour rules | Human |
| `12.2` | Two-layer pour strategy | Human |
| `13.1` | Layer-count choice | Human |
| `13.2` | Four-layer stackup | Human |
| `13.3` | Two-layer strategy | Human |
| `14.1` | EMC/EMI | Human |
| `15.1` | Datasheet value comparison | Human |
| `15.2` | Pin completeness | Human |
| `15.3` | Voltage compatibility | Human |
| `15.4` | Board-area justification | Human |
| `15.5` | Controlled impedance | Human |
| `15.6` | Interface choices | Human |
| `15.7` | Real-part symbol and footprint verification | Human |

Current executable scope, recorded from the checker rather than offered as
universal design advice:

- `1.2`: pad-gap proxy between selected heat sources and named analog nets;
  not an assembly-clearance or thermal-performance analysis.
- `2.2`: nearest small capacitor on a heuristically identified power net;
  not proof of its return path, pin function, effective capacitance or noise.
- `5.1`: crystal/IC and small-cap/crystal proximity; not an oscillator model
  or proof that every nearby small capacitor is the correct load capacitor.
- `6.1`: nearest capacitor on a recognized regulator supply net; not proof
  of correct value, stability, headroom or thermal suitability.

The bulk-cap exclusion historically labeled `2.4` is part of the `2.2`
implementation, not a fifth independently validated subsection. This index
does not add checks, change thresholds, or broaden any declared waiver.
