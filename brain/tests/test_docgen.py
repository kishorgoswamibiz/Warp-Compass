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


# --- 6) persona display names (P13) ---------------------------------------------------------


def test_persona_ids_render_as_people_when_names_are_known():
    """The deliverable is read by humans; a slug tells them nothing about who said what."""
    docs = DocGenerator(_connected_org(), ONT).generate()
    md = render_markdown(
        docs,
        {
            "persona.rep": "Asha Rao (Sales Rep)",
            "persona.wh": "Rahul Mehta (Business Analyst), retired",
        },
    )
    assert "source: Asha Rao (Sales Rep) @ 2026-06-29" in md
    assert "source: Rahul Mehta (Business Analyst), retired @ 2026-06-29" in md
    assert "persona.rep" not in md


def test_an_unknown_persona_falls_back_to_its_raw_id_never_a_blank():
    docs = DocGenerator(_connected_org(), ONT).generate()
    md = render_markdown(docs, {"persona.rep": "Asha Rao (Sales Rep)"})  # persona.wh unmapped
    assert "source: Asha Rao (Sales Rep) @" in md
    assert "source: persona.wh @" in md


def test_rendering_without_a_name_map_is_unchanged():
    docs = DocGenerator(_connected_org(), ONT).generate()
    assert render_markdown(docs) == render_markdown(docs, {})


# --- P15c: the stage-spine process map + Gaps & Recommendations (plan §7.3) ---------------------


def _staged_lifecycle(g):
    """Pre-Sales -> Discovery, each with one activity and a named owner."""
    g.upsert_node(_node("stg.presales", NodeType.STAGE, "Pre-Sales", codes=["00"]))
    g.upsert_node(_node("stg.discovery", NodeType.STAGE, "Discovery", codes=["00"]))
    g.add_edge(_edge(EdgeType.PRECEDES, "stg.presales", "stg.discovery"))

    g.upsert_node(_node("role.am", NodeType.ROLE, "Account Management Specialist", codes=["04"]))
    g.upsert_node(_node("role.ba", NodeType.ROLE, "Business Analysis Specialist", codes=["04"]))
    g.add_edge(_edge(EdgeType.OWNS, "role.am", "stg.presales"))
    g.add_edge(_edge(EdgeType.OWNS, "role.ba", "stg.discovery"))

    # Each activity is contributed by the person who actually performs it, so role ownership is
    # unambiguous — which is what makes each contributor's altitude resolvable.
    g.upsert_node(_node("act.demo", NodeType.ACTIVITY, "Run the demo", persona="persona.am"))
    g.upsert_node(_node("act.brd", NodeType.ACTIVITY, "Write the BRD", persona="persona.ba"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.am", "act.demo"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.ba", "act.brd"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.demo", "stg.presales"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.brd", "stg.discovery"))


def test_the_process_map_is_rendered_on_the_stage_spine():
    g = FakeGraphStore()
    _staged_lifecycle(g)

    docs = DocGenerator(g, ONT).generate()
    assert [s.label for s in docs.end_to_end.stages] == ["Pre-Sales", "Discovery"]
    assert docs.end_to_end.stages[0].activity_ids == ["act.demo"]
    assert docs.end_to_end.stages[0].owner_name == "Account Management Specialist"
    assert docs.end_to_end.unstaged_activity_ids == []

    md = render_markdown(docs)
    # Stages become Mermaid subgraphs — that grouping is what makes the diagram legible.
    assert "subgraph" in md
    assert "Pre-Sales — Account Management Specialist" in md
    assert "The journey has **2 stages**: Pre-Sales → Discovery" in md
    # The activity is declared INSIDE its stage's subgraph, not alongside it.
    lines = md.splitlines()
    start = next(i for i, ln in enumerate(lines) if "subgraph stg_presales" in ln)
    end = next(i for i, ln in enumerate(lines[start:], start=start) if ln.strip() == "end")
    assert any("Run the demo" in ln for ln in lines[start:end])


