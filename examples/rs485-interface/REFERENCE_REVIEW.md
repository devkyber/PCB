# A1 reference comparison

Author comparison: Codex, 2026-10-29. This is not a human release decision.

- **TI SLLSEY3E p5:** compared all eight SOIC pins and electrical functions to
  the local resolved symbol, schematic instance and native footprint pad numbers.
- **TI Figure 31, p22:** adopted the half-duplex A/B bus and termination only at
  physical cable ends. JP1 makes this board's termination removable.
- **TI p19 section 9.4.1, p24 section 10.2.1.4:** adopted independent DE/nRE,
  documented default pulls and internal receiver failsafe; no external bus bias.
- **TI p28 section 11; p29 section 12.1/Figure 40:** adopted 100 nF local bypass,
  close pad placement, enable pull-downs within the 1-10 kOhm recommendation and
  paired ground return vias. Added a separately justified 1 uF entry reservoir.
- **TI SLLU173C Figure 3-1, p3:** the generic half-duplex EVM linked by TI's
  THVD1450 product page uses the compatible eight-pin RO/nRE/DE/DI/GND/A/B/VCC
  interface, 100 nF local bypass, 1 uF reservoir and 120 Ohm termination. Its
  schematic names SN65HVD7x; this is a generic interface comparison, not an exact
  THVD1450 implementation or a test result for this board. The extra measurement
  jumpers, common-mode stimulus and optional bias are not adopted. Exact-part
  THVD1450 limits and internal failsafe behavior take priority.
- **TI Figures 37/38:** these are surge-protection examples, not the circuit
  implemented here. No equivalent surge/TVS or industrial qualification is claimed.
- **Vishay 20035:** decoded exact selected values/tolerance/package, compared
  dimensional tables to the generic 0805/1206 lands. R3's simple dissipation
  calculation excludes external fault voltages and temperature qualification.
- **Yageo exact-part sheets:** checked both MPN strings, nominal capacitance,
  tolerance, dielectric, rating and 0805 dimensions. Effective biased capacitance
  and generic 3D-body height agreement remain unqualified.
- **Samtec TSW/HTSW and SNT catalogs:** decoded position count, lead style -07,
  G plating and S row code; selected HTSW's compatible assembly material.
  Checked shunt mating family, 2.54 mm pitch, post size and insertion depth.

All actual primary source identities and complete hashes are in
[the index](evidence/index.yaml). Native ERC/DRC, pin-net parity and library
receipt checks establish only their stated software scopes. Actual pin-1,
connector mating/hole tolerance, cable polarity, plane return paths, signal
quality, thermal and bench operation need separate engineering review.
