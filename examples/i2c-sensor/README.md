# I2C temperature sensor

An editable 3.3 V MCP9808 MSOP breakout: eight selectable I2C addresses, a local ceramic bypass, fixed bus pullups and a separate open-drain ALERT header. Unbuilt DRAFT; no owner or fabrication approval.

J1 is 3V3 / GND / SCL / SDA. JP1..3 select A0..A2; no shunts gives 0x18. Power off before changing address shunts. Start at 100 kHz and assess the real host's voltage, combined pullups and measured bus rise time. ALERT requires firmware configuration after reset.

The root KiCad files are the editable design. REQUIREMENTS.md defines the operating assumptions; DESIGN_BASIS.md records exact source decisions and calculations. evidence/index.yaml binds archived primary manufacturer bytes. Local official KiCad library copies, models and license/source receipts are in libs/. Generic mechanical models and a clean native check do not qualify physical fit, temperature accuracy or assembly.

```powershell
uv run pcb-copilot review examples/i2c-sensor
uv run pcb-copilot report examples/i2c-sensor --output C:/Temp/i2c-sensor-handover
```

Retained native views/check results in output/ are bound to declared source hashes by SOURCE.json. Any source change requires fresh checks and views. Full review deliberately remains blocked by unsigned human decisions and missing supplier assembly contracts. No fabrication outputs or bench results are included.
