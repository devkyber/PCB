"""Fetch KiCad library files (symbol, footprint, 3D model) for an LCSC part.

Conversion is delegated to `easyeda2kicad`, which reads EasyEDA's
component CAD data and emits fully-detailed KiCad libraries:

  1. `.kicad_sym` symbols with real pin names, numbers, positions, and
     electrical types (not a generic numbered rectangle).
  2. `.kicad_mod` footprints with per-package pad geometry, courtyards,
     silkscreen, and thermal/exposed pads.
  3. `.step` and `.wrl` 3D models, referenced from the footprint so the
     board renders and exports to STEP for mechanical fit checks.

EasyEDA's component data is the canonical source for JLCPCB-stocked
parts because EasyEDA, LCSC, and JLCPCB share a parent company.

Everything installs into <project>/libs/ under one library name
(`jlcpcb`), so a project has exactly three things to register in KiCad:
`jlcpcb.kicad_sym`, `jlcpcb.pretty/`, and `jlcpcb.3dshapes/`.

If `easyeda2kicad` is unavailable or fails on a specific part, we fall
back to the generic placeholder symbol/footprint generators below and
flag it in `FetchResult.warnings` — the pipeline keeps moving, but the
result needs manual review before fabrication.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from . import config
from .lcsc_client import get_part

logger = logging.getLogger(__name__)

# EasyEDA's component info endpoint. Returns the raw schematic symbol +
# footprint data that the EasyEDA web app uses to render previews. We use
# it for two things:
#   1. Pin-number → pin-name maps (via `part_pin_map`), so the LLM can
#      write nets like `("U1", "GPIO10")` instead of guessing pin numbers.
#   2. Placeholder symbol/footprint generation inside `fetch_part_library`.
#
# Rate-limited to roughly 1 request/minute per IP after the first burst.
# We enforce client-side throttling via a last-hit timestamp and cache
# responses in SQLite so each unique C-number is fetched exactly once.
EASYEDA_COMPONENT_URL = "https://easyeda.com/api/products/{lcsc}/components"

EASYEDA_HEADERS = {
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://easyeda.com/",
    "X-Requested-With": "XMLHttpRequest",
}

# Minimum delay between back-to-back EasyEDA requests. Empirical: the
# service tolerates roughly 1 req/minute per IP after an initial burst.
# We target ~12s between requests so a 10-part BOM takes ~2 min to warm
# the cache on first run, then instant forever after.
EASYEDA_MIN_DELAY_SECONDS = 12.0


class EasyEdaRateLimiter:
    """Throttle EasyEDA component fetches to 1 request per ``EASYEDA_MIN_DELAY_SECONDS``.

    State is process-local (no cross-worker coordination). That is fine
    because the MCP server runs in a single process, and EasyEDA's
    anti-bot quota is applied per IP, not per connection.

    The delay is read from the module-level constant each time so tests
    can set it to 0 via ``monkeypatch.setattr(part_library,
    "EASYEDA_MIN_DELAY_SECONDS", 0.0)`` without replacing the limiter.
    """

    def __init__(self) -> None:
        self.last_request_time: float = 0.0
        self.lock: asyncio.Lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until the min-delay window has elapsed since the last acquire."""
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_request_time
            if elapsed < EASYEDA_MIN_DELAY_SECONDS:
                wait = EASYEDA_MIN_DELAY_SECONDS - elapsed
                logger.info("EasyEDA rate limit: sleeping %.1fs before next request", wait)
                await asyncio.sleep(wait)
            self.last_request_time = time.monotonic()

    async def backoff(self, seconds: float) -> None:
        """Hard backoff (used after a 403); resets the timing window on resume."""
        async with self.lock:
            await asyncio.sleep(seconds)
            self.last_request_time = time.monotonic()


# Process-local singleton. Tests that need the limiter reset between cases
# should set ``_limiter.last_request_time = 0.0`` in a fixture.
_limiter = EasyEdaRateLimiter()


@dataclass
class FetchResult:
    """What got installed for one LCSC part.

    ``symbol_name`` / ``footprint_name`` are the library-internal IDs
    (e.g. ``ME6211C33M5G-N`` and ``SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL``),
    which is what a schematic or PCB spec must reference — not the file
    paths. ``fidelity`` is ``"real"`` when easyeda2kicad produced the
    files and ``"placeholder"`` when we fell back to a generic outline.
    """

    lcsc: str
    symbol_path: Path | None = None
    footprint_path: Path | None = None
    model_3d_path: Path | None = None
    symbol_name: str | None = None
    footprint_name: str | None = None
    pin_count: int = 0
    fidelity: str = "placeholder"
    warnings: list[str] = field(default_factory=list)
    # Populated only by `fetch_part_library_verified` — plain
    # `fetch_part_library` leaves these at their defaults.
    requested_lcsc: str | None = None
    substituted: bool = False
    mpn_verified: bool | None = None
    candidates_tried: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "lcsc": self.lcsc,
            "symbol_path": str(self.symbol_path) if self.symbol_path else None,
            "footprint_path": str(self.footprint_path) if self.footprint_path else None,
            "model_3d_path": str(self.model_3d_path) if self.model_3d_path else None,
            "symbol_name": self.symbol_name,
            "footprint_name": self.footprint_name,
            "pin_count": self.pin_count,
            "fidelity": self.fidelity,
            "warnings": self.warnings,
            "requested_lcsc": self.requested_lcsc,
            "substituted": self.substituted,
            "mpn_verified": self.mpn_verified,
            "candidates_tried": self.candidates_tried,
        }


