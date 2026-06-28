"""Phase 3 — completeness engine: per-activity gaps, scores, and the end-to-end chain check.

All tests run against the in-memory FakeGraphStore (no Neo4j, no network)."""

from __future__ import annotations

from conftest import FakeGraphStore

from warp_compass_brain.completeness import CompletenessEngine, GapKind
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
TS = "2026-03-12T10:00:00Z"


def _prov(persona: str = "persona.A", status: ConfidenceStatus = ConfidenceStatus.CONFIRMED):
    return Provenance(said_by=persona, session_id="s1", confidence=0.9, status=status, ts=TS)


def _node(node_id: str, ntype: NodeType, name: str, **kw) -> NodeCard:
    return NodeCard(
        id=node_id,
        type=ntype,
        canonical_name=name,
        description=f"{name} description",
        category_codes=kw.pop("category_codes", ["02"]),
        key_attributes=kw.pop("key_attributes", {}),
        provenance=kw.pop("provenance", [_prov()]),
        aliases=kw.pop("aliases", []),
    )


def _edge(etype: EdgeType, a: str, b: str) -> Edge:
    return Edge(type=etype, from_id=a, to_id=b, provenance=[_prov()])


def _fully_describe(
    g: FakeGraphStore, act_id: str, name: str, *, suffix: str, handoff_to: str | None = None
) -> None:
    """Attach all 7 ontology completeness fields to an Activity (trigger, inputs, system,
    output, next_handoff/handoff_to-or-final-output, exceptions, rules)."""
    act = _node(act_id, NodeType.ACTIVITY, name, key_attributes={"exceptions": "if out of stock"})
    g.upsert_node(act)
    evt = _node(f"evt.{suffix}", NodeType.EVENT, f"{name} trigger")
    art_in = _node(f"art.{suffix}-in", NodeType.ARTIFACT, f"{name} input")
    art_out = _node(f"art.{suffix}-out", NodeType.ARTIFACT, f"{name} output")
    sys = _node(f"sys.{suffix}", NodeType.SYSTEM, f"{name} system")
    rule = _node(f"rule.{suffix}", NodeType.RULE, f"{name} rule")
    for n in (evt, art_in, art_out, sys, rule):
        g.upsert_node(n)
    g.add_edge(_edge(EdgeType.TRIGGERS, evt.id, act_id))
    g.add_edge(_edge(EdgeType.CONSUMES, act_id, art_in.id))
    g.add_edge(_edge(EdgeType.PRODUCES, act_id, art_out.id))
    g.add_edge(_edge(EdgeType.USES, act_id, sys.id))
    g.add_edge(_edge(EdgeType.GOVERNED_BY, act_id, rule.id))
    if handoff_to is not None:
        g.add_edge(_edge(EdgeType.HANDS_OFF_TO, act_id, handoff_to))


def _engine(g: FakeGraphStore) -> CompletenessEngine:
    return CompletenessEngine(g, ONT, persona_threshold=0.9, org_threshold=0.9)


# --- test 1: missing trigger + handoff --------------------------------------------------------


