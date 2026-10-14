# TMS A0 reference review

The 2026-10-14 component audit in docs/design/COMPONENT_VERIFICATION.md
supersedes any inference that archived sources alone establish completeness.
It compares every current physical reference and the required support groups,
including Digi revision W's 47 pF recommendation versus older online 8.2 pF
text, and TI's recommended floating unused ADS1220 AIN3 connection.

Current source comparisons and limitations are in docs/design/CAPTURE.md.
Exact bytes, hashes, URLs and current references are in evidence/index.yaml.

- TI TPS54302 Fig7-1 inspected:retain passive/hot-loop topology and49.9 Ohm/75 pF
  feed-forward network; use13.6k lower feedback resistor for nominal 4.98 V.
- ADS1256 terminal table/Figs25-26 inspected:separate supply bypasses, input
  buffers and an actual external buffered reference source.
- ADS1220 PW table and archived EVM consulted:separate AVDD/DVDD bypasses,
  selected reference/input range and explicit unused pins.
- PJRC front/back cards establish socket signals; VIN/VUSB handling checked.
- Digi RP-SMA drawing/pin tables match owner XB3-24AST-J selection.
- Both Hongfa drawings inspected:5 A resistive/30 VDC, not historical7 A.
  Local numbering is explicitly documented because source drawing is unnumbered.
- AOS AO3400A, Nexperia BAV199, TI TPD2E2U06DCK and Kingbright indicators were
  freshly archived. Pin/pad inventories are checked independently of ERC.
- CAS BCA and Sensata IPSU sources freshly archived. CAS recommends 10 V;
  retained 5 V excitation needs accuracy/noise proof. IPSU sheet does not state
  a minimum output-load resistance; do not inherit an unsupported load limit.

Ferrite remains a passive sourcing candidate whose detailed specification needs
an archive. WJ500V supplier CAD was freshly imported; old datasheet URLs returned
HTML, so manufacturer drawing/fit remain open. No HTML response is a datasheet.
Unused historical research has empty component_refs. Source bytes are preserved.
