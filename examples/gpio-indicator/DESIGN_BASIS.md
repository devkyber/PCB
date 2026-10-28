# GPIO indicator design basis

Revision A1, 2026-10-29. Fresh educational design; no owner board or frozen fixture was used.

The topology is four independent visible series paths: GPIO -> resistor -> LED -> GND. The exact Kingbright WP710A10ID datasheet supplies polarity, lead dimensions and electrical/optical limits. The exact Yageo MFR series ordering table supplies the selected MFR-25FBF52-1K1 identity: 1/4 W, 1%, bulk, 100 ppm/degC, axial 52.4 mm packaging and 1.1 kOhm. The exact Wuerth 61300511121 drawing supplies the five-position 2.54 mm header dimensions.

The initially suggested 1 kOhm was increased to 1.1 kOhm because a 1 kOhm 1% resistor can be 990 Ohm: 3.3 / 990 = 3.333 mA when no LED Vf credit is taken. The chosen initial-tolerance lower resistance is 1089 Ohm. I <= 3.3 / 1089 = 3.031 mA; resistor dissipation <= 3.3^2 / 1089 = 10.0 mW. The manufacturer's 250 mW room-temperature rating is well above this calculated bound. These calculations omit aging/temperature drift and qualify only the stated bench assumptions.

Kingbright specifies typical 1.9 V / maximum 2.3 V at 10 mA, not a guaranteed brightness or Vf at this design's lower current. No guaranteed LED current or brightness is inferred. LED absolute maxima are not operating targets. The board has no ESD or abuse qualification.

Pad mapping: official KiCad Device:LED uses pin 1=K (cathode), pin 2=A (anode); official LED_D3.0mm uses pad 1=K, pad 2=A. Kingbright's package drawing identifies the cathode by its flat/short lead. Device:R is nonpolar (pins 1/2); axial footprint pad numbers preserve that mapping. Connector_Generic:Conn_01x05 and the straight header footprint use sequential pins/pads 1..5; J1 pin 1 is square and explicitly marked IN1, pin 5 marked GND. The selected header drawing specifies 1.10 +/-0.15 mm recommended holes; the official generic footprint's 1.0 mm holes lie within that stated range, with actual fit still open.

Native geometry/rules start from the dated workspace JLCPCB two-layer/1 oz baseline. Signal tracks are 0.4 mm and ground-return tracks are 0.6 mm for readability at this low load. No ampacity certification is implied. The circuit is routed explicitly; no autorouter was used. Ground returns have visible continuous copper on the back layer. No copper pours hide the individual signal routes.

The project-local library copies and 3D models come from the installed official KiCad 10 library distribution. Their exact paths/hashes, pad functions and manufacturer evidence locations are recorded in libs/PROVENANCE.json. Local model transforms are preserved. Models are generic visualization aids, not manufacturer mechanical qualification. The embedded PCB instances increase only silkscreen stroke widths to the baseline's 0.15 mm minimum and use 1 mm or larger silkscreen text. The archived and project-library footprints preserve upstream geometry; the declared library edit is only the model URI. Native numbered pad geometry remains unchanged.
