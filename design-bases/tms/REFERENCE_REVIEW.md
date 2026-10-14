# Retained TMS research

Exact source bytes, URLs, retrieval dates, roles and hashes are preserved in
evidence/index.yaml. This is inherited research, not a live revision or sourcing
check. Reassign old component_refs to new designators without changing source bytes.

| Subject | Local source | Use |
| --- | --- | --- |
| ADS1256 | ADS1256_ti.pdf; U2__ADS1256__ADS1256IDBR_sbau090e.pdf | Pin functions, reference, clock, supply limits, TI EVM |
| ADS1220 | ADS1220_ti.pdf; U3__ADS1220__ADS1220IPWR_sbau203.pdf | Reference/input range, bypass and TI EVM |
| ADS1220 practice | Pinned ProtoCentral Eagle pair, ZIP and PDF | Exact values/nets; 0-ohm rail/return bridges do not establish isolation |
| Teensy | card11a_rev4_web.pdf and card11b_rev4_web.pdf | Front/back numbered pins and underside connections |
| XBee | xbee3_hardware_ref.pdf | Pin map, module/antenna-specific envelope and RF guidance |
| Relay | HF46F_hongfa_en.pdf and HF46F_C5274026.pdf | Variant-specific coil/contact diagram and limits |
| Other candidates | Indexed regulator, diode, transistor, TVS, crystal and connector PDFs | Verify against the actual newly selected package/MPN |

Datasheet authority precedes manufacturer EVM, proven hardware and teaching
rationale. Inspect exact archived native CAD or PDF pages for pin/value facts;
pcb-copilot research --extract supports source extraction. Identity hashes do
not prove interpretation. Reference selection, pressure scaling, power budgets,
clock and physical module/connector fit remain unresolved.
