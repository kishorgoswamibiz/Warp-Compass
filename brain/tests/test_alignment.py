"""P15c — derived altitude, misalignment-vs-conflict, and the structural findings (plan §7, §11).

The through-line: a **cross-altitude** divergence is a *finding* and must never be routed for
reconciliation, because the delta between what leadership believes and what actually happens is the
product (ADR #32). A **same-altitude** divergence stays a data-quality problem and keeps the P9
behaviour. Everything here runs against the in-memory FakeGraphStore — no LLM, no network.
"""

from __future__ import annotations

from conftest import FakeGraphStore

from warp_compass_brain.alignment import (
    AlignmentEngine,
    FindingKind,
    derive_altitudes,
)
from warp_compass_brain.completeness import CompletenessEngine, GapKind, load_snapshot
from warp_compass_brain.crosspersona import KIND_CROSS_CONFLICT, CrossPersonaEngine
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
TS = "2026-08-04T10:00:00Z"


def _prov(persona: str, *, status=ConfidenceStatus.UNVERIFIED, account: str = "", ts: str = TS):
    return Provenance(
        said_by=persona, session_id="s1", confidence=0.9, status=status, ts=ts, account=account
    )


def _node(node_id, ntype, name, *, provs=None, **kw) -> NodeCard:
    return NodeCard(
        id=node_id,
        type=ntype,
        canonical_name=name,
        description=kw.pop("description", f"{name} description"),
        category_codes=kw.pop("category_codes", ["02"]),
        key_attributes=kw.pop("key_attributes", {}),
        provenance=provs if provs is not None else [_prov("persona.A")],
    )


def _edge(etype, a, b, persona="persona.A") -> Edge:
    return Edge(type=etype, from_id=a, to_id=b, provenance=[_prov(persona)])


# --- derived altitude (§6.3) --------------------------------------------------------------------


def _three_level_org(g):
    """CEO <- Head <- Developer. Depth 0 / 1 / 2 counted UP to the role with no outgoing REPORTS_TO."""
    g.upsert_node(_node("role.ceo", NodeType.ROLE, "Chief Executive Officer"))
    g.upsert_node(_node("role.head", NodeType.ROLE, "Quality Assurance Head"))
    g.upsert_node(_node("role.dev", NodeType.ROLE, "Technical Specialist"))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.dev", "role.head"))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.head", "role.ceo"))


def test_altitude_is_derived_from_reports_to_depth():
    g = FakeGraphStore()
    _three_level_org(g)

    alt = derive_altitudes(load_snapshot(g))
    assert alt.of("role.ceo") == 0, "the role with no outgoing REPORTS_TO is the root"
    assert alt.of("role.head") == 1
    assert alt.of("role.dev") == 2
    assert alt.cycles == []


def test_roles_at_equal_depth_are_peers():
    g = FakeGraphStore()
    _three_level_org(g)
    g.upsert_node(_node("role.ba", NodeType.ROLE, "Business Analysis Specialist"))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.ba", "role.head"))

    alt = derive_altitudes(load_snapshot(g))
    assert alt.of("role.ba") == alt.of("role.dev") == 2
    assert alt.same_altitude("role.ba", "role.dev") is True
    assert alt.same_altitude("role.ba", "role.ceo") is False


def test_unknown_depth_degrades_gracefully_rather_than_guessing():
    g = FakeGraphStore()
    g.upsert_node(_node("role.lonely", NodeType.ROLE, "Finance"))
    g.upsert_node(_node("role.other", NodeType.ROLE, "Solution Architect"))

    alt = derive_altitudes(load_snapshot(g))
    # A role with no REPORTS_TO at all IS a root by definition — that is the honest reading.
    assert alt.of("role.lonely") == 0
    # An id we know nothing about is unknown, and comparisons return None rather than a guess.
    assert alt.of("role.nope") is None
    assert alt.same_altitude("role.nope", "role.other") is None


