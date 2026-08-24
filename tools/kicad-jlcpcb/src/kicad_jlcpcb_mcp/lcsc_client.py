"""LCSC / JLCPCB part query client, backed by the jlcparts data mirror.

The jlcparts project (https://github.com/yaqwsx/jlcparts) publishes a
community-maintained mirror of JLCPCB's own parts catalog at
https://yaqwsx.github.io/jlcparts/data/. The mirror exposes:

  - ``/data/manifest.json``                          — catalog manifest
  - ``/data/attributes-lut.json.gz``                  — attribute lookup table
  - ``/data/components-<name>-NNN.jsonl.gz``          — gzipped JSONL shards
  - ``/data/lookup-NNNNN.json.gz``                    — C-number → shard buckets

Each component shard is gzipped newline-delimited JSON (JSONL):
  - Line 1 is a schema dict mapping field names to array indices::

        {"lcsc":0,"mfr":1,...,"attributes":8,"stock":9,"subcategory":10}

  - Subsequent lines are JSON arrays with values at those indices.

Component attributes are stored as integer indices into the attributes
LUT (a JSON array of ``[name, {format, primary, values}]`` entries).
Stock is inline in each component record.  The manifest's ``categories``
list maps subcategory IDs (referenced by component records) to
human-readable category/subcategory names.

This module downloads the entire dataset on first use (~1 400 shards +
attributes LUT), normalizes every component into the local ``Part``
dataclass, and stores the whole catalog in a SQLite database under
``config.CACHE_DIR / config.LCSC_CACHE_DB``. All subsequent queries are
pure local SQL.

Re-population: the marker file ``<cache_dir>/.jlcparts_populated_at``
holds a unix timestamp.  The cache is considered fresh for
``CACHE_TTL_SECONDS``; after that, the next call to ``get_part`` /
``search`` / ``resolve_bom`` triggers a refresh.  Pass
``force_refresh=True`` to any of those to rebuild now.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import httpx

from . import config

logger = logging.getLogger(__name__)

# Cache freshness for the populated catalog (in seconds).
CACHE_TTL_SECONDS = 7 * 24 * 3600

# Parallelism for the bulk shard fetch.
FETCH_CONCURRENCY = 16

# Per-request timeouts (seconds).
MANIFEST_TIMEOUT = 30.0
SHARD_TIMEOUT = 60.0
ATTRIBUTES_LUT_TIMEOUT = 120.0
LOOKUP_TIMEOUT = 30.0


class LcscError(RuntimeError):
    """An LCSC query failed (network, parse, or unknown C-number)."""


@dataclass
class Part:
    """Normalized representation of a JLCPCB-stocked LCSC part.

    Field names match the original HTTP-era shape so callers (and the
    MCP server's JSON responses) don't have to change.
    """

    lcsc: str  # C-number, e.g. "C25804"
    mfr_part: str  # Manufacturer part number
    manufacturer: str
    description: str
    package: str  # Footprint family, e.g. "0603", "SOT-23-5"
    basic: bool  # True = JLCPCB Basic library (no setup fee)
    stock: int  # Current JLCPCB SMT inventory
    price_usd: float  # Unit price at qty 1 (USD, approximate)
    datasheet_url: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def tier(self) -> str:
        return "basic" if self.basic else "extended"

    def cost_warning(self) -> str | None:
        """Return a human-readable warning if this is an extended part."""
        if self.basic:
            return None
        return (
            f"{self.lcsc} ({self.mfr_part}) is an EXTENDED part. "
            f"JLCPCB charges a one-time ${config.EXTENDED_PART_SETUP_FEE_USD:.2f} "
            f"setup fee per unique extended part on assembled boards."
        )


# ---------------------------------------------------------------------------
# SQLite cache
# ---------------------------------------------------------------------------


def _cache_path() -> Path:
    """Resolve the cache db path lazily so monkeypatched config takes effect."""
    return Path(config.CACHE_DIR) / config.LCSC_CACHE_DB


def _populated_marker() -> Path:
    return Path(config.CACHE_DIR) / ".jlcparts_populated_at"


@contextmanager
def _open_cache():
    """Yield a sqlite3 connection, creating the schema on first use."""
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS parts (
                lcsc TEXT PRIMARY KEY,
                mfr_part TEXT NOT NULL,
                manufacturer TEXT,
                description TEXT,
                package TEXT,
                basic INTEGER NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                price_usd REAL NOT NULL DEFAULT 0,
                datasheet_url TEXT,
                category TEXT,
                subcategory TEXT
            );
            CREATE INDEX IF NOT EXISTS parts_basic ON parts(basic);
            CREATE INDEX IF NOT EXISTS parts_package ON parts(package);
            CREATE INDEX IF NOT EXISTS parts_mfr ON parts(mfr_part);
            CREATE INDEX IF NOT EXISTS parts_desc ON parts(description);
            """
        )
        conn.commit()
        yield conn
    finally:
        conn.close()


