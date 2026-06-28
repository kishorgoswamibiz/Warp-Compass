"""Shared test doubles: an in-memory GraphStore and a scripted LLM, so the Phase-2 pipeline
is fully testable without Neo4j or any network."""

from __future__ import annotations

import re

import pytest

from warp_compass_brain.graphstore.base import GraphStore
from warp_compass_brain.llm.base import LLMProvider
from warp_compass_brain.models import (
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    Provenance,
)


class FakeGraphStore(GraphStore):
    """Dict-backed store that mimics Neo4j semantics (returns fresh copies on read)."""

    def __init__(self) -> None:
        self.nodes: dict[str, NodeCard] = {}
        self._edges: list[Edge] = []

    def connect(self) -> None:  # no-op
        pass

    def close(self) -> None:  # no-op
        pass

    def upsert_node(self, card: NodeCard) -> None:
        self.nodes[card.id] = card.model_copy(deep=True)

    def get_node(self, node_id: str) -> NodeCard | None:
        c = self.nodes.get(node_id)
        return c.model_copy(deep=True) if c else None

    def find_by_alias(self, name: str, node_type: str | None = None) -> list[NodeCard]:
        out = []
        low = name.lower()
        for c in self.nodes.values():
            if node_type and c.type.value != node_type:
                continue
            names = {c.canonical_name.lower(), *(a.lower() for a in c.aliases)}
            if low in names:
                out.append(c.model_copy(deep=True))
        return out

    def add_provenance(self, node_id: str, provenance: Provenance) -> None:
        self.nodes[node_id].provenance.append(provenance)

    def set_status(self, node_id: str, status: ConfidenceStatus) -> None:
        n = self.nodes.get(node_id)
        if n and n.provenance:
            n.provenance[-1].status = status

    def add_edge(self, edge: Edge) -> None:
        # Idempotent MERGE on (type, from, to), mirroring Neo4jGraphStore: re-adding an edge
        # overwrites its provenance rather than creating a duplicate relationship.
        for i, e in enumerate(self._edges):
            if e.type == edge.type and e.from_id == edge.from_id and e.to_id == edge.to_id:
                self._edges[i] = edge.model_copy(deep=True)
                return
        self._edges.append(edge.model_copy(deep=True))

    def neighbors(self, node_id: str, edge_type: EdgeType | None = None) -> list[NodeCard]:
        out = []
        for e in self._edges:
            if e.from_id == node_id and (edge_type is None or e.type == edge_type):
                tgt = self.nodes.get(e.to_id)
                if tgt:
                    out.append(tgt.model_copy(deep=True))
        return out

    def nodes_by_type(self, node_type: str) -> list[NodeCard]:
        return [
            c.model_copy(deep=True) for c in self.nodes.values() if c.type.value == node_type
        ]

    def edges(self, edge_type: EdgeType | None = None) -> list[Edge]:
        return [
            e.model_copy(deep=True)
            for e in self._edges
            if edge_type is None or e.type == edge_type
        ]

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        return []


class FakeLLM(LLMProvider):
    """Returns queued extraction JSON for extractor calls; auto-adjudicates other calls.

    Adjudication picks the first ``id=`` it sees in the prompt and returns ``adjudicate_verdict``.
    """

    def __init__(self, extractions: list[dict], adjudicate_verdict: str = "same") -> None:
        self._extractions = list(extractions)
        self._verdict = adjudicate_verdict

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict:
        if "knowledge extractor" in system:
            return self._extractions.pop(0) if self._extractions else {"nodes": [], "relations": []}
        m = re.search(r"id=(\S+)", user)
        return {
            "verdict": self._verdict,
            "match_id": m.group(1) if m else None,
            "reason": "scripted",
        }


@pytest.fixture
def fake_graph() -> FakeGraphStore:
    return FakeGraphStore()