def test_a_reporting_cycle_is_reported_not_crashed():
    """Plan §6.3: cycles are a finding. Depth is unknown — there is no root to count from."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.a", NodeType.ROLE, "Delivery Specialist"))
    g.upsert_node(_node("role.b", NodeType.ROLE, "Account Management Specialist"))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.a", "role.b"))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.b", "role.a"))

    alt = derive_altitudes(load_snapshot(g))  # must not raise or hang
    assert alt.of("role.a") is None and alt.of("role.b") is None
    assert len(alt.cycles) == 1
    assert set(alt.cycles[0]) == {"role.a", "role.b"}

    findings = AlignmentEngine(g).assess().of_kind(FindingKind.REPORTING_CYCLE)
    assert len(findings) == 1
    assert "loop" in findings[0].detail.lower()


# --- §7.1 misalignment vs conflict --------------------------------------------------------------


def _divergent_activity(g, *, personas: list[tuple[str, str, str]]):
    """One conflicting Activity, described differently by each (persona, role_id, own words).

    Each persona is made the *owner* of their role by contributing an activity that role performs —
    the same definition `crosspersona` uses, since merely being named on a Role node is not being it.
    """
    provs = []
    for persona, role_id, account in personas:
        status = ConfidenceStatus.CONFLICTING if provs else ConfidenceStatus.UNVERIFIED
        provs.append(_prov(persona, status=status, account=account))
        # the persona's own work, which is what makes them the owner of role_id.
        # `persona.ceo` -> `act.own-ceo`: node ids are `<prefix>.<kebab-case>`, so the dot in the
        # persona id cannot be carried into the slug.
        own = f"act.own-{persona.split('.')[-1]}"
        g.upsert_node(_node(own, NodeType.ACTIVITY, f"{persona} work", provs=[_prov(persona)]))
        g.add_edge(_edge(EdgeType.PERFORMS, role_id, own, persona=persona))
    g.upsert_node(_node("act.signoff", NodeType.ACTIVITY, "Sign off the release", provs=provs))


def test_cross_altitude_divergence_is_a_misalignment_with_both_accounts_kept():
    g = FakeGraphStore()
    _three_level_org(g)
    _divergent_activity(
        g,
        personas=[
            ("persona.ceo", "role.ceo", "Every release is signed off by me personally."),
            ("persona.dev", "role.dev", "We sign off ourselves; it never reaches the CEO."),
        ],
    )

    report = AlignmentEngine(g).assess()
    mis = report.misalignments
    assert len(mis) == 1
    f = mis[0]
    assert f.node_id == "act.signoff"

    # BOTH accounts survive, each with who holds it and their altitude — highest in the org first.
    assert [a.said_by for a in f.accounts] == ["persona.ceo", "persona.dev"]
    assert [a.altitude for a in f.accounts] == [0, 2]
    assert "signed off by me personally" in f.accounts[0].account
    assert "never reaches the CEO" in f.accounts[1].account
    assert f.recommendation


def test_same_altitude_divergence_stays_a_conflict_to_reconcile():
    """Two peers disagreeing about their own shared process really is a data-quality problem."""
    g = FakeGraphStore()
    _three_level_org(g)
    g.upsert_node(_node("role.ba", NodeType.ROLE, "Business Analysis Specialist"))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.ba", "role.head"))
    _divergent_activity(
        g,
        personas=[
            ("persona.dev", "role.dev", "The developer signs it off."),
            ("persona.ba", "role.ba", "The BA signs it off."),
        ],
    )

    report = AlignmentEngine(g).assess()
    assert report.misalignments == [], "peers are not a misalignment"

    gaps = CompletenessEngine(g, ONT).assess().gaps
    kinds = {gp.kind for gp in gaps if gp.node_id == "act.signoff"}
    assert GapKind.UNRESOLVED_CONFLICT in kinds
    assert GapKind.MISALIGNMENT not in kinds


def test_a_misalignment_routes_no_reconciliation_thread_to_anybody():
    """The behaviour ADR #32 exists to change. Asking would delete the finding."""
    g = FakeGraphStore()
    _three_level_org(g)
    _divergent_activity(
        g,
        personas=[
            ("persona.ceo", "role.ceo", "Signed off by me."),
            ("persona.dev", "role.dev", "Signed off by us."),
        ],
    )

    report = CrossPersonaEngine(g, ONT, now=TS).assess()
    reconciliation = [
        rt for rt in report.routed
        if rt.thread.kind == KIND_CROSS_CONFLICT and rt.thread.node_id == "act.signoff"
    ]
    assert reconciliation == [], "nobody may be asked to reconcile a cross-altitude divergence"
    assert "act.signoff" in report.misalignments
    assert "act.signoff" not in report.conflicts


