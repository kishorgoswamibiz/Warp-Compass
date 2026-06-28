"""Local text embedders for candidate lookup. No paid API — keeps the cost model intact.

``FastEmbedEmbedder`` (ONNX, light) is the real one; ``HashingEmbedder`` is a deterministic,
dependency-free fallback so the resolve pipeline still functions (with weaker recall) before
``uv sync --extra vectors`` is run or in CI. Both produce L2-normalized vectors.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(ABC):
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one L2-normalized vector per input text."""


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


class HashingEmbedder(Embedder):
    """Hashing bag-of-words. Deterministic, zero-dependency. Lexical, not semantic."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            vec = [0.0] * self.dim
            for tok in _TOKEN.findall(t.lower()):
                h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                vec[h % self.dim] += 1.0
            out.append(_normalize(vec))
        return out


class FastEmbedEmbedder(Embedder):
    """Local ONNX embeddings via fastembed (default BAAI/bge-small-en-v1.5)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding  # lazy: only when actually used

        self._model = TextEmbedding(model_name=model_name)
        # bge-small is 384-dim; query the model once to be exact.
        self.dim = len(next(iter(self._model.embed(["dimension probe"]))))

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_normalize(list(map(float, v))) for v in self._model.embed(texts)]


def get_embedder(model_name: str = "BAAI/bge-small-en-v1.5") -> Embedder:
    """Return the best available embedder, falling back to hashing if fastembed is absent."""
    try:
        return FastEmbedEmbedder(model_name)
    except Exception:  # fastembed not installed, or model download unavailable offline
        return HashingEmbedder()
