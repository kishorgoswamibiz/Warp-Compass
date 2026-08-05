"""P16a + P16a-bis — a declared role is owned, and a role's open questions reach every holder.

Two bugs, one wire (`profile.json` -> the brain):

* **P16a / routing in.** A colleague hands work to a role a multi-hat person *declared* but whose
  work never earned a `PERFORMS` edge under that hat. Pre-P16a the role had no owner, so the
  colleague was asked "who would know?" every round and the real person was never asked at all.
* **P16a-bis / routing out.** Persona scoping could only ask somebody about nodes they had already
  spoken about, so a role's open gaps never reached its *other* holders — three Business Analysts
  each describing a quarter of the role left a quarter that nobody was ever asked.

The invariant that must survive both: **provenance stays keyed to the person.** Only *scoping* is
role-shaped. See `docs/plan/phase-16-hat-fidelity.md` §2 Finding 5 and ADRs #34/#36.

No Neo4j, no network, no bus — declared roles go in as a plain dict.
"""

from __future__ import annotations

from conftest import FakeGraphStore

from warp_compass_brain.coverage import build_coverage, render_coverage
from warp_compass_brain.crosspersona import (
    KIND_HANDOFF_CONFIRM,
    KIND_HANDOFF_SELF,
    KIND_HANDOFF_TRACE,
    CrossPersonaEngine,
)
from warp_compass_brain.lifecycle import declared_roles, profile_role_titles
from warp_compass_brain.models import (
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)
from warp_compass_brain.ontology import load_ontology
from warp_compass_brain.planner import Planner
from warp_compass_brain.roles import REGISTRY_SAID_BY, resolve_declared_roles

ONT = load_ontology()
TS = "2026-08-05T10:00:00Z"

BA = "Business Analysis Specialist"
TECH = "Technical Specialist"


def _prov(persona, status=ConfidenceStatus.UNVERIFIED):
    return Provenance(said_by=persona, session_id="s1", confidence=0.8, status=status, ts=TS)


def _node(node_id, ntype, name, *, personas, aliases=()):
    if isinstance(personas, str):
        personas = [personas]
    return NodeCard(
        id=node_id,
        type=ntype,
        canonical_name=name,
        description=f"{name} description",
        category_codes=["02"],
        aliases=list(aliases),
        provenance=[_prov(p) for p in personas],
    )


def _edge(etype, a, b, persona="persona.A"):
    return Edge(type=etype, from_id=a, to_id=b, provenance=[_prov(persona)])


def _role(g, role_id, name, *, personas=REGISTRY_SAID_BY, aliases=()):
    g.upsert_node(_node(role_id, NodeType.ROLE, name, personas=personas, aliases=aliases))


def _activity(g, act_id, name, *, personas, role_id=None):
    """An activity with no completeness fields -> it generates MISSING_FIELD gaps."""
    g.upsert_node(_node(act_id, NodeType.ACTIVITY, name, personas=personas))
    if role_id:
        g.add_edge(_edge(EdgeType.PERFORMS, role_id, act_id))


def _planner(g, declared=None, **kw) -> Planner:
    return Planner(g, ONT, now=TS, declared_roles=declared or {}, **kw)


def _thread_nodes(brief) -> set[str]:
    """The node names a brief's threads are about, read off the openers + goals."""
    return {f"{t.goal} {t.suggested_opener}" for t in brief.open_threads}


def _mentions(brief, needle: str) -> bool:
    return any(needle in f"{t.goal} {t.why} {t.suggested_opener}" for t in brief.open_threads)


# --- P16a: a declared role is owned -------------------------------------------------------------


def _handoff_graph():
    """A colleague hands the build to the Technical Specialist, whom nobody has described."""
    g = FakeGraphStore()
    _role(g, "role.ba", BA, personas="persona.colleague")
    _role(g, "role.tech", TECH, personas="persona.colleague")
    _activity(g, "act.spec", "Write the spec", personas="persona.colleague", role_id="role.ba")
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.spec", "role.tech"))
    return g


