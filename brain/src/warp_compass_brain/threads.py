"""Gap → open-thread generator (docs/02 §10, phase-03 brief step 4).

Each :class:`~warp_compass_brain.completeness.Gap` becomes a candidate **open thread**: a concrete
thing to find out, with a ``goal`` (what to learn), a ``why`` (the ontology rationale), and a
``priority`` seed (impact + recency). These are scaffolding for the Planner (P4), which turns the
prioritized list into each persona's next Session Brief — they are not a fixed questionnaire.

Priority is deterministic: a per-kind/per-field **impact** weight plus a small **recency** bonus
when a reference ``now`` is supplied (a more recently touched activity is a more active topic).
Impact dominates so a broken chain always outranks a missing-system detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .completeness import CompletenessReport, Gap, GapKind

# Impact weight per gap kind (the chain/conflict defects matter most).
_KIND_IMPACT: dict[GapKind, float] = {
    GapKind.BROKEN_CHAIN: 1.0,
    GapKind.UNRESOLVED_CONFLICT: 0.9,
    GapKind.ONE_SIDED_HANDOFF: 0.7,
    GapKind.MISSING_FIELD: 0.5,  # refined per-field below
}

# Per-field impact for MISSING_FIELD gaps (structural fields the process depends on rank higher).
_FIELD_IMPACT: dict[str, float] = {
    "next_handoff": 0.65,
    "trigger": 0.6,
    "output": 0.55,
    "inputs": 0.45,
    "rules": 0.4,
    "system": 0.35,
    "exceptions": 0.3,
}

_RECENCY_BONUS_MAX = 0.15  # newest activity gets at most this added on top of impact
_RECENCY_HALF_LIFE_DAYS = 14.0


@dataclass
class OpenThread:
    """A candidate thing to learn next, derived from a completeness gap."""

    id: str
    kind: str
    goal: str
    why: str
    priority: float
    node_id: str | None = None
    node_name: str | None = None
    role_id: str | None = None
    role_name: str | None = None
    other_role_id: str | None = None
    other_role_name: str | None = None
    field: str | None = None


def build_threads(report: CompletenessReport, *, now: str | None = None) -> list[OpenThread]:
    """Turn a completeness report's gaps into a prioritized, de-duplicated thread list."""
    return threads_from_gaps(report.gaps, now=now)


def threads_from_gaps(gaps: list[Gap], *, now: str | None = None) -> list[OpenThread]:
    """Turn an arbitrary gap list into prioritized, de-duplicated threads.

    The Planner (P4) calls this on a single persona's gaps; :func:`build_threads` calls it on a
    whole report. Highest impact first, with a deterministic id tie-break.
    """
    ref = _parse_ts(now) if now else None
    threads: list[OpenThread] = []
    used_ids: set[str] = set()
    for gap in gaps:
        goal, why = _goal_and_why(gap)
        threads.append(
            OpenThread(
                id=_unique_id(gap, used_ids),
                kind=gap.kind.value,
                goal=goal,
                why=why,
                priority=round(_priority(gap, ref), 4),
                node_id=gap.node_id,
                node_name=gap.node_name,
                role_id=gap.role_id,
                role_name=gap.role_name,
                other_role_id=gap.other_role_id,
                other_role_name=gap.other_role_name,
                field=gap.field,
            )
        )
    # Highest impact first; stable, deterministic tie-break on id.
    threads.sort(key=lambda t: (-t.priority, t.id))
    return threads


# --- priority -------------------------------------------------------------------------------


def _priority(gap: Gap, ref: datetime | None) -> float:
    if gap.kind is GapKind.MISSING_FIELD and gap.field:
        impact = _FIELD_IMPACT.get(gap.field, _KIND_IMPACT[GapKind.MISSING_FIELD])
    else:
        impact = _KIND_IMPACT[gap.kind]
    return impact + _recency_bonus(gap.latest_ts, ref)


def _recency_bonus(latest_ts: str | None, ref: datetime | None) -> float:
    if not latest_ts or ref is None:
        return 0.0
    ts = _parse_ts(latest_ts)
    if ts is None:
        return 0.0
    age_days = max((ref - ts).total_seconds() / 86400.0, 0.0)
    # Exponential decay: fresh → ~full bonus, old → ~0.
    decay = 0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS)
    return _RECENCY_BONUS_MAX * decay


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


# --- copy -----------------------------------------------------------------------------------


def _goal_and_why(gap: Gap) -> tuple[str, str]:
    name = gap.node_name or gap.node_id or "this item"
    if gap.kind is GapKind.MISSING_FIELD:
        return _missing_field_copy(gap.field or "", name)
    if gap.kind is GapKind.ONE_SIDED_HANDOFF:
        other = gap.other_role_name or "the receiving role"
        return (
            f"Verify the handoff from '{name}' to {other}, from {other}'s side.",
            f"A handoff is only trustworthy when both sides confirm it; {other} hasn't described "
            "picking this up, so the end-to-end chain dangles here.",
        )
    if gap.kind is GapKind.BROKEN_CHAIN:
        return (
            f"Connect '{name}' into the end-to-end process.",
            "The goal is one connected process from first trigger to final output; this step "
            "isn't reachable on any such path, so something linking it is still unknown.",
        )
    if gap.kind is GapKind.UNRESOLVED_CONFLICT:
        return (
            f"Reconcile the conflicting accounts of '{name}'.",
            "Two or more sources disagree; the graph holds this as conflicting until a source "
            "resolves it.",
        )
    return (f"Look into '{name}'.", gap.detail)


_FIELD_GOALS: dict[str, str] = {
    "trigger": "Find out what triggers '{name}' — the event that starts it.",
    "inputs": "Find out what inputs '{name}' consumes.",
    "system": "Find out which system or tool '{name}' is done in.",
    "output": "Find out what '{name}' produces.",
    "next_handoff": "Find out who '{name}' hands off to next.",
    "exceptions": "Find out the exceptions and edge cases for '{name}'.",
    "rules": "Find out the rules or policies that govern '{name}'.",
}


def _missing_field_copy(field_name: str, name: str) -> tuple[str, str]:
    goal = _FIELD_GOALS.get(field_name, f"Find out the {field_name} for '{name}'.").format(
        name=name
    )
    why = (
        f"The ontology counts '{field_name}' as part of a complete picture of an activity, and "
        f"it's currently unknown for '{name}'."
    )
    return goal, why


# --- ids ------------------------------------------------------------------------------------


def _unique_id(gap: Gap, used: set[str]) -> str:
    base = "thread"
    parts = [base, gap.kind.value]
    if gap.node_id:
        parts.append(gap.node_id)
    if gap.field:
        parts.append(gap.field)
    candidate = ".".join(parts)
    out = candidate
    n = 2
    while out in used:
        out = f"{candidate}#{n}"
        n += 1
    used.add(out)
    return out
