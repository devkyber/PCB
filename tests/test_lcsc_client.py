"""Tests for the jlcparts-backed LCSC client.

All HTTP is mocked with a fake httpx.AsyncClient that responds to:
  - /data/manifest.json
  - /data/attributes-lut.json.gz  (gzipped attributes LUT array)
  - /data/<shard>.jsonl.gz        (gzipped JSONL component shards)

SQLite is redirected to tmp_path via monkeypatch on config.CACHE_DIR.
"""

import gzip
import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from kicad_jlcpcb_mcp import config
from kicad_jlcpcb_mcp.lcsc_client import (
    LcscError,
    _extract_attr,
    _extract_basic_flag,
    _extract_price,
    _resolve_attributes,
    _row_dict_to_part,
    get_part,
    populate_cache,
    resolve_bom,
    search,
)

# ---------------------------------------------------------------------------
# Fake jlcparts mirror (new sharded JSONL format)
# ---------------------------------------------------------------------------

# Attributes LUT entries: [name, value_obj]
SAMPLE_LUT = [
    # 0: Basic/Extended = "Basic"
    [
        "Basic/Extended",
        {"format": "${default}", "primary": "default", "values": {"default": ["Basic", "string"]}},
    ],
    # 1: Manufacturer = "YAGEO"
    [
        "Manufacturer",
        {"format": "${default}", "primary": "default", "values": {"default": ["YAGEO", "string"]}},
    ],
    # 2: Package = "0603"
    [
        "Package",
        {"format": "${default}", "primary": "default", "values": {"default": ["0603", "string"]}},
    ],
    # 3: Basic/Extended = "Extended"
    [
        "Basic/Extended",
        {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["Extended", "string"]},
        },
    ],
    # 4: Manufacturer = "Acme Corp"
    [
        "Manufacturer",
        {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["Acme Corp", "string"]},
        },
    ],
    # 5: Package = "QFN-32"
    [
        "Package",
        {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["QFN-32", "string"]},
        },
    ],
]

# JSONL shard schema (field name → array index)
SHARD_SCHEMA = {
    "lcsc": 0,
    "mfr": 1,
    "joints": 2,
    "description": 3,
    "datasheet": 4,
    "price": 5,
    "img": 6,
    "url": 7,
    "attributes": 8,
    "stock": 9,
    "subcategory": 10,
}

# Component records (arrays matching the schema above)
RESISTOR_RECORD = [
    "C25804",
    "RC0603FR-0710KL",
    2,
    "10 kOhms +/-1% 0.1W 0603 Chip Resistor",
    "https://example.com/ds.pdf",
    [{"price": 0.0012, "qFrom": 1, "qTo": 99}],
    None,
    None,
    [0, 1, 2],  # LUT indices → Basic, YAGEO, 0603
    100000,
    1,  # subcategory ID → maps to Resistors/Chip Resistor
]

EXOTIC_RECORD = [
    "C9000",
    "EXOTIC-CHIP",
    32,
    "Exotic 32-pin mystery chip",
    "",
    [{"price": 5.50, "qFrom": 1, "qTo": 99}],
    None,
    None,
    [3, 4, 5],  # LUT indices → Extended, Acme Corp, QFN-32
    50,
    2,  # subcategory ID → maps to ICs/Exotic
]

# Manifest (replaces old index.json)
SAMPLE_MANIFEST = {
    "version": 4,
    "created": "2026-04-08T00:00:00Z",
    "totalComponents": 2,
    "attributesLut": "attributes-lut.json.gz",
    "categories": [
        {
            "id": 1,
            "category": "Resistors",
            "subcategory": "Chip Resistor",
            "componentCount": 1,
            "shards": ["components-resistors_chip-001.jsonl.gz"],
            "browseShards": [],
        },
        {
            "id": 2,
            "category": "ICs",
            "subcategory": "Exotic",
            "componentCount": 1,
            "shards": ["components-ics_exotic-001.jsonl.gz"],
            "browseShards": [],
        },
    ],
    "files": {
        "attributes-lut.json.gz": {"kind": "attributes-lut", "sha256": "abc"},
        "components-resistors_chip-001.jsonl.gz": {
            "kind": "components",
            "sha256": "def",
            "componentCount": 1,
        },
        "components-ics_exotic-001.jsonl.gz": {
            "kind": "components",
            "sha256": "ghi",
            "componentCount": 1,
        },
    },
    "lookupBucketSize": 100000,
    "lookupBuckets": {},
}

