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

## New JLCPCB boards

For future new two-layer / 1 oz / green-mask JLCPCB designs, start from
[`templates/jlcpcb-2layer-1oz`](../templates/jlcpcb-2layer-1oz/meta/info.html).
Its native project settings and scoped custom rules are the workspace baseline;
copy the three same-stem KiCad files and rename them to the new project's stem,
or select **JLCPCB 2-layer 1oz** in KiCad 10's New Project template selector.
KiCad creates an empty schematic if the template does not contain one.
Use the normal project requirements, evidence and review workflow afterward.

This is a dated, conservative geometry baseline, not a live supplier-rule feed.
Recheck the linked capabilities when manufacturing options change. Power widths,
voltage spacing, component spacing, stencil/thermal-pad details, fiducials/rails,
physical fit and supplier stock/rotation remain project-specific reviews.
The template does not set a universal board outline or select a surface finish.

For an existing owner-edited board, prepare a scoped candidate, preserve its
netclasses and stricter constraints, and run the normal preview/apply path.
Do not replace its settings wholesale or redraw copper to make this template fit.
In KiCad, the manual equivalent is **File > Board Setup > Import Settings from
Another Board**, selecting only the intended categories, followed by DRC.
Global Preferences do not apply manufacturing rules to every project.

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

These conventions apply to every new schematic and every authorized schematic
edit in this workspace. The owner adopted the drawing approaches in
[Tiago Gala's guide](https://medium.com/@tiago.gala/the-art-of-drawing-good-schematics-be3e7e59eb40)
and [Gregor Gross's guide](https://medium.com/@gregorgross/style-guide-for-schematics-if-you-like-your-schematics-to-be-understood-easily-7ed3452346cc)
on 2026-09-30. Use them as presentation references; manufacturer requirements
and the current owner CAD retain their authority over circuit decisions.

- Begin a multi-sheet design with a system overview showing power domains,
  interfaces, destinations and planning loads. Keep the hierarchy shallow.
- Separate functional groups with whitespace and concise headings. Reserve
  frames for actual hierarchy or a boundary that needs explanation. Avoid both
  crowded pages and unnecessarily long wires across mostly empty pages.
- Arrange symbols by electrical function rather than package perimeter:
  inputs normally left, outputs right, positive supply above, returns below.
  Power converters may take their input from the left. Bidirectional interfaces
  and fixed connector pin order are legitimate exceptions; identify their role.
- Keep familiar circuit shapes: vertical dividers and pull resistors, clear
  feedback paths, and a short, visible bootstrap loop. Size symbols for their
  connected circuitry; leave room between pins for actual support components.
- Positive supply glyphs point upward; GND and negative supply glyphs downward.
  Keep their text beside the glyph, clear of signal wires.
- Use the KiCad 1.27 mm connection grid unless the library requires a finer
  compatible grid. Leave visible wire between separate component terminals;
  aim for at least two grid steps. Never use coincident terminals as a shortcut.
- Use T junctions with visible dots. Stagger branches instead of four-way joins.
  Minimize crossings; an unavoidable crossing must be distinct from a junction,
  away from text and pin ends. Do not add a dot to a crossing of separate nets.
- Label important wired nets above the line. Keep spelling and units consistent
  within a project. New projects default to explicit units (100 nF, 10 kOhm,
  6.8 uH), with ratings/tolerances where they inform selection or testing.
  Do not change an existing part's electrical value to enforce typography.
- Preserve local, global and hierarchical label scope. Use sheet navigation or
  destination notes for interfaces; enable intersheet references when global
  labels are used. Do not replace an established hierarchy solely for styling.
- Annotate design intent near the block: nominal voltage, documented limits,
  planning load, logic levels, address, configuration, feedback calculation,
  useful probe values, and placement constraints. Distinguish assumptions and
  calculated bounds from guarantees; never invent missing limits.
- Include brief revision history and source references. Mark optional/DNP parts
  and describe configuration changes without relying on colour alone.
- Keep intentional no-connect marks explicit. An NC marker, an ERC exclusion
  and a PWR_FLAG have different meanings: PWR_FLAG asserts a driven power net
  and must never be used as an unused-pin marker or to conceal a real error.

- Organize around functional blocks and left-to-right signal/power flow.
- Draw the complete local circuit with direct wires. Keep each IC's bypass
  capacitors, pull-ups, feedback divider, bootstrap network, straps, and other
  supporting parts beside the pins they serve. A reader must be able to follow
  the local circuit without matching detached groups of labels.
- Use labels for deliberate boundaries: remote blocks, distant connectors, or
  sheet interfaces. They remain useful; do not replace an easily drawn local
  connection with repeated labels merely to simplify generation.
- Attach hierarchical ports directly to the relevant circuit wires. Do not
  create separate port-to-local-label islands at the top of the page.
- Attach test points to the rails or signals they expose. Attach necessary
  `PWR_FLAG` markers to the actual source/return wiring, rather than collecting
  flags and labels in detached islands.
- Use graphical power symbols for standard rails, with enough clearance that
  the glyph and its text cannot appear to touch an unrelated wire. A crossing
  without a junction dot is not a readability fix for an overlapping glyph.
- Keep reference and value fields close to their own symbol, with consistent
  orientation and separation from wires, pins, and neighboring fields. Do not
  move fields far away to resolve a collision; rearrange the local group.
- Attach wires and labels to actual symbol pin coordinates on the KiCad grid.
- Minimize cross-net wire crossings; prevent overlapping symbols/text, clipped content,
  and ambiguous label placement.
- Split crowded designs into hierarchy instead of shrinking until unreadable.
- Use a complete title, revision, date, and project identity.

Before handover, render and actually inspect every sheet at page scale and at
readable circuit scale. Check the rules above, repair issues, then inspect fresh
renders of changed sheets. Record which sheets were reviewed and any remaining
issues. ERC, export success, geometry diagnostics, and connectivity parity do
not establish visual readability. This is an author review requirement, not an
automated certification or a replacement for the owner's engineering sign-off.

For a presentation-only edit, record native pin-net and explicit-NC equivalence,
preserved component values/MPNs/footprints and UUIDs, then review the final PDF at
both page and circuit scale. Record any deliberate style exceptions. This is
an authoring standard, not a reason to overwrite later manual owner edits.

Release enforces the shared `shared.schematic-readability` human decision for
every project, in addition to its local profile. The decision must describe the
actual sheet inspection; an automated export cannot fill it. See the
[shared enforcement map](ARCHITECTURE.md#rover-lessons-used-by-the-shared-pipeline).

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

## Editable PCB handover

- Preserve each footprint's schematic UUID path, including its hierarchical
  sheet path. Matching references and nets alone do not preserve F8 updates.
  A routine update must not propose adding footprints that already exist.
  Infer a missing link only on a staged copy after complete part and pin-net
  parity; a conflicting existing link needs explicit reconciliation.
- For ordinary pad entries, route to the actual pad connection anchor using
  native pad coordinates, including footprint rotation and side. A footprint's
  origin or body centre is not a routing target. Offset entries, shared switch
  pads, Kelvin branches and thermal connections can be intentional; inspect
  those against their circuit purpose instead of moving them automatically.
- Build continuous routes with exact shared endpoints and deliberate branch
  junctions. Avoid tiny overlaid patch segments, fully covered duplicates and
  visual-only joins. Rework the local route when needed; do not hide a gap with
  another sliver or globally delete owner copper. Use interactive routing and
  inspect any track-cleanup preview before committing it.
- Run native DRC after refilling zones and after every routing edit. Also review
  the routing-topology findings for covered straight tracks, segments shorter
  than both 0.25 mm and their width, and contacted pads whose track centreline
  misses the pad anchor by over 0.05 mm. These are drawing heuristics, not
  electrical-open, clearance or current-capacity rules. The audit does not
  cover via/arc/zone topology or custom/offset pad anchors.
- Save useful net-class routing defaults and width/via presets in the project's
  `.kicad_pro`; do not leave a power board with only a thin signal default.
  Net-class widths guide new routing; they do not resize existing segments or
  establish current ratings. Do not impose a trunk width on thin feedback,
  Kelvin-sense or indicator branches merely because they share a power net.
- Remove temporary authoring locks before handover unless a lock has a documented
  purpose. Intentional owner locks must not be removed automatically.
- Keep native tracks, vias, zones and footprints editable. A 3D body model is
  separate from the electrical footprint; report absent models without implying
  that the component has no pads or routing.
- Render review images from a current disposable CAD snapshot and bind their
  source/output hashes. Never put a fresh CAD hash on stale images. DRC, visual
  inspection and mechanical/thermal verification are separate results.

Every release also requires `shared.layout-handover`. Resolve topology and
editability findings by inspecting the actual circuit purpose; neither a clean
advisory report nor a netclass width establishes adequate load-current copper.

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
- Bind supplier corrections to the exact part, side and pad geometry. Check
  physical pin 1, polarity, model transforms and printed wire-pad labels against
  native numbered pad nets. Retail stock and local STEP models do not establish
  supplier allocation or placement. Follow [JLCPCB assembly](JLCPCB_ASSEMBLY.md).

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
