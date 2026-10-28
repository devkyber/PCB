"""Validate exact archived KiCad footprint copies, with model-URI-only edits.

The receipt establishes local source lineage and pad-map coverage. It does not
authenticate the upstream download, interpret a datasheet or qualify physical fit.
Symbol provenance fields are metadata; this validator checks footprints only.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

import sexpdata
from kicad_claude.adapters import sch_io

from pcb_copilot.evidence.index import load_evidence_index
from pcb_copilot.evidence.models import EvidenceRole, TrustTier
from pcb_copilot.layout.lib_ids import split_footprint_lib_id
from pcb_copilot.models import Project
from pcb_copilot.schematic.preview import schematic_files

OFFICIAL_COPY_DESCRIPTION = 'official kicad footprint copies; see libs/provenance.json'
_ROOT_FIELDS = {'schema_version', 'distribution', 'author_review', 'source', 'upstream_version', 'records'}
_RECORD_FIELDS = {
    'symbol', 'source_symbol', 'source_symbol_library_sha256', 'footprint', 'source_footprint',
    'upstream_path', 'upstream_sha256', 'upstream_url', 'local_path', 'local_sha256',
    'changes', 'mpn', 'pad_functions', 'models', 'manufacturer_evidence_ids',
    'manufacturer_locations', 'physical_fit_qualified',
}
_MODEL_FIELDS = {'source', 'path', 'sha256', 'upstream_path', 'upstream_sha256', 'upstream_uri', 'local_uri'}


def _object(value, required: set[str], optional: set[str] | None = None) -> dict:
    if (not isinstance(value, dict) or not required.issubset(value)
            or set(value) - required - (optional or set())):
        raise ValueError('invalid official KiCad footprint provenance schema fields')
    return value


def _text(value, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f'official footprint provenance needs {label}')
    return value


def _strings(value, label: str, *, required: bool = False) -> list[str]:
    if (not isinstance(value, list) or (required and not value)
            or any(not isinstance(item, str) or not item.strip() for item in value)
            or len(set(value)) != len(value)):
        raise ValueError(f'official footprint provenance needs unique {label}')
    return value


def _digest(value) -> str:
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('official footprint provenance needs a lowercase SHA-256')
    return value


def _path(root: Path, relative: str) -> Path:
    _text(relative, 'contained relative path')
    posix, windows = PurePosixPath(relative), PureWindowsPath(relative)
    if (posix.is_absolute() or windows.drive or windows.is_absolute() or '\\' in relative
            or '..' in posix.parts or posix.as_posix() != relative or relative == '.'
            or '"' in relative or ':' in relative or any(ord(char) < 32 for char in relative)):
        raise ValueError(f'official footprint provenance path must be contained and relative: {relative}')
    path = (root / relative).resolve()
    if path == root.resolve() or not path.is_relative_to(root.resolve()):
        raise ValueError(f'official footprint provenance path escapes its root: {relative}')
    return path


def _hash(path: Path, expected: str) -> bytes:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != _digest(expected):
        raise ValueError(f'official footprint provenance hash mismatch: {path.name}')
    return payload


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate official footprint provenance key: {key}')
        result[key] = value
    return result


def _manifest(project: Project) -> dict:
    path = _path(project.root, 'libs/PROVENANCE.json')
    if not path.is_file() or path.stat().st_size > 1_048_576:
        raise ValueError('official footprint copy needs a scoped libs/PROVENANCE.json receipt')
    try:
        data = _object(json.loads(path.read_bytes(), object_pairs_hook=_unique_keys), _ROOT_FIELDS)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('malformed official footprint provenance JSON') from exc
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('invalid official footprint provenance schema version')
    for key in ('distribution', 'author_review', 'upstream_version'):
        _text(data[key], key)
    if data['source'] not in {'https://gitlab.com/kicad/libraries', 'https://github.com/KiCad'}:
        raise ValueError('official footprint provenance must identify the official KiCad libraries')
    if not isinstance(data['records'], list) or not data['records']:
        raise ValueError('official footprint provenance records must be a nonempty list')
    for record in data['records']:
        _object(record, _RECORD_FIELDS, {'fabricated_only'})
        for key in ('symbol', 'source_symbol', 'footprint', 'source_footprint',
                    'upstream_path', 'upstream_url', 'local_path'):
            _text(record[key], key)
        for key in ('source_symbol_library_sha256', 'upstream_sha256', 'local_sha256'):
            _digest(record[key])
        _text(record['mpn'], 'selected MPN', empty=True)
        for key in ('changes', 'manufacturer_evidence_ids', 'manufacturer_locations'):
            _strings(record[key], key, required=key == 'manufacturer_locations')
        functions = record['pad_functions']
        if not isinstance(functions, dict) or any(
                not isinstance(key, str) or not key.strip() or not isinstance(value, str)
                or not value.strip() for key, value in functions.items()):
            raise ValueError('invalid official footprint pad-function map')
        if (record['physical_fit_qualified'] is not False
                or type(record.get('fabricated_only', False)) is not bool):
            raise ValueError('official footprint source receipt must not claim physical qualification')
        if not isinstance(record['models'], list):
            raise ValueError('official footprint models must be a list')  # noqa: TRY004 -- invalid file content
        for model in record['models']:
            _object(model, _MODEL_FIELDS)
            for key in ('source', 'path', 'upstream_path', 'upstream_uri', 'local_uri'):
                _text(model[key], key)
            _digest(model['sha256'])
            _digest(model['upstream_sha256'])
    for key in ('local_path', 'footprint'):
        values = [record[key] for record in data['records']]
        if len(values) != len(set(values)):
            raise ValueError(f'duplicate official footprint provenance {key}')
    return data


def _official_url(record: dict) -> None:
    url = urlsplit(record['upstream_url'])
    prefixes = {
        'gitlab.com': '/kicad/libraries/kicad-footprints/-/blob/',
        'github.com': '/KiCad/kicad-footprints/blob/',
    }
    path = unquote(url.path)
    library, name = split_footprint_lib_id(record['source_footprint'])
    if (url.scheme != 'https' or url.netloc not in prefixes or url.query or url.fragment
            or '..' in PurePosixPath(path).parts
            or not path.startswith(prefixes.get(url.netloc, '<invalid>'))
            or not path.endswith(f'/{library}.pretty/{name}.kicad_mod')
            or Path(record['upstream_path']).name != name + '.kicad_mod'):
        raise ValueError('official footprint source URL/identity is not a KiCad footprint origin')


def _selected_part(project: Project, ref: str, lib_id: str, record: dict, pads: list) -> None:
    matches = []
    for sheet in schematic_files(project.schematic_path):
        for symbol in sch_io.find_children(sch_io.parse_file(sheet), 'symbol'):
            fields = {str(item[1]): str(item[2]) for item in sch_io.find_children(symbol, 'property')}
            if fields.get('Reference') == ref:
                identity = sch_io.find_child(symbol, 'lib_id')
                unit = sch_io.find_child(symbol, 'unit')
                if unit is not None and (len(unit) != 2 or type(unit[1]) is not int or unit[1] <= 0):
                    raise ValueError(f'{ref}: native component has an invalid unit number')
                matches.append((fields, str(identity[1]) if identity and len(identity) == 2 else None,
                                unit[1] if unit else None))
    if not matches or any(fields.get('Footprint') != lib_id for fields, _, _ in matches):
        raise ValueError(f'{ref}: official footprint receipt needs a matching native component')
    identities = {identity for _, identity, _ in matches}
    if identities != {record['symbol']}:
        raise ValueError(f'{ref}: native component units have conflicting library identities')
    units = [unit for _, _, unit in matches]
    if len(matches) > 1 and (None in units or len(set(units)) != len(units)):
        raise ValueError(f'{ref}: native component units must have distinct positive unit numbers')
    selected_mpns = {fields.get('MPN', '') for fields, _, _ in matches}
    if len(selected_mpns) != 1:
        raise ValueError(f'{ref}: native component units have conflicting MPNs')
    if record.get('fabricated_only', False):
        if (not re.fullmatch(r'(?:H|MH)\d+', ref) or record['mpn']
                or record['manufacturer_evidence_ids'] or not pads
                or any(len(pad) < 3 or str(pad[1]) or str(pad[2]) != 'np_thru_hole' for pad in pads)):
            raise ValueError('fabricated-only footprint receipt is limited to unnumbered NPTH mounting features')
    elif not record['mpn'].strip() or selected_mpns != {record['mpn']}:
        raise ValueError(f'{ref}: official footprint receipt does not match the exact selected native MPN')


def _manufacturer_evidence(project: Project, record: dict) -> None:
    if record.get('fabricated_only', False):
        return
    ids = _strings(record['manufacturer_evidence_ids'], 'manufacturer evidence IDs', required=True)
    index = load_evidence_index(project.evidence_index_path)
    for evidence_id in ids:
        source = next((item for item in index.records if item.id == evidence_id), None)
        if (source is None or source.trust_tier not in {TrustTier.MANUFACTURER, TrustTier.MANUFACTURER_EVM}
                or record['mpn'] not in source.part_numbers or not source.source_url
                or not source.roles.intersection({EvidenceRole.DATASHEET, EvidenceRole.FOOTPRINT_DRAWING,
                                                  EvidenceRole.MODULE_PINOUT})):
            raise ValueError(f'official footprint needs exact-part manufacturer drawing evidence: {evidence_id}')
        path = _path(project.evidence_index_path.parent, source.path)
        _hash(path, source.sha256)


def official_copy_receipt(project: Project, path: Path, ref: str, lib_id: str) -> dict:
    data = _manifest(project)
    relative = path.resolve().relative_to(project.root.resolve()).as_posix()
    matches = [record for record in data['records'] if record['local_path'] == relative]
    if len(matches) != 1 or matches[0]['footprint'] != lib_id:
        raise ValueError(f'official footprint needs one exact local receipt: {relative}')
    record = matches[0]
    _official_url(record)
    library, name = split_footprint_lib_id(lib_id)
    if (record['local_path'] != f'libs/{library}.pretty/{name}.kicad_mod'
            or not record['upstream_path'].startswith('libs/upstream/')
            or record['upstream_path'] == record['local_path']):
        raise ValueError('official footprint needs distinct local-library and archived upstream paths')
    local_path = _path(project.root, record['local_path'])
    upstream_path = _path(project.root, record['upstream_path'])
    if local_path.samefile(upstream_path):
        raise ValueError('official footprint source archive must be distinct from its local copy')
    local = _hash(local_path, record['local_sha256'])
    upstream = _hash(upstream_path, record['upstream_sha256'])
    try:
        original_tree = sexpdata.loads(upstream.decode('utf-8'))
    except Exception as exc:  # sexpdata exposes several parse exception types
        raise ValueError('malformed archived KiCad footprint') from exc
    if sch_io.head_of(original_tree) != 'footprint':
        raise ValueError('archived KiCad source is not a footprint')
    pads = sch_io.find_children(original_tree, 'pad')
    numbered = {str(pad[1]) for pad in pads if len(pad) > 1 and str(pad[1])}
    if set(record['pad_functions']) != numbered:
        raise ValueError('official footprint provenance pad-function coverage mismatch')
    models = sch_io.find_children(original_tree, 'model')
    if len(models) != len(record['models']):
        raise ValueError('official footprint provenance must cover every model URI')
    original_uris = [str(model[1]) for model in models if len(model) > 1]
    declared_uris = [model['upstream_uri'] for model in record['models']]
    if len(set(declared_uris)) != len(declared_uris) or set(original_uris) != set(declared_uris):
        raise ValueError('official footprint model source URI mismatch')
    expected = upstream
    for model in record['models']:
        if not model['path'].startswith('libs/models/'):
            raise ValueError('official model archive must be contained in libs/models')
        if not model['upstream_path'].startswith('libs/upstream/'):
            raise ValueError('official model source archive must be contained in libs/upstream')
        model_path = _path(project.root, model['path'])
        source_path = _path(project.root, model['upstream_path'])
        if model_path.samefile(source_path):
            raise ValueError('official model source archive must be distinct from its local copy')
        payload = _hash(model_path, model['sha256'])
        original = _hash(source_path, model['upstream_sha256'])
        if payload != original:
            raise ValueError('official model copy differs from its pinned upstream SHA-256')
        if model['local_uri'] != '${KIPRJMOD}/' + model['path']:
            raise ValueError('official model URI must match its contained local archive path')
        uri = model['upstream_uri']
        if any(char in uri for char in ('"', '\\', '\r', '\n')):
            raise ValueError('unsupported official model URI quoting')
        token = ('"' + uri + '"').encode('utf-8')
        if expected.count(token) != 1:
            raise ValueError('official model URI substitution must identify exactly one token')
        expected = expected.replace(token, ('"' + model['local_uri'] + '"').encode('utf-8'))
    if local != expected:
        raise ValueError('local footprint differs from archived KiCad source beyond allowed model URI replacements')
    _selected_part(project, ref, lib_id, record, pads)
    _manufacturer_evidence(project, record)
    return record