# Keep old-format test data for _row_dict_to_part direct tests
SAMPLE_SCHEMA_LIST = [
    "lcsc",
    "mfr",
    "joints",
    "description",
    "datasheet",
    "price",
    "img",
    "url",
    "attributes",
]

RESISTOR_ROW_OLD = [
    "C25804",
    "RC0603FR-0710KL",
    2,
    "10 kOhms +/-1% 0.1W 0603 Chip Resistor",
    "https://example.com/ds.pdf",
    [{"price": 0.0012, "qFrom": 1, "qTo": 99}],
    None,
    None,
    {
        "Basic/Extended": {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["Basic", "string"]},
        },
        "Manufacturer": {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["YAGEO", "string"]},
        },
        "Package": {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["0603", "string"]},
        },
    },
]

EXOTIC_ROW_OLD = [
    "C9000",
    "EXOTIC-CHIP",
    32,
    "Exotic 32-pin mystery chip",
    "",
    [{"price": 5.50, "qFrom": 1, "qTo": 99}],
    None,
    None,
    {
        "Basic/Extended": {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["Extended", "string"]},
        },
        "Manufacturer": {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["Acme Corp", "string"]},
        },
        "Package": {
            "format": "${default}",
            "primary": "default",
            "values": {"default": ["QFN-32", "string"]},
        },
    },
]


def _make_jsonl_gz(schema: dict, records: list) -> bytes:
    """Build gzipped JSONL content (schema line + record lines)."""
    lines = [json.dumps(schema)]
    for rec in records:
        lines.append(json.dumps(rec))
    return gzip.compress("\n".join(lines).encode("utf-8"))


