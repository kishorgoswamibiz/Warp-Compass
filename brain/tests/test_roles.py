"""P15a — the role registry, seeding, and the alias behaviour the whole design leans on.

The centrepiece is ``test_the_pm_resolves_onto_delivery_specialist``: it encodes the failure the
alias table exists to prevent. Without it, "the PM" mints a rival Role node, that node has no owner,
and every handoff to it routes back to whoever mentioned them as "who would know?" forever, while the
real Delivery Specialist is never asked (docs/plan/phase-15-lifecycle-and-alignment.md §4.3).
"""

from __future__ import annotations

import json
import re

import pytest
from conftest import FakeGraphStore

from warp_compass_brain.crosspersona import (
    KIND_HANDOFF_CONFIRM,
    KIND_HANDOFF_TRACE,
    CrossPersonaEngine,
)
from warp_compass_brain.llm.base import LLMProvider
from warp_compass_brain.models import (
    CandidateNode,
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)
from warp_compass_brain.ontology import load_ontology
from warp_compass_brain.resolve import Resolver
from warp_compass_brain.roles import (
    _DEFAULT_ROLES_PATH,
    REGISTRY_SAID_BY,
    RoleRegistry,
    load_roles,
    seed_roles,
)
from warp_compass_brain.vectorindex.embedder import HashingEmbedder
from warp_compass_brain.vectorindex.local_index import LocalVectorIndex

TS = "2026-08-04T10:00:00Z"
REG = load_roles()
ONT = load_ontology()


def _prov(persona: str) -> Provenance:
    return Provenance(
        said_by=persona, session_id="s1", confidence=0.8, status=ConfidenceStatus.UNVERIFIED, ts=TS
    )


def _edge(etype, a, b, persona: str = "persona.ba") -> Edge:
    return Edge(type=etype, from_id=a, to_id=b, provenance=[_prov(persona)])


# --- the contract itself ----------------------------------------------------------------------


def test_registry_holds_the_ten_roles_the_owner_specified():
    assert REG.canonical_names == (
        "Business Analysis Specialist",
        "Technical Specialist",
        "Solution Architect",
        "Delivery Specialist",
        "Account Management Specialist",
        "Quality Assurance Head",
        "Quality Assurance Specialist",
        "Finance",
        "Chief Executive Officer",
        "Chief Operating Officer",
    )


@pytest.mark.parametrize(
    ("spoken", "canonical"),
    [
        ("PM", "Delivery Specialist"),
        ("Project Manager", "Delivery Specialist"),
        ("BA", "Business Analysis Specialist"),
        ("developer", "Technical Specialist"),  # case-insensitive
        ("Sales", "Account Management Specialist"),  # owner's decision, 04 Aug 2026
        ("CEO", "Chief Executive Officer"),
        ("COO", "Chief Operating Officer"),
        ("QA", "Quality Assurance Specialist"),
        ("QA Head", "Quality Assurance Head"),  # exact matching keeps these apart
    ],
)
def test_find_resolves_the_words_people_actually_say(spoken, canonical):
    entry = REG.find(spoken)
    assert entry is not None, f"{spoken!r} resolves to nothing — it would fork a new Role node"
    assert entry.canonical_name == canonical


def test_unknown_role_resolves_to_nothing_rather_than_guessing():
    # An external party is NOT in the registry, and must not be forced into it.
    assert REG.find("End Client") is None


def test_duplicate_alias_is_rejected_because_it_would_merge_two_roles():
    bad = {
        "roles": [
            {"slug": "role.a", "canonical_name": "Role A", "aliases": ["Shared"]},
            {"slug": "role.b", "canonical_name": "Role B", "aliases": ["Shared"]},
        ]
    }
    with pytest.raises(ValueError, match="claimed by both"):
        RoleRegistry(bad)


def test_alias_colliding_with_another_canonical_name_is_rejected():
    bad = {
        "roles": [
            {"slug": "role.a", "canonical_name": "Finance", "aliases": []},
            {"slug": "role.b", "canonical_name": "Role B", "aliases": ["Finance"]},
        ]
    }
    with pytest.raises(ValueError, match="claimed by both"):
        RoleRegistry(bad)


def test_explicit_path_loads_the_same_registry(tmp_path):
    """Covers the loader's non-cached branch (used by ``cli seed-roles --roles``)."""
    src = json.loads(_DEFAULT_ROLES_PATH.read_text(encoding="utf-8"))
    p = tmp_path / "roles.json"
    p.write_text(json.dumps(src), encoding="utf-8")
    assert load_roles(p).canonical_names == REG.canonical_names


