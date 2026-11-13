import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from . import config
from .coins import COINS, coin_name
from .providers import PROVIDERS

log = logging.getLogger(__name__)

SNAPSHOT_FILE = config.CACHE_DIR / "market_snapshot.json"
CHART_DAYS = 7
CHART_POINTS = 60
FAIL_BACKOFF = 60
DISK_CHECK_INTERVAL = 15
STALE_RATIO = 0.9

_lock = threading.RLock()
_refresh_lock = threading.Lock()
_market: dict[str, dict] = {}
_charts: dict[str, dict] = {}
_fail_until: dict[str, float] = {}
_disk_mtime = 0.0
_disk_checked = 0.0


def tracked_symbols() -> list[str]:
    """Return the configured symbols that are refreshed in the background.

    Returns:
        Known ticker symbols from the ``MARKET_SYMBOLS`` setting.
    """
    return [s for s in config.MARKET_SYMBOLS if s in COINS]


def _providers() -> list:
    """Return the enabled data providers in priority order, skipping those that failed very recently.

    Returns:
        Provider descriptors for the names listed in ``MARKET_PROVIDERS``. If all of them failed recently, the full list.
    """
    chain = [PROVIDERS[n] for n in config.MARKET_PROVIDERS if n in PROVIDERS]
    now = time.time()
    healthy = [p for p in chain if not _in_backoff(f"p:{p.name}", now)]
    return healthy or chain


def _iso(ts: float) -> str:
    """Format a Unix timestamp as a UTC ISO-8601 string.

    Args:
        ts: Unix timestamp in seconds.

    Returns:
        The formatted time, for example ``2026-11-12T14:03:00Z``.
    """
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _downsample(prices: list[float], points: int) -> list[float]:
    """Reduce a price series to roughly the requested number of points, keeping the last value.

    Args:
        prices: Full price series.
        points: Approximate maximum number of points.

    Returns:
        The reduced series.
    """
    step = max(1, len(prices) // points)
    series = prices[::step]
    if series[-1] != prices[-1]:
        series.append(prices[-1])
    return series


def _save_disk() -> None:
    """Persist the in-memory snapshot to disk atomically."""
    global _disk_mtime
    with _lock:
        payload = json.dumps({"market": _market, "charts": _charts}, ensure_ascii=False)
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SNAPSHOT_FILE.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, SNAPSHOT_FILE)
    _disk_mtime = SNAPSHOT_FILE.stat().st_mtime


def _merge(target: dict, source: dict) -> None:
    """Merge snapshot entries, keeping the more recently fetched one for each key.

    Args:
        target: Dictionary updated in place.
        source: Dictionary with candidate entries.
    """
    for key, entry in source.items():
        current = target.get(key)
        if current is None or entry.get("fetched_at", 0) > current.get("fetched_at", 0):
            target[key] = entry


def load() -> None:
    """Load the persisted snapshot from disk, if one exists."""
    global _disk_mtime, _disk_checked
    if not SNAPSHOT_FILE.exists():
        return
    try:
        data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        with _lock:
            _merge(_market, data.get("market", {}))
            _merge(_charts, data.get("charts", {}))
        _disk_mtime = SNAPSHOT_FILE.stat().st_mtime
        _disk_checked = time.time()
        log.info("Market snapshot loaded: %d coins, %d charts", len(_market), len(_charts))
    except (OSError, ValueError) as e:
        log.warning("Could not read market snapshot: %s", e)


def _sync_from_disk() -> None:
    """Reload the snapshot if another process (worker or scheduled task) has updated the file."""
    global _disk_checked
    now = time.time()
    if now - _disk_checked < DISK_CHECK_INTERVAL:
        return
    _disk_checked = now
    try:
        if SNAPSHOT_FILE.stat().st_mtime > _disk_mtime:
            load()
    except OSError:
        pass


def _stamp(row: dict, provider, now: float) -> dict:
    """Attach source and timing metadata to a market-data row.

    Args:
        row: Market data from a provider.
        provider: The provider descriptor that produced the row.
        now: Fetch time as a Unix timestamp.

    Returns:
        The row, extended with ``source``, ``fetched_at`` and ``updated``.
    """
    return {**row, "source": provider.name, "fetched_at": now, "updated": _iso(now)}


def fetch_markets(symbols: list[str]) -> dict[str, dict]:
    """Fetch market data, falling back to the next provider for coins that are still missing.

    Args:
        symbols: Ticker symbols to fetch.

    Returns:
        A mapping from symbol to stamped market data, containing only the coins that were found.
    """
    remaining, out = list(symbols), {}
    for provider in _providers():
        if not remaining:
            break
        try:
            rows = provider.markets(remaining)
        except Exception as e:
            log.warning("%s markets failed: %s", provider.name, e)
            _mark_failed(f"p:{provider.name}")
            continue
        now = time.time()
        for sym, row in rows.items():
            out[sym] = _stamp(row, provider, now)
        remaining = [s for s in remaining if s not in out]
    return out