def _make_gzip_response(content: bytes) -> MagicMock:
    """Build a fake httpx.Response carrying already-gzipped content."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.content = content
    resp.json = MagicMock(side_effect=ValueError("gzipped, not JSON"))
    return resp


def _make_json_response(obj, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.content = json.dumps(obj).encode("utf-8")
    resp.json = MagicMock(return_value=obj)
    return resp


def _make_404() -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    resp.content = b""
    resp.json = MagicMock(side_effect=ValueError)
    return resp


def make_fake_client(
    *,
    manifest=SAMPLE_MANIFEST,
    lut=SAMPLE_LUT,
    shards=None,
) -> MagicMock:
    """Build a fake httpx.AsyncClient that serves a full fake mirror.

    ``shards`` is a dict of shard_filename -> (schema, records_list).
    """
    if shards is None:
        shards = {
            "components-resistors_chip-001.jsonl.gz": (SHARD_SCHEMA, [RESISTOR_RECORD]),
            "components-ics_exotic-001.jsonl.gz": (SHARD_SCHEMA, [EXOTIC_RECORD]),
        }

    # Pre-build the gzipped LUT
    lut_gz = gzip.compress(json.dumps(lut).encode("utf-8"))

    # Pre-build the gzipped shard content
    shard_gz = {}
    for filename, (schema, records) in shards.items():
        shard_gz[filename] = _make_jsonl_gz(schema, records)

    client = MagicMock(spec=httpx.AsyncClient)

    async def fake_get(path, params=None, **kwargs):
        if path == "/data/manifest.json":
            return _make_json_response(manifest)
        if path == "/data/attributes-lut.json.gz":
            return _make_gzip_response(lut_gz)
        if path.startswith("/data/") and path.endswith(".jsonl.gz"):
            filename = path.split("/")[-1]
            if filename in shard_gz:
                return _make_gzip_response(shard_gz[filename])
            return _make_404()
        return _make_404()

    client.get = AsyncMock(side_effect=fake_get)
    client.aclose = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Autouse fixture: fresh cache dir per test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Each test gets its own SQLite cache directory."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Attribute-extraction helpers
# ---------------------------------------------------------------------------


class TestExtractAttr:
    def test_reads_primary_default(self):
        attrs = {
            "Package": {
                "primary": "default",
                "values": {"default": ["0603", "string"]},
            }
        }
        assert _extract_attr(attrs, "Package") == "0603"

    def test_reads_primary_identifier(self):
        attrs = {
            "Package": {
                "primary": "identifier",
                "values": {"identifier": ["0603", "identifier"]},
            }
        }
        assert _extract_attr(attrs, "Package") == "0603"

    def test_missing_key_returns_empty(self):
        assert _extract_attr({}, "Package") == ""

    def test_non_dict_safe(self):
        assert _extract_attr("nope", "Package") == ""


class TestExtractBasicFlag:
    def test_basic(self):
        attrs = {
            "Basic/Extended": {"primary": "default", "values": {"default": ["Basic", "string"]}}
        }
        assert _extract_basic_flag(attrs) is True

    def test_extended(self):
        attrs = {
            "Basic/Extended": {"primary": "default", "values": {"default": ["Extended", "string"]}}
        }
        assert _extract_basic_flag(attrs) is False

    def test_missing(self):
        assert _extract_basic_flag({}) is False

    def test_lut_style_catalog_class(self):
        attrs = {
            "Basic/Extended": {
                "primary": "catalog class 1",
                "values": {"catalog class 1": ["Basic", "identifier"]},
            }
        }
        assert _extract_basic_flag(attrs) is True


class TestExtractPrice:
    def test_list_with_entries(self):
        assert _extract_price([{"price": 0.0012, "qFrom": 1}]) == 0.0012

    def test_empty(self):
        assert _extract_price([]) == 0.0

    def test_none(self):
        assert _extract_price(None) == 0.0


# ---------------------------------------------------------------------------
# _resolve_attributes
# ---------------------------------------------------------------------------


class TestResolveAttributes:
    def test_resolves_indices(self):
        result = _resolve_attributes([0, 1, 2], SAMPLE_LUT)
        assert "Basic/Extended" in result
        assert "Manufacturer" in result
        assert "Package" in result
        assert _extract_attr(result, "Package") == "0603"

    def test_none_returns_empty(self):
        assert _resolve_attributes(None, SAMPLE_LUT) == {}

    def test_empty_list(self):
        assert _resolve_attributes([], SAMPLE_LUT) == {}

    def test_out_of_range_skipped(self):
        result = _resolve_attributes([0, 999], SAMPLE_LUT)
        assert len(result) == 1  # only index 0 resolved

    def test_negative_index_skipped(self):
        result = _resolve_attributes([-1, 0], SAMPLE_LUT)
        assert len(result) == 1

    def test_non_int_skipped(self):
        result = _resolve_attributes(["foo", 0], SAMPLE_LUT)
        assert len(result) == 1

    def test_later_entry_overrides_same_name(self):
        result = _resolve_attributes([0, 3], SAMPLE_LUT)
        assert _extract_attr(result, "Basic/Extended") == "Extended"


class TestRowDictToPart:
    def test_resistor(self):
        row_dict = dict(zip(SAMPLE_SCHEMA_LIST, RESISTOR_ROW_OLD))
        part = _row_dict_to_part(
            row_dict, stock=100000, category="Resistors", subcategory="Chip Resistor"
        )
        assert part.lcsc == "C25804"
        assert part.basic is True
        assert part.stock == 100000
        assert part.package == "0603"
        assert part.manufacturer == "YAGEO"
        assert part.price_usd == 0.0012
        assert part.cost_warning() is None

    def test_extended_part(self):
        row_dict = dict(zip(SAMPLE_SCHEMA_LIST, EXOTIC_ROW_OLD))
        part = _row_dict_to_part(row_dict, stock=50, category="ICs", subcategory="Exotic")
        assert part.basic is False
        assert part.tier == "extended"
        warning = part.cost_warning()
        assert warning is not None and "C9000" in warning

    def test_with_resolved_lut_attrs(self):
        resolved = _resolve_attributes([0, 1, 2], SAMPLE_LUT)
        row_dict = {
            "lcsc": "C25804",
            "mfr": "RC0603FR-0710KL",
            "description": "10k resistor",
            "datasheet": "https://example.com/ds.pdf",
            "price": [{"price": 0.0012, "qFrom": 1}],
            "attributes": resolved,
        }
        part = _row_dict_to_part(row_dict, stock=100000, category="Resistors", subcategory="Chip")
        assert part.lcsc == "C25804"
        assert part.basic is True
        assert part.manufacturer == "YAGEO"
        assert part.package == "0603"


# ---------------------------------------------------------------------------
# populate_cache
# ---------------------------------------------------------------------------


class TestPopulateCache:
    @pytest.mark.asyncio
    async def test_full_populate(self):
        client = make_fake_client()
        result = await populate_cache(client=client, force=True)
        assert result["skipped"] is False
        assert result["categories_total"] == 2
        assert result["categories_failed"] == 0
        assert result["parts_inserted"] == 2

    @pytest.mark.asyncio
    async def test_skips_when_fresh(self):
        client = make_fake_client()
        await populate_cache(client=client, force=True)
        result = await populate_cache(client=client, force=False)
        assert result["skipped"] is True

    @pytest.mark.asyncio
    async def test_force_refresh(self):
        client = make_fake_client()
        await populate_cache(client=client, force=True)
        result = await populate_cache(client=client, force=True)
        assert result["skipped"] is False

    @pytest.mark.asyncio
    async def test_manifest_fetch_error_raises(self):
        client = MagicMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.ConnectError("no internet"))
        client.aclose = AsyncMock()
        with pytest.raises(LcscError, match="manifest fetch failed"):
            await populate_cache(client=client, force=True)

    @pytest.mark.asyncio
    async def test_shard_fetch_failure_tolerated(self):
        client = make_fake_client(
            shards={
                "components-resistors_chip-001.jsonl.gz": (SHARD_SCHEMA, [RESISTOR_RECORD]),
                # ICs_Exotic shard is missing from the mock → will 404
            },
        )
        result = await populate_cache(client=client, force=True)
        assert result["categories_failed"] == 1
        assert result["parts_inserted"] == 1

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        client = make_fake_client()
        progress = []
        await populate_cache(client=client, force=True, progress_cb=lambda d, t: progress.append((d, t)))
        assert len(progress) == 2
        assert progress[-1] == (2, 2)

    @pytest.mark.asyncio
    async def test_category_map_applied(self):
        client = make_fake_client()
        await populate_cache(client=client, force=True)
        part = await get_part("C25804", client=client)
        assert part.extra["category"] == "Resistors"
        assert part.extra["subcategory"] == "Chip Resistor"

    @pytest.mark.asyncio
    async def test_lut_fetch_failure_raises(self):
        manifest = {**SAMPLE_MANIFEST, "attributesLut": "nonexistent-lut.json.gz"}
        client = make_fake_client(manifest=manifest)
        with pytest.raises(LcscError, match="Failed to fetch attributes LUT"):
            await populate_cache(client=client, force=True)


# ---------------------------------------------------------------------------
# get_part
# ---------------------------------------------------------------------------


class TestGetPart:
    @pytest.mark.asyncio
    async def test_found(self):
        client = make_fake_client()
        part = await get_part("C25804", client=client)
        assert part.lcsc == "C25804"
        assert part.basic is True

    @pytest.mark.asyncio
    async def test_found_extended(self):
        client = make_fake_client()
        part = await get_part("C9000", client=client)
        assert part.lcsc == "C9000"
        assert part.basic is False
        assert part.manufacturer == "Acme Corp"
        assert part.package == "QFN-32"
        assert part.stock == 50

    @pytest.mark.asyncio
    async def test_invalid_format(self):
        with pytest.raises(LcscError, match="Invalid LCSC"):
            await get_part("not-a-c-number")

    @pytest.mark.asyncio
    async def test_not_in_catalog(self):
        client = make_fake_client()
        with pytest.raises(LcscError, match="not found"):
            await get_part("C99999", client=client)

    @pytest.mark.asyncio
    async def test_second_call_reuses_cache(self):
        client1 = make_fake_client()
        await get_part("C25804", client=client1)
        client2 = MagicMock(spec=httpx.AsyncClient)
        client2.get = AsyncMock(return_value=_make_404())
        client2.aclose = AsyncMock()
        part = await get_part("C25804", client=client2)
        assert part.lcsc == "C25804"
        assert client2.get.call_count == 0


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_finds_basic(self):
        client = make_fake_client()
        results = await search("10k 0603", basic_only=True, client=client)
        assert len(results) == 1
        assert results[0].lcsc == "C25804"

    @pytest.mark.asyncio
    async def test_basic_only_excludes_extended(self):
        client = make_fake_client()
        results = await search("Exotic", basic_only=True, client=client)
        assert results == []

    @pytest.mark.asyncio
    async def test_includes_extended_when_allowed(self):
        client = make_fake_client()
        results = await search("Exotic", basic_only=False, client=client)
        assert len(results) == 1
        assert results[0].lcsc == "C9000"

    @pytest.mark.asyncio
    async def test_package_filter(self):
        client = make_fake_client()
        results = await search("Chip", package="0603", client=client)
        assert all(p.package == "0603" for p in results)

    @pytest.mark.asyncio
    async def test_stock_min(self):
        client = make_fake_client()
        results = await search("chip", stock_min=100, basic_only=False, client=client)
        assert all(p.stock >= 100 for p in results)

    @pytest.mark.asyncio
    async def test_empty_query_returns_nothing(self):
        client = make_fake_client()
        results = await search("   ", client=client)
        assert results == []


# ---------------------------------------------------------------------------
# resolve_bom
# ---------------------------------------------------------------------------


class TestResolveBom:
    @pytest.mark.asyncio
    async def test_resolves_lcsc_rows(self):
        client = make_fake_client()
        result = await resolve_bom([{"lcsc": "C25804", "qty": 10}], client=client)
        assert len(result["resolved"]) == 1
        assert result["unresolved"] == []
        assert result["extended_part_count"] == 0
        assert result["estimated_setup_fee_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_warns_on_extended_part(self):
        client = make_fake_client()
        result = await resolve_bom([{"lcsc": "C9000", "qty": 1}], client=client)
        assert result["extended_part_count"] == 1
        assert result["estimated_setup_fee_usd"] == config.EXTENDED_PART_SETUP_FEE_USD
        assert len(result["resolved"][0]["warnings"]) == 1

    @pytest.mark.asyncio
    async def test_unresolved_collected(self):
        client = make_fake_client()
        result = await resolve_bom([{"lcsc": "C99999", "qty": 1}], client=client)
        assert result["resolved"] == []
        assert len(result["unresolved"]) == 1
        assert "not found" in result["unresolved"][0]["reason"]

    @pytest.mark.asyncio
    async def test_query_row_falls_through_to_search(self):
        client = make_fake_client()
        result = await resolve_bom([{"query": "Exotic chip", "qty": 1}], client=client)
        assert len(result["resolved"]) == 1
        assert result["resolved"][0]["part"]["lcsc"] == "C9000"
        assert result["extended_part_count"] == 1

    @pytest.mark.asyncio
    async def test_query_with_no_match(self):
        client = make_fake_client()
        result = await resolve_bom([{"query": "nothing at all", "qty": 1}], client=client)
        assert result["resolved"] == []
        assert len(result["unresolved"]) == 1

    @pytest.mark.asyncio
    async def test_duplicate_extended_parts_count_once(self):
        client = make_fake_client()
        result = await resolve_bom(
            [
                {"lcsc": "C9000", "qty": 1},
                {"lcsc": "C9000", "qty": 3},
            ],
            client=client,
        )
        assert len(result["resolved"]) == 2
        assert result["extended_part_count"] == 1
        assert result["estimated_setup_fee_usd"] == config.EXTENDED_PART_SETUP_FEE_USD
