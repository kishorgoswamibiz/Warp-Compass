"""Phase 4 — Planner / Session Brief: cold start, ranked threads, corroboration, persona scoping,
and contract validation against contracts/session-brief.schema.json (no Neo4j, no network)."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import FakeGraphStore
from jsonschema import validate

from warp_compass_brain.models import (
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)
from warp_compass_brain.ontology import load_ontology
from warp_compass_brain.planner import COLD_START_OPENERS, Planner

ONT = load_ontology()
TS = "2026-06-28T10:00:00Z"

_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "session-brief.schema.json").read_text(
        encoding="utf-8"
    )
)


def _prov(persona: str = "persona.A", status: ConfidenceStatus = ConfidenceStatus.CONFIRMED):
    return Provenance(said_by=persona, session_id="s1", confidence=0.9, status=status, ts=TS)


def _node(node_id, ntype, name, *, persona="persona.A", **kw) -> NodeCard:
    return NodeCard(
        id=node_id,
        type=ntype,
        canonical_name=name,
        description=f"{name} description",
        category_codes=kw.pop("category_codes", ["02"]),
        key_attributes=kw.pop("key_attributes", {}),
        provenance=[_prov(persona)],
    )


def _edge(etype, a, b) -> Edge:
    return Edge(type=etype, from_id=a, to_id=b, provenance=[_prov()])


def _bare_activity(g, act_id, name, *, persona, role_id):
    """An activity with a performer but no completeness fields → many gaps."""
    g.upsert_node(_node(act_id, NodeType.ACTIVITY, name, persona=persona))
    if role_id not in g.nodes:
        g.upsert_node(_node(role_id, NodeType.ROLE, role_id.split(".")[-1], persona=persona))
    g.add_edge(_edge(EdgeType.PERFORMS, role_id, act_id))


def _planner(g, **kw) -> Planner:
    return Planner(g, ONT, now=TS, **kw)


# --- cold start -------------------------------------------------------------------------------


def test_empty_graph_is_cold_start():
    g = FakeGraphStore()
    brief = _planner(g).plan("persona.A", session_id="s_cold")
    assert brief.cold_start is True
    assert brief.open_threads == []
    d = brief.to_dict()
    validate(instance=d, schema=_SCHEMA)
    assert d["cold_start"] is True and d["open_threads"] == []
    assert len(COLD_START_OPENERS) >= 3  # runner has generic openers to fall back on


# --- ranked threads + schema ------------------------------------------------------------------


def test_seeded_gaps_produce_ranked_schema_valid_brief():
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order", persona="persona.A", role_id="role.rep")

    brief = _planner(g).plan("persona.A", session_id="s_2026")
    assert brief.cold_start is False
    assert len(brief.open_threads) >= 2
    # integer ranks, contiguous from 1, strictly increasing
    ranks = [t.priority for t in brief.open_threads]
    assert ranks == list(range(1, len(ranks) + 1))
    # rank 1 is a higher-impact gap (handoff/trigger) than the last
    assert brief.open_threads[0].why and brief.open_threads[0].suggested_opener
    validate(instance=brief.to_dict(), schema=_SCHEMA)


def test_threads_capped_and_overflow_goes_to_reserve():
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order", persona="persona.A", role_id="role.rep")
    # a bare activity yields ~6 missing-field gaps; cap to 3
    brief = _planner(g, max_threads=3).plan("persona.A", session_id="s_2026")
    assert len(brief.open_threads) == 3
    assert len(brief.reserve_threads) >= 1
    # reserve ids don't overlap with carried ids
    carried = {t.id for t in brief.open_threads}
    assert carried.isdisjoint(set(brief.reserve_threads))
    validate(instance=brief.to_dict(), schema=_SCHEMA)


# --- cross-persona corroboration --------------------------------------------------------------


def test_one_sided_handoff_emits_corroboration_thread_naming_other_role():
    g = FakeGraphStore()
    # persona.A's activity hands off to a role nobody performs (one-sided).
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", persona="persona.A"))
    g.upsert_node(_node("role.warehouse", NodeType.ROLE, "Warehouse", persona="persona.A"))
    g.upsert_node(_node("act.a", NodeType.ACTIVITY, "Take order", persona="persona.A"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.a"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.a", "role.warehouse"))

    brief = _planner(g).plan("persona.A", session_id="s_2026")
    corroboration = [t for t in brief.open_threads if "Warehouse" in t.goal]
    assert corroboration, "expected a corroboration thread naming the receiving role"
    assert "Warehouse" in corroboration[0].suggested_opener
    validate(instance=brief.to_dict(), schema=_SCHEMA)


def test_handoff_corroboration_routes_to_the_receiving_personas_brief():
    """P9: A says it hands work to B; B is active but hasn't connected it -> the confirmation
    thread lands in B's brief (not A's), at top priority, and the brief stays schema-valid."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", persona="persona.A"))
    g.upsert_node(_node("role.wh", NodeType.ROLE, "Warehouse", persona="persona.B"))
    g.upsert_node(_node("act.take", NodeType.ACTIVITY, "Take order", persona="persona.A"))
    g.upsert_node(_node("art.order", NodeType.ARTIFACT, "Order form", persona="persona.A"))
    g.upsert_node(_node("act.other", NodeType.ACTIVITY, "Stock counts", persona="persona.B"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.take"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.wh", "act.other"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.take", "art.order"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.take", "role.wh"))

    brief_b = _planner(g).plan("persona.B", session_id="s")
    confirm = [t for t in brief_b.open_threads if "Take order" in t.goal and "receive" in t.goal]
    assert confirm, "B's brief should ask B to confirm receiving A's handoff"
    assert confirm[0].priority == 1, "the cross-persona handoff thread should rank first"
    assert "Sales Rep" in confirm[0].suggested_opener
    validate(instance=brief_b.to_dict(), schema=_SCHEMA)

    # A (the giver) should NOT also be asked to chase it — it's routed to B.
    brief_a = _planner(g).plan("persona.A", session_id="s")
    assert not [t for t in brief_a.open_threads if "Take order" in t.goal and "receive" in t.goal]


# --- persona scoping --------------------------------------------------------------------------


def test_brief_is_scoped_to_the_personas_own_subgraph():
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "A's activity", persona="persona.A", role_id="role.a")
    _bare_activity(g, "act.b", "B's activity", persona="persona.B", role_id="role.b")

    brief_a = _planner(g).plan("persona.A", session_id="s")
    # thread ids embed their node id; A's brief must reference only A's node
    ids = [t.id for t in brief_a.open_threads]
    assert ids and all("act.a" in tid for tid in ids)
    assert not any("act.b" in tid for tid in ids), "A's brief leaked B's nodes"

    # plan_all yields one brief per contributing persona
    assert {b.persona_id for b in _planner(g).plan_all(session_id="s")} == {
        "persona.A",
        "persona.B",
    }


def test_persona_summary_mentions_role_and_activity():
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order", persona="persona.A", role_id="role.rep")
    brief = _planner(g).plan("persona.A", session_id="s")
    assert "rep" in brief.persona_summary.lower()
    assert "activit" in brief.persona_summary.lower()
