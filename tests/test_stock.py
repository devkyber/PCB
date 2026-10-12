import csv
import gzip
import hashlib
import json

import pytest

from pcb_copilot.stock import check_stock, parse_lcsc


def page(code='C123', mpn='INDUCTOR-3R3', stock=12):
    data = {'props': {'pageProps': {
        'webData': {'productCode': code, 'productModel': mpn, 'stockNumber': stock},
        'related': [{'productCode': 'C456', 'stockNumber': 99999}],
    }}}
    return ('<script type="application/json" id="__NEXT_DATA__">'
            + json.dumps(data) + '</script>').encode()


@pytest.mark.parametrize('stock', [None, '123', True, -1])
def test_invalid_stock_never_becomes_available(stock):
    with pytest.raises(ValueError):
        parse_lcsc(page(stock=stock), 'C123', 'INDUCTOR-3R3')


@pytest.mark.parametrize('code,mpn', [('C456', 'INDUCTOR-3R3'), ('C123', 'INDUCTOR-4R7')])
def test_redirect_or_wrong_mpn_rejected(code, mpn):
    with pytest.raises(ValueError, match='exactly match'):
        parse_lcsc(page(), code, mpn)


def test_actual_zero_is_kept_despite_related_stock():
    assert parse_lcsc(page(stock=0), 'C123', 'INDUCTOR-3R3')['available'] == 0


@pytest.mark.parametrize('mode', ['available', 'shortage', 'unknown'])
def test_bom_quantity_stock_sources_and_failure_states(tmp_path, mode):
    bom = tmp_path / 'bom.csv'
    with bom.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Designator', 'Quantity', 'MPN', 'LCSC Part #'])
        writer.writerow(['L1,L2', 2, 'INDUCTOR-3R3', 'C123'])
        writer.writerow(['L3', 1, 'INDUCTOR-3R3', 'C123'])
    payload = page(stock=15 if mode == 'available' else 14)
    calls = []

    def fetch(url):
        calls.append(url)
        if mode == 'unknown':
            raise OSError('offline')
        return payload

    output = tmp_path / 'out'
    result = check_stock(bom, output, quantity=5, fetch=fetch)
    assert len(calls) == 1
    part, = result['parts']
    assert part['required'] == 15 and part['status'] == mode
    assert result['passed'] == (mode == 'available')
    assert not result['assembly_inventory_confirmed']
    if mode != 'unknown':
        assert gzip.decompress((output / part['source_file']).read_bytes()) == payload
        assert part['response_sha256'] == hashlib.sha256(payload).hexdigest()
    else:
        assert part['available'] is None


@pytest.mark.parametrize('quantity', [0, -1, True, 1.5])
def test_invalid_board_quantity_fails_before_network(tmp_path, quantity):
    with pytest.raises(ValueError, match='quantity'):
        check_stock(tmp_path / 'bom.csv', tmp_path, quantity=quantity,
                    fetch=lambda _: pytest.fail('unexpected network'))
