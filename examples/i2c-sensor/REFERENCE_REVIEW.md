# Author source comparison

Codex author comparison, 2026-10-29. This records source interpretation, not owner sign-off or physical qualification.

- Microchip DS20005095B Table 3-1 supplies the selected MSOP pin map; p40-42 shows the MSOP-8 3 x 3 mm nominal body, 0.65 mm pitch and 4.9 mm overall lead width. The DFN exposed pad is absent in this variant.
- Microchip DS50002480A p47, U5/C7, supplies a real manufacturer demonstration circuit with I2C, ALERT, local 100 nF bypass and grounded address inputs. Its U5 is DFN; no package equivalence is inferred. The new board uses the verified MSOP and adds three resistively defaulted high-select address headers.
- DS20005095B sections 3.3/3.5/6.1 and reset defaults support open-drain ALERT with an external pullup, normal 0x18..0x1F addressing, local ceramic bypass, and ALERT initially disabled. Firmware and actual bus timing require bench review.
- Exact Yageo/KEMET part sheets and both Wuerth drawings were archived from manufacturer endpoints. The local official generic package choices and pad functions are compared and disclosed in DESIGN_BASIS.md and libs/PROVENANCE.json, including the generic MSOP land-size difference.
- The original installed symbol library has an inherited stale datasheet URL and a generic output electrical type on ALERT. Local derivative metadata records the corrected datasheet URL and open_collector pin type. Pin numbering and functional arrangement are preserved.

No manufacturer endorsement, supplier assembly rotation, thermal performance, mating fit or measured accuracy is asserted.
