"""The offline explorer must bind displayed facts to its retained native sources."""

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import build_example_explorer as explorer

ROOT = Path(__file__).resolve().parents[1]
RETAINED = ROOT / 'docs/demos/example-explorer'


@pytest.fixture(scope='session')
def retained_bundle():
    paths = {name: RETAINED / name for name in ('manifest.json', 'index.html')}
    assert all(path.is_file() for path in paths.values()), 'the retained example explorer bundle is required'
    return {name: path.read_bytes() for name, path in paths.items()}


@pytest.fixture
def packet(tmp_path, retained_bundle):
    output = tmp_path / 'explorer'
    output.mkdir()
    for name, payload in retained_bundle.items():
        (output / name).write_bytes(payload)
    return SimpleNamespace(output=output,
                           manifest=json.loads(retained_bundle['manifest.json']),
                           data=explorer._data(retained_bundle['index.html']))


@pytest.fixture
def embedded_only(monkeypatch):
    # Keep actual current CAD/evidence/image reads in validate_embedded_board;
    # omit repeated whole-repository validation only for isolated display faults.
    monkeypatch.setattr(explorer, '_check_sources', lambda *_: None)


def write_packet(packet):
    """Use the supported renderer and fresh outer hash, so it cannot mask a fault."""
    payload = explorer.render_explorer(packet.data)
    (packet.output / 'index.html').write_bytes(payload)
    packet.manifest['outputs']['index.html'] = {
        'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload),
    }
    (packet.output / 'manifest.json').write_bytes(json.dumps(packet.manifest).encode())


def sensor(packet):
    return next(board for board in packet.data['boards'] if board['id'] == 'i2c-sensor')


def purchased_component(packet):
    return next(part for part in sensor(packet)['geometry']['components'] if part['reference'] == 'U1')


def test_retained_explorer_genuine_positive_control_matches_all_three_current_examples(packet):
    result = explorer.verify(ROOT, packet.output)
    assert result['integrity_valid'] is True and result['current_source_matches'] is True
    assert result['boards'] == 3
    assert {board['id'] for board in packet.data['boards']} == set(explorer.BOARDS)
    assert 'no native rerun or engineering approval' in result['scope']


