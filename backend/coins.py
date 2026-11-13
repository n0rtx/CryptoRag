import re

COINS: dict[str, tuple[str, str, list[str]]] = {
    "BTC": ("bitcoin", "Bitcoin", ["btc", "bitcoin", "биткоин", "биткойн", "биток", "битка"]),
    "ETH": ("ethereum", "Ethereum", ["eth", "ethereum", "эфир", "эфириум", "эфира", "эфире"]),
    "SOL": ("solana", "Solana", ["sol", "solana", "солана", "солану", "солане"]),
    "BNB": ("binancecoin", "BNB", ["bnb", "binance coin", "бнб"]),
    "XRP": ("ripple", "XRP", ["xrp", "ripple", "рипл", "xrp ledger"]),
    "ADA": ("cardano", "Cardano", ["ada", "cardano", "кардано"]),
    "DOGE": ("dogecoin", "Dogecoin", ["doge", "dogecoin", "догикоин", "доге", "додж"]),
    "TON": ("the-open-network", "Toncoin", ["ton", "toncoin", "тон", "тонкоин"]),
    "AVAX": ("avalanche-2", "Avalanche", ["avax", "avalanche", "авакс", "аваланч"]),
    "DOT": ("polkadot", "Polkadot", ["dot", "polkadot", "полкадот"]),
    "LINK": ("chainlink", "Chainlink", ["link", "chainlink", "чейнлинк"]),
    "MATIC": ("matic-network", "Polygon", ["matic", "polygon", "полигон"]),
    "LTC": ("litecoin", "Litecoin", ["ltc", "litecoin", "лайткоин"]),
    "TRX": ("tron", "TRON", ["trx", "tron", "трон"]),
    "USDT": ("tether", "Tether", ["usdt", "tether", "тезер", "тетер"]),
    "USDC": ("usd-coin", "USD Coin", ["usdc", "usd coin"]),
    "SHIB": ("shiba-inu", "Shiba Inu", ["shib", "shiba", "шиба"]),
    "ATOM": ("cosmos", "Cosmos", ["atom", "cosmos", "космос"]),
    "NEAR": ("near", "NEAR Protocol", ["near", "near protocol"]),
    "ARB": ("arbitrum", "Arbitrum", ["arb", "arbitrum", "арбитрум"]),
    "OP": ("optimism", "Optimism", ["optimism", "оптимизм"]),
    "SUI": ("sui", "Sui", ["sui", "суи"]),
}

_ALIAS_TO_SYMBOL: dict[str, str] = {}
for _sym, (_cg, _name, _aliases) in COINS.items():
    for _a in _aliases:
        _ALIAS_TO_SYMBOL[_a] = _sym

_PATTERN = re.compile(
    r"(?<![\w])(" + "|".join(re.escape(a) for a in sorted(_ALIAS_TO_SYMBOL, key=len, reverse=True)) + r")(?![\w])",
    re.IGNORECASE,
)
_AMBIGUOUS = {"link", "near", "sol", "op", "ton", "dot", "atom", "sui", "arb", "ada", "тон", "космос", "оптимизм", "трон", "полигон", "доге"}
_UPPER_OK = re.compile(r"\b[A-Z]{2,5}\b")


def detect_coins(text: str, limit: int = 3) -> list[str]:
    """Find cryptocurrencies mentioned in a text.

    Ambiguous words (for example ``link`` or ``sol``) are accepted only when written in upper case, to avoid false positives.

    Args:
        text: User text to scan.
        limit: Maximum number of tickers to return.

    Returns:
        Ticker symbols in order of appearance, without duplicates.
    """
    found: list[str] = []
    for m in _PATTERN.finditer(text):
        word = m.group(1)
        low = word.lower()
        if low in _AMBIGUOUS and not (word.isupper() and _UPPER_OK.fullmatch(word)):
            continue
        sym = _ALIAS_TO_SYMBOL[low]
        if sym not in found:
            found.append(sym)
        if len(found) >= limit:
            break
    return found


def coingecko_id(symbol: str) -> str | None:
    """Map a ticker symbol to its CoinGecko identifier.

    Args:
        symbol: Ticker symbol, case-insensitive.

    Returns:
        The CoinGecko id, or None if the coin is unknown.
    """
    c = COINS.get(symbol.upper())
    return c[0] if c else None


def coin_name(symbol: str) -> str:
    """Get the display name of a coin.

    Args:
        symbol: Ticker symbol, case-insensitive.

    Returns:
        The coin name, or the upper-cased symbol if the coin is unknown.
    """
    c = COINS.get(symbol.upper())
    return c[1] if c else symbol.upper()
