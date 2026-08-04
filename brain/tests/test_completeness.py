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
    """Attach all 8 ontology completeness fields to an Activity (trigger, inputs, system,
    output, next_handoff/handoff_to-or-final-output, cadence, exceptions, rules).

    ``cadence`` joined the list in P15b — the graph must be able to record that pre-sales demos are
    per-opportunity rather than daily, which was Finding 5 expressed as schema."""
    act = _node(
        act_id,
        NodeType.ACTIVITY,
        name,
        key_attributes={"exceptions": "if out of stock", "cadence": "every order"},
    )
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
        key_attributes={"exceptions": "backorder path", "cadence": "every order"},
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
    # P15b scores Roles too, so "fully described" now includes the org chart: every role must
    # perform something AND have its reporting line known. `role.y` is the top of this little org and
    # so uses the attribute escape hatch — an edge could never exist for it, and without the hatch
    # its `reports_to` gap would be unclosable and asked forever.
    role_x = _node("role.x", NodeType.ROLE, "Sales Rep")
    role_y = _node(
        "role.y",
        NodeType.ROLE,
        "Fulfilment Lead",
        key_attributes={"reports_to": "nobody — top of the org"},
    )
    g.upsert_node(role_x)
    g.upsert_node(role_y)
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.x", "role.y"))

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


# --- P15b: Stage + Role scoring, and the false-broken-chain fix (plan §6.1, §6.2, §11) ---------


def _stage(g, stage_id: str, name: str, **kw):
    g.upsert_node(_node(stage_id, NodeType.STAGE, name, category_codes=["00"], **kw))


def test_stage_with_nothing_known_yields_exactly_its_four_gaps():
    g = FakeGraphStore()
    _stage(g, "stg.discovery", "Discovery")

    report = _engine(g).assess()
    missing = {gap.field for gap in report.gaps if gap.node_id == "stg.discovery"}
    # A stage with no PRECEDES edge at all IS unpositioned — we've been told the phase exists but
    # not where it sits. That's a real gap, and it closes as soon as a second stage is named.
    assert missing == {"position", "activities", "owner", "exit_criteria"}


def test_a_first_stage_with_no_predecessor_is_still_positioned():
    """The `"either"` direction. A lifecycle's first stage has nothing before it — correctly."""
    g = FakeGraphStore()
    _stage(g, "stg.presales", "Pre-Sales")
    _stage(g, "stg.kickoff", "Kickoff")
    g.add_edge(_edge(EdgeType.PRECEDES, "stg.presales", "stg.kickoff"))

    report = _engine(g).assess()
    for sid in ("stg.presales", "stg.kickoff"):
        fields = {gap.field for gap in report.gaps if gap.node_id == sid}
        assert "position" not in fields, f"{sid} reported as unpositioned"
    assert report.org.stage_chain_connectivity == 1.0


def test_a_stage_cycle_is_reported_not_crashed():
    """Plan §6.3: a cycle is a finding. Nothing is anchored, so nothing is on a path."""
    g = FakeGraphStore()
    _stage(g, "stg.a", "A")
    _stage(g, "stg.b", "B")
    g.add_edge(_edge(EdgeType.PRECEDES, "stg.a", "stg.b"))
    g.add_edge(_edge(EdgeType.PRECEDES, "stg.b", "stg.a"))

    report = _engine(g).assess()  # must not raise
    assert report.org.stage_chain_connectivity == 0.0
    assert report.satisfied is False


def test_role_gaps_are_scored_which_is_what_makes_the_org_chart_get_asked_about():
    """Finding 3: `Role.completeness_fields` was declared in the contract and never measured."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.ba", NodeType.ROLE, "Business Analysis Specialist"))

    report = _engine(g).assess()
    missing = {gap.field for gap in report.gaps if gap.node_id == "role.ba"}
    assert missing == {"reports_to", "performs"}
    # The gap is attributed to the role itself, so it lands in that person's own brief.
    reports_to = next(gap for gap in report.gaps if gap.field == "reports_to")
    assert (reports_to.role_id, reports_to.role_name) == (
        "role.ba",
        "Business Analysis Specialist",
    )


def test_the_org_root_can_close_reports_to_without_an_edge():
    """Otherwise the CEO's `reports_to` gap is unclosable and gets asked forever."""
    g = FakeGraphStore()
    g.upsert_node(
        _node(
            "role.ceo",
            NodeType.ROLE,
            "Chief Executive Officer",
            key_attributes={"reports_to": "nobody, top of the org"},
        )
    )
    report = _engine(g).assess()
    assert "reports_to" not in {gap.field for gap in report.gaps if gap.node_id == "role.ceo"}