def test_declared_role_is_owned_so_the_handoff_reaches_the_real_person():
    """The forever-loop regression: the point of P16a.

    Priya declared Technical Specialist but every activity she described landed under another hat
    (the extractor cannot see who is speaking — phase-16 §2 Finding 1). Pre-P16a `role.tech` had no
    owner, so the *colleague* was asked "who picks this up?" forever.
    """
    g = _handoff_graph()
    declared = {"persona.priya": (TECH,)}

    report = CrossPersonaEngine(g, ONT, now=TS, declared_roles=declared).assess()

    assert [h.state for h in report.handoffs] == ["route_receiver"]
    confirm = [rt for rt in report.routed if rt.thread.kind == KIND_HANDOFF_CONFIRM]
    assert {rt.persona_id for rt in confirm} == {"persona.priya"}
    # ...and the colleague is no longer asked to go find them.
    assert not [rt for rt in report.routed if rt.thread.kind == KIND_HANDOFF_TRACE]


def test_declaring_both_sides_of_a_handoff_makes_it_a_dual_hat_question():
    """P16a composes with P15a §4.5 rather than bypassing it.

    Kishor declared *both* the giving and the receiving role, so the handoff happens inside one
    person. Routing him the standard "a colleague handed this to you" copy would read as a bug and
    invite a "that's me" non-answer; he gets the hat-switch question instead — which is the step
    most likely to be tacit and undocumented.
    """
    g = _handoff_graph()

    report = CrossPersonaEngine(
        g, ONT, now=TS, declared_roles={"persona.kishor": (BA, TECH)}
    ).assess()

    assert [h.state for h in report.handoffs] == ["route_receiver"]
    routed = [rt for rt in report.routed if rt.persona_id == "persona.kishor"]
    assert [rt.thread.kind for rt in routed] == [KIND_HANDOFF_SELF]
    assert "hat" in routed[0].thread.goal


def test_without_the_declaration_it_still_loops_on_the_discoverer():
    """The same graph with no declared roles — proves the fix is the declaration, not the graph."""
    report = CrossPersonaEngine(_handoff_graph(), ONT, now=TS).assess()

    assert [h.state for h in report.handoffs] == ["route_discoverer"]
    trace = [rt for rt in report.routed if rt.thread.kind == KIND_HANDOFF_TRACE]
    assert {rt.persona_id for rt in trace} == {"persona.colleague"}


def test_mentioning_a_role_still_does_not_own_it():
    """P16a sharpens the old rule, it does not discard it (ADR #34).

    The colleague has provenance on the Technical Specialist ROLE node — they mentioned it, that is
    how it got there. That must still not make them its owner, or every handoff would resolve to
    whoever named the receiving role.
    """
    g = _handoff_graph()
    tech = g.get_node("role.tech")
    assert any(p.said_by == "persona.colleague" for p in tech.provenance)  # they mentioned it

    report = CrossPersonaEngine(g, ONT, now=TS).assess()
    assert [h.state for h in report.handoffs] == ["route_discoverer"]


def test_declaration_resolves_onto_an_adopted_node_id():
    """`seed_roles` may ADOPT an older node id (`role.business-analyst`) rather than mint the
    registry slug. Resolving a declaration against the registry slug would then point at a node
    that does not exist and the declared role would silently own nothing."""
    g = FakeGraphStore()
    _role(g, "role.business-analyst", "Business Analyst", aliases=[BA, "BA"])
    _role(g, "role.tech", TECH)
    _activity(g, "act.spec", "Write the spec", personas="persona.colleague", role_id="role.tech")
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.spec", "role.business-analyst"))

    report = CrossPersonaEngine(
        g, ONT, now=TS, declared_roles={"persona.kishor": (BA,)}
    ).assess()

    assert [h.state for h in report.handoffs] == ["route_receiver"]
    assert {rt.persona_id for rt in report.routed} == {"persona.kishor"}


def test_the_registry_is_never_a_routing_target():
    """Seeded roles carry `registry` provenance. It is vocabulary, not somebody who can be asked."""
    g = _handoff_graph()
    g.upsert_node(_node("act.reg", NodeType.ACTIVITY, "Seeded work", personas=REGISTRY_SAID_BY))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.tech", "act.reg"))

    report = CrossPersonaEngine(g, ONT, now=TS).assess()
    assert REGISTRY_SAID_BY not in {rt.persona_id for rt in report.routed}


