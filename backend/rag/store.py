"""Мини-векторное хранилище на numpy (без faiss/chroma — они тяжёлые для PythonAnywhere)."""
import json
import threading
from pathlib import Path

import numpy as np

from .. import config


class VectorStore:
    def __init__(self, index_dir: Path = config.INDEX_DIR):
        self.dir = index_dir
        self.vecs: np.ndarray | None = None
        self.meta: list[dict] = []
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self.vecs is not None and len(self.meta) > 0

    def load(self) -> bool:
        vp, mp = self.dir / "vectors.npy", self.dir / "meta.json"
        if not (vp.exists() and mp.exists()):
            return False
        with self._lock:
            self.vecs = np.load(vp).astype(np.float32)
            self.meta = json.loads(mp.read_text(encoding="utf-8"))
        return True

    def save(self, vecs: np.ndarray, meta: list[dict]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        vecs = self._normalize(vecs.astype(np.float32))
        np.save(self.dir / "vectors.npy", vecs)
        (self.dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        with self._lock:
            self.vecs, self.meta = vecs, meta

    @staticmethod
    def _normalize(m: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(m, axis=-1, keepdims=True)
        return m / np.clip(n, 1e-12, None)

    def search(self, qvec: list[float], k: int, min_score: float, symbols: list[str] | None = None) -> list[dict]:
        if not self.ready:
            return []
        q = self._normalize(np.asarray(qvec, dtype=np.float32)[None, :])[0]
        scores = self.vecs @ q
        # лёгкий буст чанков из документов про упомянутые в вопросе монеты
        if symbols:
            for i, m in enumerate(self.meta):
                if m.get("symbol") in symbols:
                    scores[i] += 0.08
        order = np.argsort(-scores)[:k]
        return [{**self.meta[i], "score": float(scores[i])} for i in order if scores[i] >= min_score]
