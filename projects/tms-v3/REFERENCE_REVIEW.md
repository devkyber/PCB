# TMS V3 reference and transcription review

Review date: 2026-09-17. Status: partial research and source-preserving intent;
human electrical, physical, visual and release review remain pending. This
record does not accept a draft or change any owner decision. The accepted
schematic and PCB, not historical generator code, remain authoritative.

## Exact accepted sources

| File | SHA-256 at transcription |
|---|---|
| `tms-v3.kicad_sch` | `1a1ceceb4099194ebd94a21939f1b2289597d8af0bbbfa2f488974e3a946a2fa` |
| `tms-v3.kicad_pcb` | `7012096ec8281fa6477880bffe165272c3ce6ce9eb57a00020c50d0759ec858e` |
| `netmap.json` | `acf49a05e4237fe990890ff6b59d48e0c208c4a0404f645e9f7f524590c79358` |

The intent preserves 66 physical symbols and three existing `#FLG` assertions,
their accepted values, library identifiers, footprints and pin assignments.
Generated `#PWR` symbols are represented by standard power connections instead.
The empty `#FLG` footprint is represented as `~`. All 60 declared NC pins were
matched against actual accepted schematic NC-marker coordinates with the
existing KiCad pin-position and coordinate helpers. KiCad's extracted physical
netlist matched the saved baseline. A pin-map evidence ID identifies the
archived source; it is not a declaration that every physical orientation or
electrical characteristic has been reviewed.

There are six functional child sheets, in the required order, plus the empty
overview required by the hierarchy renderer. Module sockets remain with the
controller and telemetry; J1-J6, TP1-TP9 and H1-H4 are on the external sheet.
D2 stays with the load-cell input because those are its actual connected nets.
L1/C17 are grouped with excitation power. C13/C14 are grouped with module
supply bypass by their accepted supply nets; local placement and association
with the physical module pins still need human review. Only `+5V`, `+3V3` and
`GND` use global power style. Other cross-sheet nets, including `VBAT` and
`+5V_FILT`, use explicit hierarchical endpoints. `IGN_GND` remains a separate
net and is never implicitly bonded to electronics ground.

## Searches actually executed

These exact live queries were executed on 2026-09-17. Search snippets alone
were used only for discovery; selected engineering evidence is identified
separately below.

| Query | Outcome |
|---|---|
| `site.ti.com ADS1256EVM schematic PCB layout SBAU090` | TI SBAU090E, already archived, provides both schematic and PCB layer views. A TI-hosted older schematic also appeared; it was not substituted for the archived Rev E guide. |
| `ADS1256 open hardware schematic PCB KiCad github` | Mostly firmware and unrelated hardware results. No exact open-hardware schematic/PCB pair was established by this query. |
| `site.ti.com ADS1220EVM schematic PCB layout SBAU203` | TI SBAU203 and TI support discussion about EVM Gerbers. The archived guide includes a schematic, but no reviewed EVM copper layout. |
| `ADS1220 open hardware schematic PCB github` | A fork of ProtoCentral and other ADC projects appeared. Followed the original manufacturer's repository below. |
| `ADS1256 open source hardware schematic pcb GitHub ADS1256 board` | Waveshare High-Precision AD/DA Board surfaced as a vendor schematic candidate; a matching native PCB and open-hardware license were not established. Firmware-only libraries were not treated as hardware references. |
| `site.github.com Protocentral ADS1220 hardware schematic brd` | Original `Protocentral/Protocentral_ADS1220` repository found; pinned archive contains a matching Eagle schematic and board. |

The web reader could not open the ProtoCentral hardware directory, Waveshare
wiki or TI support thread directly. A read-only GitHub API tree request
successfully resolved ProtoCentral master to commit
`3db37824948f75e60ca93cc8aacef5c5abad9a48`; raw files at that immutable commit
were then archived. TI's SBAU203 direct web-open also failed, but the existing
local archive was intact and readable. These access limitations do not count
as completed visual review.

