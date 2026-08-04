"""Phase 4 — Planner / Session Brief: cold start, ranked threads, corroboration, persona scoping,
and contract validation against contracts/session-brief.schema.json (no Neo4j, no network)."""

from __future__ import annotations

import json
import pathlib
import re
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
    # Thread ids embed their node id; A's brief must reference only nodes A contributed to. Since
    # P15b that includes A's own Role node (its `reports_to` is now scored, which is what makes the
    # org chart get asked about at all) — but never anything of B's.
    ids = [t.id for t in brief_a.open_threads]
    assert ids and all(("act.a" in tid or "role.a" in tid) for tid in ids), ids
    assert any("role.a" in tid for tid in ids), "the org chart is never asked about"
    assert not any("act.b" in tid or "role.b" in tid for tid in ids), "A's brief leaked B's nodes"

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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 13 — retirement + the orphan thread pool.
# ─────────────────────────────────────────────────────────────────────────────


def test_retired_persona_is_not_planned_for():
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order", persona="persona.A", role_id="role.rep")
    _bare_activity(g, "act.b", "Pack order", persona="persona.B", role_id="role.wh")

    planner = _planner(g, retired_personas={"persona.B"})
    assert planner.personas() == ["persona.A", "persona.B"]  # the graph still holds their work
    assert planner.live_personas() == ["persona.A"]  # ...but nobody is there to read a brief
    assert [b.persona_id for b in planner.plan_all(session_id="s")] == ["persona.A"]


def test_orphaned_nodes_questions_are_offered_to_whoever_is_still_here():
    """P13 Finding 2 — a departed teammate's open questions must not go silent.

    Gaps are scoped to a persona's own subgraph, so a node only the retired person ever touched
    belongs to nobody. Those gaps become low-priority, third-person threads on everyone else's
    brief, because the question is about the business, and the business is still here.
    """
    g = FakeGraphStore()
    _bare_activity(g, "act.mine", "Take order", persona="persona.A", role_id="role.rep")
    _bare_activity(g, "act.theirs", "Reconcile invoices", persona="persona.GONE", role_id="role.fin")

    brief = _planner(g, retired_personas={"persona.GONE"}).plan("persona.A", session_id="s")
    orphans = [t for t in brief.open_threads if t.id.startswith("orphan.")]

    assert orphans, "the retired person's gaps should have been re-offered"
    assert all("Reconcile invoices" in t.suggested_opener for t in orphans)
    # Third-person framing: they didn't say it, so we must not imply they did.
    assert all("colleague" in t.suggested_opener for t in orphans)
    assert all("no longer in the engagement" in t.why for t in orphans)
    # An "I don't know" escape hatch — it's someone else's process.
    assert any("right person to ask" in f["ask"] for t in orphans for f in t.followups)
    validate(instance=brief.to_dict(), schema=_SCHEMA)


def test_orphan_threads_rank_below_the_persons_own_work_and_are_capped():
    g = FakeGraphStore()
    _bare_activity(g, "act.mine", "Take order", persona="persona.A", role_id="role.rep")
    _bare_activity(g, "act.t1", "Reconcile invoices", persona="persona.GONE", role_id="role.fin")
    _bare_activity(g, "act.t2", "Chase debtors", persona="persona.GONE", role_id="role.fin")

    brief = _planner(g, retired_personas={"persona.GONE"}, orphan_max=2).plan(
        "persona.A", session_id="s"
    )
    own = [t for t in brief.open_threads if not t.id.startswith("orphan.")]
    orphans = [t for t in brief.open_threads if t.id.startswith("orphan.")]

    assert len(orphans) == 2  # capped
    assert own, "the person's own threads must still be there"
    # The rank floor is structural: every orphan sits below every own thread.
    assert max(t.priority for t in own) < min(t.priority for t in orphans)
    # Ranks stay contiguous from 1 so the contract holds.
    assert [t.priority for t in brief.open_threads] == list(
        range(1, len(brief.open_threads) + 1)
    )
    validate(instance=brief.to_dict(), schema=_SCHEMA)


def test_a_node_with_one_live_contributor_is_not_orphaned():
    """Shared knowledge stays owned — this is why retirement can leave the graph alone."""
    g = FakeGraphStore()
    _bare_activity(g, "act.shared", "Take order", persona="persona.A", role_id="role.rep")
    # persona.GONE also spoke about it; A is still here, so it is A's to answer for.
    g.nodes["act.shared"].provenance.append(_prov("persona.GONE"))

    brief = _planner(g, retired_personas={"persona.GONE"}).plan("persona.A", session_id="s")
    assert not [t for t in brief.open_threads if t.id.startswith("orphan.")]


