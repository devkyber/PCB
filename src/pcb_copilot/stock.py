"""Fresh exact-MPN LCSC observations; retail inventory is not an assembly reservation."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path


class _NextData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.data = []

    def handle_starttag(self, tag, attrs):
        self.inside = tag == 'script' and dict(attrs).get('id') == '__NEXT_DATA__'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.data.append(data)


def parse_lcsc(payload: bytes, code: str, mpn: str) -> dict:
    parser = _NextData()
    parser.feed(payload.decode('utf-8'))
    document = json.loads(''.join(parser.data))
    product = document['props']['pageProps']['webData']
    if product.get('productCode') != code or product.get('productModel', '').strip() != mpn.strip():
        raise ValueError('Supplier C-number/MPN does not exactly match the BOM')
    quantity = product.get('stockNumber')
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValueError('Supplier stock is absent or invalid')
    return {'lcsc_part': code, 'mpn': product['productModel'], 'available': quantity,
            'manufacturer': product.get('brandNameEn'),
            'immediate_stock': product.get('overseasStockVO', {}).get('shipImmediately'),
            'minimum_purchase': product.get('minBuyNumber'),
            'supplier_product': product}


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': 'pcb-copilot/0.1 stock-check'})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError(f'Supplier HTTP status {response.status}')
        return response.read(8_000_001)


def check_stock(bom: Path, output: Path, *, quantity: int, fetch=_fetch) -> dict:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError('Board quantity must be a positive integer')
    groups = {}
    with bom.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('Cannot check an empty BOM')
    for row in rows:
        code, mpn = row['LCSC Part #'].strip(), row['MPN'].strip()
        count = int(row['Quantity'])
        refs = row['Designator'].split(',')
        if count < 1 or count != len(refs):
            raise ValueError('BOM quantity/designator mismatch')
        group = groups.setdefault((code, mpn), {'refs': [], 'per_board': 0})
        group['refs'].extend(refs)
        group['per_board'] += count
    output.mkdir(parents=True, exist_ok=True)
    sources = output / 'stock-sources'
    sources.mkdir(exist_ok=True)

    def inspect(entry):
        (code, mpn), group = entry
        result = {'lcsc_part': code, 'mpn': mpn, **group,
                  'required': group['per_board'] * quantity,
                  'observed_at': datetime.now(UTC).isoformat(), 'available': None,
                  'source_url': f'https://www.lcsc.com/product-detail/{code}.html',
                  'status': 'unknown'}
        if not re.fullmatch(r'C\d+', code) or not mpn:
            result['reason'] = 'Missing exact LCSC code or manufacturer part number'
            return result
        try:
            payload = fetch(result['source_url'])
            if len(payload) > 8_000_000:
                raise ValueError('Supplier response exceeds size limit')
            result['response_sha256'] = hashlib.sha256(payload).hexdigest()
            filename = f'{code}-{result["response_sha256"][:12]}.html.gz'
            (sources / filename).write_bytes(gzip.compress(payload, mtime=0))
            result['source_file'] = 'stock-sources/' + filename
            observed = parse_lcsc(payload, code, mpn)
            observed.pop('supplier_product')
            result.update(observed)
            result['status'] = 'available' if result['available'] >= result['required'] else 'shortage'
        except (OSError, ValueError, KeyError, TypeError) as error:
            result['reason'] = f'{type(error).__name__}: {error}'
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        parts = list(pool.map(inspect, sorted(groups.items())))
    report = {'schema_version': 1, 'supplier': 'LCSC retail', 'board_quantity': quantity,
              'bom_sha256': hashlib.sha256(bom.read_bytes()).hexdigest(),
              'checked_at': datetime.now(UTC).isoformat(),
              'passed': all(p['status'] == 'available' for p in parts), 'parts': parts,
              'assembly_inventory_confirmed': False,
              'scope': 'Exact C-number/MPN retail stock at request time; zero assembly attrition allowance. '
                       'No inventory is reserved. Confirm JLCPCB assembly stock, extra-parts allowance, '
                       'preorder requirements and part eligibility in the actual order.'}
    (output / 'stock.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    with (output / 'stock.csv').open('w', encoding='utf-8', newline='') as stream:
        fields = ['lcsc_part', 'mpn', 'per_board', 'required', 'available', 'status', 'observed_at', 'source_url']
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(parts)
    return report
