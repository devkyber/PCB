# Design Basis — TMS V3 (Thrust Measurement System)

Every key part's circuit names what it was learned from. Verdicts are `Match`,
`Deviate: <reason>`, or `Unresolved: <missing proof>`. A departure nobody wrote down is indistinguishable
from an oversight.

## Sources archived for this board

Everything cited below is **a file on this disk**, with its source URL and
content hash recorded in `evidence/index.yaml`. Nothing here is cited from memory.

### Reference designs in `evidence/files/`
| File | What it is | Trust tier |
|---|---|---|
| `U2__ADS1256__ADS1256IDBR_sbau090e.pdf` | TI **ADS1256EVM** User's Guide SBAU090E — manufacturer's own evaluation-module schematic | Tier 1 |
| `U3__ADS1220__ADS1220IPWR_sbau203.pdf` | TI **ADS1x20EVM** User's Guide SBAU203 — manufacturer's EVM schematic + BOM | Tier 1 |
| `card11a_rev4_web.pdf` | PJRC Teensy 4.1 pinout card rev4 | Tier 1 — for a module socket the vendor pinout card **is** the reference design; it is the only authority on which net belongs on which pin |
| `xbee3_hardware_ref.pdf` | Digi XBee 3 Hardware Reference | Tier 1 |

### Datasheets and pinout documents in `evidence/files/`
`ADS1256_ti.pdf` · `ADS1220_ti.pdf` · `card11a_rev4_web.pdf` ·
`card11b_rev4_web.pdf` (back side — the underside pads the front card omits) ·
`xbee3_hardware_ref.pdf` · `HF46F_hongfa_en.pdf` + `HF46F_C5274026.pdf` ·
`LM7805_C22467097.pdf` · `SS54_C22452.pdf` · `MMBT3904_C20526.pdf` ·
`1N4148WS_C57759.pdf` · `PESD5V0S2BT_C49338.pdf` · `7.68MHz_...pdf` ·
`XT60_XT60.pdf`

## Basis rows