# --- seeding ----------------------------------------------------------------------------------


def test_seed_creates_every_role_with_its_aliases():
    g = FakeGraphStore()
    result = seed_roles(g, REG, now=TS)

    assert len(result.created) == len(REG.roles)
    assert not result.updated and not result.adopted
    ds = g.get_node("role.delivery-specialist")
    assert ds is not None
    assert ds.type is NodeType.ROLE
    assert ds.canonical_name == "Delivery Specialist"
    assert set(ds.aliases) == {"Project Manager", "PM", "DS", "Delivery Manager"}


def test_seed_is_idempotent():
    g = FakeGraphStore()
    seed_roles(g, REG, now=TS)
    before = len(g.nodes)

    again = seed_roles(g, REG, now=TS)

    assert len(g.nodes) == before
    assert not again.created
    assert len(again.unchanged) == len(REG.roles)


def test_dry_run_writes_nothing():
    g = FakeGraphStore()
    result = seed_roles(g, REG, now=TS, dry_run=True)
    assert len(result.created) == len(REG.roles)
    assert g.nodes == {}


def test_seed_tops_up_aliases_on_a_node_that_already_exists_at_the_slug():
    g = FakeGraphStore()
    g.upsert_node(
        NodeCard(
            id="role.delivery-specialist",
            type=NodeType.ROLE,
            canonical_name="Delivery Specialist",
            aliases=["PM"],  # only one of the four
            description="Described by a person before the registry was seeded.",
            category_codes=["04"],
            provenance=[
                Provenance(said_by="p_ajay", session_id="s1", confidence=0.9, ts=TS)
            ],
        )
    )

    result = seed_roles(g, REG, now=TS)

    assert "role.delivery-specialist" in result.updated
    card = g.get_node("role.delivery-specialist")
    assert set(card.aliases) >= {"PM", "Project Manager", "DS", "Delivery Manager"}
    # The person's own provenance survives; seeding never overwrites testimony.
    assert [p.said_by for p in card.provenance] == ["p_ajay"]


def test_seed_adopts_an_existing_node_under_a_different_id_instead_of_minting_a_rival():
    """The old graph named this role ``role.business-analyst``; the registry says
    ``role.business-analysis-specialist``. Node ids are stamped into every edge and provenance
    entry, so the existing node must be extended, never duplicated or renamed."""
    g = FakeGraphStore()
    g.upsert_node(
        NodeCard(
            id="role.business-analyst",
            type=NodeType.ROLE,
            canonical_name="Business Analyst",
            description="Minted from an interview before the registry existed.",
            category_codes=["04"],
            provenance=[
                Provenance(said_by="p_kishor", session_id="s1", confidence=0.9, ts=TS)
            ],
        )
    )

    result = seed_roles(g, REG, now=TS)

    assert ("role.business-analysis-specialist", "role.business-analyst") in result.adopted
    assert g.get_node("role.business-analysis-specialist") is None, "must not mint a rival node"
    card = g.get_node("role.business-analyst")
    assert card.canonical_name == "Business Analyst", "the person's own words are preserved"
    # ...but the registry title and abbreviation now resolve onto it.
    assert "Business Analysis Specialist" in card.aliases
    assert g.find_by_alias("BA", NodeType.ROLE.value)[0].id == "role.business-analyst"


def test_seeded_provenance_is_the_registry_not_a_persona():
    g = FakeGraphStore()
    seed_roles(g, REG, now=TS)
    card = g.get_node("role.finance")
    assert [p.said_by for p in card.provenance] == [REGISTRY_SAID_BY]
    assert card.provenance[0].status is ConfidenceStatus.UNVERIFIED


# --- the failure this whole mechanism exists to prevent (plan §4.3) ---------------------------


def test_the_pm_resolves_onto_delivery_specialist():
    """A mention of "the PM" must land on the seeded Delivery Specialist node.

    This is the exact-match alias lookup the resolver tries FIRST, before vector similarity — where
    the default lexical embedder would never connect "PM" to "Delivery Specialist".
    """
    g = FakeGraphStore()
    seed_roles(g, REG, now=TS)

    for spoken in ("PM", "the pm".replace("the ", ""), "Project Manager", "project manager"):
        hits = g.find_by_alias(spoken, NodeType.ROLE.value)
        assert [h.id for h in hits] == ["role.delivery-specialist"], f"{spoken!r} forked"


