import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _f(name: str, default: float) -> float:
    """Read a float environment variable.

    Args:
        name: Environment variable name.
        default: Value used when the variable is not set.

    Returns:
        The parsed float value.
    """
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    """Read an integer environment variable.

    Args:
        name: Environment variable name.
        default: Value used when the variable is not set.

    Returns:
        The parsed integer value.
    """
    return int(os.getenv(name, default))


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if OPENAI_API_KEY in ("sk-...", "your-key-here"):
    OPENAI_API_KEY = ""
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
COINGECKO_BASE_URL = os.getenv("COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3").rstrip("/")

FILTER_THRESHOLD = _f("FILTER_THRESHOLD", 0.5)
MAX_QUESTION_CHARS = _i("MAX_QUESTION_CHARS", 500)

RAG_TOP_K = _i("RAG_TOP_K", 4)
RAG_MIN_SCORE = _f("RAG_MIN_SCORE", 0.25)
ANSWER_CACHE_TTL = _i("ANSWER_CACHE_TTL", 300)
RATE_LIMIT_PER_MIN = _i("RATE_LIMIT_PER_MIN", 10)

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

KNOWLEDGE_DIR = ROOT / "data" / "knowledge"
INDEX_DIR = ROOT / "data" / "index"
MODEL_PATH = ROOT / "models" / "query_filter.joblib"
FRONTEND_DIST = ROOT / "frontend" / "dist"

MARKET_SYMBOLS = [s.strip().upper() for s in os.getenv("MARKET_SYMBOLS", "BTC,ETH,SOL,BNB,XRP,DOGE").split(",") if s.strip()]
MARKET_REFRESH_SECONDS = _i("MARKET_REFRESH_SECONDS", 7200)
MARKET_ONDEMAND_TTL = _i("MARKET_ONDEMAND_TTL", 600)
MARKET_PROVIDERS = [p.strip().lower() for p in os.getenv("MARKET_PROVIDERS", "coingecko,binance,coinbase").split(",") if p.strip()]
MARKET_BACKGROUND = os.getenv("MARKET_BACKGROUND", "true").strip().lower() in ("1", "true", "yes")
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com/api/v3").rstrip("/")
COINBASE_BASE_URL = os.getenv("COINBASE_BASE_URL", "https://api.exchange.coinbase.com").rstrip("/")
CACHE_DIR = ROOT / "data" / "cache"
