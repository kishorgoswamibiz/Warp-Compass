"""Phase 2 — retrieval type-filtering + adjudication guard (no network)."""

from __future__ import annotations

from conftest import FakeGraphStore, FakeLLM

from warp_compass_brain.llm.base import LLMProvider
from warp_compass_brain.models import CandidateNode, NodeCard, NodeType
from warp_compass_brain.ontology import load_ontology
from warp_compass_brain.resolve import Resolver
from warp_compass_brain.vectorindex.embedder import HashingEmbedder
from warp_compass_brain.vectorindex.local_index import LocalVectorIndex

ONT = load_ontology()


def _seed(graph: FakeGraphStore, vector: LocalVectorIndex):
    for card in [
        NodeCard(id="act.check-stock", type=NodeType.ACTIVITY, canonical_name="Check stock",
                 description="verify availability", category_codes=["02"]),
        NodeCard(id="role.check-stock", type=NodeType.ROLE, canonical_name="Check stock",
                 description="a role oddly named the same", category_codes=["04"]),
    ]:
        graph.upsert_node(card)
        vector.add(card.id, card.canonical_name + " " + card.description)


def test_retrieve_filters_by_type(fake_graph):
    vector = LocalVectorIndex(":memory:", HashingEmbedder())
    _seed(fake_graph, vector)
    resolver = Resolver(fake_graph, vector, ONT, FakeLLM([]))
    cand = CandidateNode(ref="n1", type=NodeType.ACTIVITY, canonical_name="Check stock",
                         description="check the stock")
    retrieved = resolver.retrieve(cand)
    assert retrieved, "should find the same-named Activity"
    assert all(r.card.type == NodeType.ACTIVITY for r in retrieved)
    assert all(r.card.id != "role.check-stock" for r in retrieved)


def test_adjudicate_guard_demotes_bad_match_id(fake_graph):
    vector = LocalVectorIndex(":memory:", HashingEmbedder())
    _seed(fake_graph, vector)

    class BogusLLM(LLMProvider):
        def complete_json(self, system, user, *, temperature=0.0):
            return {"verdict": "same", "match_id": "does.not-exist", "reason": "oops"}

    resolver = Resolver(fake_graph, vector, ONT, BogusLLM())
    cand = CandidateNode(ref="n1", type=NodeType.ACTIVITY, canonical_name="Check stock",
                         description="x")
    retrieved = resolver.retrieve(cand)
    adj = resolver.adjudicate(cand, retrieved)
    assert adj.verdict == "new"  # invalid match_id → treated as new