class PartLibraryError(RuntimeError):
    """Fetch / convert / install failed."""


# ---------------------------------------------------------------------------
# Pin-map cache (SQLite alongside the LCSC parts cache)
# ---------------------------------------------------------------------------


def _pinmap_cache_path() -> Path:
    """Resolve the cache db path for pin maps. Lazy so monkeypatch works."""
    return Path(config.CACHE_DIR) / "easyeda_pinmaps.sqlite"


@contextmanager
def _open_pinmap_cache():
    path = _pinmap_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pinmaps (
                lcsc TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()
        yield conn
    finally:
        conn.close()


def _pinmap_from_cache(lcsc: str) -> dict | None:
    with _open_pinmap_cache() as conn:
        row = conn.execute("SELECT payload FROM pinmaps WHERE lcsc = ?", (lcsc,)).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def _pinmap_to_cache(lcsc: str, payload: dict) -> None:
    with _open_pinmap_cache() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pinmaps (lcsc, payload, fetched_at) VALUES (?, ?, ?)",
            (lcsc, json.dumps(payload), int(time.time())),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Pin map extraction from EasyEDA's shape array
# ---------------------------------------------------------------------------


def parse_pinmap_from_shape(shape_list: list) -> dict[str, str]:
    """Extract {pin_name: pin_num} from an EasyEDA dataStr.shape array.

    EasyEDA's shape entries for pins have the format:

        P~<show>~<electric>~<pinNum>~<x>~<y>~<rot>~<id>~<locked>
         ^^<pathStart>
         ^^<pathDrawing>~<color>
         ^^<nameShow>~<nx>~<ny>~<nr>~<pinName>~<anchor>~<?>~<?>~<nameColor>
         ^^<numShow>~<numx>~<numy>~<numr>~<pinNum>~<anchor>~<?>~<?>~<numColor>
         ...

    Segments are joined by `^^`. Within each segment, fields are `~`-separated.
    We extract pin_num from segment 0 position 3 and pin_name from segment 3
    position 4. Entries with empty names are skipped.

    Returns an empty dict if no pins are found (common for passives and
    connectors where EasyEDA doesn't name the pins).
    """
    pinmap: dict[str, str] = {}
    if not isinstance(shape_list, list):
        return pinmap
    for s in shape_list:
        if not isinstance(s, str) or not s.startswith("P~"):
            continue
        segs = s.split("^^")
        if len(segs) < 4:
            continue
        seg0 = segs[0].split("~")
        seg3 = segs[3].split("~")
        if len(seg0) < 4 or len(seg3) < 5:
            continue
        pin_num = seg0[3].strip()
        pin_name = seg3[4].strip()
        if pin_num and pin_name:
            # Later entries with same name overwrite earlier — shouldn't
            # happen in practice since EasyEDA assigns unique names, but
            # keep the pinmap keyed by name so nets can reference it.
            pinmap[pin_name] = pin_num
    return pinmap


# ---------------------------------------------------------------------------
# Rate-limited EasyEDA fetch
# ---------------------------------------------------------------------------


async def _fetch_easyeda_raw(lcsc: str, client: httpx.AsyncClient) -> dict:
    """Low-level EasyEDA fetch with rate limiting and one-shot retry on 403.

    Returns the parsed ``result`` dict. Raises :class:`PartLibraryError`
    on unrecoverable failure.
    """
    await _limiter.acquire()

    url = EASYEDA_COMPONENT_URL.format(lcsc=lcsc)
    for attempt in (1, 2):
        try:
            resp = await client.get(url, headers=EASYEDA_HEADERS, timeout=15.0)
        except httpx.HTTPError as e:
            raise PartLibraryError(f"EasyEDA network error for {lcsc}: {e}") from e
        if resp.status_code == 200:
            break
        if resp.status_code == 403 and attempt == 1:
            # Rate-limited despite our throttling; back off hard and retry once
            logger.warning("EasyEDA 403 for %s, backing off 60s", lcsc)
            await _limiter.backoff(60.0)
            continue
        if resp.status_code == 404:
            raise PartLibraryError(f"EasyEDA has no component data for {lcsc}")
        raise PartLibraryError(f"EasyEDA returned HTTP {resp.status_code} for {lcsc}")

    try:
        data = resp.json()
    except ValueError as e:
        raise PartLibraryError(f"EasyEDA returned non-JSON for {lcsc}: {e}") from e
    if not isinstance(data, dict) or data.get("success") is False:
        raise PartLibraryError(
            f"EasyEDA component fetch unsuccessful for {lcsc}: "
            f"{data.get('result') if isinstance(data, dict) else 'malformed'}"
        )
    return data.get("result", data)


# ---------------------------------------------------------------------------
# Public API for pin maps
# ---------------------------------------------------------------------------


async def get_pin_map(
    lcsc: str,
    *,
    client: httpx.AsyncClient | None = None,
    force_refresh: bool = False,
) -> dict:
    """Return the pin-name → pad-number map for an LCSC C-number.

    Hits the SQLite cache first. On cache miss, fetches from EasyEDA with
    client-side rate limiting (minimum 12s between requests) and writes
    the result to cache indefinitely.

    Returns:
      {
        "lcsc": "C82942",
        "title": "ME6211C33M5G-N",
        "pin_count": 5,
        "pinmap": {"VIN": "1", "VSS": "2", "CE": "3", "NC": "4", "VOUT": "5"},
        "pad_to_name": {"1": "VIN", "2": "VSS", ...},   # reverse lookup
        "source": "cache" | "easyeda"
      }

    Raises PartLibraryError on unrecoverable fetch failure. An empty
    pinmap (e.g. passives without named pins) is a valid successful
    result — the caller can use bare pad numbers instead.
    """
    if not lcsc.startswith("C") or not lcsc[1:].isdigit():
        raise PartLibraryError(f"Invalid LCSC part number: {lcsc!r}")

    if not force_refresh:
        cached = _pinmap_from_cache(lcsc)
        if cached is not None:
            cached["source"] = "cache"
            return cached

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True)
    try:
        result = await _fetch_easyeda_raw(lcsc, client)
        title = result.get("title", "")
        shape = result.get("dataStr", {}).get("shape", [])
        pinmap = parse_pinmap_from_shape(shape)
        pad_to_name = {v: k for k, v in pinmap.items()}

        payload = {
            "lcsc": lcsc,
            "title": title,
            "pin_count": len(pinmap),
            "pinmap": pinmap,
            "pad_to_name": pad_to_name,
        }
        _pinmap_to_cache(lcsc, payload)
        payload["source"] = "easyeda"
        return payload
    finally:
        if own_client:
            await client.aclose()