Discovery links: [ProtoCentral repository](https://github.com/Protocentral/Protocentral_ADS1220),
[Waveshare board](https://www.waveshare.com/wiki/High-Precision_AD/DA_Board),
[TI ADS1220 Gerber discussion](https://e2e.ti.com/support/data-converters-group/data-converters/f/data-converters-forum/996897/ads1220evm-msp430-sample-code-and-altium-files-of-ads1220evm).
The repository currently states CERN-OHL-P v2 for hardware; exact licensing of
the historical 2014 hardware files should be checked before redistribution.

## Archived and inspected sources

All 16 pre-existing evidence records passed byte/hash verification. The four
new ProtoCentral records below preserve their downloaded bytes, immutable
source URL, retrieval date and commit in `evidence/index.yaml`. Eagle members
were extracted verbatim; their source URLs use the pinned ZIP URL followed by
the exact member path as a fragment. They are supplementary references for
U3 and do not replace the TI datasheet pin-map citation.

| Source | Exact evidence identity | Scope completed |
|---|---|---|
| TI ADS1256EVM guide SBAU090E, November 2018 | `sha256:1d5a17540e48f0739cb56687babc7b62d1e2d5058bcbd7ce4cba4268a51385df` | Archived; visually inspected page 39, Figures 37-40, and page 40, Figure 41. |
| TI ADS1x20EVM guide SBAU203, July 2013 | `sha256:483b3351badfa960fcc9bbea1fab18e3ccfd21e0cb282c192950d26452feafc4` | Archived; visually inspected PDF page 18 schematic, title-block Rev A, SVN 28, dated 2013-06-06. EVM copper review incomplete. |
| ProtoCentral native ZIP, pinned commit above | `sha256:83c75b67b2f7d4c6f46f65f6b7bfc7647ddf0220fb10479eeedf8d0f6f659a5e` | Archived; contains two Eagle 6.4 XML members. |
| ProtoCentral `pc_ads1220_brk/pc_ads1220_brk.sch` | `sha256:06809c8c1335a3581d08cc29f73f9cbd5d76d59f864283c90997d73321750691` | Archived; exact pin/pad pair comparison performed. |
| ProtoCentral `pc_ads1220_brk/pc_ads1220_brk.brd` | `sha256:30c7978775749e9178d67311229ada682460f87f777642532a6a854d5d07b790` | Archived; XML metadata and later limited four-layer explicit-copper views inspected (below); filled return-path and TMS applicability review remain pending. |
| ProtoCentral schematic PDF, title-block 2014-07-18 | `sha256:891a4b71a749d574a93fa67d03564ae00f6d13abf8c555b03d877303707cfa3b` | Archived; one-page circuit visually inspected. PDF-to-native revision identity not independently proven. |

TI source URLs are recorded in the existing index. The new archive source is
[the commit-pinned ZIP](https://raw.githubusercontent.com/Protocentral/Protocentral_ADS1220/3db37824948f75e60ca93cc8aacef5c5abad9a48/hardware/pc_ads1220_brk.zip),
with [the PDF beside it](https://raw.githubusercontent.com/Protocentral/Protocentral_ADS1220/3db37824948f75e60ca93cc8aacef5c5abad9a48/hardware/pc_ads1220_brk.pdf).

The native Eagle comparison found 48 compared pad assignments and zero
pin/pad/package/explicit-value mismatches. Its board metadata reports 91
routed wires, 21 vias and GND/AGND polygons on copper layers 1 and 16. The
stored design-rule layer setup is `(1*2*15*16)`, so visible outer-layer copper
metadata alone must not be presented as proof of a two-layer fabrication
stackup. This check does not establish completed routing, DRC, manufacturability
or applicability to TMS.

## Comparison findings and preserved questions

- ADS1256: TI Figure 41 contains an external reference source and buffer;
  Figure 39 shows a broad return plane, while the top layer separates analog
  entry and digital headers around the ADC. These are useful review examples,
  not evidence that TMS meets its decoupling-distance deviations. In the
  accepted TMS netmap, `VREF_P` and `VREF_N` each connect only U2 and C7: an
  active reference source is absent. The DESIGN_BASIS external-reference row
  was corrected from `Match` to `Unresolved` in the 2026-09-17 documentation
  follow-up. Reference-source selection still needs an owner decision. The
  source-preserving intent deliberately leaves these nets unchanged.
- U2 pin identity: accepted symbol and the inspected TI schematic identify
  pin 15 as RESET and pin 16 as DVDD; TI's archived datasheet p.5 independently
  confirms this. DESIGN_BASIS was corrected in the 2026-09-17 follow-up and
  DEVIATIONS now warns about the historical U2.15 misidentification. The old
  waiver row remains unchanged and does not cover U2.16. Bypass distance must
  be remeasured before proposing any replacement waiver; none was granted.
- ADS1220: TI's schematic shows independent AVDD/DVDD bypass. TMS has C10 on
  +5V and C11 on +3V3; the archived ADS1220 datasheet page 64, section 9.3.3,
  calls for bypass at each relevant supply. This is a connectivity comparison,
  not validation of placement or noise performance. TMS's single pressure
  input and internal-reference configuration differ from the multipurpose EVM.
- ProtoCentral: the schematic labels separate AVDD/DVDD entries with 100nF
  bypass, but source R6=0R bridges VCC/+5V and R5=0R bridges GND/AGND.
  Header labels do not establish isolation; assembly/DNP state is unverified.
  The reference also has 47-ohm SPI series elements.
  TMS retains its accepted 33-ohm series resistors and shared electronics GND.
  Do not copy the breakout's supply wiring into the Teensy interface without
  checking the actual voltage domains against the TI datasheet.
- D3's accepted symbol names pin 1 A and pin 2 K; its recorded VBAT-to-
  VBAT_PROT connection is consistent with those labels. This resolves the
  superficial pin-number ambiguity only; package orientation remains a
  physical review item.
- Requirements, PDR and SIGNOFF contain historical statements superseded by
  accepted XT30/XT60 connector footprints and the 33pF C8/C9 values. These
  accepted choices are retained. SIGNOFF remains unchecked; stale wording
  must not be used to invent approval or silently undo owner choices.

The igniter cold resistance/current, ignition trace suitability, isolated
return intent, LM7805 thermal budget, module/socket orientation, physical
connector fit and reset/brownout behavior remain human-owned open items.
No reference or parity result here establishes ignition safety, successful
bench validation or readiness for fabrication.

## Remaining coverage and next review

ADS1256 open-hardware PCB coverage remains unresolved. ADS1220 now has an
archived open-hardware native pair and limited explicit-copper visualization
(below), but comparison against actual TMS copper remains pending. Search, archive,
inspection and engineering comparison are separate statuses.

No new manufacturer/open-hardware schematic-and-PCB searches were performed
for LM7805, HF46F, driver/protection parts, Teensy 4.1, XBee 3, the exact
crystal, connectors or passive selections in this pass. Existing indexed
datasheets and module cards remain available; their presence does not imply
complete reference-PCB coverage. Exact connector and generic-part pin-map
citations remain explicitly unverified in the intent. This report is not a
claim of complete per-part research.

Intent model validation and transcription checks pass. The accepted files
have not been changed.

### Latest hierarchical preview

Latest checked draft: `20260916T181255Z-schematic-2b264620`, with PDF
`.pcb-copilot/drafts/20260916T181255Z-schematic-2b264620/preview.pdf`.
All seven pages were visually inspected. The draft command exits zero with
no blocking findings, zero ERC errors, 38 ERC pin-type warnings, one
sheet-qualified-net-name review and 58 unresolved pin-map evidence reviews.
Strict physical net-group comparison passes; the accepted schematic, PCB and
netmap hashes still match the table above. No acceptance was performed.

The final grouping keeps C1-C6 with ADS1256, places the sparse C7 reference
lane between input protection and ADS1256, and groups the existing +3V3
`#FLG02` assertion with the controller supply. These are presentational
changes only; the reference-source gap remains explicit. Measured row spacing
resolves tall-symbol collisions, shorter sheet titles fit, outward label
justification resolves text over connector pins, and D2 fields now clear its
body and the neighboring ADC labels. The label-direction regression was
verified with real KiCad PDF text rectangles on left/right connector pins,
ordinary/hierarchical labels, and netlist roundtrip connectivity.

The follow-up local router protects generated power Value text and searches
bounded multi-bend paths when simple lanes are blocked. The relay-control
local route clears those keepouts without changing its electrical grouping.
All seven pages remain pixel-identical to the previously inspected previews;
the findings below persist.

Remaining visual limitations: J8's ground glyph near pin 1 intrudes into the
ADS1220_CS label on pin 2, and its +3V3 arrow near pin 15 crowds SPI0_MISO on
pin 14. Dense mixed power and signal annotation still needs visual refinement.
The new diagnostic flags both contacts, plus J3.2's ground triangle overlapping
`LC_SIG_P` on the external-connectors page. The assistant confirmed that third
contact in an enlarged page-7 PDF view. These three `power-text-collision`
findings are review advisories, not automatic repairs or electrical blockers.
The A1 overview has excessive empty space, although corrected labels are now
separate from sheet-pin text. These limitations and the unresolved engineering
items above remain human-review findings. A successful structural command is
not visual approval, acceptance, bench validation or release approval.

## ADS1220 limited copper inspection — 2026-09-20

The controller inspected all four enabled copper-layer exports from the pinned
ProtoCentral source, SHA-256
`30c7978775749e9178d67311229ada682460f87f777642532a6a854d5d07b790`, unchanged.
KiCad 10.0.6 Eagle import required no graphics omissions or sanitization.
SaveBoard(..., True) and fresh-process reload preserved 12 footprint
anchors/rotations, 48 pads (identity/net/position/size/rotation/drill/shape/layer
mask), 112 tracks/vias (91 wires + 21 vias, identity/net/endpoints/width/layer)
and four zone records by count. Zone outlines/fills were not compared; this
checks the derived saved inventory against the import, not all Eagle semantics.
The disposable diagnostic and exports exited zero without warnings.

Ignored outputs are `.pcb-copilot/reference-review/ads1220-20260920/`:
`reference-explicit-copper.kicad_pcb` and
`copper/reference-explicit-copper-{F_Cu,B_Cu,In1_Cu,In2_Cu}.svg`/PNG.
All four 1600px-wide views use top view with Edge.Cuts/F.SilkS; bottom is not
mirrored. No zone refill/check-zones occurred. Cropping clips boundary silk,
so no conclusion relies on missing text.

U$1 is central, SV1 digital header left and SV3 analog header right. R1/R2/R3
47-ohm SPI elements lie on the digital side; pad 2 connects to ADC pins 2/1/16
respectively. C1/C2=100nF lie above the ADC; source contacts tie U$1.13/C1.1
to VCC and U$1.12/C2.1 to +5V, with GND/AGND returns. Return vias surround
ADC/header/power areas. Top carries most fanout; bottom has crossovers and
portions of input/reference/supply routes. Inner views show through-hole pads
and vias, no explicit routed wires. Layer-1/16 wire counts do not prove a
two-layer fabricated stackup: four layers are configured. GND/AGND polygons
exist on 1/16, but newly filled planes are not shown. R6.2=VCC, R6.1=+5V;
R5 bridges GND/AGND. Values are source entries, not verified population.
No DRC, filled-plane equivalence, return-current quality, bypass-distance
conformance or actual TMS suitability is established.

## J9 source geometry and remaining blocker — 2026-09-20

Read-only inspection of the hand-authored footprint and Digi 90001543 PDF
pages 36–37, 45 and 52–56 used indexed source
`sha256:a02aee173feaec9b7504a1794d94e579ae62ca01ae868217befb62b1638efcfa`.
Index revision is null and the exact module/antenna/socket is unspecified.
P45 top-view numbering agrees: 1 top-left, 10 bottom-left, 11 bottom-right,
20 top-right. Nominal 2mm pitch and 22mm row spacing agree approximately with
rounded 0.079in and twice 0.433in; this does not prove socket drill/fit tolerances.

P36 through-hole U.FL drawing implies body Y approximately -7.7216 to
19.9136mm relative to pin 1 in library x-right/y-down coordinates (body-end
ordinates +/-0.544in, first pin +0.240in). P25 independently gives 27.61mm
body length. Current Fab/silk Y -6.53..19.2 is only 25.73mm; courtyard
-7.03..19.7 is 26.73mm and underbounds even the pictured body by approximately
0.69mm at the nose and 0.21mm opposite. X body 24.4mm approximately matches
0.960in/24.384mm. P37 RPSMA hardware extends farther for that variant.

P55 is the through-hole embedded-antenna all-layer clearance/edge-placement
view; P53/P54 concern other packages. P56 note 4 excludes external RF
connectors from that preceding guidance. No keepout can be adopted until the
actual antenna/module variant is selected. P52 VCC pin 1 bypass/ripple/brownout
guidance still needs circuit review. Socket contact/body/drill drawing,
enclosure clearance and physical mating are unresolved; a module pin drawing
does not validate a 0.9mm board drill. The geometry/provenance blocker is not
cleared by recognizing the custom description or relabeling it imported.
A source-backed corrected proposed envelope requires review before any repair
of the accepted footprint/board. No such repair or approval occurred here.

## Accepted geometry discrepancies for layout migration

Read-only native inventory also finds C8/C9 PCB Value fields still 22pF while
the schematic and earlier basis describe 33pF; C4 actually connects +5V/GND,
despite generator comments placing it at DVDD. These are unresolved source
disagreements, not authorization to rewrite accepted CAD. Y1/C10/C11 parent
angles are 90 degrees while both pads in each are native 0 degrees; library
local-zero pads would imply 90 degrees. Native Y1 pads are 5.5x1.4mm and cap
pads 0.56x0.62mm, making orientation material. Current drafting preserves
embedded pad geometry and emits instance-difference warnings. Footprint-ID
and net parity do not establish geometric or value equivalence.
