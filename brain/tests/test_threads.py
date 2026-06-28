"""Phase 3 — gap → open-thread generation: copy, priority ordering, recency, unique ids."""

from __future__ import annotations

from warp_compass_brain.completeness import (
    CompletenessReport,
    Gap,
    GapKind,
    OrgScore,
)
from warp_compass_brain.threads import build_threads


def _report(gaps: list[Gap]) -> CompletenessReport:
    return CompletenessReport(
        gaps=gaps,
        persona_scores=[],
        org=OrgScore(1.0, 1.0, 1.0, True),
        satisfied=False,
    )


def test_threads_ordered_by_impact():
    gaps = [
        Gap(GapKind.MISSING_FIELD, "no system", node_id="act.a", node_name="A", field="system"),
        Gap(GapKind.BROKEN_CHAIN, "disconnected", node_id="act.b", node_name="B"),
        Gap(GapKind.MISSING_FIELD, "no handoff", node_id="act.a", node_name="A",
            field="next_handoff"),
    ]
    threads = build_threads(_report(gaps))
    kinds = [t.kind for t in threads]
    # broken chain (1.0) > next_handoff (0.65) > system (0.35)
    assert kinds[0] == GapKind.BROKEN_CHAIN.value
    assert threads[1].field == "next_handoff"
    assert threads[2].field == "system"
    assert threads[0].priority > threads[1].priority > threads[2].priority


def test_thread_copy_mentions_node_and_goal():
    gap = Gap(GapKind.MISSING_FIELD, "x", node_id="act.a", node_name="Take order", field="trigger")
    t = build_threads(_report([gap]))[0]
    assert "Take order" in t.goal
    assert "trigger" in t.goal.lower()
    assert "Take order" in t.why


def test_recency_bonus_breaks_ties_toward_fresher():
    old = Gap(GapKind.MISSING_FIELD, "x", node_id="act.old", node_name="Old", field="system",
              latest_ts="2026-01-01T00:00:00Z")
    new = Gap(GapKind.MISSING_FIELD, "x", node_id="act.new", node_name="New", field="system",
              latest_ts="2026-06-28T00:00:00Z")
    threads = build_threads(_report([old, new]), now="2026-06-28T12:00:00Z")
    assert threads[0].node_id == "act.new"  # fresher topic wins the tie
    assert threads[0].priority > threads[1].priority


def test_thread_ids_are_unique():
    # two one-sided handoffs out of the same activity must not collide on id
    gaps = [
        Gap(GapKind.ONE_SIDED_HANDOFF, "to Y", node_id="act.a", node_name="A"),
        Gap(GapKind.ONE_SIDED_HANDOFF, "to Z", node_id="act.a", node_name="A"),
    ]
    threads = build_threads(_report(gaps))
    assert len({t.id for t in threads}) == 2