async def get_pin_maps(
    lcscs: list[str],
    *,
    client: httpx.AsyncClient | None = None,
    force_refresh: bool = False,
) -> dict[str, dict]:
    """Bulk variant. Fetches in order (respecting rate limits) and returns
    a dict keyed by C-number. Individual failures are captured as
    `{"error": "..."}` entries so one bad part doesn't blow up the whole
    BOM resolution."""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True)
    try:
        results: dict[str, dict] = {}
        for lcsc in lcscs:
            try:
                results[lcsc] = await get_pin_map(lcsc, client=client, force_refresh=force_refresh)
            except PartLibraryError as e:
                results[lcsc] = {"lcsc": lcsc, "error": str(e), "pinmap": {}}
        return results
    finally:
        if own_client:
            await client.aclose()


# ---------------------------------------------------------------------------
# EasyEDA fetch
# ---------------------------------------------------------------------------


async def _fetch_easyeda_component(lcsc: str, client: httpx.AsyncClient) -> dict:
    """Fetch raw EasyEDA component JSON for an LCSC part."""
    url = EASYEDA_COMPONENT_URL.format(lcsc=lcsc)
    try:
        resp = await client.get(url)
    except httpx.HTTPError as e:
        raise PartLibraryError(f"EasyEDA fetch failed for {lcsc}: {e}") from e
    if resp.status_code == 404:
        raise PartLibraryError(f"EasyEDA has no component data for {lcsc}")
    if resp.status_code != 200:
        raise PartLibraryError(f"EasyEDA returned HTTP {resp.status_code} for {lcsc}")
    try:
        data = resp.json()
    except ValueError as e:
        raise PartLibraryError(f"EasyEDA returned non-JSON for {lcsc}: {e}") from e
    if not isinstance(data, dict) or data.get("success") is False:
        raise PartLibraryError(
            f"EasyEDA component fetch unsuccessful for {lcsc}: {data.get('result') if isinstance(data, dict) else 'malformed'}"
        )
    return data.get("result", data)


# ---------------------------------------------------------------------------
# Symbol generation
# ---------------------------------------------------------------------------