def _row_to_part(row: tuple) -> Part:
    """Reconstruct a Part from a SQLite row in the ``parts`` table column order."""
    (
        lcsc,
        mfr_part,
        manufacturer,
        description,
        package,
        basic,
        stock,
        price_usd,
        datasheet_url,
        category,
        subcategory,
    ) = row
    return Part(
        lcsc=lcsc,
        mfr_part=mfr_part or "",
        manufacturer=manufacturer or "",
        description=description or "",
        package=package or "",
        basic=bool(basic),
        stock=int(stock or 0),
        price_usd=float(price_usd or 0),
        datasheet_url=datasheet_url or "",
        extra={"category": category or "", "subcategory": subcategory or ""},
    )


_PARTS_COLUMNS = (
    "lcsc, mfr_part, manufacturer, description, package, basic, stock, "
    "price_usd, datasheet_url, category, subcategory"
)


# ---------------------------------------------------------------------------
# jlcparts JSON → Part conversion
# ---------------------------------------------------------------------------


def _extract_attr(attributes: dict, key: str) -> str:
    """Extract a string attribute from a jlcparts attributes blob.

    Attributes look like::

        {"Package": {"primary": "identifier",
                      "values": {"identifier": ["0603", "identifier"]},
                      "format": "${identifier}"}}
    """
    if not isinstance(attributes, dict):
        return ""
    attr = attributes.get(key)
    if not isinstance(attr, dict):
        return ""
    values = attr.get("values")
    if not isinstance(values, dict):
        return ""
    primary_key = attr.get("primary", "default")
    primary = values.get(primary_key)
    if isinstance(primary, list) and primary:
        return str(primary[0])
    # Fallback: first value in the dict
    for v in values.values():
        if isinstance(v, list) and v:
            return str(v[0])
    return ""


def _extract_basic_flag(attributes: dict) -> bool:
    """Parse the Basic/Extended attribute. Default to False (extended)
    when the field is missing — that's the conservative choice for cost
    estimation."""
    tier = _extract_attr(attributes, "Basic/Extended")
    return tier.strip().lower() == "basic"


def _extract_price(price_field) -> float:
    """jlcparts price is a list of {qFrom, qTo, price} break-points sorted
    ascending. Take the qty=1 tier."""
    if not isinstance(price_field, list) or not price_field:
        return 0.0
    first = price_field[0]
    if not isinstance(first, dict):
        return 0.0
    return float(first.get("price", 0) or 0)


def _resolve_attributes(attr_indices: list | None, lut: list) -> dict:
    """Resolve attribute index list to ``{name: value_obj}`` dict via the LUT.

    Component records store attributes as a list of integer indices into
    the attributes lookup table.  Each LUT entry is ``[name, value_obj]``
    where *value_obj* has the same shape as the old per-component
    attribute dicts (``{format, primary, values}``).

    The returned dict is keyed by attribute name and compatible with
    :func:`_extract_attr` / :func:`_extract_basic_flag`.
    """
    if not isinstance(attr_indices, list):
        return {}
    result: dict = {}
    for idx in attr_indices:
        if not isinstance(idx, int) or idx < 0 or idx >= len(lut):
            continue
        entry = lut[idx]
        if isinstance(entry, list) and len(entry) >= 2:
            result[entry[0]] = entry[1]
    return result