def test_a_registry_seeded_role_is_vocabulary_and_is_not_scored():
    """ADR #33: a seeded role is not yet a claim about the business (would be 20 phantom gaps)."""
    from warp_compass_brain.roles import REGISTRY_SAID_BY, load_roles, seed_roles

    g = FakeGraphStore()
    seed_roles(g, load_roles(), now=TS)

    report = _engine(g).assess()
    assert report.gaps == [], f"seeded roles produced gaps: {[x.detail for x in report.gaps]}"
    assert report.satisfied is True

    # ...but the moment a real person mentions one, it starts being scored.
    card = g.get_node("role.delivery-specialist")
    card.provenance.append(_prov(persona="persona.A"))
    g.upsert_node(card)
    report = _engine(g).assess()
    assert {gap.field for gap in report.gaps if gap.node_id == "role.delivery-specialist"} == {
        "reports_to",
        "performs",
    }
    assert card.provenance[0].said_by == REGISTRY_SAID_BY  # the registry entry is still there


# --- the Finding 2 fix: an activity inside an ordered stage is LOCATED, not broken -------------


def _two_islands_in_one_lifecycle(g, *, with_stages: bool):
    """One anchored activity, and one the artifact plumbing cannot place.

    `activity_flow` can only infer order from handoffs and produced-then-consumed artifacts, and
    real interviews rarely yield complete plumbing: someone describes a step without naming what
    kicks it off, and nothing else links to it. `act.two` is exactly that — it has no `TRIGGERS`
    edge and no artifact shared with `act.one`, so it is unreachable from any entry and lands off
    the trigger-to-output path. Pre-P15b that made it a BROKEN_CHAIN, which is the false noise
    Finding 2 describes (the pre-P15 deliverable reported 3 of these and hid 21 activities behind
    them). Its *real* defect is the missing trigger, and that gap is still reported either way.
    """
    g.upsert_node(
        _node(
            "role.r",
            NodeType.ROLE,
            "Delivery Specialist",
            key_attributes={"reports_to": "nobody, top of the org"},
        )
    )
    _fully_describe(g, "act.one", "Run the demo", suffix="one", handoff_to=None)
    g.upsert_node(
        _node(
            "act.two",
            NodeType.ACTIVITY,
            "Write the BRD",
            key_attributes={"exceptions": "none", "cadence": "every project"},
        )
    )
    g.upsert_node(_node("art.brd", NodeType.ARTIFACT, "BRD"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.two", "art.brd"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.r", "act.one"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.r", "act.two"))
    if with_stages:
        _stage(g, "stg.presales", "Pre-Sales", key_attributes={"exit_criteria": "deal signed"})
        _stage(g, "stg.discovery", "Discovery", key_attributes={"exit_criteria": "BRD approved"})
        g.add_edge(_edge(EdgeType.PRECEDES, "stg.presales", "stg.discovery"))
        g.add_edge(_edge(EdgeType.PART_OF, "act.one", "stg.presales"))
        g.add_edge(_edge(EdgeType.PART_OF, "act.two", "stg.discovery"))
        g.add_edge(_edge(EdgeType.OWNS, "role.r", "stg.presales"))
        g.add_edge(_edge(EdgeType.OWNS, "role.r", "stg.discovery"))


def test_without_stages_a_disconnected_activity_is_reported_as_a_broken_chain():
    """The pre-P15b behaviour, kept as the control for the test below."""
    g = FakeGraphStore()
    _two_islands_in_one_lifecycle(g, with_stages=False)

    report = _engine(g).assess()
    broken = {gap.node_id for gap in report.gaps if gap.kind is GapKind.BROKEN_CHAIN}
    assert broken, "expected the flow-only check to flag the disconnected activity"
    assert report.org.chain_unbroken is False


def test_an_activity_inside_an_ordered_stage_is_located_not_broken():
    """Finding 2 fixed: the stage spine places it, so the verdict is no longer BROKEN_CHAIN."""
    g = FakeGraphStore()
    _two_islands_in_one_lifecycle(g, with_stages=True)

    report = _engine(g).assess()
    broken = [gap for gap in report.gaps if gap.kind is GapKind.BROKEN_CHAIN]
    assert broken == [], f"still reported broken: {[x.detail for x in broken]}"
    assert report.org.chain_unbroken is True
    assert report.org.stage_chain_connectivity == 1.0
    # The raw flow connectivity is deliberately UNCHANGED — activity_flow is shared with the doc
    # generator and stays the truth about artifact/handoff plumbing. Only the verdict moved.
    assert report.org.chain_connectivity < 1.0


def test_a_stage_that_floats_free_of_the_lifecycle_does_not_launder_a_broken_chain():
    """`PART_OF` alone must not suppress the gap, or the noise just moves one level up."""
    g = FakeGraphStore()
    _two_islands_in_one_lifecycle(g, with_stages=False)
    # A real ordered lifecycle exists; act.two's stage is NOT connected to it.
    _stage(g, "stg.real", "Pre-Sales")
    _stage(g, "stg.later", "Kickoff")
    g.add_edge(_edge(EdgeType.PRECEDES, "stg.real", "stg.later"))
    _stage(g, "stg.floating", "Somewhere")
    g.add_edge(_edge(EdgeType.PART_OF, "act.two", "stg.floating"))

    report = _engine(g).assess()
    broken = {gap.node_id for gap in report.gaps if gap.kind is GapKind.BROKEN_CHAIN}
    assert "act.two" in broken, "a free-floating stage should not count as placing an activity"
