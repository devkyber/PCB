"""Route pipeline: unconnected-item classification and pour-net detection.

The distinction these tests protect is the one that made every board in this
workspace look broken in the same undiagnosable way: a pour net that is not
bonded and a signal net that is not routed both surface as "unconnected
items", but only one of them is the router's fault, and the fixes are not
interchangeable.
"""

from __future__ import annotations

from kicad_claude.adapters import route_pipeline


def _item(*descriptions: str) -> dict:
    return {"items": [{"description": d, "position": [1.0, 2.0]}
                      for d in descriptions]}


def test_pour_items_are_separated_from_signal_items():
    drc = {"unconnected_items": [
        _item("Pad 2 [GND] of U2 on F.Cu",
              "Zone 'GND_TOP' [GND] on F.Cu, priority 0"),
        _item("Pad 1 [SPI0_SCK] of U1 on F.Cu",
              "Pad 3 [SPI0_SCK] of U4 on F.Cu"),
    ]}
    out = route_pipeline.classify_unconnected(drc, {"GND"})
    assert len(out["pour"]) == 1
    assert len(out["signal"]) == 1
    assert out["signal"][0]["nets"] == ["SPI0_SCK"]


def test_escape_targets_are_deduplicated_pads_on_pour_nets():
    drc = {"unconnected_items": [
        _item("Pad 2 [GND] of U2 on F.Cu", "Zone 'GND_TOP' [GND] on F.Cu"),
        _item("Zone 'GND_TOP' [GND] on F.Cu", "Pad 2 [GND] of U2 on F.Cu"),
        _item("Pad 5 [GND] of U2 on F.Cu", "Zone 'GND_TOP' [GND] on F.Cu"),
    ]}
    out = route_pipeline.classify_unconnected(drc, {"GND"})
    assert out["escape_targets"] == [("U2", "2"), ("U2", "5")]


def test_zone_to_zone_items_are_pour_work_with_no_pad_to_escape():
    drc = {"unconnected_items": [
        _item("Zone 'GND_TOP' [GND] on F.Cu", "Zone 'GND_BOTTOM' [GND] on B.Cu"),
    ]}
    out = route_pipeline.classify_unconnected(drc, {"GND"})
    assert len(out["pour"]) == 1
    assert out["escape_targets"] == []


def test_a_net_without_a_pour_is_never_treated_as_bonding_work():
    """GND with no zone on this board is a signal net like any other."""
    drc = {"unconnected_items": [
        _item("Pad 2 [GND] of U2 on F.Cu", "Pad 1 [GND] of U3 on F.Cu"),
    ]}
    out = route_pipeline.classify_unconnected(drc, set())
    assert out["signal"] and not out["pour"]


def test_pour_nets_read_both_board_file_dialects(tmp_path):
    """Stock KiCAD writes (net_name "GND"); generated boards write (net "GND")."""
    stock = tmp_path / "stock.kicad_pcb"
    stock.write_text('(kicad_pcb (zone (net 3) (net_name "GND") (layer "F.Cu")))')
    assert route_pipeline._nets_with_zones(stock) == {"GND"}

    generated = tmp_path / "generated.kicad_pcb"
    generated.write_text('(kicad_pcb (zone (net "GND") (layer "F.Cu") (name "GND_TOP")))')
    assert route_pipeline._nets_with_zones(generated) == {"GND"}
