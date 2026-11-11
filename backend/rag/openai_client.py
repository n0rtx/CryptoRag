"""Ленивая инициализация клиента OpenAI (ключ берётся из .env)."""
from openai import OpenAI

from .. import config

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY не задан. Создайте .env по образцу .env.example")
        _client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=40, max_retries=2)
    return _client


def embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), 96):
        resp = get_client().embeddings.create(model=config.EMBED_MODEL, input=texts[i : i + 96])
        out.extend(d.embedding for d in resp.data)
    return out
