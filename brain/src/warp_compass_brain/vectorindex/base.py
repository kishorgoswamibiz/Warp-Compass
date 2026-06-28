"""The ``VectorIndex`` interface — a helper that finds candidate matches for resolution.

Deliberately tiny: add embeddings keyed by node id; search returns the nearest ids with
scores. The resolve pipeline (Phase 2) combines these candidates with alias matches and a
same-type / same-category filter before the adjudicator LLM decides same / conflict / new.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class VectorIndex(ABC):
    @abstractmethod
    def add(self, node_id: str, text: str) -> None:
        """Embed ``text`` (the node card) and store it under ``node_id``."""

    @abstractmethod
    def search(self, text: str, k: int = 10) -> list[tuple[str, float]]:
        """Return up to ``k`` (node_id, similarity) pairs nearest to ``text``."""
