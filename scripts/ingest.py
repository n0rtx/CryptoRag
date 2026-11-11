"""Построение векторного индекса: data/knowledge/*.md (+ описания монет из CoinGecko).

Запуск (нужен OPENAI_API_KEY):
    python scripts/ingest.py                # только локальные .md
    python scripts/ingest.py --coingecko    # + описания всех монет из backend/coins.py
Индекс сохраняется в data/index/ и коммитится в репозиторий (деплой на PythonAnywhere без ключей на этапе сборки).
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import requests

from backend import config
from backend.coins import COINS
from backend.market import _headers
from backend.rag.chunker import chunk_markdown
from backend.rag.openai_client import embed
from backend.rag.store import VectorStore


def symbol_from_filename(name: str) -> str | None:
    s = name.upper()
    return s if s in COINS else None


def fetch_coingecko_docs() -> list[dict]:
    docs = []
    for sym, (cg_id, name, _) in COINS.items():
        try:
            r = requests.get(
                f"{config.COINGECKO_BASE_URL}/coins/{cg_id}",
                params={"localization": "false", "tickers": "false", "market_data": "false",
                        "community_data": "false", "developer_data": "false"},
                headers=_headers(), timeout=15,
            )
            r.raise_for_status()
            j = r.json()
            desc = re.sub(r"<[^>]+>", "", (j.get("description") or {}).get("en", "")).strip()
            cats = ", ".join(c for c in j.get("categories", []) if c)
            genesis = j.get("genesis_date") or "n/a"
            algo = j.get("hashing_algorithm") or "n/a"
            if desc:
                text = (f"# {name} ({sym}) — CoinGecko profile\n\nCategories: {cats}. "
                        f"Genesis date: {genesis}. Hashing algorithm: {algo}.\n\n{desc}")
                docs.append({"source": f"coingecko:{cg_id}", "symbol": sym, "text": text})
                print(f"  + {sym}: {len(desc)} chars")
        except Exception as e:
            print(f"  ! {sym}: {e}")
        time.sleep(2.5)  # бережём лимиты бесплатного API
    return docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coingecko", action="store_true", help="добавить описания монет из CoinGecko")
    args = ap.parse_args()

    docs = []
    for p in sorted(config.KNOWLEDGE_DIR.glob("*.md")):
        docs.append({"source": p.name, "symbol": symbol_from_filename(p.stem), "text": p.read_text(encoding="utf-8")})
    if args.coingecko:
        print("Загружаю описания из CoinGecko…")
        docs += fetch_coingecko_docs()

    chunks = []
    for d in docs:
        for c in chunk_markdown(d["text"], d["source"]):
            c["symbol"] = d["symbol"]
            chunks.append(c)
    if not chunks:
        sys.exit("Нет документов в data/knowledge/")
    print(f"Документов: {len(docs)}, чанков: {len(chunks)}. Считаю эмбеддинги ({config.EMBED_MODEL})…")
    vecs = np.array(embed([c["text"] for c in chunks]), dtype=np.float32)
    VectorStore().save(vecs, chunks)
    print(f"Готово: {config.INDEX_DIR} ({vecs.shape[0]} x {vecs.shape[1]})")


if __name__ == "__main__":
    main()
