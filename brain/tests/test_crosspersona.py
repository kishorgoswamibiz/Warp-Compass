"""Phase 9 — cross-persona corroboration + conflict routing (no Neo4j, no network).

Covers the handoff verdict matrix (confirmed / route-to-receiver / route-to-discoverer), conflict
routing to every contributor, confidence promotion, and "no false conflicts on paraphrases".
"""

from __future__ import annotations

from conftest import FakeGraphStore

from warp_compass_brain.crosspersona import (
    KIND_CROSS_CONFLICT,
    KIND_HANDOFF_CONFIRM,
    KIND_HANDOFF_SELF,
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
from warp_compass_brain.planner import _opener_and_followups

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


def _engine(g, declared=None):
    return CrossPersonaEngine(g, ONT, now=TS, declared_roles=declared)


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


# --- P15a §4.5: a multi-hat person hands work to themselves ------------------------------------


#: What persona.A ticked at onboarding. The dual-hat copy is gated on the DECLARATION of both
#: roles, never on having contributed their activities (P17a, ADR #38) — see
#: `test_contributing_to_both_roles_is_not_enough_to_claim_two_hats` for the reason.
_DUAL_HAT_DECLARED = {"persona.A": ("Delivery Specialist", "Account Management Specialist")}


def _dual_hat_graph():
    """One persona holding two roles, handing work from the first hat to the second.

    Delivery Specialist closes a project and hands it to Account Management — and the same human
    is both. The receiving role is "active" (its activity carries this persona's provenance), so
    ``_handoff_state`` returns ``route_receiver``; without the P15a branch the persona would be
    told a stranger handed it to them.

    Pair it with ``_DUAL_HAT_DECLARED``: the graph alone establishes that persona.A *talked about*
    both roles, which is deliberately no longer enough to tell them they wear both hats.
    """
    g = FakeGraphStore()
    g.upsert_node(_node("role.ds", NodeType.ROLE, "Delivery Specialist", personas="persona.A"))
    g.upsert_node(
        _node("role.ams", NodeType.ROLE, "Account Management Specialist", personas="persona.A")
    )
    g.upsert_node(_node("act.close", NodeType.ACTIVITY, "Close the project", personas="persona.A"))
    g.upsert_node(_node("act.renew", NodeType.ACTIVITY, "Chase the renewal", personas="persona.A"))
    g.upsert_node(_node("art.signoff", NodeType.ARTIFACT, "Sign-off note", personas="persona.A"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.ds", "act.close"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.ams", "act.renew"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.close", "art.signoff"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.close", "role.ams"))
    return g


def test_self_handoff_is_routed_as_a_hat_switch_not_a_stranger():
    report = _engine(_dual_hat_graph(), _DUAL_HAT_DECLARED).assess()
    assert [h.state for h in report.handoffs] == ["route_receiver"]

    routed = [rt for rt in report.routed if rt.thread.node_id == "act.close"]
    assert {rt.persona_id for rt in routed} == {"persona.A"}
    # The dual-hat twin replaces the standard confirm thread rather than adding to it.
    assert [rt.thread.kind for rt in routed] == [KIND_HANDOFF_SELF]
    thread = routed[0].thread
    assert "Delivery Specialist" in thread.goal and "Account Management Specialist" in thread.goal
    # Both role names survive so the Planner can name each hat.
    assert (thread.role_name, thread.other_role_name) == (
        "Delivery Specialist",
        "Account Management Specialist",
    )


def test_self_handoff_copy_never_says_another_team():
    """The regression the copy branch exists for (plan §11)."""
    report = _engine(_dual_hat_graph(), _DUAL_HAT_DECLARED).assess()
    thread = next(rt.thread for rt in report.routed if rt.thread.kind == KIND_HANDOFF_SELF)

    opener, followups = _opener_and_followups(thread)
    assert "another team" not in opener.lower()
    assert "another role" not in opener.lower()
    assert "hat" in opener.lower()
    assert "Close the project" in opener
    assert followups  # still probes for what leaks in the switch


def test_contributing_to_both_roles_is_not_enough_to_claim_two_hats():
    """The P17a regression, straight from a live session (ADR #38).

    ``_dual_hat_graph`` gives persona.A provenance on both roles' activities and nothing else —
    which is what merely *describing* how two roles work looks like in the graph. That used to
    satisfy the dual-hat branch, so a Solution Architect who declared exactly one role was opened
    with *"when you switch from your Quality Assurance Head hat to your Technical Specialist
    hat…"*, and a Business Analyst was asked the Delivery Specialist version a third time after
    denying it twice: *"I told you I do not act as a delivery specialist."*

    They must still be ROUTED the thread — they are the only person who has spoken about this work,
    and the handoff is still unconfirmed. Only the wording narrows, to something answerable.
    """
    report = _engine(_dual_hat_graph()).assess()  # no declaration anywhere

    routed = [rt for rt in report.routed if rt.thread.node_id == "act.close"]
    assert [(rt.persona_id, rt.thread.kind) for rt in routed] == [
        ("persona.A", KIND_HANDOFF_CONFIRM)
    ]
    opener, _ = _opener_and_followups(routed[0].thread)
    assert "both hats" not in opener.lower()
    assert "your delivery specialist hat" not in opener.lower()
    assert "Delivery Specialist hands" in opener  # named as a role, not as one of theirs


def test_declaring_only_one_of_the_two_roles_is_still_not_two_hats():
    """Half a declaration is not a declaration — the giving side has to be theirs too."""
    declared = {"persona.A": ("Account Management Specialist",)}  # receiver only

    report = _engine(_dual_hat_graph(), declared).assess()

    routed = [rt for rt in report.routed if rt.thread.node_id == "act.close"]
    assert [rt.thread.kind for rt in routed] == [KIND_HANDOFF_CONFIRM]


def test_a_genuine_second_person_still_gets_the_stranger_copy():
    """The branch must not swallow real cross-person handoffs — only same-persona ones."""
    g = _dual_hat_graph()
    # A different human owns Account Management: their interview produced the receiving activity.
    card = g.get_node("act.renew")
    card.provenance = [_prov("persona.B")]
    g.upsert_node(card)

    report = _engine(g).assess()
    routed = [rt for rt in report.routed if rt.thread.node_id == "act.close"]
    assert [(rt.persona_id, rt.thread.kind) for rt in routed] == [
        ("persona.B", KIND_HANDOFF_CONFIRM)
    ]
    opener, _ = _opener_and_followups(routed[0].thread)
    assert "your delivery specialist hat" not in opener.lower()
    assert "Delivery Specialist hands" in opener  # named as someone else, which they are