def _row_dict_to_part(
    row_dict: dict,
    stock: int,
    category: str,
    subcategory: str,
) -> Part:
    """Convert one jlcparts component record dict into a Part.

    Accepts both old-style attribute dicts (keys are attribute names
    mapping to ``{format, primary, values}``) and pre-resolved dicts
    produced by :func:`_resolve_attributes`.
    """
    attributes = row_dict.get("attributes") or {}
    return Part(
        lcsc=str(row_dict.get("lcsc", "")),
        mfr_part=str(row_dict.get("mfr", "") or ""),
        manufacturer=_extract_attr(attributes, "Manufacturer"),
        description=str(row_dict.get("description", "") or ""),
        package=_extract_attr(attributes, "Package"),
        basic=_extract_basic_flag(attributes),
        stock=int(stock or 0),
        price_usd=_extract_price(row_dict.get("price")),
        datasheet_url=str(row_dict.get("datasheet") or ""),
        extra={"category": category, "subcategory": subcategory},
    )


# ---------------------------------------------------------------------------
# HTTP client + bulk populate
# ---------------------------------------------------------------------------


def _make_client() -> httpx.AsyncClient:
    """Build the httpx client. Factored out so tests can patch."""
    return httpx.AsyncClient(
        base_url=config.JLCSEARCH_BASE,
        timeout=httpx.Timeout(SHARD_TIMEOUT),
        headers={
            "User-Agent": "kicad-jlcpcb/0.1 (+https://github.com/BeckhamLabsLLC/kicad-jlcpcb)",
            "Accept-Encoding": "gzip",
        },
        follow_redirects=True,
    )


async def _fetch_manifest(client: httpx.AsyncClient) -> dict:
    """Fetch ``/data/manifest.json``. Returns the parsed catalog manifest."""
    try:
        resp = await client.get("/data/manifest.json", timeout=MANIFEST_TIMEOUT)
    except httpx.HTTPError as e:
        raise LcscError(f"jlcparts manifest fetch failed: {e}") from e
    if resp.status_code != 200:
        raise LcscError(f"jlcparts manifest returned HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as e:
        raise LcscError(f"jlcparts manifest is not valid JSON: {e}") from e


async def _fetch_gzipped_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    timeout: float = SHARD_TIMEOUT,
) -> bytes | None:
    """Fetch a gzipped file and return decompressed bytes, or *None* on failure."""
    try:
        resp = await client.get(path, timeout=timeout)
    except httpx.HTTPError as e:
        logger.warning("Fetch %s: %s", path, e)
        return None
    if resp.status_code != 200:
        logger.warning("Fetch %s: HTTP %s", path, resp.status_code)
        return None
    raw = resp.content
    try:
        return gzip.decompress(raw)
    except OSError:
        # Server may have already decompressed via Content-Encoding
        return raw


async def _fetch_attributes_lut(
    client: httpx.AsyncClient, filename: str
) -> list:
    """Fetch the attributes lookup table (gzipped JSON array).

    Returns a list of ``[name, value_obj]`` entries.
    """
    body = await _fetch_gzipped_json(
        client, f"/data/{filename}", timeout=ATTRIBUTES_LUT_TIMEOUT
    )
    if body is None:
        raise LcscError(f"Failed to fetch attributes LUT: {filename}")
    try:
        lut = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise LcscError(f"Attributes LUT parse failed: {e}") from e
    if not isinstance(lut, list):
        raise LcscError(f"Attributes LUT is not a list (got {type(lut).__name__})")
    return lut