# --- P16a-bis: a role's gaps reach every holder -------------------------------------------------


def _three_bas():
    """BA#1 described one activity; BA#2 and BA#3 hold the same role and have said nothing."""
    g = FakeGraphStore()
    _role(g, "role.ba", BA)
    _activity(g, "act.stories", "Write user stories", personas="persona.ba1", role_id="role.ba")
    declared = {p: (BA,) for p in ("persona.ba1", "persona.ba2", "persona.ba3")}
    return g, declared


def test_a_roles_open_gap_reaches_every_holder_of_that_role():
    """The owner's case: three BAs each describe a quarter, so the missing quarter fires at all."""
    g, declared = _three_bas()
    planner = _planner(g, declared)

    for persona in ("persona.ba2", "persona.ba3"):
        brief = planner.plan(persona, session_id="s1")
        assert brief.open_threads, f"{persona} got an empty brief"
        assert _mentions(brief, "Write user stories")
        assert _mentions(brief, BA), "the opener must name the role, not invent work"


def test_the_gap_closes_for_everyone_the_moment_one_holder_answers():
    """Self-clearing, with no ledger: gaps are recomputed from the graph every round.

    This is what makes "fire at all holders" safe rather than a spam loop.
    """
    g, declared = _three_bas()
    before = _planner(g, declared).plan("persona.ba2", session_id="s1")
    assert _mentions(before, "Write user stories")

    # BA#1 answers the trigger question: the activity gains what it was missing.
    g.upsert_node(_node("ev.kickoff", NodeType.EVENT, "Kickoff call", personas="persona.ba1"))
    g.add_edge(_edge(EdgeType.TRIGGERS, "ev.kickoff", "act.stories"))

    after = _planner(g, declared).plan("persona.ba2", session_id="s1")
    triggers = [t for t in after.open_threads if "kicks off" in t.suggested_opener]
    assert not triggers, "an answered gap must vanish from every other holder's brief"


def test_inherited_threads_never_outrank_your_own_work():
    """Structural floor, same as P13 orphans: someone else's account of your role is never rank 1."""
    g, declared = _three_bas()
    # BA#2 now has an activity of their own.
    _activity(g, "act.uat", "Run UAT", personas="persona.ba2", role_id="role.ba")

    brief = _planner(g, declared).plan("persona.ba2", session_id="s1")
    own = [i for i, t in enumerate(brief.open_threads) if not t.id.startswith("role.")]
    inherited = [i for i, t in enumerate(brief.open_threads) if t.id.startswith("role.")]
    assert own and inherited
    assert max(own) < min(inherited)


def test_a_holder_with_no_contributions_still_gets_a_real_brief():
    """P16a-bis part C. `live_personas` used to be derived from provenance alone, so a newly joined
    BA was absent from `plan_all` entirely: no brief written, and their first session fell back to
    generic cold-start openers while their role's questions sat unasked."""
    g, declared = _three_bas()
    planner = _planner(g, declared)

    assert "persona.ba3" not in planner.personas()      # has contributed nothing
    assert "persona.ba3" in planner.live_personas()     # ...but is on the bus, so gets a brief

    briefs = {b.persona_id: b for b in planner.plan_all(session_id="s1")}
    assert "persona.ba3" in briefs
    assert briefs["persona.ba3"].open_threads
    assert BA in briefs["persona.ba3"].persona_summary


def test_inheritance_is_declared_never_inferred_from_contribution():
    """The WC-R5 over-reach must not come back through this door.

    An exec who merely *comments on* a BA activity picks up provenance on it. If inheritance were
    computed from contribution rather than declaration, they would start receiving the BA's entire
    question set — which is exactly the mis-attribution `alignment._persona_role` had to be hardened
    against in P15c.
    """
    g, declared = _three_bas()
    # The CEO comments on the BA's activity: real provenance, not a declaration.
    g.add_provenance("act.stories", _prov("persona.ceo"))
    _role(g, "role.ceo", "Chief Executive Officer")
    declared["persona.ceo"] = ("Chief Executive Officer",)

    brief = _planner(g, declared).plan("persona.ceo", session_id="s1")
    assert not [t for t in brief.open_threads if t.id.startswith("role.")]


