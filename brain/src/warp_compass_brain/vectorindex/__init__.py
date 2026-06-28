"""VectorIndex — the swap seam over the candidate-lookup helper (§6.1, §13).

Vectors only LOCATE candidates for the resolve pipeline; the graph holds the meaning.
This is the interface only; a concrete sqlite-vec / brute-force implementation and local
sentence-transformers embeddings are wired in Phase 2.
"""

from .base import VectorIndex
from .embedder import Embedder, FastEmbedEmbedder, HashingEmbedder, get_embedder
from .local_index import LocalVectorIndex

__all__ = [
    "VectorIndex",
    "LocalVectorIndex",
    "Embedder",
    "FastEmbedEmbedder",
    "HashingEmbedder",
    "get_embedder",
]