async def _fetch_shard(
    client: httpx.AsyncClient, filename: str
) -> dict | None:
    """Fetch a component shard (``.jsonl.gz``).

    Returns ``{"schema": {field: idx, ...}, "records": [[...], ...]}``
    or *None* on failure.  The first JSONL line is the schema dict
    mapping field names to array indices; subsequent lines are component
    record arrays.
    """
    body = await _fetch_gzipped_json(client, f"/data/{filename}")
    if body is None:
        return None
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as e:
        logger.warning("Shard %s: decode failed: %s", filename, e)
        return None
    lines = text.strip().split("\n")
    if not lines:
        return None
    try:
        schema = json.loads(lines[0])
        records = [json.loads(line) for line in lines[1:] if line.strip()]
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Shard %s: parse failed: %s", filename, e)
        return None
    return {"schema": schema, "records": records}


async def _fetch_lookup_bucket(
    client: httpx.AsyncClient, filename: str
) -> dict | None:
    """Fetch a C-number lookup bucket (``{C-number: shard_filename}`` dict)."""
    body = await _fetch_gzipped_json(
        client, f"/data/{filename}", timeout=LOOKUP_TIMEOUT
    )
    if body is None:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        logger.warning("Lookup bucket %s: parse failed: %s", filename, e)
        return None


def _bulk_insert_shard(
    conn: sqlite3.Connection,
    shard_data: dict,
    lut: list,
    category_map: dict[int, tuple[str, str]],
) -> int:
    """Insert every component from a shard into the parts table.

    Returns the count of rows inserted.
    """
    schema = shard_data.get("schema") or {}
    records = shard_data.get("records") or []
    rows: list[tuple] = []
    for record in records:
        if not isinstance(record, list):
            continue
        row_dict: dict = {}
        for key, idx in schema.items():
            if isinstance(idx, int) and 0 <= idx < len(record):
                row_dict[key] = record[idx]

        lcsc = str(row_dict.get("lcsc") or "")
        if not lcsc:
            continue

        raw_attrs = row_dict.get("attributes")
        if isinstance(raw_attrs, list):
            row_dict["attributes"] = _resolve_attributes(raw_attrs, lut)

        sub_id = row_dict.get("subcategory")
        if isinstance(sub_id, int):
            category, subcategory = category_map.get(sub_id, ("", ""))
        else:
            category, subcategory = "", ""

        stock = int(row_dict.get("stock", 0) or 0)
        part = _row_dict_to_part(row_dict, stock, category, subcategory)
        rows.append(
            (
                part.lcsc,
                part.mfr_part,
                part.manufacturer,
                part.description,
                part.package,
                1 if part.basic else 0,
                part.stock,
                part.price_usd,
                part.datasheet_url,
                category,
                subcategory,
            )
        )
    if rows:
        conn.executemany(
            f"INSERT OR REPLACE INTO parts ({_PARTS_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
    return len(rows)


async def populate_cache(
    *,
    client: httpx.AsyncClient | None = None,
    force: bool = False,
    progress_cb=None,
) -> dict:
    """Ensure the local SQLite cache holds the full jlcparts catalog.

    If the cache is fresh (populated within ``CACHE_TTL_SECONDS``) and
    *force* is False, this is a no-op.  Otherwise fetches the manifest,
    attributes LUT, and every component shard in parallel, normalizes
    into Parts, and inserts into SQLite.

    Returns a summary dict.  Raises :class:`LcscError` on manifest or
    LUT fetch failure; individual shard fetch failures are logged and
    counted but don't abort the populate.

    ``progress_cb`` is an optional callable ``progress_cb(done, total)``
    invoked after each shard is written.
    """
    marker = _populated_marker()
    if not force and marker.exists():
        try:
            age = time.time() - float(marker.read_text().strip())
            if age < CACHE_TTL_SECONDS:
                return {
                    "skipped": True,
                    "reason": f"cache age {int(age)}s < TTL {CACHE_TTL_SECONDS}s",
                }
        except ValueError:
            pass  # Marker is corrupt; re-populate

    own_client = client is None
    if own_client:
        client = _make_client()

    try:
        # 1. Fetch catalog manifest
        manifest = await _fetch_manifest(client)

        # 2. Build category map: subcategory ID → (category, subcategory)
        category_map: dict[int, tuple[str, str]] = {}
        for cat in manifest.get("categories", []):
            cat_id = cat.get("id")
            if cat_id is not None:
                category_map[int(cat_id)] = (
                    cat.get("category", ""),
                    cat.get("subcategory", ""),
                )

        # 3. Fetch the attributes lookup table
        lut_filename = manifest.get("attributesLut", "attributes-lut.json.gz")
        lut = await _fetch_attributes_lut(client, lut_filename)

        # 4. Collect all unique component shard filenames
        shard_set: set[str] = set()
        for cat in manifest.get("categories", []):
            for shard_name in cat.get("shards", []):
                shard_set.add(shard_name)
        shards = sorted(shard_set)
        total = len(shards)
        logger.info(
            "jlcparts: populating cache (%d shards, LUT has %d entries)",
            total,
            len(lut),
        )

        # 5. Fetch all shards in parallel
        sem = asyncio.Semaphore(FETCH_CONCURRENCY)

        async def fetch_one(filename):
            async with sem:
                return filename, await _fetch_shard(client, filename)

        results = await asyncio.gather(*(fetch_one(fn) for fn in shards))

        # 6. Insert into SQLite
        with _open_cache() as conn:
            conn.execute("DELETE FROM parts")
            conn.commit()

            rows_inserted = 0
            parse_failures = 0
            done = 0
            for filename, shard_data in results:
                done += 1
                if shard_data is None:
                    parse_failures += 1
                    if progress_cb:
                        progress_cb(done, total)
                    continue
                try:
                    rows_inserted += _bulk_insert_shard(
                        conn, shard_data, lut, category_map
                    )
                except sqlite3.Error as e:
                    logger.warning("Shard %s: insert failed: %s", filename, e)
                    parse_failures += 1
                if progress_cb:
                    progress_cb(done, total)
            conn.commit()

        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(time.time()))

        return {
            "skipped": False,
            "categories_total": total,
            "categories_failed": parse_failures,
            "parts_inserted": rows_inserted,
        }
    finally:
        if own_client:
            await client.aclose()


