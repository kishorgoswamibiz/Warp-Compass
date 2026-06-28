"""Phase 10 — documentation generator (no Neo4j, no network).

Covers: a connected org → one unbroken end-to-end diagram + narrative with taxonomy section
numbers; a broken handoff surfaced (not bridged); the confidence filter (confirmed-by-default,
unverified shown+marked with the flag); provenance traceability; and the problem register.
"""

from __future__ import annotations

from conftest import FakeGraphStore

from warp_compass_brain.docgen import DocGenerator, render_markdown
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


def _node(node_id, ntype, name, *, persona="persona.rep",
          status=ConfidenceStatus.CONFIRMED, codes=None, **ka):
    return NodeCard(
        id=node_id,
        type=ntype,
        canonical_name=name,
        description=f"{name} description",
        category_codes=codes or ["02"],
        key_attributes=ka,
        provenance=[Provenance(said_by=persona, session_id="s1", confidence=0.9,
                               status=status, ts=TS)],
    )


def _edge(etype, a, b):
    return Edge(type=etype, from_id=a, to_id=b,
                provenance=[Provenance(said_by="persona.rep", session_id="s1",
                                       confidence=0.9, status=ConfidenceStatus.CONFIRMED, ts=TS)])


def _connected_org() -> FakeGraphStore:
    """evt → Take order (Rep) → [order form] → Pack order (Warehouse) → [shipment, final]."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", codes=["02"]))
    g.upsert_node(_node("role.wh", NodeType.ROLE, "Warehouse", persona="persona.wh", codes=["02"]))
    g.upsert_node(_node("evt.order", NodeType.EVENT, "Order received", codes=["01"]))
    g.upsert_node(_node("act.take", NodeType.ACTIVITY, "Take order", codes=["02"]))
    g.upsert_node(_node("art.order", NodeType.ARTIFACT, "Order form", codes=["07"]))
    g.upsert_node(_node("act.pack", NodeType.ACTIVITY, "Pack order", persona="persona.wh",
                        codes=["02"]))
    g.upsert_node(_node("art.ship", NodeType.ARTIFACT, "Shipment", persona="persona.wh",
                        codes=["07"]))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.take"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.wh", "act.pack"))
    g.add_edge(_edge(EdgeType.TRIGGERS, "evt.order", "act.take"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.take", "art.order"))
    g.add_edge(_edge(EdgeType.CONSUMES, "act.pack", "art.order"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.pack", "art.ship"))
    return g


# --- 1) connected end-to-end + section numbering ----------------------------------------------


def test_connected_org_is_one_unbroken_chain_with_diagram_and_narrative():
    docs = DocGenerator(_connected_org(), ONT).generate()
    assert docs.end_to_end.unbroken is True
    assert not docs.end_to_end.gaps
    md = render_markdown(docs)
    assert "```mermaid" in md and "flowchart TD" in md
    assert "Take order" in md and "Pack order" in md
    assert "one connected chain" in md


def test_section_numbers_follow_the_taxonomy():
    md = render_markdown(DocGenerator(_connected_org(), ONT).generate())
    assert "### 01 Intake & Triggers" in md
    assert "### 02 Core Activities" in md
    assert "### 07 Outputs & Artifacts" in md
    # taxonomy order: 01 before 02 before 07
    assert md.index("### 01 ") < md.index("### 02 ") < md.index("### 07 ")


# --- 2) broken handoff surfaced, not bridged --------------------------------------------------


def test_broken_handoff_is_surfaced_not_bridged():
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep"))
    g.upsert_node(_node("role.wh", NodeType.ROLE, "Warehouse"))  # nobody performs it
    g.upsert_node(_node("evt.order", NodeType.EVENT, "Order received", codes=["01"]))
    g.upsert_node(_node("act.take", NodeType.ACTIVITY, "Take order"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.take"))
    g.add_edge(_edge(EdgeType.TRIGGERS, "evt.order", "act.take"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.take", "role.wh"))

    docs = DocGenerator(g, ONT).generate()
    assert docs.end_to_end.unbroken is False
    kinds = {gp.kind for gp in docs.end_to_end.gaps}
    assert "dangling_handoff" in kinds
    md = render_markdown(docs)
    assert "dangling handoff" in md
    assert "not bridged" in md
    # the gap is shown, not invented into a real activity for the warehouse
    assert "(not described)" in md


# --- 3) confidence filter ---------------------------------------------------------------------


def test_unverified_hidden_by_default_shown_with_flag():
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", status=ConfidenceStatus.UNVERIFIED))
    g.upsert_node(_node("act.draft", NodeType.ACTIVITY, "Draft quote",
                        status=ConfidenceStatus.UNVERIFIED))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.draft"))

    default_md = render_markdown(DocGenerator(g, ONT).generate())
    assert "Draft quote" not in default_md
    assert "hidden as not-yet-confirmed" in default_md

    flagged_md = render_markdown(DocGenerator(g, ONT, include_unverified=True).generate())
    assert "Draft quote" in flagged_md
    assert "_(unverified)_" in flagged_md


def test_conflicting_node_is_always_surfaced_with_a_marker():
    g = FakeGraphStore()
    card = _node("act.appr", NodeType.ACTIVITY, "Approve refund")
    card.provenance.append(Provenance(said_by="persona.mgr", session_id="s2", confidence=0.5,
                                      status=ConfidenceStatus.CONFLICTING, ts=TS))
    g.upsert_node(card)
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.appr"))

    md = render_markdown(DocGenerator(g, ONT).generate())  # default = confirmed-only
    assert "Approve refund" in md  # conflict is NOT hidden
    assert "⚠️ _(conflicting)_" in md


# --- 4) traceability --------------------------------------------------------------------------


def test_every_rendered_node_carries_a_provenance_source():
    md = render_markdown(DocGenerator(_connected_org(), ONT).generate())
    assert "source: persona.rep @ 2026-06-29" in md
    assert "source: persona.wh @ 2026-06-29" in md


# --- 5) problem register ----------------------------------------------------------------------


def test_problem_register_links_activity_attributes_and_desire():
    g = _connected_org()
    g.upsert_node(_node("prob.slow", NodeType.PROBLEM, "Manual entry is slow", codes=["09"],
                        frequency="daily", impact="high", suspected_cause="no integration"))
    g.upsert_node(_node("des.auto", NodeType.DESIRE, "Auto-import orders", codes=["09"],
                        relates_to_problem="prob.slow"))
    g.add_edge(_edge(EdgeType.BLOCKS, "prob.slow", "act.take"))

    docs = DocGenerator(g, ONT).generate()
    assert len(docs.problems) == 1
    entry = docs.problems[0]
    assert "Take order" in entry.affected_activities
    assert entry.frequency == "daily" and entry.impact == "high"
    assert any(d.name == "Auto-import orders" for d in entry.desires)

    md = render_markdown(docs)
    assert "## 4. Problem Register" in md
    assert "**Affects:** Take order" in md
    assert "**Frequency:** daily" in md
    assert "**Wished-for:** Auto-import orders" in md