| Ref | Part | Aspect | Ours | Reference says | Source | Verdict |
|---|---|---|---|---|---|---|
| U3.12 | ADS1220 | AVDD decoupling | C10 100nF 0402 at 2.0mm | "AVDD, AVSS ... and DVDD **must** be decoupled with at least a 0.1µF capacitor ... as close to the power-supply pins of the device as possible" | ADS1220_ti.pdf §9.3.3 | Match |
| U3.13 | ADS1220 | **DVDD decoupling** | **C11 100nF 0402 on +3V3 at the pin (fixed 2026-08-26)** | same clause — DVDD needs its own | ADS1220_ti.pdf §9.3.3 | Match. **Was absent.** C10 *and* C11 were both on AVDD (pin 12) and nothing decoupled DVDD; the gap had been logged as a rule-2.2 *distance* deviation, which explained away the symptom and stopped anyone looking for the cause. |
| U3 | ADS1220 | package decoupling geometry | both caps 0402, not 0603 | — | measured | Deviate from house habit: AVDD/DVDD are adjacent 0.65mm-pitch pins; two 0603s cannot both sit inside 2mm of their own pin, two 0402s can. Smaller package is also lower ESL. |
| U3 | ADS1220 | reference | internal 2.048V intended | EVM exposes both internal and external | sbau203.pdf | Deviate: internal reference. Suitability needs the pressure-channel error budget; U2's external reference is unresolved, not established by this choice. |
| U2 | ADS1256 | VREF | VREF_P/VREF_N connect only U2 and C7 in the accepted netmap; no reference source is present | EVM has an external reference source and buffer | evidence/files/U2__ADS1256__ADS1256IDBR_sbau090e.pdf p.40 Fig 41; netmap.json | Unresolved: the former external-reference Match claim was unsupported. Owner must specify and review the reference circuit; drawing parity does not fix it. |
| U2.3/U2.16 | ADS1256 | reference / DVDD bypass distance | Historical 2.4–3.0mm claim; remeasurement required at the correctly identified pads | VREFN is pin 3, DVDD is pin 16; pin 15 is RESET | evidence/files/ADS1256_ti.pdf p.5 Terminal Functions | Unresolved: DEVIATIONS.md's existing U2.15 row misidentifies RESET as DVDD. It does not waive U2.16, and no waiver is transferred by this correction. |
| U2 | ADS1256 | RESET / SYNCPDWN | tied to DVDD | must not float | ADS1256_ti.pdf | Match — was floating in Rev D |
| Y1 | 7.68MHz | **crystal load caps** | **C8/C9 = 33pF (fixed 2026-08-26)** | every 7.68MHz HC-49S-SMD part in this footprint specifies **C_L = 20pF** | `7.68MHz_...pdf` (Huiyuan C5265772) | Match. **Was 22pF**, giving `(22·22)/44 + C_stray ≈ 15pF` — under-loaded, so the crystal ran fast. The crystal **is** the ADS1256 conversion clock, so that was a sample-rate error in every thrust and pressure reading: a board that works and quietly produces wrong numbers. |
| J7, J8 | Teensy 4.1 socket | pin map | rebuilt from the vendor card | PJRC card rev4 front + back | `card11a/b_rev4_web.pdf` | Match. Rev E had **invented** the pin assignments, putting +5V on the Teensy's GND pin — a dead short of the 5V rail on first power-up. |
| J9 | XBee 3 socket | pin map | rebuilt from the vendor manual | Digi 90001543 p.36, p.45–46 | `xbee3_hardware_ref.pdf` | Match. Rev E tied the XBee's UART output to ground and left its ground pin floating. |
| K1 | HF46F-G/5-HS1T | relay pinout | coil 1/6, COM 2, NO 3 | read from the wiring diagram, not the symbol | `HF46F_hongfa_en.pdf` | Match |
| D1 | 1N4148WS | coil flyback | across K1 coil | standard inductive-kickback clamp; MMBT3904 Vceo 40V | `1N4148WS_C57759.pdf`, `MMBT3904_C20526.pdf` | Match |
| D3 | SS54 | reverse-polarity protection | series in VBAT | 40V 5A Schottky | `SS54_C22452.pdf` | Match |
| U4 | LM7805 | 5V regulation | linear, TO-263 | — | `LM7805_C22467097.pdf` | Deviate: **see REQUIREMENTS.md [OWNER]** — dropping 16.8V to 5V dissipates 11.8V × I; at 200mA that is 2.4W in a TO-263. Thermal budget unverified. |
| D2 | PESD5V0S2BT | ADC input TVS | on the analog inputs | — | `PESD5V0S2BT_C49338.pdf` | Match |
| **J1, J2** | **AMASS XT30PW-F** (C2913282) | **battery connectors** | **real XT30PW female, board-mount (fitted 2026-08-26)** | 15A, DC500V | LCSC C2913282 | Match to the owner's spec. Both were `PinHeader_1x02_P2.54mm` — a ~3A friction-fit pin — while their Value claimed XT60. The PDR §1 register said XT60U-F for both; **XT30PW supersedes it**: 15A is ample (electronics under 1A, igniter pulse a few amps) and the XT30 is far smaller on a board that had no room. |
| **J6** | **AMASS XT60-F** (C98734) | **igniter output** | **real XT60 female (fitted 2026-08-26)** | 30A continuous / 60A instantaneous | `XT60_XT60.pdf` | Match. XT60 is kept where the current actually is. The igniter is a **nichrome bridgewire across a KNSB grain**, not a commercial e-match: nichrome is a low resistance (order 1–3 Ω), so a 2S pack drives several amps into it, and unlike an e-match it is a deliberate short. XT60 carries that with margin and latches — this is the one lead that must not fall off. |
| **J5** | **Ningbo Kangnex WJ500V-5.08-2P** (C8465) | **ARM switch** | 5.08mm screw terminal, 18A | PDR §7: "the PCB provides a 2-pin screw terminal for the switch wires" | PDR §7 | Match — the PDR specifies a screw terminal here, deliberately, because the ARM switch is external and user-wired. Kept beside K1 so `IGN_ARM_RET` is short. |
| **J3** | **JST B5B-XH-A** (C157991) | **load cell** | 1x05 polarised latching, 3A | PDR §2: 4-wire bridge + shield | PDR §2 signal chain | Match to the owner's "Molex-like" requirement. **JST XH rather than Molex KK**: same class (polarised, latching, crimp wire-to-board) but KK has *no* LCSC stock while XH has 36k, and KiCad ships the exact B5B-XH-A land pattern. Polarisation matters here — a load-cell bridge plugged in reversed reads backwards. |
| **J4** | **JST B3B-XH-A** (C144394) | **pressure sensor** | 1x03 polarised latching | PDR §4: 3-wire 0–5V sensor on VBAT | PDR §4 | Match |
| **J7, J8** | **1x24 female socket** (C2883741) | **Teensy 4.1** | **female sockets — the Teensy plugs in and lifts out** | PDR §1 register: "Module (socket)" | PDR §1 | Match. Previously `PinHeader` (male pins), which would have required soldering the Teensy down permanently, contradicting the register's own "socket". |
| **J9** | 1x10 female 2.00mm ×2 (C2925557) | **XBee 3 socket** | two rows of ten at 2.00mm; hand-authored body/courtyard underbounds the pictured module | Digi 90001543 mechanical pp.36–37, 45; antenna guidance pp.52–56 | `evidence/files/xbee3_hardware_ref.pdf` | Unresolved: nominal pad order/pitch is consistent, but body envelope, exact module/antenna/socket and drill/physical fit require review. The historical two-socket BOM quantity is not fit approval; see REFERENCE_REVIEW. |

## Note on the XT60 rating

