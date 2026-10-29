"""Offline handover rendering must preserve meaning and keep native text inert."""

import base64
import copy
import hashlib
import re
from html.parser import HTMLParser

import pytest

from pcb_copilot.review.report_html import JS, render_report

PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFuoAAAAASUVORK5CYII='


@pytest.fixture
def document():
    scope = {'proves': 'Executed a scoped check', 'does_not_prove': 'Safe hardware',
             'deterministic': True, 'requires_external_tool': False}
    return {'schema_version': 1, 'generated_utc': '2026-10-29T12:00:00Z', 'project': {'name': 'Inspection fixture'},
            'source_inputs_unchanged': True, 'source_inputs': {'board.kicad_pcb': 'b' * 64, 'review-signoff.yaml': None},
            'toolchain': {'kicad_version': '10.0.6'}, 'scope': 'Inspection aid; no fabrication approval.',
            'review': {'schema_version': 1, 'blocking': True, 'schematic_hash': 'a' * 64, 'pcb_hash': 'b' * 64,
                       'results': [
                           {'check_id': 'erc', 'passed': True, 'detail': '0 violations', 'finding_kind': 'machine_failure',
                            'scope': scope, 'duration_ms': 12, 'advisories': ['Engineering review still required']},
                           {'check_id': 'signoff', 'passed': False, 'detail': 'unsigned', 'finding_kind': 'human_decision',
                            'scope': scope, 'duration_ms': 1, 'advisories': []}],
                       'findings': [{'check_id': 'signoff', 'detail': 'unsigned', 'kind': 'human_decision', 'blocking': True},
                                    {'check_id': 'erc', 'detail': 'Engineering review still required',
                                     'kind': 'engineering_warning', 'blocking': False}]}}


def images():
    return [{'id': 'sheet-1', 'title': 'Schematic 1 / Power', 'kind': 'schematic', 'orientation': 'Native sheet', 'data_uri': PNG},
            {'id': 'sheet-2', 'title': 'Schematic 2 / I2C', 'kind': 'schematic', 'orientation': 'Native sheet', 'data_uri': PNG},
            {'id': 'back', 'title': 'Bottom copper', 'kind': 'copper', 'orientation': 'Underside; mirrored', 'data_uri': PNG}]


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_actual_counts_scopes_and_all_native_pages_are_present_without_js(document):
    result = render_report(document, images())
    assert '1 passed, 1 failed; 1 blocking finding.' in result
    assert 'Human decisions (1)' in result and 'Engineering advisories (1)' in result
    assert 'Machine findings (0)' in result and '<strong>Blocked</strong>' in result
    assert result.count('data-artifact data-kind=') == 3
    assert 'Schematic 1 / Power' in result and 'Schematic 2 / I2C' in result
    assert 'Underside; mirrored' in result and 'Does not establish' in result
    assert 'Executed a scoped check' in result and 'Safe hardware' in result
    assert 'Not present in this snapshot' in result and '<noscript>' in result
    assert 'quality score' not in result.lower() and '>Approve<' not in result
    assert document['review']['results'][0]['passed'] is True


def test_untrusted_native_text_and_script_json_cannot_create_active_markup(document):
    payload = '</script><img src=x onerror=alert(1)><script>alert(2)</script>\u2028\u2029'
    document['project']['name'] = payload
    document['review']['results'][0]['detail'] = payload
    document['review']['results'][0]['scope']['proves'] = payload
    document['review']['findings'][0]['detail'] = payload
    document['source_inputs'][payload] = 'c' * 64
    view = images()
    view[0]['title'] = payload
    result = render_report(document, view)
    parsed = Elements()
    parsed.feed(result)
    assert len([tag for tag, attrs in parsed.tags if tag == 'script']) == 2
    assert not any('onerror' in attrs or 'onclick' in attrs for _tag, attrs in parsed.tags)
    assert all(attrs.get('src', '').startswith('data:image/png;base64,')
               for tag, attrs in parsed.tags if tag == 'img' and attrs.get('src'))
    encoded = re.search(r'<script type="application/json" id="report-data">(.*?)</script>', result, re.DOTALL).group(1)
    assert '<' not in encoded and '\u2028' not in encoded and '\u2029' not in encoded
    assert r'\u003c/script\u003e' in encoded and r'\u2028' in encoded and r'\u2029' in encoded


def test_report_has_only_inline_script_and_local_filter_zoom_hooks(document):
    result = render_report(document, images())
    parsed = Elements()
    parsed.feed(result)
    assert not any(attrs.get('src') for tag, attrs in parsed.tags if tag == 'script')
    assert not any(tag in {'iframe', 'object', 'embed', 'link'} for tag, _attrs in parsed.tags)
    assert 'fetch(' not in result and 'innerHTML' not in result
    assert all(f'id="{value}"' in result for value in ('check-search', 'check-status', 'check-kind', 'view-kind', 'image-dialog'))
    script_hash = base64.b64encode(hashlib.sha256(JS.encode()).digest()).decode()
    assert script_hash in result and "connect-src &#x27;none&#x27;" in result
    assert 'prefers-reduced-motion' in result and ':focus-visible' in result
    assert all(href.startswith('#') for tag, attrs in parsed.tags if tag == 'a' for href in [attrs.get('href', '')])


@pytest.mark.parametrize('uri', ['https://example.com/image.png', 'data:image/svg+xml;base64,PHN2Zz4=',
                                  'data:image/png;base64,PHN2Zz4=', PNG + '" onerror="alert(1)'])
def test_only_embedded_png_can_enter_the_artifact_canvas(document, uri):
    view = images()
    view[0]['data_uri'] = uri
    with pytest.raises(ValueError):
        render_report(document, view)


def test_duplicate_image_ids_and_unpreserved_sources_are_rejected(document):
    view = images()
    view[1]['id'] = view[0]['id']
    with pytest.raises(ValueError):
        render_report(document, view)
    changed = copy.deepcopy(document)
    changed['source_inputs_unchanged'] = False
    with pytest.raises(ValueError):
        render_report(changed, images())


def test_no_registered_blocker_is_not_reported_as_approval(document):
    document['review'].update(blocking=False, findings=[])
    document['review']['results'][1]['passed'] = True
    result = render_report(document, [])
    assert '<strong>No registered blocker</strong>' in result
    assert '2 passed, 0 failed; 0 blocking findings.' in result
    assert 'No native images are included' in result and 'records no approval' in result


def test_vector_pdf_download_is_embedded_and_not_an_active_or_external_url(document):
    document['schematic_pdf_uri'] = 'data:application/pdf;base64,' + base64.b64encode(b'%PDF-1.7\nfixture').decode()
    result = render_report(document, images())
    assert 'Download vector schematic PDF' in result and 'download="schematic.pdf"' in result
    for bad in ('https://example.com/file.pdf', 'javascript:alert(1)', 'data:application/pdf;base64,PHN2Zz4='):
        document['schematic_pdf_uri'] = bad
        with pytest.raises(ValueError, match='PDF'):
            render_report(document, images())