def test_seeding_leaves_qa_head_and_qa_specialist_as_separate_nodes():
    g = FakeGraphStore()
    seed_roles(g, REG, now=TS)
    assert g.find_by_alias("QA", NodeType.ROLE.value)[0].id == "role.quality-assurance-specialist"
    assert g.find_by_alias("QA Head", NodeType.ROLE.value)[0].id == "role.quality-assurance-head"


# --- the consequence, end to end: resolution → ownership → routing (plan §11 item 3) -----------
#
# The tests above prove "the PM" lands on the right NODE. These prove the thing the owner actually
# cares about: that the question then reaches the right PERSON. They run the real Resolver and the
# real CrossPersonaEngine, with the seeded/unseeded registry as the only difference between them.


def _ba_hands_off_to_the_pm(g, *, pm_role_id: str):
    """The BA describes writing a BRD and handing it to whoever ``pm_role_id`` turned out to be."""
    for card in (
        NodeCard(
            id="role.business-analysis-specialist-actor",
            type=NodeType.ROLE,
            canonical_name="Business Analysis Specialist (as interviewed)",
            description="the BA we interviewed",
            category_codes=["04"],
            provenance=[_prov("persona.ba")],
        ),
        NodeCard(
            id="act.write-brd",
            type=NodeType.ACTIVITY,
            canonical_name="Write the BRD",
            description="capture requirements",
            category_codes=["02"],
            provenance=[_prov("persona.ba")],
        ),
        NodeCard(
            id="art.brd",
            type=NodeType.ARTIFACT,
            canonical_name="BRD",
            description="the requirements document",
            category_codes=["03"],
            provenance=[_prov("persona.ba")],
        ),
    ):
        g.upsert_node(card)
    g.add_edge(_edge(EdgeType.PERFORMS, "role.business-analysis-specialist-actor", "act.write-brd"))
    g.add_edge(_edge(EdgeType.PRODUCES, "act.write-brd", "art.brd"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.write-brd", pm_role_id))


def _delivery_specialist_is_interviewed(g):
    """A second human is interviewed AS the Delivery Specialist, so that role has an owner."""
    g.upsert_node(
        NodeCard(
            id="act.run-standup",
            type=NodeType.ACTIVITY,
            canonical_name="Run the daily standup",
            description="keep the build moving",
            category_codes=["02"],
            provenance=[_prov("persona.ds")],
        )
    )
    g.add_edge(
        _edge(EdgeType.PERFORMS, "role.delivery-specialist", "act.run-standup", persona="persona.ds")
    )


def _resolve_role_mention(g, spoken: str):
    """Run the real ``Resolver`` over a Role candidate named ``spoken``.

    Returns ``(retrieved, landed_on)``. The vector index is the production default
    (``HashingEmbedder`` — lexical only, per the plan's Blockers note).

    What the alias table changes is **retrieval**, and that is what these tests assert. An
    ``via="alias"`` hit at score 1.0 is a *determined* match — ``find_by_alias`` found the node by
    exact whole-string lookup before the model was consulted at all. A ``via="vector"`` hit is not:
    it is a low-similarity neighbour handed to the adjudicator, and whether the mention forks is then
    the model's call on any given day. The stub LLM below agrees with whatever retrieval ranked
    first, so nothing here depends on model taste in either direction.
    """
    vector = LocalVectorIndex(":memory:", HashingEmbedder())
    for card in g.nodes_by_type(NodeType.ROLE.value):
        vector.add(card.id, card.canonical_name + " " + card.description)

    cand = CandidateNode(
        ref="n1", type=NodeType.ROLE, canonical_name=spoken, description="signs off the BRD"
    )
    resolver = Resolver(g, vector, ONT, _SaysSameLLM())
    retrieved = resolver.retrieve(cand)
    adj = resolver.adjudicate(cand, retrieved)
    return retrieved, ("" if adj.verdict == "new" else (adj.match_id or ""))


class _SaysSameLLM(LLMProvider):
    """Agrees with the top retrieval candidate, so the test measures retrieval, not model taste."""

    def complete_json(self, system, user, *, temperature=0.0):
        match = re.search(r"^- id=(\S+)", user, re.MULTILINE)
        return {"verdict": "same", "match_id": match.group(1) if match else None, "reason": "alias"}


def test_with_the_registry_seeded_the_handoff_reaches_the_delivery_specialist():
    """The design working: "the PM" resolves onto the seeded node, so the DS gets asked."""
    g = FakeGraphStore()
    seed_roles(g, REG, now=TS)

    retrieved, landed_on = _resolve_role_mention(g, "Project Manager")
    # Determined by exact alias lookup at score 1.0 — the model was never the deciding factor.
    top = retrieved[0]
    assert (top.card.id, top.via, top.score) == ("role.delivery-specialist", "alias", 1.0)
    assert landed_on == "role.delivery-specialist", "the alias table should have caught this"

    _ba_hands_off_to_the_pm(g, pm_role_id=landed_on)
    _delivery_specialist_is_interviewed(g)

    report = CrossPersonaEngine(g, ONT, now=TS).assess()
    assert [h.state for h in report.handoffs] == ["route_receiver"]

    routed = [rt for rt in report.routed if rt.thread.node_id == "act.write-brd"]
    # The question lands in the Delivery Specialist's brief — NOT back on the BA as a trace.
    assert [(rt.persona_id, rt.thread.kind) for rt in routed] == [
        ("persona.ds", KIND_HANDOFF_CONFIRM)
    ]
    assert not [rt for rt in routed if rt.thread.kind == KIND_HANDOFF_TRACE]
    assert "role.project-manager" not in {c.id for c in g.nodes_by_type(NodeType.ROLE.value)}


def test_without_the_registry_nothing_determines_the_match():
    """Half of the §4.3 failure: with no alias table the match is left to chance.

    Deliberately NOT asserted here: that the verdict *is* "new". With one Role node in the graph the
    lexical index returns it as a neighbour whatever its similarity, so the outcome depends on what
    the adjudicating model decides about "Project Manager" vs "Delivery Specialist" — which is the
    whole problem. The assertable, load-bearing fact is that **no exact match protects it**: the only
    hit is a weak vector neighbour, so the fork in the next test is a live possibility rather than a
    hypothetical.
    """
    g = FakeGraphStore()  # NO seed_roles — the alias table does not exist
    _delivery_specialist_is_interviewed_without_seeding(g)

    assert g.find_by_alias("Project Manager", NodeType.ROLE.value) == []
    assert g.find_by_alias("PM", NodeType.ROLE.value) == []

    retrieved, _ = _resolve_role_mention(g, "Project Manager")
    assert [r.via for r in retrieved] == ["vector"], "no alias hit — the model is left to guess"
    assert retrieved[0].score < 0.9, "and on a weak lexical neighbour at that"


def test_once_the_role_forks_the_ba_is_asked_who_would_know_and_the_ds_never_is():
    """The other half of §4.3: the routing consequence, asserted so a refactor can't lose it."""
    g = FakeGraphStore()
    _delivery_specialist_is_interviewed_without_seeding(g)

    # The fork the previous test shows is unguarded: a rival Role node, and the handoff points at it.
    g.upsert_node(
        NodeCard(
            id="role.project-manager",
            type=NodeType.ROLE,
            canonical_name="Project Manager",
            description="signs off the BRD",
            category_codes=["04"],
            provenance=[_prov("persona.ba")],
        )
    )
    _ba_hands_off_to_the_pm(g, pm_role_id="role.project-manager")

    report = CrossPersonaEngine(g, ONT, now=TS).assess()
    assert [h.state for h in report.handoffs] == ["route_discoverer"]

    routed = [rt for rt in report.routed if rt.thread.node_id == "act.write-brd"]
    # The BA is asked "who would know?" — and the real Delivery Specialist is never asked.
    assert [(rt.persona_id, rt.thread.kind) for rt in routed] == [
        ("persona.ba", KIND_HANDOFF_TRACE)
    ]
    assert "persona.ds" not in {rt.persona_id for rt in routed}
    roles = {c.id for c in g.nodes_by_type(NodeType.ROLE.value)}
    assert {"role.project-manager", "role.delivery-specialist"} <= roles, "forked into two"


def _delivery_specialist_is_interviewed_without_seeding(g):
    """The Delivery Specialist node as an interview would mint it: no registry aliases on it."""
    g.upsert_node(
        NodeCard(
            id="role.delivery-specialist",
            type=NodeType.ROLE,
            canonical_name="Delivery Specialist",
            description="owns delivery of the project",
            category_codes=["04"],
            provenance=[_prov("persona.ds")],
        )
    )
    _delivery_specialist_is_interviewed(g)