def test_a_peer_conflict_still_routes_to_every_contributor():
    """The P9 behaviour must survive intact for the same-altitude case."""
    g = FakeGraphStore()
    _three_level_org(g)
    g.upsert_node(_node("role.ba", NodeType.ROLE, "Business Analysis Specialist"))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.ba", "role.head"))
    _divergent_activity(
        g,
        personas=[("persona.dev", "role.dev", "Dev signs."), ("persona.ba", "role.ba", "BA signs.")],
    )

    report = CrossPersonaEngine(g, ONT, now=TS).assess()
    routed = {
        rt.persona_id for rt in report.routed
        if rt.thread.kind == KIND_CROSS_CONFLICT and rt.thread.node_id == "act.signoff"
    }
    assert routed == {"persona.dev", "persona.ba"}
    assert "act.signoff" in report.conflicts
    assert report.misalignments == []


def test_unknown_altitude_falls_back_to_reconciling_rather_than_claiming_a_finding():
    """With no org chart we cannot assert a misalignment — and asking is how the chart fills in."""
    g = FakeGraphStore()
    g.upsert_node(_node("role.x", NodeType.ROLE, "Delivery Specialist"))
    g.upsert_node(_node("role.y", NodeType.ROLE, "Technical Specialist"))
    _divergent_activity(
        g, personas=[("persona.x", "role.x", "One way."), ("persona.y", "role.y", "Another way.")]
    )

    # Both are roots (no REPORTS_TO anywhere), so both are depth 0 → peers → reconcile.
    assert AlignmentEngine(g).assess().misalignments == []
    report = CrossPersonaEngine(g, ONT, now=TS).assess()
    assert "act.signoff" in report.conflicts


def test_the_registry_is_never_counted_as_a_voice_in_a_misalignment():
    """A seeded role is vocabulary, not a contributor with an altitude (ADR #33)."""
    from warp_compass_brain.roles import REGISTRY_SAID_BY

    g = FakeGraphStore()
    _three_level_org(g)
    provs = [
        _prov(REGISTRY_SAID_BY),
        _prov("persona.ceo", status=ConfidenceStatus.CONFLICTING, account="Mine."),
    ]
    g.upsert_node(_node("act.solo", NodeType.ACTIVITY, "Only one real voice", provs=provs))
    g.upsert_node(_node("act.own", NodeType.ACTIVITY, "CEO work", provs=[_prov("persona.ceo")]))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.ceo", "act.own", persona="persona.ceo"))

    report = AlignmentEngine(g).assess()
    solo = [f for f in report.misalignments if f.node_id == "act.solo"]
    assert solo == [], "one real contributor plus the registry is not a divergence"


# --- §7.2 structural findings — one fixture per row ---------------------------------------------


def _stage(g, sid, name, **kw):
    g.upsert_node(_node(sid, NodeType.STAGE, name, category_codes=["00"], **kw))


