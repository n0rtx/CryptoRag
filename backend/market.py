"""Живые рыночные данные из CoinGecko с кэшем (экономит лимиты и ускоряет ответы)."""
import logging
import threading
import time

import requests

from . import config
from .coins import coin_name, coingecko_id

log = logging.getLogger(__name__)

_TTL = 60  # секунд
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def _headers() -> dict:
    h = {"accept": "application/json", "User-Agent": "crypto-rag/1.0"}
    if config.COINGECKO_API_KEY:
        # демо-ключ и pro-ключ используют разные заголовки
        name = "x-cg-pro-api-key" if "pro-api" in config.COINGECKO_BASE_URL else "x-cg-demo-api-key"
        h[name] = config.COINGECKO_API_KEY
    return h


def get_market(symbol: str) -> dict | None:
    """Цена, капитализация, изменения. None — если монета неизвестна или API недоступен."""
    cg_id = coingecko_id(symbol)
    if not cg_id:
        return None
    now = time.time()
    with _lock:
        hit = _cache.get(cg_id)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    try:
        r = requests.get(
            f"{config.COINGECKO_BASE_URL}/coins/markets",
            params={"vs_currency": "usd", "ids": cg_id, "price_change_percentage": "24h,7d,30d"},
            headers=_headers(),
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        d = rows[0]
        data = {
            "symbol": symbol.upper(),
            "name": coin_name(symbol),
            "price_usd": d.get("current_price"),
            "market_cap_usd": d.get("market_cap"),
            "rank": d.get("market_cap_rank"),
            "volume_24h_usd": d.get("total_volume"),
            "change_24h_pct": d.get("price_change_percentage_24h_in_currency"),
            "change_7d_pct": d.get("price_change_percentage_7d_in_currency"),
            "change_30d_pct": d.get("price_change_percentage_30d_in_currency"),
            "high_24h": d.get("high_24h"),
            "low_24h": d.get("low_24h"),
            "ath_usd": d.get("ath"),
            "ath_date": d.get("ath_date"),
            "circulating_supply": d.get("circulating_supply"),
            "max_supply": d.get("max_supply"),
            "updated": d.get("last_updated"),
        }
        with _lock:
            _cache[cg_id] = (now, data)
        return data
    except Exception as e:  # сеть/лимиты — не роняем ответ, просто отвечаем без live-данных
        log.warning("CoinGecko error for %s: %s", symbol, e)
        with _lock:
            stale = _cache.get(cg_id)
        return stale[1] if stale else None


def _fmt(v, suffix="", digits=2):
    if v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        if abs(v) >= 1000:
            return f"{v:,.0f}{suffix}"
        return f"{v:,.{digits}f}{suffix}"
    return str(v)


def format_market(d: dict) -> str:
    """Текстовый блок для контекста LLM."""
    price = d["price_usd"]
    price_s = f"{price:,.2f}" if price and price >= 1 else (f"{price:.6f}" if price else "n/a")
    return (
        f"[LIVE MARKET DATA — CoinGecko, {d.get('updated') or 'now'}]\n"
        f"{d['name']} ({d['symbol']}): price ${price_s}; rank #{d.get('rank')}; "
        f"market cap ${_fmt(d['market_cap_usd'])}; 24h volume ${_fmt(d['volume_24h_usd'])}; "
        f"change 24h {_fmt(d['change_24h_pct'], '%')}, 7d {_fmt(d['change_7d_pct'], '%')}, "
        f"30d {_fmt(d['change_30d_pct'], '%')}; 24h range ${_fmt(d['low_24h'])}–${_fmt(d['high_24h'])}; "
        f"ATH ${_fmt(d['ath_usd'])} ({(d.get('ath_date') or '')[:10]}); "
        f"circulating supply {_fmt(d['circulating_supply'])}; max supply {_fmt(d['max_supply'])}."
    )


_chart_cache: dict[tuple[str, int], tuple[float, list[float]]] = {}
_CHART_TTL = 600  # график меняется медленно — кэшируем на 10 минут


def get_chart(symbol: str, days: int = 7, points: int = 60) -> list[float] | None:
    """Ряд цен (USD) за `days` дней, уменьшенный до ~`points` точек для спарклайна."""
    cg_id = coingecko_id(symbol)
    if not cg_id:
        return None
    key = (cg_id, days)
    now = time.time()
    with _lock:
        hit = _chart_cache.get(key)
        if hit and now - hit[0] < _CHART_TTL:
            return hit[1]
    try:
        r = requests.get(
            f"{config.COINGECKO_BASE_URL}/coins/{cg_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        prices = [p[1] for p in r.json().get("prices", []) if p and p[1] is not None]
        if len(prices) < 2:
            return None
        step = max(1, len(prices) // points)
        series = prices[::step]
        if series[-1] != prices[-1]:
            series.append(prices[-1])
        with _lock:
            _chart_cache[key] = (now, series)
        return series
    except Exception as e:
        log.warning("CoinGecko chart error for %s: %s", symbol, e)
        with _lock:
            stale = _chart_cache.get(key)
        return stale[1] if stale else None
