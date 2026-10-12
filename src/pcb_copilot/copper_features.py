"""Recognize explicit, non-purchased native PCB copper features.

Reference prefixes or BOM exclusion alone never exempt a component. This is
only a distinction between a physical package and geometry fabricated in the
board; electrical parity, pad bounds and native DRC still apply to both.
"""

from __future__ import annotations

import re

import sexpdata


def copper_feature_type(block: str) -> str | None:
    """Return ``net_tie`` or ``wire_pad`` for conservatively recognized copper."""
    tree = sexpdata.loads(block)
    if not isinstance(tree, list) or len(tree) < 2 or str(tree[0]) != 'footprint':
        return None
    children = [node for node in tree if isinstance(node, list) and node]
    props = {str(n[1]): str(n[2]).strip() for n in children
             if str(n[0]) == 'property' and len(n) >= 3}
    attrs = {str(value) for n in children if str(n[0]) == 'attr' for value in n[1:]}
    if 'exclude_from_bom' not in attrs:
        return None
    wire_identity = ('smd' in attrs and re.fullmatch(r'P\d+', props.get('Reference', ''))
                     and re.search(r'(?:^|:)WirePads_', str(tree[1])))
    identities = {'mpn', 'manufacturer part number', 'part number', 'lcsc',
                  'lcsc part #', 'lcsc part', 'jlcpcb', 'jlcpcb part'}
    for key, value in props.items():
        if key.casefold() not in identities or not value:
            continue
        # Native forward annotation can copy the descriptive wire-pad value
        # into MPN (e.g. "BATTERY IN"). This is not a purchasing identity.
        # Restrict this exception to explicitly excluded WirePads footprints;
        # supplier codes and distinct MPNs still require component review.
        if (wire_identity and key.casefold() == 'mpn' and value == props.get('Value')):
            continue
        return None
    if any(str(n[0]) == 'model' for n in children):
        return None
    pads = [n for n in children if str(n[0]) == 'pad']
    if len(pads) < 2:
        return None
    numbered = []
    for pad in pads:
        if len(pad) < 4:
            return None
        number, kind = str(pad[1]), str(pad[2])
        layers = {str(v) for n in pad if isinstance(n, list) and n
                  and str(n[0]) == 'layers' for v in n[1:]}
        if any('Paste' in layer for layer in layers):
            return None
        if number:
            if kind != 'smd' or not layers & {'F.Cu', 'B.Cu'}:
                return None
            numbered.append(number)
        elif kind != 'np_thru_hole':
            return None
    if len(numbered) < 2 or len(set(numbered)) != len(numbered):
        return None
    groups = [str(v) for n in children if str(n[0]) == 'net_tie_pad_groups' for v in n[1:]]
    if groups:
        grouped = [part.strip() for group in groups for part in group.split(',')]
        # A copper-only net tie has no assembly body/courtyard, and every pad
        # belongs to an explicitly declared native shorting group.
        courtyard = any('CrtYd' in str(v) for n in children
                        if str(n[0]).startswith('fp_')
                        for child in n if isinstance(child, list) and child
                        and str(child[0]) == 'layer' for v in child[1:])
        if ('exclude_from_pos_files' in attrs and not courtyard and len(numbered) == len(pads)
                and set(grouped) == set(numbered) and len(grouped) == len(numbered)
                and all(len(group.split(',')) >= 2 for group in groups)):
            return 'net_tie'
        return None
    # Wire lands have assembly access/strain-relief courtyards, so unlike ties
    # they remain in the physical placement check. Their native ID and all
    # fabrication attributes must agree; a generic P/J prefix is insufficient.
    if wire_identity:
        return 'wire_pad'
    return None
