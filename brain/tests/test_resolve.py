"""Phase 2 — retrieval type-filtering + adjudication guard (no network)."""

from __future__ import annotations

from conftest import FakeGraphStore, FakeLLM

from warp_compass_brain.llm.base import LLMProvider
from warp_compass_brain.models import CandidateNode, Edge, EdgeType, NodeCard, NodeType
from warp_compass_brain.ontology import load_ontology
from warp_compass_brain.resolve import _ADJ_SYSTEM, Resolver
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


# --- P17b: the adjudicator sees who performs it and which stage it's in (ADR #40) ---------------


class _CapturingLLM(LLMProvider):
    """Records the prompt so a test can assert on what the adjudicator was actually shown."""

    def __init__(self):
        self.user = ""

    def complete_json(self, system, user, *, temperature=0.0):
        self.user = user
        return {"verdict": "new", "match_id": None, "reason": "captured"}


def _placed_activity(graph, vector, act_id, name, desc, *, role, stage):
    graph.upsert_node(NodeCard(id=act_id, type=NodeType.ACTIVITY, canonical_name=name,
                               description=desc, category_codes=["02"]))
    graph.upsert_node(NodeCard(id=role[0], type=NodeType.ROLE, canonical_name=role[1],
                               description="a role", category_codes=["04"]))
    graph.upsert_node(NodeCard(id=stage[0], type=NodeType.STAGE, canonical_name=stage[1],
                               description="a stage", category_codes=["00"]))
    graph.add_edge(Edge(type=EdgeType.PERFORMS, from_id=role[0], to_id=act_id))
    graph.add_edge(Edge(type=EdgeType.PART_OF, from_id=act_id, to_id=stage[0]))
    vector.add(act_id, f"{name} {desc}")


def test_the_adjudicator_is_shown_the_performing_role_and_the_stage(fake_graph):
    """Without this, wording is the only evidence — and wording cannot separate the two cases.

    Measured on the live graph 06 Aug 2026: `give-demo` (Discovery) and `give-uat-demos` (UAT) are
    DIFFERENT work at 0.808 cosine, while `code-review` and `review-checks` are the SAME habit at
    0.862. The two populations overlap, so no similarity threshold can tell them apart — but the
    stage and the performing role can, and neither was ever put in front of the adjudicator.
    """
    vector = LocalVectorIndex(":memory:", HashingEmbedder())
    _placed_activity(fake_graph, vector, "act.give-demo", "Give Demo", "demo to the client",
                     role=("role.ba", "Business Analysis Specialist"),
                     stage=("stg.discovery", "Discovery"))
    llm = _CapturingLLM()
    resolver = Resolver(fake_graph, vector, ONT, llm)

    cand = CandidateNode(ref="n1", type=NodeType.ACTIVITY, canonical_name="Give UAT Demos",
                         description="demo to the client during UAT")
    resolver.adjudicate(cand, resolver.retrieve(cand), cand_context=" [in stage UAT]")

    assert "performed by Business Analysis Specialist" in llm.user
    assert "in stage Discovery" in llm.user
    assert "in stage UAT" in llm.user  # the candidate's own placement, from its extraction batch


def test_node_context_is_empty_for_an_unplaced_node(fake_graph):
    """A first mention has no edges. Empty must read as "no evidence", never as a difference."""
    vector = LocalVectorIndex(":memory:", HashingEmbedder())
    fake_graph.upsert_node(NodeCard(id="act.loose", type=NodeType.ACTIVITY, canonical_name="Loose",
                                    description="nobody has placed this", category_codes=["02"]))
    resolver = Resolver(fake_graph, vector, ONT, FakeLLM([]))

    assert resolver.node_context(fake_graph.get_node("act.loose")) == ""


def test_adjudicator_system_prompt_teaches_the_stage_and_role_rule():
    assert "DIFFERENT stage, or a different performing role" in _ADJ_SYSTEM
    assert "SAME performer AND same stage" in _ADJ_SYSTEM
