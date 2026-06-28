"""The ``GraphStore`` interface — every graph access goes through this seam (§13).

Keep this surface minimal and storage-agnostic. The resolve/create-gate pipeline
(Phase 2), completeness engine (Phase 3), and doc generator (Phase 10) all build on it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from ..models import ConfidenceStatus, Edge, EdgeType, NodeCard


class GraphStore(ABC):
    """Abstract knowledge-graph store. Implementations: Neo4jGraphStore (now)."""

    # --- lifecycle ---

    @abstractmethod
    def connect(self) -> None:
        """Open the connection and ensure schema constraints/indexes exist."""

    @abstractmethod
    def close(self) -> None:
        """Close the connection."""

    def __enter__(self) -> GraphStore:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- nodes ---

    @abstractmethod
    def upsert_node(self, card: NodeCard) -> None:
        """Idempotently create or update a node by its slug id (merge-on-id)."""

    @abstractmethod
    def get_node(self, node_id: str) -> NodeCard | None:
        """Fetch a node card by id, or None if absent."""

    @abstractmethod
    def find_by_alias(self, name: str, node_type: str | None = None) -> list[NodeCard]:
        """Find nodes whose canonical_name or aliases match ``name`` (case-insensitive).

        Optionally constrained to a node type. Used by the resolve pipeline's
        alias-match candidate retrieval (§7).
        """

    @abstractmethod
    def add_provenance(self, node_id: str, provenance: Any) -> None:
        """Append a provenance record to a node."""

    @abstractmethod
    def set_status(self, node_id: str, status: ConfidenceStatus) -> None:
        """Set the confidence status on a node's latest provenance / summary."""

    # --- edges ---

    @abstractmethod
    def add_edge(self, edge: Edge) -> None:
        """Idempotently create a typed relationship between two existing nodes."""

    @abstractmethod
    def neighbors(self, node_id: str, edge_type: EdgeType | None = None) -> list[NodeCard]:
        """Return nodes reachable from ``node_id`` (optionally via one edge type)."""

    # --- bulk reads (used by the completeness engine, planner, doc generator) ---

    @abstractmethod
    def nodes_by_type(self, node_type: str) -> list[NodeCard]:
        """Return every node carrying the given ontology type label."""

    @abstractmethod
    def edges(self, edge_type: EdgeType | None = None) -> list[Edge]:
        """Return every typed relationship in the graph (optionally one edge type).

        Powers whole-graph traversals (completeness scoring, end-to-end chain check)
        that build their flow graph in memory rather than per-node round-trips.
        """

    # --- escape hatch ---

    @abstractmethod
    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Run a raw query (Cypher for Neo4j) and return rows as dicts.

        Used by completeness/conflict queries and the doc generator's traversals.
        """

    # --- convenience ---

    def upsert_nodes(self, cards: Iterable[NodeCard]) -> None:
        for c in cards:
            self.upsert_node(c)
