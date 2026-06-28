"""Phase 2 — full extract→resolve→gate→persist pipeline against the in-memory graph (no network)."""

from __future__ import annotations

from conftest import FakeGraphStore, FakeLLM

from warp_compass_brain.create_gate import CreateGate
from warp_compass_brain.extractor import Extractor
from warp_compass_brain.ingest import Ingestor
from warp_compass_brain.models import ConfidenceStatus, EdgeType
from warp_compass_brain.ontology import load_ontology
from warp_compass_brain.queues import JsonlQueue
from warp_compass_brain.resolve import Resolver
from warp_compass_brain.vectorindex.embedder import HashingEmbedder
from warp_compass_brain.vectorindex.local_index import LocalVectorIndex

ONT = load_ontology()


def _ingestor(graph, llm, tmp_path):
    vector = LocalVectorIndex(":memory:", HashingEmbedder())
    return Ingestor(
        graph=graph,
        vector=vector,
        ontology=ONT,
        extractor=Extractor(llm, ONT),
        resolver=Resolver(graph, vector, ONT, llm),
        gate=CreateGate(ONT, similarity_ceiling=0.86),
        quarantine=JsonlQueue(str(tmp_path / "q.jsonl")),
        pending_taxonomy=JsonlQueue(str(tmp_path / "p.jsonl")),
    )


def test_paraphrased_answers_merge_to_one_node(tmp_path):
    ext1 = {"nodes": [{"ref": "n1", "type": "ApprovalPoint",
                       "canonical_name": "Discount approval above 10%",
                       "description": "approval when a discount exceeds 10%",
                       "category_codes": ["05.1"]}], "relations": []}
    ext2 = {"nodes": [{"ref": "n1", "type": "ApprovalPoint",
                       "canonical_name": "Discount sign-off",
                       "aliases": ["the 10% thing"],
                       "description": "manager signs off large discounts",
                       "category_codes": ["05"]}], "relations": []}
    graph = FakeGraphStore()
    llm = FakeLLM([ext1, ext2], adjudicate_verdict="same")
    ing = _ingestor(graph, llm, tmp_path)

    s1 = ing.ingest_answer("...", persona_id="persona.A", session_id="s1", ts="2026-03-12T10:00:00Z")
    assert len(s1.created) == 1 and len(graph.nodes) == 1

    s2 = ing.ingest_answer("...", persona_id="persona.B", session_id="s2", ts="2026-03-13T10:00:00Z")
    assert len(s2.merged) == 1
    assert len(graph.nodes) == 1, "paraphrase should merge, not create a duplicate"

    node = next(iter(graph.nodes.values()))
    assert "Discount sign-off" in node.aliases and "the 10% thing" in node.aliases
    assert len(node.provenance) == 2
    # corroborated by a second persona → confirmed
    assert all(p.status == ConfidenceStatus.CONFIRMED for p in node.provenance)


def test_relations_committed_between_created_nodes(tmp_path):
    ext = {"nodes": [
        {"ref": "n1", "type": "Role", "canonical_name": "Inventory Lead", "description": "owns stock"},
        {"ref": "n2", "type": "Activity", "canonical_name": "Check stock", "description": "verify availability"},
    ], "relations": [{"type": "PERFORMS", "from_ref": "n1", "to_ref": "n2"}]}
    graph = FakeGraphStore()
    ing = _ingestor(graph, FakeLLM([ext]), tmp_path)
    s = ing.ingest_answer("...", persona_id="persona.A", session_id="s1", ts="2026-03-12T10:00:00Z")
    assert len(s.created) == 2 and s.edges == 1
    role_id = next(c for c in s.created if c.startswith("role."))
    neigh = graph.neighbors(role_id, EdgeType.PERFORMS)
    assert any(n.canonical_name == "Check stock" for n in neigh)


def test_incomplete_node_is_quarantined(tmp_path):
    ext = {"nodes": [{"ref": "n1", "type": "Activity", "canonical_name": "Vague thing",
                      "description": ""}], "relations": []}
    graph = FakeGraphStore()
    ing = _ingestor(graph, FakeLLM([ext]), tmp_path)
    s = ing.ingest_answer("...", persona_id="persona.A", session_id="s1", ts="2026-03-12T10:00:00Z")
    assert s.quarantined == 1 and len(graph.nodes) == 0
    assert len(JsonlQueue(str(tmp_path / "q.jsonl")).all()) == 1


def test_unregistered_category_recorded_in_pending(tmp_path):
    ext = {"nodes": [{"ref": "n1", "type": "Activity", "canonical_name": "Odd step",
                      "description": "does something", "category_codes": ["77.7"]}], "relations": []}
    graph = FakeGraphStore()
    ing = _ingestor(graph, FakeLLM([ext]), tmp_path)
    # NOTE: extractor sanitize already strips unregistered codes, so to exercise the gate's
    # pending path we feed the gate directly is covered in test_create_gate; here we just confirm
    # the pipeline still creates the node with a default category.
    s = ing.ingest_answer("...", persona_id="persona.A", session_id="s1", ts="2026-03-12T10:00:00Z")
    assert len(s.created) == 1
    node = next(iter(graph.nodes.values()))
    assert node.category_codes == ["02"]  # default for Activity (77.7 stripped upstream)