The "60" is the **instantaneous** figure. Continuous rating is **30 A**
(`XT60_XT60.pdf`). Nothing on this board approaches either number — the
electronics draw is under an amp and the igniter pulse is a few amps. The
XT60 is here on the igniter output for **retention and current margin**; it
latches and matches the accepted output-harness decision. Sizing the copper
to the connector's rating instead of the actual current would be the wrong
lesson to take from this. **[OWNER]** the actual nichrome cold resistance and
firing pulse current are still unspecified, and trace width on the ignition
path depends on them.

## What this comparison caught

1. **DVDD with no decoupling capacitor at all**, hidden behind a
   distance-deviation that described the symptom.
2. **Crystal load caps 22pF against a 20pF-load crystal** — silent
   measurement error on the board's entire purpose.
3. **Four connectors on the battery and igniter path** footprinted as
   2.54mm headers while claiming XT60s and screw terminals.
4. Earlier revisions: **invented Teensy and XBee pin maps** (+5V onto a GND
   pin), fixed by rebuilding both from the vendor documents now archived here.

## Assisted layout proposal — 2026-09-20

The unapproved `layout-intent.yaml` uses native accepted 100x100mm outline,
exact footprint IDs and pad nets, SHA-256
`7012096ec8281fa6477880bffe165272c3ce6ce9eb57a00020c50d0759ec858e`.
Shared bottom-left/y-up conversion uses native outline (10,100)-(110,200).
Legacy generator design y increases with native y despite contradictory
comments: its (4.5,4.5) H1 becomes (4.5,95.5), and Teensy rows become
J7=(26,18), J8=(26,33.24), both rotation 90. Their 15.24mm separation,
connectors J1–9, holes and PCB-only FID1–3 remain fixed existing mechanics.
U2/U3/U4 and L1 retain current anchors as provisional functional seeds.
Keeping those anchors neither approves socket fit nor freezes every passive.

Proposed controller/interface y0–38, analog x0–50/y38–80, power x0–50/y80–100,
telemetry x50–100/y38–70 and relay/status x50–100/y70–100 regions follow
the existing circuit grouping. Movable passives, relay/driver, LEDs and probe
points remain search candidates. Pad-distance proposals use the house bypass
2mm target (C1→U2.1, C5/C6→actual DVDD U2.16, C10→U3.12, C11→U3.13);
additional bypass C2 uses 3mm, bulk C3/C4/C12 and regulator caps C15/C16
use 5mm. C7→U2.4 uses 3mm while VREF source remains absent.
Y1→U2.19 uses 5mm; C8/C9→Y1.1/.2 use 3mm. C13→J7.3 and C14→J9.1
use proposed 5mm module bypass limits instead of blindly repeating generator
U3 associations. C17→L1.2 uses 5mm. These choices require physical routing
review; no historical misidentified U2.15 waiver transfers to pin16.

TI ADS1256EVM layout separation/return-plane views and TI/ProtoCentral ADS1220
bypass observations inform grouping. ProtoCentral's R6=0R VCC/+5V bridge
and R5=0R GND/AGND bridge preclude assuming isolation from header labels;
its 47-ohm resistors differ from accepted TMS 33-ohm SPI elements. Four
enabled-layer explicit-copper views prove neither filled returns nor stackup/
two-layer suitability. No source positions are copied; ADS1256 open-hardware
coverage and per-part reference gaps remain explicit.

Native named-net rules are retained: Default width/clearance 0.254/0.2mm,
vias 0.6/0.3mm; Power +3V3/+5V/+5V_FILT 0.5/0.2mm, vias 0.8/0.4mm;
HighCurrent VBAT/VBAT_PROT/IGN_BATT+/IGN_ARM_RET/IGN_OUT/IGN_GND 1/0.3mm,
vias 1/0.5mm. These historical dimensions are not verified current capacity.
Only GND B.Cu zone with 0.3mm clearance is requested; generated connection/
fill defaults are proposals, not native-zone equivalence. IGN_GND remains
separate and no ignition-current/thermal model is run without owner inputs.

J9 remains blocked by unsupported hand-authored provenance and an undersized
body/courtyard relative to the Digi through-hole drawing. See the exact
dimensions and variant-dependent p55/p56 antenna guidance in REFERENCE_REVIEW.
A source-backed proposed envelope correction, selected module/socket, drill fit
and physical mating review are prerequisites; no accepted footprint is repaired
or relabeled verified. Y1/C10/C11's six non-square pad-angle differences remain
preserved embedded geometry and explicit review findings. Actual PCB C8/C9
still say 22pF despite schematic/earlier 33pF prose; C4 actually sits on +5V,
not generator-described DVDD. Resolve these source disagreements before
approval. Igniter cold resistance/current/duration, isolated return decision,
LM7805 thermal budget, external VREF source and reset/brownout behavior remain
human decisions. No acceptance, physical signoff or release occurred.