# ---------------------------------------------------------------------------
# Public query API (unchanged shape from the earlier HTTP-per-part version)
# ---------------------------------------------------------------------------


async def _ensure_cache(client: httpx.AsyncClient | None, force_refresh: bool) -> None:
    """Populate the cache if it's empty or stale. Cheap no-op on hit."""
    await populate_cache(client=client, force=force_refresh)


async def get_part(
    lcsc: str,
    *,
    client: httpx.AsyncClient | None = None,
    force_refresh: bool = False,
) -> Part:
    """Fetch a single part by LCSC C-number.

    Triggers a cache populate on first use. Subsequent calls are
    served directly from SQLite. Raises LcscError if the C-number
    isn't in the catalog after a successful populate.
    """
    if not lcsc.startswith("C") or not lcsc[1:].isdigit():
        raise LcscError(f"Invalid LCSC part number: {lcsc!r}")

    await _ensure_cache(client, force_refresh)

    with _open_cache() as conn:
        row = conn.execute(f"SELECT {_PARTS_COLUMNS} FROM parts WHERE lcsc = ?", (lcsc,)).fetchone()
    if row is None:
        raise LcscError(f"LCSC part not found: {lcsc}")
    return _row_to_part(row)


async def search(
    query: str,
    *,
    package: str | None = None,
    basic_only: bool = True,
    stock_min: int = 1,
    limit: int = 20,
    client: httpx.AsyncClient | None = None,
    force_refresh: bool = False,
) -> list[Part]:
    """Search the cached catalog by free-text query.

    Matches ``query`` against description, mfr_part, and (package) if
    provided.  Sorts basic-first, then by descending stock.  When
    ``basic_only=True``, extended parts are excluded entirely.
    """
    await _ensure_cache(client, force_refresh)

    tokens = [t for t in query.strip().split() if t]
    if not tokens:
        return []

    where_clauses: list[str] = []
    params: list = []
    for tok in tokens:
        where_clauses.append("(description LIKE ? OR mfr_part LIKE ? OR package LIKE ?)")
        wild = f"%{tok}%"
        params.extend([wild, wild, wild])

    if package:
        where_clauses.append("package = ?")
        params.append(package)

    where_clauses.append("stock >= ?")
    params.append(int(stock_min))

    if basic_only:
        where_clauses.append("basic = 1")

    where_sql = " AND ".join(where_clauses)
    sql = (
        f"SELECT {_PARTS_COLUMNS} FROM parts WHERE {where_sql} "
        "ORDER BY basic DESC, stock DESC LIMIT ?"
    )
    params.append(int(limit))

    with _open_cache() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_part(r) for r in rows]