def test_missing_trigger_and_handoff_surface_exactly_those_gaps():
    g = FakeGraphStore()
    # act.main has inputs, system, output, exceptions, rules — but NO trigger and NO handoff.
    # Its output is consumed by act.sink, so it is NOT a final-output endpoint → the handoff is
    # genuinely missing (not exempted).
    main = _node(
        "act.main", NodeType.ACTIVITY, "Process order",
        key_attributes={"exceptions": "backorder path"},
    )
    g.upsert_node(main)
    art_in = _node("art.in", NodeType.ARTIFACT, "Order form")
    art_out = _node("art.out", NodeType.ARTIFACT, "Picked order")
    sys = _node("sys.erp", NodeType.SYSTEM, "ERP")
    rule = _node("rule.sla", NodeType.RULE, "Same-day SLA")
    sink = _node("act.sink", NodeType.ACTIVITY, "Ship order")
    for n in (art_in, art_out, sys, rule, sink):
        g.upsert_node(n)
    g.add_edge(_edge(EdgeType.CONSUMES, "act.main", "art.in"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.main", "art.out"))
    g.add_edge(_edge(EdgeType.USES, "act.main", "sys.erp"))
    g.add_edge(_edge(EdgeType.GOVERNED_BY, "act.main", "rule.sla"))
    g.add_edge(_edge(EdgeType.CONSUMES, "act.sink", "art.out"))  # makes art.out non-final

    report = _engine(g).assess()
    missing = {
        gap.field
        for gap in report.gaps
        if gap.kind is GapKind.MISSING_FIELD and gap.node_id == "act.main"
    }
    assert missing == {"trigger", "next_handoff"}


def test_final_output_activity_is_not_penalized_for_missing_handoff():
    g = FakeGraphStore()
    # Fully described EXCEPT it has no handoff — but it produces a final output (consumed by no
    # one), so next_handoff is satisfied by the endpoint exemption.
    _fully_describe(g, "act.final", "Deliver report", suffix="final", handoff_to=None)
    report = _engine(g).assess()
    missing = {
        gap.field for gap in report.gaps if gap.kind is GapKind.MISSING_FIELD
    }
    assert missing == set(), f"unexpected field gaps: {missing}"


# --- test 2: one-sided handoff ----------------------------------------------------------------


def test_one_sided_handoff_penalizes_org_and_emits_thread():
    g = FakeGraphStore()
    role_x = _node("role.x", NodeType.ROLE, "Sales Rep")
    role_y = _node("role.y", NodeType.ROLE, "Warehouse")  # performs NOTHING → receiving side blank
    g.upsert_node(role_x)
    g.upsert_node(role_y)
    _fully_describe(g, "act.a", "Take order", suffix="a", handoff_to="role.y")
    g.add_edge(_edge(EdgeType.PERFORMS, "role.x", "act.a"))

    report = _engine(g).assess()
    one_sided = [gap for gap in report.gaps if gap.kind is GapKind.ONE_SIDED_HANDOFF]
    assert len(one_sided) == 1
    assert one_sided[0].node_id == "act.a"
    # org-wide handoff coverage is penalized (the lone handoff is one-sided)
    assert report.org.handoff_coverage == 0.0
    assert report.org.chain_unbroken is False
    assert report.satisfied is False


# --- test 3: fully described, fully connected → satisfied -------------------------------------


def test_fully_described_connected_org_is_satisfied():
    g = FakeGraphStore()
    role_x = _node("role.x", NodeType.ROLE, "Sales Rep")
    role_y = _node("role.y", NodeType.ROLE, "Fulfilment")
    g.upsert_node(role_x)
    g.upsert_node(role_y)

    # A: triggered, fully described, hands off to role Y.
    _fully_describe(g, "act.a", "Take order", suffix="a", handoff_to="role.y")
    g.add_edge(_edge(EdgeType.PERFORMS, "role.x", "act.a"))
    # B: triggered, fully described, terminal (produces a final output, no handoff). It also
    # consumes A's output so the flow connects A → B.
    _fully_describe(g, "act.b", "Fulfil order", suffix="b", handoff_to=None)
    g.add_edge(_edge(EdgeType.PERFORMS, "role.y", "act.b"))
    g.add_edge(_edge(EdgeType.CONSUMES, "act.b", "art.a-out"))  # B consumes A's output

    report = _engine(g).assess()
    assert report.gaps == [], f"expected no gaps, got {[g.detail for g in report.gaps]}"
    assert report.org.chain_unbroken is True
    assert report.org.handoff_coverage == 1.0
    assert report.org.score == 1.0
    assert all(ps.score == 1.0 for ps in report.persona_scores)
    assert report.satisfied is True


def test_persona_score_is_fraction_of_complete_activities():
    g = FakeGraphStore()
    role = _node("role.z", NodeType.ROLE, "Analyst")
    g.upsert_node(role)
    # one complete (terminal) activity, one barely-there activity
    _fully_describe(g, "act.good", "Compile report", suffix="good", handoff_to=None)
    g.upsert_node(_node("act.bad", NodeType.ACTIVITY, "Do something vague"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.z", "act.good"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.z", "act.bad"))

    report = _engine(g).assess()
    ps = next(p for p in report.persona_scores if p.role_id == "role.z")
    assert ps.activities_total == 2
    assert ps.activities_complete == 1
    assert ps.score == 0.5


def test_conflicting_node_becomes_a_gap():
    g = FakeGraphStore()
    _fully_describe(g, "act.c", "Approve discount", suffix="c", handoff_to=None)
    # flag the activity as conflicting via a conflicting provenance entry
    card = g.get_node("act.c")
    card.provenance.append(_prov(persona="persona.B", status=ConfidenceStatus.CONFLICTING))
    g.upsert_node(card)

    report = _engine(g).assess()
    conflicts = [gap for gap in report.gaps if gap.kind is GapKind.UNRESOLVED_CONFLICT]
    assert len(conflicts) == 1
    assert conflicts[0].node_id == "act.c"
    assert report.org.conflict_resolution < 1.0