def fetch_chart(symbol: str, days: int) -> dict | None:
    """Fetch a price series, trying each provider in priority order.

    Args:
        symbol: Ticker symbol.
        days: Number of days of history.

    Returns:
        A dictionary with ``prices``, ``source`` and ``fetched_at``, or None if every provider failed.
    """
    for provider in _providers():
        try:
            prices = provider.chart(symbol, days)
        except Exception as e:
            log.warning("%s chart failed for %s: %s", provider.name, symbol, e)
            _mark_failed(f"p:{provider.name}")
            continue
        if len(prices) >= 2:
            return {"prices": _downsample(prices, CHART_POINTS), "source": provider.name, "fetched_at": time.time()}
    return None


def _in_backoff(key: str, now: float) -> bool:
    """Check whether fetching a key recently failed and should not be retried yet.

    Args:
        key: Failure key, for example ``m:BTC``.
        now: Current Unix timestamp.

    Returns:
        True if the key is still within the failure back-off window.
    """
    with _lock:
        return _fail_until.get(key, 0) > now


def _mark_failed(key: str) -> None:
    """Start a short back-off for a key so that a failing API is not hammered.

    Args:
        key: Failure key, for example ``m:BTC``.
    """
    with _lock:
        _fail_until[key] = time.time() + FAIL_BACKOFF


def _ttl(symbol: str) -> int:
    """Return how long cached data for a coin is considered fresh.

    Args:
        symbol: Ticker symbol.

    Returns:
        The refresh interval for tracked coins and the on-demand TTL for all others.
    """
    return config.MARKET_REFRESH_SECONDS if symbol in tracked_symbols() else config.MARKET_ONDEMAND_TTL


def get_market(symbol: str) -> dict | None:
    """Return market data for a coin, using the snapshot and fetching only when it is stale.

    If every provider fails, the last known data is returned so that its ``updated`` time tells how old it is.

    Args:
        symbol: Ticker symbol, for example ``BTC``.

    Returns:
        Market data with source and timestamp, or None if the coin is unknown and nothing is cached.
    """
    sym = symbol.upper()
    if sym not in COINS:
        return None
    _sync_from_disk()
    now = time.time()
    with _lock:
        entry = _market.get(sym)
    if entry and now - entry["fetched_at"] < _ttl(sym):
        return entry
    key = f"m:{sym}"
    if _in_backoff(key, now):
        return entry
    fresh = fetch_markets([sym]).get(sym)
    if fresh:
        with _lock:
            _market[sym] = fresh
        if sym in tracked_symbols():
            _save_disk()
        return fresh
    _mark_failed(key)
    return entry


def get_chart(symbol: str, days: int = CHART_DAYS) -> list[float] | None:
    """Return a price series for a coin, using the snapshot and fetching only when it is stale.

    Args:
        symbol: Ticker symbol.
        days: Number of days of history.

    Returns:
        A list of USD prices, or None if no data is available.
    """
    sym = symbol.upper()
    if sym not in COINS:
        return None
    _sync_from_disk()
    cache_key = f"{sym}:{days}"
    now = time.time()
    with _lock:
        entry = _charts.get(cache_key)
    persistent = sym in tracked_symbols() and days == CHART_DAYS
    ttl = config.MARKET_REFRESH_SECONDS if persistent else config.MARKET_ONDEMAND_TTL
    if entry and now - entry["fetched_at"] < ttl:
        return entry["prices"]
    key = f"c:{cache_key}"
    if _in_backoff(key, now):
        return entry["prices"] if entry else None
    fresh = fetch_chart(sym, days)
    if fresh:
        with _lock:
            _charts[cache_key] = fresh
        if persistent:
            _save_disk()
        return fresh["prices"]
    _mark_failed(key)
    return entry["prices"] if entry else None


def get_overview() -> dict:
    """Build the payload for the market tab from cached data only, without calling any API.

    Returns:
        A dictionary with the newest update time, the refresh interval and one entry per tracked coin.
    """
    _sync_from_disk()
    coins, newest = [], 0.0
    with _lock:
        for sym in tracked_symbols():
            m = _market.get(sym)
            c = _charts.get(f"{sym}:{CHART_DAYS}")
            if m:
                newest = max(newest, m["fetched_at"])
            coins.append({
                "symbol": sym,
                "name": coin_name(sym),
                "price_usd": m["price_usd"] if m else None,
                "change_24h_pct": m["change_24h_pct"] if m else None,
                "source": m["source"] if m else None,
                "updated": m["updated"] if m else None,
                "prices": c["prices"] if c else None,
            })
    return {
        "updated": _iso(newest) if newest else None,
        "refresh_seconds": config.MARKET_REFRESH_SECONDS,
        "coins": coins,
    }