def test_unowned_stage():
    g = FakeGraphStore()
    _stage(g, "stg.build", "Build")
    g.upsert_node(_node("act.code", NodeType.ACTIVITY, "Write the code"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.code", "stg.build"))

    findings = AlignmentEngine(g).assess().of_kind(FindingKind.UNOWNED_STAGE)
    assert [f.node_id for f in findings] == ["stg.build"]
    assert "nobody is accountable" in findings[0].detail


def test_unmeasured_stage():
    g = FakeGraphStore()
    _stage(g, "stg.uat", "UAT")
    g.upsert_node(_node("act.test", NodeType.ACTIVITY, "Run the tests"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.test", "stg.uat"))

    findings = AlignmentEngine(g).assess().of_kind(FindingKind.UNMEASURED_STAGE)
    assert [f.node_id for f in findings] == ["stg.uat"]

    # Give it a KPI and the finding goes away.
    g.upsert_node(_node("kpi.defects", NodeType.KPI, "Defects found", category_codes=["10"]))
    g.add_edge(_edge(EdgeType.MEASURED_BY, "act.test", "kpi.defects"))
    assert AlignmentEngine(g).assess().of_kind(FindingKind.UNMEASURED_STAGE) == []


def test_a_single_activity_stage_is_not_reported_as_a_single_point_of_failure():
    """Otherwise every stage gets a SPOF row early in an engagement and the real ones drown."""
    g = FakeGraphStore()
    _stage(g, "stg.tiny", "Kickoff")
    g.upsert_node(_node("role.one", NodeType.ROLE, "Delivery Specialist"))
    g.upsert_node(_node("act.only", NodeType.ACTIVITY, "Hold the kickoff call"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.only", "stg.tiny"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.one", "act.only"))

    assert AlignmentEngine(g).assess().of_kind(FindingKind.SINGLE_POINT_OF_FAILURE) == []


def test_single_point_of_failure():
    g = FakeGraphStore()
    _stage(g, "stg.golive", "Go-Live")
    g.upsert_node(_node("role.only", NodeType.ROLE, "Solution Architect"))
    for i in (1, 2):
        g.upsert_node(_node(f"act.step{i}", NodeType.ACTIVITY, f"Step {i}"))
        g.add_edge(_edge(EdgeType.PART_OF, f"act.step{i}", "stg.golive"))
        g.add_edge(_edge(EdgeType.PERFORMS, "role.only", f"act.step{i}"))

    findings = AlignmentEngine(g).assess().of_kind(FindingKind.SINGLE_POINT_OF_FAILURE)
    assert [f.node_id for f in findings] == ["stg.golive"]
    assert findings[0].role_names == ("Solution Architect",)

    # A second performer clears it.
    g.upsert_node(_node("role.second", NodeType.ROLE, "Technical Specialist"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.second", "act.step2"))
    assert AlignmentEngine(g).assess().of_kind(FindingKind.SINGLE_POINT_OF_FAILURE) == []


def test_approval_with_no_criteria():
    g = FakeGraphStore()
    g.upsert_node(
        _node("appr.vague", NodeType.APPROVAL_POINT, "Discount sign-off", category_codes=["05"])
    )
    g.upsert_node(
        _node(
            "appr.clear",
            NodeType.APPROVAL_POINT,
            "Credit sign-off",
            category_codes=["05"],
            key_attributes={"condition": "over 10% discount"},
        )
    )

    findings = AlignmentEngine(g).assess().of_kind(FindingKind.APPROVAL_WITHOUT_CRITERIA)
    assert [f.node_id for f in findings] == ["appr.vague"], "a stated condition clears it"


def test_expectation_with_no_execution_behind_it():
    """An Objective on a stage its holder does NOT own, with nothing in the stage measured."""
    g = FakeGraphStore()
    _stage(g, "stg.support", "Support")
    g.upsert_node(_node("role.ceo", NodeType.ROLE, "Chief Executive Officer"))
    g.upsert_node(_node("role.qa", NodeType.ROLE, "Quality Assurance Specialist"))
    g.upsert_node(
        _node("obj.sla", NodeType.OBJECTIVE, "Two-hour response", category_codes=["11"])
    )
    g.add_edge(_edge(EdgeType.PURSUES, "role.ceo", "obj.sla"))
    g.add_edge(_edge(EdgeType.OBJECTIVE_FOR, "obj.sla", "stg.support"))
    # The stage is owned by someone else and has unmeasured work in it.
    g.add_edge(_edge(EdgeType.OWNS, "role.qa", "stg.support"))
    g.upsert_node(_node("act.reply", NodeType.ACTIVITY, "Reply to tickets"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.reply", "stg.support"))

    findings = AlignmentEngine(g).assess().of_kind(FindingKind.EXPECTATION_WITHOUT_EXECUTION)
    assert len(findings) == 1
    assert "Chief Executive Officer" in findings[0].detail
    assert "Two-hour response" in findings[0].detail
    assert "Support" in findings[0].detail


def test_an_objective_on_your_own_stage_is_not_an_expectation_on_someone_else():
    g = FakeGraphStore()
    _stage(g, "stg.support", "Support")
    g.upsert_node(_node("role.qa", NodeType.ROLE, "Quality Assurance Specialist"))
    g.upsert_node(_node("obj.sla", NodeType.OBJECTIVE, "Fast response", category_codes=["11"]))
    g.add_edge(_edge(EdgeType.PURSUES, "role.qa", "obj.sla"))
    g.add_edge(_edge(EdgeType.OBJECTIVE_FOR, "obj.sla", "stg.support"))
    g.add_edge(_edge(EdgeType.OWNS, "role.qa", "stg.support"))  # they own what they're aiming at

    assert AlignmentEngine(g).assess().of_kind(FindingKind.EXPECTATION_WITHOUT_EXECUTION) == []


def test_duplicated_work():
    g = FakeGraphStore()
    g.upsert_node(_node("art.in", NodeType.ARTIFACT, "Requirement note", category_codes=["07"]))
    g.upsert_node(_node("art.out", NodeType.ARTIFACT, "Spec", category_codes=["07"]))
    g.upsert_node(_node("role.ba", NodeType.ROLE, "Business Analysis Specialist"))
    g.upsert_node(_node("role.sa", NodeType.ROLE, "Solution Architect"))
    for act, role in (("act.ba-spec", "role.ba"), ("act.sa-spec", "role.sa")):
        g.upsert_node(_node(act, NodeType.ACTIVITY, f"Write spec ({role})"))
        g.add_edge(_edge(EdgeType.CONSUMES, act, "art.in"))
        g.add_edge(_edge(EdgeType.PRODUCES, act, "art.out"))
        g.add_edge(_edge(EdgeType.PERFORMS, role, act))

    findings = AlignmentEngine(g).assess().of_kind(FindingKind.DUPLICATED_WORK)
    assert len(findings) == 1
    assert set(findings[0].role_names) == {
        "Business Analysis Specialist",
        "Solution Architect",
    }


def test_silent_stage():
    """A stage described by others, with nobody who works in it interviewed."""
    g = FakeGraphStore()
    _stage(g, "stg.finance", "Invoicing")
    # Work is named inside it, but no role PERFORMS anything there.
    g.upsert_node(_node("act.invoice", NodeType.ACTIVITY, "Raise the invoice"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.invoice", "stg.finance"))

    findings = AlignmentEngine(g).assess().of_kind(FindingKind.SILENT_STAGE)
    assert [f.node_id for f in findings] == ["stg.finance"]

    # Once somebody performs work there, it stops being silent.
    g.upsert_node(_node("role.fin", NodeType.ROLE, "Finance"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.fin", "act.invoice"))
    assert AlignmentEngine(g).assess().of_kind(FindingKind.SILENT_STAGE) == []


def test_findings_are_ranked_with_misalignments_first():
    g = FakeGraphStore()
    _three_level_org(g)
    _stage(g, "stg.build", "Build")
    g.upsert_node(_node("act.code", NodeType.ACTIVITY, "Write the code"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.code", "stg.build"))
    _divergent_activity(
        g,
        personas=[
            ("persona.ceo", "role.ceo", "I sign it."),
            ("persona.dev", "role.dev", "We sign it."),
        ],
    )

    ranked = AlignmentEngine(g).assess().ranked()
    assert ranked[0].kind is FindingKind.MISALIGNMENT
    assert len(ranked) > 1, "structural findings should also be present"


def test_an_exec_commenting_on_someone_elses_activity_is_not_mistaken_for_that_role():
    """The bug this heuristic exists to stop, found while writing the docgen tests.

    A CEO who merely comments on the AM's activity picks up provenance on it. A naive first-match
    then identifies the CEO AS the Account Management Specialist, both contributors collapse onto one
    altitude, and the misalignment **silently disappears** — precisely the signal ADR #32 preserves.
    So role attribution weights an activity the persona is the SOLE contributor of above one they
    merely touched.
    """
    g = FakeGraphStore()
    g.upsert_node(_node("role.ceo", NodeType.ROLE, "Chief Executive Officer"))
    g.upsert_node(_node("role.am", NodeType.ROLE, "Account Management Specialist"))
    g.add_edge(_edge(EdgeType.REPORTS_TO, "role.am", "role.ceo"))

    # The CEO's own work — sole contributor, so conclusive evidence of which role they are.
    g.upsert_node(_node("act.strategy", NodeType.ACTIVITY, "Set the strategy",
                        provs=[_prov("persona.ceo")]))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.ceo", "act.strategy", persona="persona.ceo"))

    # The AM's activity, which the CEO ALSO commented on — and they disagree about it.
    g.upsert_node(
        _node(
            "act.demo",
            NodeType.ACTIVITY,
            "Run the demo",
            provs=[
                _prov("persona.am", account="We reuse one standard deck."),
                _prov("persona.ceo", status=ConfidenceStatus.CONFLICTING,
                      account="Every demo is tailored per client."),
            ],
        )
    )
    g.add_edge(_edge(EdgeType.PERFORMS, "role.am", "act.demo", persona="persona.am"))

    engine = AlignmentEngine(g)
    snap = load_snapshot(g)

    # Attribution: each persona resolves to the role they actually ARE.
    assert engine._persona_role("persona.ceo", snap)[0] == "role.ceo"
    assert engine._persona_role("persona.am", snap)[0] == "role.am"

    # ...so the altitudes differ and the divergence survives as a finding.
    mis = engine.assess().misalignments
    assert len(mis) == 1, "the misalignment was swallowed by bad role attribution"
    assert sorted(a.altitude for a in mis[0].accounts) == [0, 1]