def test_a_retired_holder_is_never_planned_for():
    """Retirement outranks both sources of personhood (graph provenance and the declared map)."""
    g, declared = _three_bas()
    planner = _planner(g, declared, retired_personas={"persona.ba3"})

    assert "persona.ba3" not in planner.live_personas()
    assert "persona.ba3" not in {b.persona_id for b in planner.plan_all(session_id="s1")}


def test_declaring_nothing_still_gets_you_a_brief():
    """Someone who skipped the role chips is a real person, not a non-entity. They inherit nothing
    (there is no role to inherit from) but must not silently drop out of the round."""
    g, declared = _three_bas()
    declared["persona.quiet"] = ()

    planner = _planner(g, declared)
    assert "persona.quiet" in planner.live_personas()
    brief = planner.plan("persona.quiet", session_id="s1")
    assert not [t for t in brief.open_threads if t.id.startswith("role.")]


def test_a_declared_role_with_no_node_in_the_graph_inherits_nothing_quietly():
    """phase-16 R8: declaring a role nobody has seeded or mentioned is not an error — it is a role
    nobody has described yet. It must not raise, and `coverage` is where it becomes visible."""
    g, declared = _three_bas()
    declared["persona.ba2"] = (BA, "Chief Astrologer")

    brief = _planner(g, declared).plan("persona.ba2", session_id="s1")
    assert _mentions(brief, "Write user stories")  # the real role still works


def test_provenance_stays_keyed_to_the_person():
    """The invariant the whole design rests on (ADR #36).

    Role-scoping changes which questions a person is *asked*. If it ever changed what provenance is
    *stamped with*, two BAs agreeing would become indistinguishable from one BA repeating himself,
    and peer-conflict detection would go with it.
    """
    g, declared = _three_bas()
    before = {(c.id, p.said_by) for c in g.nodes.values() for p in c.provenance}

    _planner(g, declared).plan_all(session_id="s1")

    after = {(c.id, p.said_by) for c in g.nodes.values() for p in c.provenance}
    assert after == before, "planning must never write provenance, let alone role-keyed"
    # And what is there is still keyed to a *person* (plus the registry's vocabulary marker),
    # never to a role — which is what keeps two BAs agreeing distinguishable from one repeating.
    assert {s for _, s in after} == {"persona.ba1", REGISTRY_SAID_BY}
    assert not any(s.startswith("role.") for _, s in after)


# --- lifecycle: reading the declaration off a profile -------------------------------------------


def test_role_titles_array_is_the_truth_when_present():
    assert profile_role_titles({"role_titles": [BA, TECH]}) == (BA, TECH)


def test_joined_role_title_is_split_back_for_a_pre_p15a_deployment():
    """Not defensive padding — this is the live case. Verified 04 Aug 2026: the deployed Apps Script
    is the P13 build, which writes the joined string and drops the array."""
    assert profile_role_titles({"role_title": f"{BA} / {TECH}"}) == (BA, TECH)


def test_profile_role_titles_is_empty_when_nothing_was_declared():
    assert profile_role_titles({}) == ()
    assert profile_role_titles({"role_title": "   "}) == ()


def test_profile_role_titles_dedups_and_trims():
    assert profile_role_titles({"role_titles": [" BA ", "BA", ""]}) == ("BA",)


def test_declared_roles_keys_on_persona_id_and_includes_the_role_less(tmp_path):
    from warp_compass_brain.bus import FolderBus

    bus = FolderBus(str(tmp_path))
    bus.ensure_participant("kishor-8750")
    bus.write_profile(
        "kishor-8750",
        {"persona_id": "persona.kishor", "role_title": f"{BA} / {TECH}"},
    )
    bus.ensure_participant("quiet-1234")
    bus.write_profile("quiet-1234", {"persona_id": "persona.quiet"})

    assert declared_roles(bus) == {
        "persona.kishor": (BA, TECH),
        "persona.quiet": (),
    }