def snapshot_age() -> float | None:
    """Return the age of the oldest tracked market entry.

    Returns:
        Age in seconds, or None if any tracked coin has no data yet.
    """
    now = time.time()
    with _lock:
        entries = [_market.get(s) for s in tracked_symbols()]
    if not entries or any(e is None for e in entries):
        return None
    return max(now - e["fetched_at"] for e in entries)


def refresh_all(force: bool = False) -> bool:
    """Refresh market data and charts for all tracked coins and persist the result.

    Without ``force``, entries that were refreshed recently are skipped, so a retry only repeats what failed.

    Args:
        force: Refresh every tracked coin regardless of its age.

    Returns:
        True if every tracked coin has fresh market data and a fresh chart afterwards.
    """
    if not _refresh_lock.acquire(blocking=False):
        return False
    try:
        interval = config.MARKET_REFRESH_SECONDS
        limit = interval * STALE_RATIO
        symbols = tracked_symbols()
        now = time.time()
        with _lock:
            stale = [s for s in symbols if force or s not in _market or now - _market[s]["fetched_at"] >= limit]
        if stale:
            rows = fetch_markets(stale)
            with _lock:
                _market.update(rows)
            log.info("Market refresh: %d/%d coins updated", len(rows), len(stale))
        for sym in symbols:
            cache_key = f"{sym}:{CHART_DAYS}"
            with _lock:
                entry = _charts.get(cache_key)
            if force or entry is None or time.time() - entry["fetched_at"] >= limit:
                fresh = fetch_chart(sym, CHART_DAYS)
                if fresh:
                    with _lock:
                        _charts[cache_key] = fresh
                time.sleep(1.0)
        _save_disk()
        now = time.time()
        with _lock:
            return all(
                s in _market and now - _market[s]["fetched_at"] < interval
                and f"{s}:{CHART_DAYS}" in _charts and now - _charts[f"{s}:{CHART_DAYS}"]["fetched_at"] < interval
                for s in symbols
            )
    finally:
        _refresh_lock.release()


def _fmt(v, suffix: str = "", digits: int = 2) -> str:
    """Format a number for display inside the LLM context.

    Args:
        v: Value to format, or None.
        suffix: Text appended to the formatted number.
        digits: Decimal places for values below 1000.

    Returns:
        The formatted string, or ``n/a`` when the value is None.
    """
    if v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        if abs(v) >= 1000:
            return f"{v:,.0f}{suffix}"
        return f"{v:,.{digits}f}{suffix}"
    return str(v)


def format_market(d: dict) -> str:
    """Render market data as a text block for the LLM prompt, omitting fields the provider did not supply.

    Args:
        d: Market data dictionary returned by ``get_market``.

    Returns:
        A header with the data source and time, followed by a one-paragraph description of the coin.
    """
    price = d["price_usd"]
    parts = [f"price ${price:,.2f}" if price >= 1 else f"price ${price:.6f}"]
    if d.get("rank"):
        parts.append(f"rank #{d['rank']}")
    if d.get("market_cap_usd"):
        parts.append(f"market cap ${_fmt(d['market_cap_usd'])}")
    if d.get("volume_24h_usd"):
        parts.append(f"24h volume ${_fmt(d['volume_24h_usd'])}")
    changes = [
        f"{label} {_fmt(d[key], '%')}"
        for label, key in (("24h", "change_24h_pct"), ("7d", "change_7d_pct"), ("30d", "change_30d_pct"))
        if d.get(key) is not None
    ]
    if changes:
        parts.append("change " + ", ".join(changes))
    if d.get("low_24h") is not None and d.get("high_24h") is not None:
        parts.append(f"24h range ${_fmt(d['low_24h'])}–${_fmt(d['high_24h'])}")
    if d.get("ath_usd"):
        date = f" ({d['ath_date'][:10]})" if d.get("ath_date") else ""
        parts.append(f"ATH ${_fmt(d['ath_usd'])}{date}")
    if d.get("circulating_supply"):
        parts.append(f"circulating supply {_fmt(d['circulating_supply'])}")
    if d.get("max_supply"):
        parts.append(f"max supply {_fmt(d['max_supply'])}")
    header = f"[LIVE MARKET DATA — {d.get('source', 'unknown')}, as of {d.get('updated', 'unknown')}]"
    return f"{header}\n{d['name']} ({d['symbol']}): " + "; ".join(parts) + "."
