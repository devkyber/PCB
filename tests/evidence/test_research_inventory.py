import importlib

import pytest


@pytest.mark.parametrize("caller", ["packaged", "legacy"])
@pytest.mark.parametrize("legacy_spelling", [False, True])
def test_research_inventory_preserves_classification_and_property_spellings(
    caller, legacy_spelling, repo_root, monkeypatch
):
    if caller == "legacy":
        monkeypatch.syspath_prepend(str(repo_root / "docs"))
        inventory = importlib.import_module("check_research").inventory
    else:
        from pcb_copilot.evidence.inventory import inventory

    footprints = []
    for ref, value, pads, lcsc in [
        ("U1", "SMALL_LDO", 3, "C12345"),
        ("U2", "SENSOR", 8, "C23456"),
        ("R1", "RESISTOR_ARRAY", 8, ""),
        ("J9", "XBEE3_SOCKET", 2, ""),
        ("H1", "ModuleMount", 1, ""),
    ]:
        properties = (
            f'(fp_text reference "{ref}") (fp_text value "{value}")'
            if legacy_spelling
            else f'(property "Reference" "{ref}") (property "Value" "{value}")'
        )
        footprints.append(
            f'(footprint "Test:Part" {properties} (property "LCSC" "{lcsc}") '
            + " ".join(f'(pad "{i}")' for i in range(1, pads + 1))
            + ")"
        )
    text = "(kicad_pcb " + " ".join(footprints) + '(footprint "MissingRef"))'
    assert inventory(text) == [
        ("U1", "SMALL_LDO", 3, "C12345", False),
        ("U2", "SENSOR", 8, "C23456", True),
        ("R1", "RESISTOR_ARRAY", 8, "", False),
        ("J9", "XBEE3_SOCKET", 2, "", True),
        ("H1", "ModuleMount", 1, "", True),
    ]


@pytest.mark.parametrize(
    "property_name", ["LCSC", "LCSC Part #", "LCSC Part", "JLCPCB", "JLCPCB Part"]
)
def test_research_inventory_preserves_sourcing_aliases(property_name):
    from pcb_copilot.evidence.inventory import inventory

    text = (
        '(footprint "Test:Part" (property "Reference" "U1") '
        f'(property "{property_name}" "  C12345  "))'
    )
    assert inventory(text) == [("U1", "", 0, "C12345", False)]
