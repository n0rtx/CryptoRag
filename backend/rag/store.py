import json
import threading
from pathlib import Path

import numpy as np

from .. import config


class VectorStore:
    """In-memory vector store with cosine-similarity search, persisted as numpy and JSON files."""

    def __init__(self, index_dir: Path = config.INDEX_DIR):
        """Create an empty store.

        Args:
            index_dir: Directory where the index files are stored.
        """
        self.dir = index_dir
        self.vecs: np.ndarray | None = None
        self.meta: list[dict] = []
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        """Whether the store contains an index.

        Returns:
            True if vectors and metadata are loaded.
        """
        return self.vecs is not None and len(self.meta) > 0

    def load(self) -> bool:
        """Load the index from disk.

        Returns:
            True if the index files were found and loaded.
        """
        vp, mp = self.dir / "vectors.npy", self.dir / "meta.json"
        if not (vp.exists() and mp.exists()):
            return False
        with self._lock:
            self.vecs = np.load(vp).astype(np.float32)
            self.meta = json.loads(mp.read_text(encoding="utf-8"))
        return True

    def save(self, vecs: np.ndarray, meta: list[dict]) -> None:
        """Normalize and persist vectors with their metadata, and keep them in memory.

        Args:
            vecs: Matrix of chunk embeddings.
            meta: Metadata for each chunk, in the same order.
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        vecs = self._normalize(vecs.astype(np.float32))
        np.save(self.dir / "vectors.npy", vecs)
        (self.dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        with self._lock:
            self.vecs, self.meta = vecs, meta

    @staticmethod
    def _normalize(m: np.ndarray) -> np.ndarray:
        """Scale vectors to unit length.

        Args:
            m: Matrix or vector to normalize.

        Returns:
            The normalized array.
        """
        n = np.linalg.norm(m, axis=-1, keepdims=True)
        return m / np.clip(n, 1e-12, None)

    def search(self, qvec: list[float], k: int, min_score: float, symbols: list[str] | None = None) -> list[dict]:
        """Find the chunks most similar to a query vector.

        Chunks from documents about the given coins receive a small score boost.

        Args:
            qvec: Query embedding.
            k: Maximum number of results.
            min_score: Minimum similarity for a result to be returned.
            symbols: Coin symbols mentioned in the question.

        Returns:
            Chunk metadata dictionaries with an added ``score``, best first.
        """
        if not self.ready:
            return []
        q = self._normalize(np.asarray(qvec, dtype=np.float32)[None, :])[0]
        scores = self.vecs @ q
        if symbols:
            for i, m in enumerate(self.meta):
                if m.get("symbol") in symbols:
                    scores[i] += 0.08
        order = np.argsort(-scores)[:k]
        return [{**self.meta[i], "score": float(scores[i])} for i in order if scores[i] >= min_score]
