from types import SimpleNamespace

import pytest

from pcb_copilot.review import routing_topology as topology


def track(identity, start, end, width=.2, net='PWM', layer='F.Cu'):
    return {'id': identity, 'start': start, 'end': end, 'width': width, 'net': net, 'layer': layer}


def analyze(*tracks, contacts=()):
    return topology.analyze_geometry({'tracks': tracks, 'pad_contacts': contacts})


def test_tiny_overlaid_patch_is_found_with_exact_track_identity():
    main = track('main', (0, 0), (10, 0), 1)
    patch = track('patch', (4, .1), (4.1, .1), .2)
    findings = analyze(main, patch)
    assert len(findings) == 1
    assert findings[0]['code'] == 'covered_track'
    assert findings[0]['track'] == 'patch'
    assert findings[0]['covering_track'] == 'main'


def test_only_fully_covered_same_net_same_layer_tracks_are_redundant():
    main = track('main', (0, 0), (10, 0), 1)
    # Each track would be incorrectly removed by an overlap-only or XY-only test.
    cases = [track('partial', (9, 0), (11, 0)),
             track('other_net', (1, 0), (2, 0), net='GND'),
             track('other_layer', (1, 0), (2, 0), layer='B.Cu'),
             track('gap', (1, .601), (2, .601)),
             track('wider', (1, 0), (2, 0), 1.1)]
    for case in cases:
        assert not analyze(main, case)


def test_equal_reversed_duplicates_report_once():
    findings = analyze(track('a', (0, 0), (2, 0)), track('b', (2, 0), (0, 0)))
    assert [(f['track'], f['covering_track']) for f in findings] == [('b', 'a')]


def test_short_but_uncovered_join_is_advisory_not_claimed_redundant():
    findings = analyze(track('short', (0, 0), (.1, .1), .3))
    assert findings[0]['code'] == 'short_track'
    assert 'intentional' in topology.describe(findings[0])


@pytest.mark.parametrize('segment,expected', [
    (track('entry', (-2, 0), (0, 0)), []),
    (track('entry', (-2, 0), (2, 0)), []),  # Centreline through anchor is enough.
    (track('entry', (-2, .2), (0, .2)), ['off_center_pad_contact']),
])
def test_pad_anchor_entry_is_separate_from_electrical_contact(segment, expected):
    contacts = [{'ref': 'J1', 'pad': '1', 'center': [0, 0], 'net': 'PWM',
                 'layer': 'F.Cu', 'tracks': ['entry']}]
    findings = analyze(segment, contacts=contacts)
    assert [f['code'] for f in findings] == expected
    if expected:
        assert 'not an electrical-open' in topology.describe(findings[0])


def test_topology_advisories_do_not_replace_drc_or_modify_copper(tmp_path, monkeypatch):
    pcb = tmp_path / 'owner.kicad_pcb'
    pcb.write_bytes(b'owner copper')
    findings = analyze(track('short', (0, 0), (.1, 0), .3))
    monkeypatch.setattr(topology, 'inspect_routing', lambda _: {
        'findings': findings, 'counts': {'short_track': 1}, 'straight_tracks': 1,
        'arcs_not_audited': 2, 'custom_pads_not_audited': 1})
    result = topology.RoutingTopologyCheck().run(SimpleNamespace(pcb_path=pcb))
    assert result.passed and len(result.advisories) == 1
    assert 'Native DRC remains the connectivity gate' in result.detail
    assert pcb.read_bytes() == b'owner copper'