@pytest.mark.parametrize('asset', ['model', 'schematic', 'top', 'bottom', 'pdf'])
def test_rehashed_substituted_native_asset_cannot_pass(packet, embedded_only, asset):
    board = sensor(packet)
    mime = 'application/pdf' if asset == 'pdf' else 'image/png'
    substituted = f'data:{mime};base64,' + base64.b64encode(b'not the captured native artifact').decode()
    if asset == 'pdf':
        board['pdf'] = substituted
    else:
        board['images'][asset]['uri'] = substituted
    source_artifacts = copy.deepcopy(packet.manifest['source_artifacts'])
    write_packet(packet)
    assert packet.manifest['source_artifacts'] == source_artifacts
    with pytest.raises(ValueError, match='embedded artifact differs from native source'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('field', ['mpn', 'value', 'footprint'])
def test_rehashed_invented_component_identity_cannot_pass(packet, embedded_only, field):
    purchased_component(packet)[field] = 'INVENTED-IDENTITY'
    write_packet(packet)
    with pytest.raises(ValueError, match='component identity or evidence'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('url', [
    'javascript:alert(1)', 'data:text/html,<script>alert(1)</script>',
    'file:///C:/private/owner.txt', 'https://example.invalid/invented-datasheet',
])
def test_rehashed_unsafe_or_unrelated_evidence_url_cannot_pass(packet, embedded_only, url):
    purchased_component(packet)['sources'][0]['url'] = url
    write_packet(packet)
    with pytest.raises(ValueError, match='component identity or evidence'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('field', ['title', 'manufacturer', 'revision', 'retrieved_on', 'sha256'])
def test_rehashed_invented_evidence_metadata_cannot_pass(packet, embedded_only, field):
    purchased_component(packet)['sources'][0][field] = 'invented archived evidence'
    write_packet(packet)
    with pytest.raises(ValueError, match='component identity or evidence'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('field', ['erc', 'drc', 'unconnected'])
def test_rehashed_finding_counts_must_match_native_reports(packet, embedded_only, field):
    sensor(packet)[field] += 1
    write_packet(packet)
    with pytest.raises(ValueError, match='finding counts differ from native reports'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('fault', ['duplicate', 'missing', 'extra'])
def test_rehashed_physical_component_inventory_cannot_gain_or_lose_parts(packet, embedded_only, fault):
    parts = sensor(packet)['geometry']['components']
    if fault == 'missing':
        parts.pop()
    else:
        part = copy.deepcopy(parts[0])
        if fault == 'extra':
            part['reference'] = 'U999'
        parts.append(part)
    write_packet(packet)
    with pytest.raises(ValueError, match='physical component inventory'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('fault', ['extra', 'missing', 'net', 'conflicting-duplicate'])
def test_rehashed_numbered_pad_inventory_and_nets_are_exact(packet, embedded_only, fault):
    pads = purchased_component(packet)['pads']
    if fault == 'missing':
        pads.pop()
    elif fault == 'net':
        pads[0]['net'] = 'INVENTED'
    else:
        extra = copy.deepcopy(pads[0])
        if fault == 'extra':
            extra['number'] = '999'
        extra['net'] = 'INVENTED'
        pads.append(extra)
    write_packet(packet)
    with pytest.raises(ValueError, match='numbered-pad inventory|conflicting native pad net'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('fault', ['title', 'subtitle', 'boundaries', 'caption', 'pcb-sha', 'review-url'])
def test_rehashed_description_scope_and_fingerprint_cannot_be_replaced(packet, embedded_only, fault):
    board = sensor(packet)
    if fault == 'boundaries':
        board['boundaries'] = ['Qualified for production']
    elif fault == 'caption':
        board['images']['bottom']['caption'] = 'Unmirrored and manufacturing approved'
    elif fault == 'pcb-sha':
        board['pcb_sha256'] = '0' * 64
    elif fault == 'review-url':
        board['review_url'] = 'javascript:alert(1)'
    else:
        board[fault] = 'Invented circuit description'
    write_packet(packet)
    with pytest.raises(ValueError, match='description differs|view scope differs|fingerprint differs|review URL differs'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('fault', ['missing', 'extra', 'empty'])
def test_source_artifact_inventory_is_mandatory_before_source_checks(packet, fault):
    artifacts = packet.manifest['source_artifacts']
    if fault == 'missing':
        artifacts.pop(next(iter(artifacts)))
    elif fault == 'extra':
        artifacts['examples/i2c-sensor/owner-unlisted.png'] = '0' * 64
    else:
        artifacts.clear()
    write_packet(packet)
    # This calls the real _check_sources; no native or source checks are mocked.
    with pytest.raises(ValueError, match='source artifact inventory is incomplete or unexpected'):
        explorer.verify(ROOT, packet.output)


def test_rehashed_embedded_ledger_cannot_disagree_with_manifest(packet, embedded_only):
    board = sensor(packet)
    key = next(name for name, value in board['source_inputs'].items() if value is not None)
    board['source_inputs'][key] = '0' * 64
    write_packet(packet)
    with pytest.raises(ValueError, match='embedded source ledger differs'):
        explorer.verify(ROOT, packet.output)


def test_matching_embedded_and_manifest_ledgers_cannot_mask_stale_current_source(packet):
    board = sensor(packet)
    key = next(name for name, value in board['source_inputs'].items() if value is not None)
    board['source_inputs'][key] = '0' * 64
    packet.manifest['source_projects'][board['id']][key] = '0' * 64
    write_packet(packet)
    with pytest.raises(ValueError, match='explorer inputs are stale'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('assertion', [False, 1])
def test_source_preservation_requires_exact_true(packet, assertion):
    packet.manifest['source_cad_unchanged'] = assertion
    write_packet(packet)
    with pytest.raises(ValueError, match='no source-preservation assertion'):
        explorer.verify(ROOT, packet.output)


def test_duplicate_board_id_cannot_hide_in_manifest_dictionary(packet, embedded_only):
    packet.data['boards'].append(copy.deepcopy(sensor(packet)))
    write_packet(packet)
    with pytest.raises(ValueError, match='embedded source ledger differs'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('target', ['manifest.json', 'index.html'])
@pytest.mark.parametrize('fault', ['mutation', 'identical-replacement', 'hardlink'])
def test_packet_changed_during_final_source_check_is_rejected(packet, monkeypatch, target, fault):
    calls = 0

    def final_source_check(*_):
        nonlocal calls
        calls += 1
        if calls != 2:
            return
        path = packet.output / target
        if fault == 'mutation':
            path.write_bytes(path.read_bytes() + b'\nchanged after initial verification\n')
        elif fault == 'identical-replacement':
            replacement = packet.output / 'new-publisher-file'
            replacement.write_bytes(path.read_bytes())
            replacement.replace(path)
        else:
            os.link(path, packet.output / 'another-name-for-packet-file')

    monkeypatch.setattr(explorer, '_check_sources', final_source_check)
    with pytest.raises((ValueError, RuntimeError), match='changed during verification|aliased'):
        explorer.verify(ROOT, packet.output)
    assert calls == 2


@pytest.mark.parametrize('target', ['manifest.json', 'index.html'])
def test_initial_packet_hardlink_alias_is_rejected(packet, monkeypatch, target):
    os.link(packet.output / target, packet.output / 'other-name')
    monkeypatch.setattr(explorer, '_check_sources', lambda *_: pytest.fail('aliased packet reached source verification'))
    with pytest.raises(ValueError, match='aliased'):
        explorer.verify(ROOT, packet.output)


def test_packet_root_reparse_alias_is_rejected_before_source_loading(packet, monkeypatch):
    original = Path.lstat

    def lstat(path):
        if path == packet.output:
            return SimpleNamespace(st_mode=original(path).st_mode, st_file_attributes=0x400)
        return original(path)

    monkeypatch.setattr(Path, 'lstat', lstat)
    monkeypatch.setattr(explorer, '_check_sources', lambda *_: pytest.fail('redirected packet reached sources'))
    with pytest.raises(ValueError, match='aliased'):
        explorer.verify(ROOT, packet.output)


def test_changed_html_without_outer_manifest_update_is_rejected(packet, monkeypatch):
    path = packet.output / 'index.html'
    path.write_bytes(path.read_bytes() + b'\nchanged html\n')
    monkeypatch.setattr(explorer, '_check_sources', lambda *_: pytest.fail('bad output hash reached source checks'))
    with pytest.raises(ValueError, match='output bytes do not match'):
        explorer.verify(ROOT, packet.output)


@pytest.mark.parametrize('url', [None, '', 'javascript:alert(1)', 'data:text/html,unsafe',
                                 'file:///private.txt', '//example.invalid/path',
                                 'https://user:secret@example.invalid/source'])
def test_evidence_url_filter_drops_active_local_or_credentialed_links(url):
    assert explorer._safe_url(url) is None


def test_evidence_url_filter_preserves_primary_https_link():
    url = 'https://www.ti.com/lit/ds/symlink/thvd1450.pdf'
    assert explorer._safe_url(url) == url