# ---------------------------------------------------------------------------
# BOM resolution (unchanged logic, reads from local SQLite)
# ---------------------------------------------------------------------------


async def resolve_bom(
    rows: Iterable[dict],
    *,
    client: httpx.AsyncClient | None = None,
    force_refresh: bool = False,
) -> dict:
    """Resolve a BOM into concrete parts with cost-impact warnings.

    Each input row is one of::

      {"lcsc": "C25804", "qty": 10}
      {"query": "10k 0603 1%", "qty": 10}
      {"query": "...", "package": "0603", "qty": 5}

    Returns::

      {
        "resolved": [ {row, part, warnings} ... ],
        "unresolved": [ {row, reason} ... ],
        "extended_part_count": int,
        "estimated_setup_fee_usd": float,
        "summary": "..."
      }
    """
    own_client = client is None
    if own_client:
        client = _make_client()
    resolved = []
    unresolved = []
    seen_extended_lcsc = set()
    try:
        await _ensure_cache(client, force_refresh)
        for row in rows:
            try:
                part = await _resolve_one(row, client)
            except LcscError as e:
                unresolved.append({"row": row, "reason": str(e)})
                continue
            warnings = []
            cw = part.cost_warning()
            if cw:
                warnings.append(cw)
                seen_extended_lcsc.add(part.lcsc)
            resolved.append({"row": row, "part": asdict(part), "warnings": warnings})
    finally:
        if own_client:
            await client.aclose()

    setup_fee = len(seen_extended_lcsc) * config.EXTENDED_PART_SETUP_FEE_USD
    return {
        "resolved": resolved,
        "unresolved": unresolved,
        "extended_part_count": len(seen_extended_lcsc),
        "estimated_setup_fee_usd": round(setup_fee, 2),
        "summary": (
            f"Resolved {len(resolved)} of {len(resolved) + len(unresolved)} BOM rows. "
            f"{len(seen_extended_lcsc)} unique extended-tier parts; "
            f"estimated assembly setup fee impact: ${setup_fee:.2f}."
        ),
    }


async def _resolve_one(row: dict, client: httpx.AsyncClient) -> Part:
    """Resolve a single BOM row to a Part."""
    if "lcsc" in row and row["lcsc"]:
        return await get_part(row["lcsc"], client=client)

    query = row.get("query") or row.get("description")
    if not query:
        raise LcscError(f"BOM row has neither 'lcsc' nor 'query': {row}")

    package = row.get("package")
    # Try basic-only first, fall back to allowing extended.
    matches = await search(query, package=package, basic_only=True, limit=1, client=client)
    if matches:
        return matches[0]
    matches = await search(query, package=package, basic_only=False, limit=1, client=client)
    if matches:
        return matches[0]
    raise LcscError(f"No LCSC match for query={query!r} package={package!r}")