def test_resolve_declared_roles_drops_a_title_nothing_answers_to():
    g = FakeGraphStore()
    _role(g, "role.ba", BA, aliases=["BA"])
    cards = [c for c in g.nodes.values() if c.type is NodeType.ROLE]

    assert resolve_declared_roles(["ba"], cards) == {"role.ba"}      # alias, case-insensitive
    assert resolve_declared_roles(["Chief Astrologer"], cards) == set()


# --- coverage: the R1 guardrail -----------------------------------------------------------------


def test_coverage_separates_declared_but_silent_from_nobody_owns_this():
    """Pre-P16a these were indistinguishable, and only the second is an invite-list entry.

    Since P16a a declared role is a routing target, so a declared role that stays empty round after
    round is the signal that either the questions aren't landing or the chip was ticked in error.
    """
    g = FakeGraphStore()
    _role(g, "role.ba", BA, personas="persona.colleague")
    _role(g, "role.tech", TECH, personas="persona.colleague")
    _activity(g, "act.spec", "Write the spec", personas="persona.colleague", role_id="role.ba")

    report = build_coverage(g, {"persona.kishor": (TECH,)})

    silent = {r.role_id for r in report.roles_declared_but_silent}
    unowned = {r.role_id for r in report.roles_without_an_owner}
    assert silent == {"role.tech"}
    assert "role.tech" not in unowned
    assert report.roles_declared_but_silent[0].declared_by == ["persona.kishor"]


def test_coverage_without_a_bus_is_unchanged():
    """`declared_roles` is optional: the P15b report over a bare graph must be byte-identical."""
    g = FakeGraphStore()
    _role(g, "role.tech", TECH, personas="persona.colleague")
    _activity(g, "act.spec", "Write the spec", personas="persona.colleague")

    assert render_coverage(build_coverage(g)) == render_coverage(build_coverage(g, {}))
    assert {r.role_id for r in build_coverage(g).roles_without_an_owner} == {"role.tech"}


def test_declaring_a_role_someone_else_described_is_not_an_invite_list_entry():
    """`coverage.owners_of` stays narrower than `crosspersona._role_owner_personas` on purpose —
    folding declaration in would hide exactly the case P16a introduced.

    Here the role IS interviewed (the colleague described its work) and Kishor *also* holds it. He
    is listed as a declarer who hasn't described anything yet — useful, since he is now receiving
    the role's inherited gaps — but the role is not silent and is not an invite-list entry.
    """
    g = FakeGraphStore()
    _role(g, "role.tech", TECH, personas="persona.colleague")
    g.upsert_node(_node("stage.build", NodeType.STAGE, "Build", personas="persona.colleague"))
    _activity(g, "act.dev", "Develop", personas="persona.colleague")
    g.add_edge(_edge(EdgeType.PERFORMS, "role.tech", "act.dev"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.dev", "stage.build"))

    report = build_coverage(g, {"persona.kishor": (TECH,)})
    role = report.stages[0].roles[0]
    assert role.interviewed_by == ["persona.colleague"]  # described the work
    assert role.declared_by == ["persona.kishor"]        # holds it, hasn't described it
    assert not role.is_declared_but_silent               # somebody HAS described the work
    assert report.roles_declared_but_silent == []
    assert report.roles_without_an_owner == []


def test_coverage_render_stays_pure_ascii_with_declared_roles(capsys):
    """WC-R6's lesson, extended to the rows P16a adds. The CLI reconfigures stdout to UTF-8, but
    this renderer's contract is ASCII and the new `[~]` marker must not break it."""
    g = FakeGraphStore()
    _role(g, "role.tech", TECH, personas="persona.colleague")
    _activity(g, "act.spec", "Write the spec", personas="persona.colleague", role_id="role.ba")

    text = render_coverage(build_coverage(g, {"persona.kishor": (TECH,)}))
    text.encode("cp1252")  # the operation that used to crash a Windows console
    assert text.isascii()
