"""Phase 9 — cross-persona corroboration + conflict routing (no Neo4j, no network).

Covers the handoff verdict matrix (confirmed / route-to-receiver / route-to-discoverer), conflict
routing to every contributor, confidence promotion, and "no false conflicts on paraphrases".
"""

from __future__ import annotations

from conftest import FakeGraphStore

from warp_compass_brain.crosspersona import (
    KIND_CROSS_CONFLICT,
    KIND_HANDOFF_CONFIRM,
    KIND_HANDOFF_TRACE,
    CrossPersonaEngine,
)
from warp_compass_brain.models import (
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)
from warp_compass_brain.ontology import load_ontology

ONT = load_ontology()
TS = "2026-06-29T10:00:00Z"


def _prov(persona, status=ConfidenceStatus.UNVERIFIED):
    return Provenance(said_by=persona, session_id="s1", confidence=0.8, status=status, ts=TS)


def _node(node_id, ntype, name, *, personas, status=ConfidenceStatus.UNVERIFIED):
    if isinstance(personas, str):
        personas = [personas]
    return NodeCard(
        id=node_id,
        type=ntype,
        canonical_name=name,
        description=f"{name} description",
        category_codes=["02"],
        provenance=[_prov(p, status) for p in personas],
    )


def _edge(etype, a, b, persona="persona.A"):
    return Edge(type=etype, from_id=a, to_id=b, provenance=[_prov(persona)])


def _engine(g):
    return CrossPersonaEngine(g, ONT, now=TS)


# --- handoff verdict matrix -------------------------------------------------------------------


def test_handoff_routes_to_discoverer_when_receiver_not_interviewed():
    """Receiving role performs nothing (nobody interviewed as it) -> thread stays with the giver."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", personas="persona.A"))
    g.upsert_node(_node("role.warehouse", NodeType.ROLE, "Warehouse", personas="persona.A"))
    g.upsert_node(_node("act.take", NodeType.ACTIVITY, "Take order", personas="persona.A"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.take"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.take", "role.warehouse"))

    report = _engine(g).assess()
    assert [h.state for h in report.handoffs] == ["route_discoverer"]
    routed = [rt for rt in report.routed if rt.thread.kind == KIND_HANDOFF_TRACE]
    assert routed and {rt.persona_id for rt in routed} == {"persona.A"}
    assert "Warehouse" in routed[0].thread.goal


def test_handoff_routes_to_receiver_when_active_but_unlinked():
    """Receiver is an active persona but hasn't connected this handoff -> thread to the RECEIVER."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", personas="persona.A"))
    g.upsert_node(_node("role.wh", NodeType.ROLE, "Warehouse", personas="persona.B"))
    g.upsert_node(_node("act.take", NodeType.ACTIVITY, "Take order", personas="persona.A"))
    g.upsert_node(_node("art.order", NodeType.ARTIFACT, "Order form", personas="persona.A"))
    # B performs an activity (so B owns role.wh) but it doesn't consume A's output.
    g.upsert_node(_node("act.other", NodeType.ACTIVITY, "Do stock counts", personas="persona.B"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.take"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.wh", "act.other", persona="persona.B"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.take", "art.order"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.take", "role.wh"))

    report = _engine(g).assess()
    assert [h.state for h in report.handoffs] == ["route_receiver"]
    routed = [rt for rt in report.routed if rt.thread.kind == KIND_HANDOFF_CONFIRM]
    assert {rt.persona_id for rt in routed} == {"persona.B"}
    # The thread names the giver and is addressed to the receiver ("you").
    assert "Sales Rep" in routed[0].thread.why
    assert routed[0].thread.other_role_id == "role.wh"


