from openai import OpenAI

from .. import config

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Return a lazily created, shared OpenAI client.

    Returns:
        The OpenAI client.

    Raises:
        RuntimeError: If the API key is not configured.
    """
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY не задан. Создайте .env по образцу .env.example")
        _client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=40, max_retries=2)
    return _client


def embed(texts: list[str]) -> list[list[float]]:
    """Compute embeddings for a list of texts in batches.

    Args:
        texts: Texts to embed.

    Returns:
        One embedding vector per input text.
    """
    out: list[list[float]] = []
    for i in range(0, len(texts), 96):
        resp = get_client().embeddings.create(model=config.EMBED_MODEL, input=texts[i : i + 96])
        out.extend(d.embedding for d in resp.data)
    return out