def _safe_id(name: str) -> str:
    """Sanitize a name for use in KiCad library/symbol identifiers."""
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in name)


def _build_kicad_symbol(lcsc: str, mfr_part: str, description: str, pin_count: int) -> str:
    """Generate a placeholder KiCad 8 symbol library file.

    A correct KiCad symbol requires the full pin map (positions, names,
    numbers, electrical type) which EasyEDA stores in a proprietary
    schematic format that's outside Phase 1's scope. Instead we emit a
    *generic rectangular* symbol with `pin_count` numbered pins so the
    user can use it in a schematic and KiCad will accept it for ERC.

    The symbol library file (`.kicad_sym`) holds one symbol named after
    the LCSC C-number; we set the LCSC field on the symbol so a future
    BOM export picks it up.
    """
    symbol_name = _safe_id(lcsc)
    safe_desc = description.replace('"', "'")
    safe_mfr = mfr_part.replace('"', "'")
    half = max(1, pin_count) * 50  # 50 mil per pin spacing
    pins = []
    for i in range(1, max(1, pin_count) + 1):
        # Alternate pins between left side (odd) and right side (even).
        if i % 2 == 1:
            x = -300
            y = half - ((i // 2) * 100)
            angle = 0
        else:
            x = 300
            y = half - (((i - 1) // 2) * 100)
            angle = 180
        pins.append(
            f"    (pin passive line (at {x} {y} {angle}) (length 100)\n"
            f'      (name "P{i}" (effects (font (size 1.27 1.27))))\n'
            f'      (number "{i}" (effects (font (size 1.27 1.27)))))\n'
        )
    pins_block = "".join(pins)

    return (
        '(kicad_symbol_lib (version 20231120) (generator "kicad_jlcpcb_mcp")\n'
        f'  (symbol "{symbol_name}"\n'
        "    (in_bom yes) (on_board yes)\n"
        f'    (property "Reference" "U" (at 0 {half + 100} 0) (effects (font (size 1.27 1.27))))\n'
        f'    (property "Value" "{symbol_name}" (at 0 {half + 50} 0) (effects (font (size 1.27 1.27))))\n'
        f'    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (property "Description" "{safe_desc}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (property "LCSC" "{lcsc}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (property "MPN" "{safe_mfr}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (symbol "{symbol_name}_0_1"\n'
        f"      (rectangle (start -300 {half}) (end 300 -{half})\n"
        "        (stroke (width 0.254) (type default))\n"
        "        (fill (type background)))\n"
        "    )\n"
        f'    (symbol "{symbol_name}_1_1"\n'
        f"{pins_block}"
        "    )\n"
        "  )\n"
        ")\n"
    )


# ---------------------------------------------------------------------------
# Footprint generation
# ---------------------------------------------------------------------------


def _build_kicad_footprint(lcsc: str, mfr_part: str, package: str, pin_count: int) -> str:
    """Generate a placeholder KiCad 8 footprint (.kicad_mod).

    Like the symbol, this is a *generic* footprint sized for the package
    family rather than a per-package-correct one. For Phase 1 the user
    is expected to either:
      (a) accept the generic footprint and verify it in KiCad before
          routing, or
      (b) drop in a hand-picked footprint from KiCad's standard libraries
          and use this only for the symbol/LCSC linkage.

    Footprint dimensions follow IPC nominals for common SMD packages.
    """
    name = _safe_id(f"{lcsc}_{package}")
    pads_block = _generate_pads_for_package(package, pin_count)
    return (
        f'(footprint "{name}"\n'
        "  (version 20231120)\n"
        '  (generator "kicad_jlcpcb_mcp")\n'
        '  (layer "F.Cu")\n'
        "  (attr smd)\n"
        f'  (property "Reference" "REF**" (at 0 -3 0) (layer "F.SilkS"))\n'
        f'  (property "Value" "{name}" (at 0 3 0) (layer "F.Fab"))\n'
        f"{pads_block}"
        ")\n"
    )


def _generate_pads_for_package(package: str, pin_count: int) -> str:
    """Generate IPC-nominal SMD pads for common package families.

    Falls back to a generic SMD pad grid for unknown packages.
    """
    pkg = package.upper().strip()

    # 2-pin chip resistors/caps: 0402, 0603, 0805, 1206
    chip_dimensions = {
        "0402": (0.6, 0.6, 0.95),
        "0603": (0.85, 0.85, 1.55),
        "0805": (1.1, 1.4, 1.85),
        "1206": (1.2, 1.8, 2.7),
    }
    if pkg in chip_dimensions:
        pad_w, pad_h, pitch = chip_dimensions[pkg]
        return (
            f'  (pad "1" smd roundrect (at -{pitch / 2} 0) (size {pad_w} {pad_h}) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))\n'
            f'  (pad "2" smd roundrect (at {pitch / 2} 0) (size {pad_w} {pad_h}) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))\n'
        )

    # SOT-23 family
    if pkg.startswith("SOT-23"):
        n = pin_count or 3
        pads = []
        for i in range(n):
            # Three pins on the wide side, then 2 pins opposite for SOT-23-5
            if i < (n + 1) // 2:
                x = -0.95 + (i * 0.95)
                y = 1.1
            else:
                idx = i - (n + 1) // 2
                x = 0.95 - (idx * 0.95)
                y = -1.1
            pads.append(
                f'  (pad "{i + 1}" smd roundrect (at {x:.3f} {y:.3f}) (size 0.6 0.9) '
                f'(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))\n'
            )
        return "".join(pads)

    # Generic SMD grid: rows of `pin_count // 2` pins on each side at 0.5mm pitch
    n = max(2, pin_count or 2)
    pitch = 0.5
    side = max(1, n // 2)
    pads = []
    for i in range(n):
        if i < side:
            x = -1.5
            y = -((side - 1) * pitch / 2) + (i * pitch)
        else:
            x = 1.5
            j = i - side
            y = ((side - 1) * pitch / 2) - (j * pitch)
        pads.append(
            f'  (pad "{i + 1}" smd roundrect (at {x:.3f} {y:.3f}) (size 0.3 0.6) '
            f'(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))\n'
        )
    return "".join(pads)


# ---------------------------------------------------------------------------
# easyeda2kicad conversion (the real symbol/footprint/3D-model path)
# ---------------------------------------------------------------------------

# One library name for everything a project pulls from LCSC, so KiCad
# only needs three registrations: the .kicad_sym, the .pretty, the
# .3dshapes. Changing this renames all three in lockstep.
LIB_NAME = "jlcpcb"

# .kicad_sym format version to seed new libraries with. 20251024 is the
# KiCad 10 format; easyeda2kicad down-converts automatically when it
# finds an older version already in the file, so an existing library
# from an older KiCad keeps working.
KICAD_SYM_VERSION = 20251024

# Footprints reference their 3D model through this path, which KiCad
# expands relative to the project file. Keeps the project relocatable.
MODEL_3D_REF = "${KIPRJMOD}/libs/" + LIB_NAME + ".3dshapes"


def _convert_with_easyeda2kicad(lcsc: str, libs: Path, *, want_3d: bool = True) -> dict:
    """Convert one LCSC part to real KiCad libraries. Blocking — call via a thread.

    Returns a dict with symbol/footprint/model paths and names. Raises
    :class:`PartLibraryError` if the part has no EasyEDA CAD data or the
    conversion fails, so the caller can fall back to a placeholder.

    easyeda2kicad is imported lazily: it is an optional dependency, and a
    missing install should degrade to the placeholder path rather than
    breaking the whole MCP server at import time.
    """
    try:
        from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
        from easyeda2kicad.easyeda.easyeda_importer import (
            Easyeda3dModelImporter,
            EasyedaFootprintImporter,
            EasyedaSymbolImporter,
        )
        from easyeda2kicad.kicad.export_kicad_3d_model import Exporter3dModelKicad
        from easyeda2kicad.kicad.export_kicad_footprint import ExporterFootprintKicad
        from easyeda2kicad.kicad.export_kicad_symbol import ExporterSymbolKicad
    except ImportError as e:  # pragma: no cover - depends on install state
        raise PartLibraryError(
            f"easyeda2kicad is not installed ({e}); cannot build real libraries"
        ) from e

    api = EasyedaApi()
    try:
        cad = api.get_cad_data_of_component(lcsc_id=lcsc)
    except Exception as e:  # easyeda2kicad raises bare urllib/ssl errors
        raise PartLibraryError(f"EasyEDA CAD fetch failed for {lcsc}: {e}") from e
    if not cad:
        raise PartLibraryError(f"EasyEDA has no CAD data for {lcsc}")

    libs.mkdir(parents=True, exist_ok=True)
    sym_path = libs / f"{LIB_NAME}.kicad_sym"
    pretty = libs / f"{LIB_NAME}.pretty"
    shapes = libs / f"{LIB_NAME}.3dshapes"

    # Seed the symbol library at the newest format version. Once it
    # exists, easyeda2kicad reads the version back out and matches it.
    if not sym_path.exists():
        sym_path.write_text(
            f"(kicad_symbol_lib\n  (version {KICAD_SYM_VERSION})\n"
            f"  (generator kicad_jlcpcb_mcp)\n)",
            encoding="utf-8",
        )

    try:
        ee_symbol = EasyedaSymbolImporter(easyeda_cp_cad_data=cad).get_symbol()
        ExporterSymbolKicad(symbol=ee_symbol, lib_path=str(sym_path)).save_to_lib(
            lib_path=str(sym_path), footprint_lib_name=LIB_NAME, overwrite=True
        )

        ee_footprint = EasyedaFootprintImporter(easyeda_cp_cad_data=cad).get_footprint()
        pretty.mkdir(parents=True, exist_ok=True)
        fp_path = pretty / f"{ee_footprint.info.name}.kicad_mod"
        ExporterFootprintKicad(footprint=ee_footprint).export(
            footprint_full_path=str(fp_path),
            model_3d_path=MODEL_3D_REF,
        )
    except PartLibraryError:
        raise
    except Exception as e:
        raise PartLibraryError(f"easyeda2kicad conversion failed for {lcsc}: {e}") from e

    warnings: list[str] = []
    model_path: Path | None = None
    if want_3d:
        try:
            model = Easyeda3dModelImporter(
                easyeda_cp_cad_data=cad, download_raw_3d_model=True, api=api
            ).output
            if model is not None and Exporter3dModelKicad(model_3d=model).export(
                output_dir=str(shapes)
            ):
                # export() writes <name>.step and <name>.wrl; report the
                # STEP since that is what mechanical CAD consumes.
                candidate = shapes / f"{model.name}.step"
                model_path = candidate if candidate.exists() else None
            else:
                warnings.append(f"No 3D model available on EasyEDA for {lcsc}")
        except Exception as e:
            warnings.append(f"3D model fetch failed for {lcsc}: {e}")

    return {
        "symbol_path": sym_path,
        "footprint_path": fp_path,
        "model_3d_path": model_path,
        "symbol_name": ee_symbol.info.name,
        "footprint_name": ee_footprint.info.name,
        "pin_count": len(ee_footprint.pads),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_part_library(
    lcsc: str,
    libs_dir: str | Path,
    *,
    client: httpx.AsyncClient | None = None,
    want_3d: bool = True,
) -> FetchResult:
    """Install symbol + footprint + 3D model for `lcsc` into `libs_dir`.

    The primary path converts EasyEDA's CAD data via easyeda2kicad,
    producing pin-accurate symbols, per-package footprints, and STEP/WRL
    3D models. If that fails for any reason — part not in EasyEDA,
    network down, easyeda2kicad not installed — we fall back to a generic
    placeholder symbol/footprint so the rest of the pipeline proceeds,
    and set ``fidelity="placeholder"`` plus a warning. A placeholder
    result must be reviewed in KiCad before the board is fabricated.
    """
    if not lcsc.startswith("C") or not lcsc[1:].isdigit():
        raise PartLibraryError(f"Invalid LCSC part number: {lcsc!r}")

    libs = Path(libs_dir).expanduser().resolve()
    libs.mkdir(parents=True, exist_ok=True)

    # Real conversion first. easyeda2kicad is synchronous and does its
    # own HTTP, so it runs in a thread and goes through our rate limiter
    # to stay inside EasyEDA's per-IP quota.
    #
    # Note this deliberately does NOT depend on `get_part`: EasyEDA is
    # the source of truth for CAD data, and the LCSC metadata index is a
    # separate service that can be down or restructured without any
    # bearing on whether we can build correct libraries.
    await _limiter.acquire()
    try:
        converted = await asyncio.to_thread(
            _convert_with_easyeda2kicad, lcsc, libs, want_3d=want_3d
        )
        return FetchResult(
            lcsc=lcsc,
            symbol_path=converted["symbol_path"],
            footprint_path=converted["footprint_path"],
            model_3d_path=converted["model_3d_path"],
            symbol_name=converted["symbol_name"],
            footprint_name=converted["footprint_name"],
            pin_count=converted["pin_count"],
            fidelity="real",
            warnings=converted["warnings"],
        )
    except PartLibraryError as e:
        logger.warning("easyeda2kicad failed for %s, using placeholder: %s", lcsc, e)
        placeholder_reason = str(e)

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            headers={"User-Agent": "kicad-jlcpcb/0.1"},
        )

    warnings: list[str] = [
        f"PLACEHOLDER LIBRARY — pins and pads are generic, not the real part. "
        f"Verify in KiCad before fabricating. Reason: {placeholder_reason}"
    ]

    # Metadata is cosmetic here (symbol Value/Description fields), so a
    # failing LCSC index must not turn a degraded result into no result.
    try:
        part = await get_part(lcsc, client=client)
        mfr_part, description, package = part.mfr_part, part.description, part.package
    except Exception as e:
        warnings.append(f"LCSC metadata unavailable for {lcsc}: {e}")
        mfr_part, description, package = "", "", ""

    pin_count = 2  # default for 2-terminal passives
    has_3d_model = False
    model_url = ""
    try:
        try:
            ee = await _fetch_easyeda_component(lcsc, client)
            # EasyEDA's pin info lives under symbol.shape with type 'P';
            # we just count entries to get the pin count and detect 3D.
            shapes = ee.get("dataStr", {}).get("shape", [])
            if isinstance(shapes, list) and shapes:
                pin_count = sum(1 for s in shapes if isinstance(s, str) and s.startswith("P~"))
                if pin_count == 0:
                    pin_count = 2
            model_block = ee.get("packageDetail", {}).get("dataStr", {}).get("shape", [])
            for block in model_block if isinstance(model_block, list) else []:
                if isinstance(block, str) and block.startswith("SVGNODE"):
                    has_3d_model = True
                    break
            # Best-effort 3D model URL
            uuid = ee.get("packageDetail", {}).get("dataStr", {}).get("head", {}).get("uuid", "")
            if has_3d_model and uuid:
                model_url = f"https://modules.easyeda.com/3dmodel/{uuid}"
        except PartLibraryError as e:
            warnings.append(
                f"Could not fetch EasyEDA component data: {e}. "
                f"Using a generic 2-pin symbol/footprint placeholder."
            )

        symbol_text = _build_kicad_symbol(
            lcsc=lcsc,
            mfr_part=mfr_part,
            description=description,
            pin_count=pin_count,
        )
        footprint_text = _build_kicad_footprint(
            lcsc=lcsc,
            mfr_part=mfr_part,
            package=package,
            pin_count=pin_count,
        )

        sym_path = libs / f"{_safe_id(lcsc)}.kicad_sym"
        sym_path.write_text(symbol_text)

        # Footprints in KiCad live in .pretty directories.
        pretty = libs / "kicad_jlcpcb.pretty"
        pretty.mkdir(exist_ok=True)
        fp_path = pretty / f"{_safe_id(lcsc)}_{_safe_id(package or 'GEN')}.kicad_mod"
        fp_path.write_text(footprint_text)

        model_path: Path | None = None
        if has_3d_model and model_url:
            try:
                m = await client.get(model_url)
                if m.status_code == 200:
                    models_dir = libs / "3d"
                    models_dir.mkdir(exist_ok=True)
                    model_path = models_dir / f"{_safe_id(lcsc)}.obj"
                    model_path.write_bytes(m.content)
                else:
                    warnings.append(f"3D model fetch returned HTTP {m.status_code}")
            except httpx.HTTPError as e:
                warnings.append(f"3D model fetch failed: {e}")

        return FetchResult(
            lcsc=lcsc,
            symbol_path=sym_path,
            footprint_path=fp_path,
            model_3d_path=model_path,
            symbol_name=_safe_id(lcsc),
            footprint_name=_safe_id(f"{lcsc}_{package}"),
            pin_count=pin_count,
            fidelity="placeholder",
            warnings=warnings,
        )
    finally:
        if own_client:
            await client.aclose()


# ---------------------------------------------------------------------------
# MPN-verified fetch with automatic alternate-listing fallback
# ---------------------------------------------------------------------------
#
# Two failure modes came up sourcing a real BOM (TMS V3) that plain
# `fetch_part_library` can't recover from on its own:
#
#   1. The exact LCSC listing has no EasyEDA CAD data (delisted part, or
#      just never got converted), but a *different* listing of the same
#      manufacturer part number — a different reseller/batch under its
#      own C-number — does. LCSC frequently carries several listings for
#      one MPN.
#   2. The caller's C-number is simply wrong (typo'd, stale, mismatched
#      from a datasheet) and happens to resolve to a real but *unrelated*
#      part. EasyEDA/LCSC's data is internally consistent — the symbol it
#      returns really is what that C-number sells — so nothing about the
#      "real" result looks broken; only a check against the part the
#      caller actually meant to fetch catches it.
#
# `fetch_part_library_verified` wraps `fetch_part_library` with that
# check: given the manufacturer part number the caller expects, it
# fetches the requested C-number, and if the fidelity isn't "real" or the
# fetched part doesn't match, searches LCSC by MPN and retries candidates
# (highest stock first) until one converts cleanly and matches, or the
# candidates are exhausted.


def _normalize_mpn(s: str) -> str:
    """Collapse an MPN/symbol name to bare alphanumerics for comparison.

    Strips packaging/taping suffixes, punctuation, and case so
    "PESD5V0S2BT,215" and "PESD5V0S2BT" compare equal, without needing a
    manufacturer-specific suffix table.
    """
    return "".join(ch for ch in s.upper() if ch.isalnum())


def _mpn_matches(expected: str, actual: str) -> bool:
    """True if `actual` plausibly refers to the same part as `expected`.

    Containment rather than equality in either direction: MPNs commonly
    differ by a trailing taping/packaging code (`ADS1220IPWR` vs
    `ADS1220IPWR.` or `PESD5V0S2BT` vs `PESD5V0S2BT,215`) without being a
    different part. An empty side means there's nothing to check against,
    so it passes rather than blocking the pipeline on missing metadata.
    """
    if not expected or not actual:
        return True
    e, a = _normalize_mpn(expected), _normalize_mpn(actual)
    if not e or not a:
        return True
    return e in a or a in e


async def _lookup_mfr_part(lcsc: str, client: httpx.AsyncClient) -> str | None:
    """Best-effort MPN lookup for a C-number; None (not False) on failure."""
    try:
        part = await get_part(lcsc, client=client)
    except Exception:
        return None
    return part.mfr_part


async def fetch_part_library_verified(
    lcsc: str,
    libs_dir: str | Path,
    *,
    expected_mfr_part: str | None = None,
    client: httpx.AsyncClient | None = None,
    want_3d: bool = True,
    max_candidates: int = 5,
) -> FetchResult:
    """`fetch_part_library` plus automatic MPN verification and fallback.

    Pass the manufacturer part number you actually intend to source as
    `expected_mfr_part` (e.g. from a BOM row or the user's request). The
    result is checked against it; on a placeholder or a mismatch, LCSC is
    searched for alternate listings of that MPN and each candidate (by
    descending stock) is tried in turn via `fetch_part_library` until one
    comes back `fidelity="real"` and MPN-matching.

    Without `expected_mfr_part`, this behaves exactly like
    `fetch_part_library` — there is nothing to verify against, so no
    search fallback is attempted.

    The returned `FetchResult` always reflects what actually got
    installed (its `lcsc`/`symbol_name`/`footprint_name` may differ from
    the requested `lcsc` if a substitution happened); `requested_lcsc`
    and `substituted` record the original ask, and `candidates_tried`
    lists every C-number attempted, for the caller to report back.
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True)
    try:
        tried: list[str] = [lcsc]
        result = await fetch_part_library(lcsc, libs_dir, client=client, want_3d=want_3d)
        result.requested_lcsc = lcsc

        if not expected_mfr_part:
            return result

        # symbol_name from a placeholder result is just the sanitized C-number,
        # not a real MPN — only trust it as an MPN when the fetch was real.
        looked_up_mfr_part = await _lookup_mfr_part(lcsc, client)
        actual_mfr_part = looked_up_mfr_part or (
            result.symbol_name if result.fidelity == "real" else None
        )
        result.mpn_verified = _mpn_matches(expected_mfr_part, actual_mfr_part or "")

        if result.fidelity == "real" and result.mpn_verified:
            result.candidates_tried = tried
            return result

        fallback_reason = "unavailable"  # no real CAD data at this C-number
        if result.fidelity != "real":
            result.warnings.append(
                f"No real CAD data for requested {lcsc}; searching LCSC for other "
                f"listings of '{expected_mfr_part}'."
            )
        else:
            fallback_reason = "a mismatch"  # real data, but the wrong part
            result.warnings.append(
                f"MISMATCH: requested {lcsc} resolved to '{actual_mfr_part}', not "
                f"'{expected_mfr_part}'. Searching LCSC for the correct listing."
            )

        try:
            from . import lcsc_client

            candidates = await lcsc_client.search(
                expected_mfr_part,
                basic_only=False,
                stock_min=1,
                limit=max_candidates + 1,
                client=client,
            )
        except Exception as e:
            result.warnings.append(f"MPN fallback search failed: {e}")
            result.candidates_tried = tried
            return result

        fallback_best = result
        for part in candidates:
            if part.lcsc in tried or len(tried) - 1 >= max_candidates:
                continue
            tried.append(part.lcsc)
            try:
                candidate = await fetch_part_library(
                    part.lcsc, libs_dir, client=client, want_3d=want_3d
                )
            except PartLibraryError:
                continue
            candidate.requested_lcsc = lcsc
            candidate.mpn_verified = _mpn_matches(expected_mfr_part, part.mfr_part)

            if candidate.fidelity == "real" and candidate.mpn_verified:
                candidate.substituted = candidate.lcsc != lcsc
                candidate.warnings.insert(
                    0,
                    f"Substituted {part.lcsc} ({part.mfr_part}) for requested "
                    f"{lcsc} ({actual_mfr_part or 'unknown'}) — requested part was "
                    f"{fallback_reason}.",
                )
                candidate.candidates_tried = tried
                return candidate

            if fallback_best.fidelity != "real" and candidate.fidelity == "real":
                fallback_best = candidate

        fallback_best.candidates_tried = tried
        if fallback_best is result:
            fallback_best.warnings.append(
                f"MPN fallback exhausted {len(tried) - 1} alternate LCSC listing(s) "
                f"for '{expected_mfr_part}' without finding a real, verified match. "
                f"Tried: {', '.join(tried)}. Manual sourcing required."
            )
        return fallback_best
    finally:
        if own_client:
            await client.aclose()
