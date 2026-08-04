"""P15b — the stage x role coverage matrix (`cli coverage`, plan §8.4).

The operator's "who do we invite next?" report. Derived entirely from the graph: it adds no question
types and no mechanism, which is why it was allowed into a phase whose §1.2 rejects new mechanisms.
"""

from __future__ import annotations

from conftest import FakeGraphStore

from warp_compass_brain.coverage import build_coverage, render_coverage
from warp_compass_brain.models import (
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)
from warp_compass_brain.roles import REGISTRY_SAID_BY, load_roles, seed_roles

TS = "2026-08-04T10:00:00Z"


def _prov(persona: str) -> Provenance:
    return Provenance(
        said_by=persona, session_id="s1", confidence=0.9, status=ConfidenceStatus.UNVERIFIED, ts=TS
    )


def _node(node_id: str, ntype: NodeType, name: str, *, persona: str = "persona.A") -> NodeCard:
    return NodeCard(
        id=node_id,
        type=ntype,
        canonical_name=name,
        description=f"{name} description",
        category_codes=["00" if ntype is NodeType.STAGE else "02"],
        provenance=[_prov(persona)],
    )


def _edge(etype: EdgeType, a: str, b: str, persona: str = "persona.A") -> Edge:
    return Edge(type=etype, from_id=a, to_id=b, provenance=[_prov(persona)])


def _two_stage_engagement(g):
    """Pre-Sales (the AM's, interviewed) → Discovery (the BA's, NOT interviewed)."""
    g.upsert_node(_node("stg.presales", NodeType.STAGE, "Pre-Sales"))
    g.upsert_node(_node("stg.discovery", NodeType.STAGE, "Discovery"))
    g.add_edge(_edge(EdgeType.PRECEDES, "stg.presales", "stg.discovery"))

    # The Account Manager IS interviewed: their answers produced the activity.
    g.upsert_node(_node("role.am", NodeType.ROLE, "Account Management Specialist"))
    g.upsert_node(_node("act.demo", NodeType.ACTIVITY, "Run the demo", persona="persona.am"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.am", "act.demo", persona="persona.am"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.demo", "stg.presales"))
    g.add_edge(_edge(EdgeType.OWNS, "role.am", "stg.presales"))

    # The BA is only ever *mentioned* — the AM says the demo gets handed to them.
    g.upsert_node(_node("role.ba", NodeType.ROLE, "Business Analysis Specialist"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.demo", "role.ba", persona="persona.am"))
    # ...and someone describes work happening in Discovery, but not as its performer.
    g.upsert_node(_node("act.brd", NodeType.ACTIVITY, "Write the BRD", persona="persona.am"))
    g.add_edge(_edge(EdgeType.PART_OF, "act.brd", "stg.discovery"))


def test_an_interviewed_stage_and_a_silent_one_are_told_apart():
    g = FakeGraphStore()
    _two_stage_engagement(g)

    report = build_coverage(g)
    by_id = {s.stage_id: s for s in report.stages}

    presales = by_id["stg.presales"]
    assert presales.is_silent is False
    assert presales.is_unowned is False
    am = next(r for r in presales.roles if r.role_id == "role.am")
    assert am.interviewed_by == ["persona.am"]
    assert am.via == ["owns", "performs"]
    # The BA turns up in Pre-Sales as the receiver of the handoff, with no owner.
    ba = next(r for r in presales.roles if r.role_id == "role.ba")
    assert ba.via == ["receives"] and ba.has_interviewed_owner is False

    discovery = by_id["stg.discovery"]
    assert discovery.is_silent is True, "nobody has been interviewed about Discovery"
    assert discovery.is_unowned is True, "no role is accountable for Discovery"
    assert discovery.activity_count == 1
    assert [s.stage_id for s in report.silent_stages] == ["stg.discovery"]


def test_the_invite_list_names_roles_nobody_has_been_interviewed_as():
    g = FakeGraphStore()
    _two_stage_engagement(g)

    report = build_coverage(g)
    assert [r.role_id for r in report.roles_without_an_owner] == ["role.ba"]


def test_a_forked_role_shows_up_as_owner_less_rather_than_hiding():
    """Risk R1's mitigation: if an alias ever escapes, `coverage` is where it becomes visible."""
    g = FakeGraphStore()
    _two_stage_engagement(g)
    # The failure the alias table prevents: a rival Role node minted from "the PM".
    g.upsert_node(_node("role.project-manager", NodeType.ROLE, "Project Manager"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.brd", "role.project-manager"))

    report = build_coverage(g)
    orphans = {r.role_id for r in report.roles_without_an_owner}
    assert "role.project-manager" in orphans


def test_registry_only_roles_are_not_reported_as_people_we_failed_to_invite():
    """Otherwise all ten seeded roles drown the real signal every single run (ADR #33)."""
    g = FakeGraphStore()
    seed_roles(g, load_roles(), now=TS)

    report = build_coverage(g)
    assert report.roles_without_an_owner == []
    assert report.stages == []

    # Once a real person mentions one, it joins the invite list.
    card = g.get_node("role.solution-architect")
    card.provenance.append(_prov("persona.am"))
    g.upsert_node(card)
    report = build_coverage(g)
    assert [r.role_id for r in report.roles_without_an_owner] == ["role.solution-architect"]
    assert card.provenance[0].said_by == REGISTRY_SAID_BY


def test_activities_not_yet_in_any_stage_are_counted():
    g = FakeGraphStore()
    _two_stage_engagement(g)
    g.upsert_node(_node("act.loose", NodeType.ACTIVITY, "Something unplaced"))

    report = build_coverage(g)
    assert report.activities_outside_any_stage == 1


def test_render_is_readable_and_flags_the_silent_stage():
    g = FakeGraphStore()
    _two_stage_engagement(g)

    text = render_coverage(build_coverage(g))
    assert "Pre-Sales" in text and "Discovery" in text
    assert "SILENT" in text
    assert "UNOWNED" in text
    assert "NOT INTERVIEWED" in text
    assert "persona.am" in text
    # The silent flag must land on Discovery's line, not Pre-Sales'.
    presales_line = next(ln for ln in text.splitlines() if ln.startswith("## Pre-Sales"))
    assert "SILENT" not in presales_line


def test_render_is_pure_ascii_so_it_cannot_crash_a_windows_console():
    """A tick mark would kill the command on real data, not in a smoke test.

    Python on Windows hands this process a `cp1252` stdout. `U+2713` is not in that codepage, so
    `print(render_coverage(...))` raised `UnicodeEncodeError` and took `cli coverage` down — but only
    once a stage had an interviewed role, since the empty-graph message is incidentally ASCII.
    """
    g = FakeGraphStore()
    _two_stage_engagement(g)
    g.upsert_node(_node("act.loose", NodeType.ACTIVITY, "Something unplaced"))
    text = render_coverage(build_coverage(g))

    text.encode("cp1252")  # the real assertion: this is what `print` does on the owner's laptop
    assert text.isascii(), [ch for ch in set(text) if not ch.isascii()]

    # Both matrix marks must survive being ASCII.
    assert "[x]" in text and "[ ]" in text


def test_an_empty_graph_says_so_instead_of_printing_nothing():
    report = build_coverage(FakeGraphStore())
    text = render_coverage(report)
    assert "No lifecycle stages" in text
    assert "never predefined" in text