def test_handoff_confirmed_when_receiver_consumes_givers_output():
    """B performs an activity that CONSUMES A's produced artifact -> both sides agree, no thread."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", personas="persona.A"))
    g.upsert_node(_node("role.wh", NodeType.ROLE, "Warehouse", personas="persona.B"))
    g.upsert_node(_node("act.take", NodeType.ACTIVITY, "Take order", personas="persona.A"))
    g.upsert_node(_node("art.order", NodeType.ARTIFACT, "Order form", personas="persona.A"))
    g.upsert_node(_node("act.pack", NodeType.ACTIVITY, "Pack order", personas="persona.B"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.take"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.wh", "act.pack", persona="persona.B"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.take", "art.order"))
    g.add_edge(_edge(EdgeType.CONSUMES, "act.pack", "art.order", persona="persona.B"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.take", "role.wh"))

    report = _engine(g).assess()
    assert [h.state for h in report.handoffs] == ["confirmed"]
    assert not [rt for rt in report.routed if rt.thread.kind in
                (KIND_HANDOFF_CONFIRM, KIND_HANDOFF_TRACE)]


def test_confirmed_handoff_edge_is_promoted_to_confirmed():
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", personas="persona.A"))
    g.upsert_node(_node("role.wh", NodeType.ROLE, "Warehouse", personas="persona.B"))
    g.upsert_node(_node("act.take", NodeType.ACTIVITY, "Take order", personas="persona.A"))
    g.upsert_node(_node("art.order", NodeType.ARTIFACT, "Order form", personas="persona.A"))
    g.upsert_node(_node("act.pack", NodeType.ACTIVITY, "Pack order", personas="persona.B"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.take"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.wh", "act.pack", persona="persona.B"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.take", "art.order"))
    g.add_edge(_edge(EdgeType.CONSUMES, "act.pack", "art.order", persona="persona.B"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.take", "role.wh"))

    result = _engine(g).corroborate()
    assert ("act.take", "role.wh") in result.confirmed_handoffs
    handoff = [e for e in g.edges(EdgeType.HANDS_OFF_TO)]
    assert len(handoff) == 1  # idempotent re-persist, not a duplicate
    assert all(p.status is ConfidenceStatus.CONFIRMED for p in handoff[0].provenance)


# --- conflict routing -------------------------------------------------------------------------


def test_conflicting_node_routes_reconciliation_thread_to_every_contributor():
    g = FakeGraphStore()
    # Two personas described the same step incompatibly -> the gate flagged it conflicting.
    card = _node("act.x", NodeType.ACTIVITY, "Approve refund", personas=["persona.A"])
    card.provenance.append(_prov("persona.B", status=ConfidenceStatus.CONFLICTING))
    g.upsert_node(card)

    report = _engine(g).assess()
    assert report.conflicts == ["act.x"]
    conflict = [rt for rt in report.routed if rt.thread.kind == KIND_CROSS_CONFLICT]
    assert {rt.persona_id for rt in conflict} == {"persona.A", "persona.B"}
    assert "Approve refund" in conflict[0].thread.goal


def test_no_false_conflict_on_a_paraphrase_merge():
    """A node corroborated by two personas (a merge of paraphrases) is NOT a conflict."""
    g = FakeGraphStore()
    g.upsert_node(_node("act.x", NodeType.ACTIVITY, "Approve refund", personas=["persona.A", "persona.B"]))
    report = _engine(g).assess()
    assert report.conflicts == []
    assert not [rt for rt in report.routed if rt.thread.kind == KIND_CROSS_CONFLICT]


# --- confidence promotion ---------------------------------------------------------------------


def test_two_persona_node_is_promoted_unverified_to_confirmed():
    g = FakeGraphStore()
    g.upsert_node(_node("act.x", NodeType.ACTIVITY, "Approve refund", personas=["persona.A", "persona.B"]))
    result = _engine(g).corroborate()
    assert "act.x" in result.promoted_nodes
    assert all(p.status is ConfidenceStatus.CONFIRMED for p in g.get_node("act.x").provenance)


def test_single_persona_node_is_not_promoted():
    g = FakeGraphStore()
    g.upsert_node(_node("act.x", NodeType.ACTIVITY, "Approve refund", personas="persona.A"))
    result = _engine(g).corroborate()
    assert result.promoted_nodes == []
    assert g.get_node("act.x").provenance[0].status is ConfidenceStatus.UNVERIFIED


def test_conflicting_node_is_not_promoted():
    g = FakeGraphStore()
    card = _node("act.x", NodeType.ACTIVITY, "Approve refund", personas=["persona.A"])
    card.provenance.append(_prov("persona.B", status=ConfidenceStatus.CONFLICTING))
    g.upsert_node(card)
    result = _engine(g).corroborate()
    assert result.promoted_nodes == []
