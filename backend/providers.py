import logging
from types import SimpleNamespace

import requests

from . import config
from .coins import coin_name, coingecko_id

log = logging.getLogger(__name__)

TIMEOUT = 6
USER_AGENT = {"User-Agent": "crypto-rag/1.0", "accept": "application/json"}


def _get(url: str, params: dict | None = None, headers: dict | None = None):
    """Perform a GET request and return the decoded JSON body.

    Args:
        url: Request URL.
        params: Optional query parameters.
        headers: Optional extra headers, merged over the default ones.

    Returns:
        The parsed JSON response.

    Raises:
        requests.RequestException: On network errors or non-2xx responses.
    """
    r = requests.get(url, params=params, headers={**USER_AGENT, **(headers or {})}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _is_unknown_pair(exc: Exception) -> bool:
    """Check whether an error means that the exchange does not list the requested pair.

    Args:
        exc: The exception raised by a request.

    Returns:
        True for HTTP 400 and 404 responses, which indicate an unsupported symbol rather than an outage.
    """
    return isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (400, 404)


def _row(symbol: str, price: float, **extra) -> dict:
    """Build a market-data dictionary in the common format shared by all providers.

    Args:
        symbol: Ticker symbol.
        price: Current price in USD.
        **extra: Provider-specific fields that override the defaults.

    Returns:
        A dictionary with all expected keys, missing values set to None.
    """
    row = {
        "symbol": symbol,
        "name": coin_name(symbol),
        "price_usd": price,
        "market_cap_usd": None,
        "rank": None,
        "volume_24h_usd": None,
        "change_24h_pct": None,
        "change_7d_pct": None,
        "change_30d_pct": None,
        "high_24h": None,
        "low_24h": None,
        "ath_usd": None,
        "ath_date": None,
        "circulating_supply": None,
        "max_supply": None,
    }
    row.update(extra)
    return row


def _coingecko_headers() -> dict:
    """Build CoinGecko headers, including the API key when configured.

    Returns:
        A dictionary of request headers.
    """
    if not config.COINGECKO_API_KEY:
        return {}
    name = "x-cg-pro-api-key" if "pro-api" in config.COINGECKO_BASE_URL else "x-cg-demo-api-key"
    return {name: config.COINGECKO_API_KEY}


def coingecko_markets(symbols: list[str]) -> dict[str, dict]:
    """Fetch market data for several coins from CoinGecko in a single request.

    Args:
        symbols: Ticker symbols to fetch.

    Returns:
        A mapping from symbol to market data, containing only the coins that were returned.
    """
    ids = {coingecko_id(s): s for s in symbols if coingecko_id(s)}
    if not ids:
        return {}
    rows = _get(
        f"{config.COINGECKO_BASE_URL}/coins/markets",
        params={"vs_currency": "usd", "ids": ",".join(ids), "price_change_percentage": "24h,7d,30d", "per_page": len(ids)},
        headers=_coingecko_headers(),
    )
    out = {}
    for d in rows:
        sym = ids.get(d.get("id"))
        if sym and d.get("current_price"):
            out[sym] = _row(
                sym,
                d["current_price"],
                market_cap_usd=d.get("market_cap"),
                rank=d.get("market_cap_rank"),
                volume_24h_usd=d.get("total_volume"),
                change_24h_pct=d.get("price_change_percentage_24h_in_currency"),
                change_7d_pct=d.get("price_change_percentage_7d_in_currency"),
                change_30d_pct=d.get("price_change_percentage_30d_in_currency"),
                high_24h=d.get("high_24h"),
                low_24h=d.get("low_24h"),
                ath_usd=d.get("ath"),
                ath_date=d.get("ath_date"),
                circulating_supply=d.get("circulating_supply"),
                max_supply=d.get("max_supply"),
            )
    return out


def coingecko_chart(symbol: str, days: int) -> list[float]:
    """Fetch a price series for one coin from CoinGecko.

    Args:
        symbol: Ticker symbol.
        days: Number of days of history.

    Returns:
        A list of USD prices, oldest first. Empty if the coin is unknown.
    """
    cg_id = coingecko_id(symbol)
    if not cg_id:
        return []
    data = _get(
        f"{config.COINGECKO_BASE_URL}/coins/{cg_id}/market_chart",
        params={"vs_currency": "usd", "days": days},
        headers=_coingecko_headers(),
    )
    return [p[1] for p in data.get("prices", []) if p and p[1] is not None]


def binance_markets(symbols: list[str]) -> dict[str, dict]:
    """Fetch 24-hour ticker data from Binance for several coins.

    Prices are quoted in USDT, which is treated as USD. Coins that Binance does not list are skipped.

    Args:
        symbols: Ticker symbols to fetch.

    Returns:
        A mapping from symbol to market data.

    Raises:
        requests.RequestException: If Binance is unreachable or blocked.
    """
    out = {}
    for sym in symbols:
        if sym == "USDT":
            continue
        try:
            d = _get(f"{config.BINANCE_BASE_URL}/ticker/24hr", params={"symbol": f"{sym}USDT"})
        except requests.RequestException as e:
            if _is_unknown_pair(e):
                continue
            raise
        price = float(d["lastPrice"])
        if price > 0:
            out[sym] = _row(
                sym,
                price,
                volume_24h_usd=float(d["quoteVolume"]),
                change_24h_pct=float(d["priceChangePercent"]),
                high_24h=float(d["highPrice"]),
                low_24h=float(d["lowPrice"]),
            )
    return out


def binance_chart(symbol: str, days: int) -> list[float]:
    """Fetch a price series from Binance candlesticks.

    Args:
        symbol: Ticker symbol.
        days: Number of days of history.

    Returns:
        A list of closing prices, oldest first. Empty if the pair is not listed.

    Raises:
        requests.RequestException: If Binance is unreachable or blocked.
    """
    if days <= 2:
        interval, limit = "15m", days * 96
    elif days <= 10:
        interval, limit = "1h", days * 24
    else:
        interval, limit = "4h", min(days * 6, 1000)
    try:
        rows = _get(f"{config.BINANCE_BASE_URL}/klines", params={"symbol": f"{symbol}USDT", "interval": interval, "limit": limit})
    except requests.RequestException as e:
        if _is_unknown_pair(e):
            return []
        raise
    return [float(k[4]) for k in rows]


def coinbase_markets(symbols: list[str]) -> dict[str, dict]:
    """Fetch 24-hour statistics from Coinbase Exchange for several coins.

    Coins that Coinbase does not list are skipped.

    Args:
        symbols: Ticker symbols to fetch.

    Returns:
        A mapping from symbol to market data.

    Raises:
        requests.RequestException: If Coinbase is unreachable.
    """
    out = {}
    for sym in symbols:
        try:
            d = _get(f"{config.COINBASE_BASE_URL}/products/{sym}-USD/stats")
        except requests.RequestException as e:
            if _is_unknown_pair(e):
                continue
            raise
        last, open_ = float(d["last"]), float(d["open"])
        if last > 0:
            out[sym] = _row(
                sym,
                last,
                volume_24h_usd=float(d["volume"]) * last,
                change_24h_pct=(last / open_ - 1) * 100 if open_ else None,
                high_24h=float(d["high"]),
                low_24h=float(d["low"]),
            )
    return out


def coinbase_chart(symbol: str, days: int) -> list[float]:
    """Fetch a price series from Coinbase Exchange candles.

    Args:
        symbol: Ticker symbol.
        days: Number of days of history.

    Returns:
        A list of closing prices, oldest first. Empty if the pair is not listed.

    Raises:
        requests.RequestException: If Coinbase is unreachable.
    """
    granularity = 300 if days <= 1 else 3600 if days <= 10 else 21600
    wanted = min(days * 86400 // granularity, 300)
    try:
        rows = _get(f"{config.COINBASE_BASE_URL}/products/{symbol}-USD/candles", params={"granularity": granularity})
    except requests.RequestException as e:
        if _is_unknown_pair(e):
            return []
        raise
    rows = sorted(rows, key=lambda c: c[0])[-wanted:]
    return [float(c[4]) for c in rows]


PROVIDERS = {
    "coingecko": SimpleNamespace(name="CoinGecko", markets=coingecko_markets, chart=coingecko_chart),
    "binance": SimpleNamespace(name="Binance", markets=binance_markets, chart=binance_chart),
    "coinbase": SimpleNamespace(name="Coinbase", markets=coinbase_markets, chart=coinbase_chart),
}