def test_no_retirements_means_no_orphan_threads_at_all():
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order", persona="persona.A", role_id="role.rep")
    _bare_activity(g, "act.b", "Pack order", persona="persona.B", role_id="role.wh")

    brief = _planner(g).plan("persona.A", session_id="s")
    assert not [t for t in brief.open_threads if t.id.startswith("orphan.")]
    # persona.B's gaps stay persona.B's problem — unchanged pre-P13 behaviour.
    assert all("Pack order" not in (t.suggested_opener or "") for t in brief.open_threads)


# --- P15b: the interview is lifecycle-anchored, and the two prompt copies must not drift --------

_PROMPTS_TS = (
    pathlib.Path(__file__).resolve().parents[2] / "pwa" / "src" / "runner" / "prompts.ts"
)


def test_no_cold_start_opener_mentions_a_day():
    """The whole point of P15b. Guarded because the wording drifted back once already (P12→P15)."""
    for opener in COLD_START_OPENERS:
        low = opener.lower()
        assert not re.search(r"\bday\b", low), opener
        assert not re.search(r"\bdaily\b", low), opener
        assert not re.search(r"\bmorning\b", low), opener


def test_openers_ask_about_the_journey_and_the_cadence():
    joined = " ".join(COLD_START_OPENERS).lower()
    assert "one piece of work" in joined, "Pass A must ask for the lifecycle map"
    assert "on every project" in joined, "cadence must be asked (Finding 5)"


def test_the_identity_opener_is_still_index_zero():
    """P13's never-re-ask guarantee depends on this position, not on the text."""
    assert "tell me about your role" in COLD_START_OPENERS[0].lower()


def test_cold_start_openers_match_the_pwa_copy_verbatim():
    """The cross-language duplicate in `prompts.ts` (PROMPTS.md §2) must stay identical.

    Both planes need the same generic openers and there is no shared TS/Py module (ADR #18d), so the
    constant is duplicated by design — which means it needs a test that fails loudly on drift, the
    same discipline `contracts/roles.json` uses for the role registry.
    """
    src = _PROMPTS_TS.read_text(encoding="utf-8")
    block = re.search(
        r"export const COLD_START_OPENERS: readonly string\[\] = \[(.*?)\n\];", src, re.S
    )
    assert block, "could not find COLD_START_OPENERS in prompts.ts"
    ts_openers = re.findall(r'^\s*"((?:[^"\\]|\\.)*)",\s*$', block.group(1), re.M)
    ts_openers = [o.replace('\\"', '"') for o in ts_openers]
    assert ts_openers == COLD_START_OPENERS, (
        "prompts.ts and planner.py have drifted apart:\n"
        f"  ts : {ts_openers}\n"
        f"  py : {COLD_START_OPENERS}"
    )


def test_every_scored_completeness_field_has_an_opener():
    """A gap with no opener falls back to the raw `goal` string, which reads like a form field.

    Covers the P15b additions (cadence, and the Stage/Role/Objective fields) as well as the
    original Activity ones.
    """
    from warp_compass_brain.models import NodeType
    from warp_compass_brain.planner import _FIELD_OPENERS

    ont = load_ontology()
    for ntype in (NodeType.ACTIVITY, NodeType.ROLE, NodeType.STAGE, NodeType.OBJECTIVE):
        for f in ont.completeness_fields(ntype):
            if f == "measured_by":
                continue  # deliberately unmapped: no Objective->KPI edge exists (see completeness)
            assert f in _FIELD_OPENERS, f"{ntype.value}.{f} has no opener"
            assert "{name}" in _FIELD_OPENERS[f], f"{f} opener does not name the node"


def test_stage_gaps_produce_spoken_openers_not_field_names():
    g = FakeGraphStore()
    g.upsert_node(
        NodeCard(
            id="stg.discovery",
            type=NodeType.STAGE,
            canonical_name="Discovery",
            description="Working out what the client actually needs.",
            category_codes=["00"],
            provenance=[
                Provenance(
                    said_by="persona.A",
                    session_id="s1",
                    confidence=0.9,
                    status=ConfidenceStatus.UNVERIFIED,
                    ts="2026-08-04T10:00:00Z",
                )
            ],
        )
    )
    brief = _planner(g).plan("persona.A", session_id="s")
    openers = {t.suggested_opener for t in brief.open_threads}
    assert "What actually happens during 'Discovery'? Walk me through it in order." in openers
    assert "How do you know 'Discovery' is done and it's safe to move on?" in openers
    assert any("accountable for 'Discovery'" in o for o in openers)