def test_an_unstaged_activity_is_still_drawn_rather_than_dropped():
    g = FakeGraphStore()
    _staged_lifecycle(g)
    g.upsert_node(_node("act.loose", NodeType.ACTIVITY, "Unplaced work"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.am", "act.loose"))

    docs = DocGenerator(g, ONT).generate()
    assert docs.end_to_end.unstaged_activity_ids == ["act.loose"]
    md = render_markdown(docs)
    assert "Unplaced work" in md, "work outside the spine must never silently disappear"


def test_with_no_stages_the_diagram_falls_back_to_the_flat_p10_shape():
    """The spine is additive: a graph from before P15b must render exactly as it used to."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Sales Rep", codes=["04"]))
    g.upsert_node(_node("act.take", NodeType.ACTIVITY, "Take order"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.take"))

    docs = DocGenerator(g, ONT).generate()
    assert docs.end_to_end.stages == []
    md = render_markdown(docs)
    assert "subgraph" not in md
    assert "Take order" in md


def test_gaps_and_recommendations_has_all_three_groups_with_misalignments_first():
    g = FakeGraphStore()
    _staged_lifecycle(g)

    # An org chart, so a divergence can be classified by altitude.
    g.upsert_node(_node("role.ceo", NodeType.ROLE, "Chief Executive Officer", codes=["04"]))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.am", "role.ceo"))
    g.upsert_node(_node("act.ceowork", NodeType.ACTIVITY, "Set the strategy", persona="persona.ceo"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.ceo", "act.ceowork"))

    # ...and a cross-altitude divergence on the demo: the CEO and the AM describe it differently.
    card = g.get_node("act.demo")
    card.provenance = [
        Provenance(said_by="persona.ceo", session_id="s1", confidence=0.9,
                   status=ConfidenceStatus.CONFLICTING, ts=TS,
                   account="Every demo is tailored per client."),
        Provenance(said_by="persona.am", session_id="s1", confidence=0.9,
                   status=ConfidenceStatus.CONFIRMED, ts=TS,
                   account="We reuse one standard deck."),
    ]
    g.upsert_node(card)
    docs = DocGenerator(g, ONT, include_unverified=True).generate()
    assert docs.misalignments, "a cross-altitude divergence should be reported"
    assert docs.structural_findings, "structural findings should also be present"

    md = render_markdown(docs)
    assert "## Gaps & Recommendations" in md
    assert "Misalignments — recorded, not reconciled" in md
    assert "Structural findings" in md
    # Both sides are quoted verbatim, each with who holds it.
    assert "Every demo is tailored per client." in md
    assert "We reuse one standard deck." in md
    assert "level 0" in md, "the altitude is shown so the reader knows who is who"
    assert "Recommendation" in md
    # Misalignments come before structural findings in the rendered order.
    assert md.index("Misalignments — recorded") < md.index("Structural findings")


def test_a_misalignment_is_not_also_restated_as_a_knowledge_gap():
    """It is a finding with both accounts, not something missing (ADR #32)."""
    g = FakeGraphStore()
    _staged_lifecycle(g)
    g.upsert_node(_node("role.ceo", NodeType.ROLE, "Chief Executive Officer", codes=["04"]))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.am", "role.ceo"))
    g.upsert_node(_node("act.ceowork", NodeType.ACTIVITY, "Set the strategy", persona="persona.ceo"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.ceo", "act.ceowork"))

    card = g.get_node("act.demo")
    card.provenance = [
        Provenance(said_by="persona.ceo", session_id="s1", confidence=0.9,
                   status=ConfidenceStatus.CONFLICTING, ts=TS, account="Tailored."),
        Provenance(said_by="persona.am", session_id="s1", confidence=0.9,
                   status=ConfidenceStatus.CONFIRMED, ts=TS, account="Standard."),
    ]
    g.upsert_node(card)

    docs = DocGenerator(g, ONT, include_unverified=True).generate()
    assert docs.misalignments
    assert not [
        kg for kg in docs.knowledge_gaps if "described differently at different levels" in kg.detail
    ]


def test_an_empty_findings_section_is_omitted_entirely():
    """No findings and no gaps → no empty heading in the client-facing document."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.solo", NodeType.ROLE, "Finance", codes=["04"]))
    md = render_markdown(DocGenerator(g, ONT).generate())
    # `role.solo` has real gaps (no reports_to, no performs), so the section SHOULD appear here...
    assert "## Gaps & Recommendations" in md
    # ...but with nothing at all in the graph there is nothing to report.
    md_empty = render_markdown(DocGenerator(FakeGraphStore(), ONT).generate())
    assert "## Gaps & Recommendations" not in md_empty


def test_the_walkthrough_follows_the_stage_order_not_the_artifact_plumbing():
    """The other half of "rendered on the stage spine" — easy to miss, and it reads wrong if missed.

    `act.brd` sorts before `act.demo` by id and there is no artifact linking them, so the flow-only
    ordering put Discovery's work ahead of Pre-Sales'. The picture and the prose then disagree.
    """
    g = FakeGraphStore()
    _staged_lifecycle(g)

    docs = DocGenerator(g, ONT).generate()
    names = [step.node.name for step in docs.end_to_end.narrative]
    assert names == ["Run the demo", "Write the BRD"], names
    assert [s.label for s in docs.end_to_end.stages] == ["Pre-Sales", "Discovery"]


def test_unstaged_work_comes_last_in_the_walkthrough():
    g = FakeGraphStore()
    _staged_lifecycle(g)
    g.upsert_node(_node("act.aaa-unplaced", NodeType.ACTIVITY, "Unplaced work"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.am", "act.aaa-unplaced"))

    docs = DocGenerator(g, ONT).generate()
    names = [step.node.name for step in docs.end_to_end.narrative]
    # Sorts FIRST by id, so only stage-awareness can push it to the end.
    assert names[-1] == "Unplaced work", names
