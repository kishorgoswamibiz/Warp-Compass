"""Portable local vector index: sqlite-backed brute-force cosine. No native extension.

At prototype scale (hundreds of node cards) brute force is instant and dependency-free —
vectors are stored normalized so cosine similarity is a plain dot product. Swap for sqlite-vec
or a real ANN index later behind the same ``VectorIndex`` seam.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from .base import VectorIndex
from .embedder import Embedder, get_embedder


class LocalVectorIndex(VectorIndex):
    def __init__(self, db_path: str = ":memory:", embedder: Embedder | None = None) -> None:
        self._embedder = embedder or get_embedder()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS vectors (node_id TEXT PRIMARY KEY, vec BLOB NOT NULL)"
        )
        self._db.commit()

    def add(self, node_id: str, text: str) -> None:
        vec = np.asarray(self._embedder.embed([text])[0], dtype=np.float32)
        self._db.execute(
            "INSERT INTO vectors(node_id, vec) VALUES(?, ?) "
            "ON CONFLICT(node_id) DO UPDATE SET vec=excluded.vec",
            (node_id, vec.tobytes()),
        )
        self._db.commit()

    def search(self, text: str, k: int = 10) -> list[tuple[str, float]]:
        rows = self._db.execute("SELECT node_id, vec FROM vectors").fetchall()
        if not rows:
            return []
        q = np.asarray(self._embedder.embed([text])[0], dtype=np.float32)
        ids = [r[0] for r in rows]
        mat = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
        scores = mat @ q  # vectors are L2-normalized -> dot product == cosine
        order = np.argsort(-scores)[:k]
        return [(ids[i], float(scores[i])) for i in order]

    def close(self) -> None:
        self._db.close()
