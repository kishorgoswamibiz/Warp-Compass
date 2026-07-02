"""Planner → per-persona Session Brief (docs/02 §5, §10, phase-04 brief).

Between batch runs the Planner reads the *current* graph and produces each persona's next
**Session Brief**: a short evolving persona summary plus a ranked list of **open threads to pull
on** — guidance the live runner is free to deviate from, never a fixed questionnaire.

Everything is derived from the graph, so cross-pollination falls out for free: a brief written now
already reflects whatever every other persona has contributed. Concretely, for a persona it:

1. runs the completeness engine and keeps the gaps on *that persona's subgraph* — its coverage
   gaps, one-sided handoffs it discovered, and any conflicts on nodes it touched (free-narration
   threads it raised are already encoded as gaps on the nodes it just created, and float up via
   the recency term);
2. turns each gap into a thread with a ``goal``, a ``why``, a ``suggested_opener`` and conditional
   ``followups`` (deterministic scaffolding; an LLM may later draft richer copy);
3. ranks by impact + recency, caps to ``max_threads`` (the rest become ``reserve_threads``);
4. emits a dict that validates against ``contracts/session-brief.schema.json``. On an empty brain
   it emits ``cold_start: true`` with no threads — only the generic openers below.

A persona is identified by the ``said_by`` id stamped on provenance during ingest; its subgraph is
every node it contributed to. (Persona↔role is 1:1 in the prototype; explicit clustering is P9.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .completeness import CompletenessEngine, GapKind, load_snapshot
from .crosspersona import (
    KIND_CROSS_CONFLICT,
    KIND_HANDOFF_CONFIRM,
    KIND_HANDOFF_TRACE,
    CrossPersonaEngine,
)
from .graphstore.base import GraphStore
from .models import NodeType
from .ontology import Ontology
from .threads import OpenThread, threads_from_gaps

# Handoff + conflict threads are owned by the cross-persona engine (P9), which routes them to the
# right persona (receiver for a handoff, every contributor for a conflict). The Planner therefore
# drops these gap kinds from its own gap→thread pass and pulls the routed versions instead.
_CROSS_PERSONA_GAP_KINDS = frozenset({GapKind.ONE_SIDED_HANDOFF, GapKind.UNRESOLVED_CONFLICT})

# Generic discovery openers for a first-ever session (empty brain). The live runner (P5) also
# knows this list; it is the only scaffolding when there's nothing in the graph yet.
# Ground-up + chronological by design (P12 owner feedback): the goal is the complete SOP of the
# role, walked in order — never leading with "most difficult/frustrating part" questions.
COLD_START_OPENERS: list[str] = [
    "To start, tell me about your role — what are you responsible for, day to day?",
    "Let's map your day from the very beginning: what's the first piece of work that lands on "
    "your plate, and what kicks it off?",
    "What happens right after that? Walk me through the steps one by one, in order.",
    "For that step — what do you need in hand to start it, and which tool or screen do you do "
    "it in?",
    "When that piece of work leaves your hands, who picks it up next, and how does it reach "
    "them?",
]


@dataclass
class BriefThread:
    """One ranked thread in a Session Brief (mirrors the schema's open_threads item)."""

    id: str
    goal: str
    why: str
    priority: int  # integer RANK in the brief: 1 = pull on this first
    suggested_opener: str
    followups: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "why": self.why,
            "priority": self.priority,
            "suggested_opener": self.suggested_opener,
            "followups": list(self.followups),
        }


@dataclass
class SessionBrief:
    """The brain→runner artifact for one persona (mirrors session-brief.schema.json)."""

    session_id: str
    persona_id: str
    cold_start: bool
    open_threads: list[BriefThread]
    persona_summary: str = ""
    reserve_threads: list[str] = field(default_factory=list)
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "persona_id": self.persona_id,
            "schema_version": self.schema_version,
            "cold_start": self.cold_start,
            "persona_summary": self.persona_summary,
            "open_threads": [t.to_dict() for t in self.open_threads],
            "reserve_threads": list(self.reserve_threads),
        }


class Planner:
    """Builds per-persona Session Briefs from the live graph. Read-only."""

    def __init__(
        self,
        graph: GraphStore,
        ontology: Ontology,
        *,
        max_threads: int = 6,
        now: str | None = None,
    ) -> None:
        self._g = graph
        self._ont = ontology
        self._max = max_threads
        self._now = now

    def personas(self) -> list[str]:
        """Every persona that has contributed (distinct provenance ``said_by``), sorted."""
        snap = load_snapshot(self._g)
        seen = {p.said_by for card in snap.nodes.values() for p in card.provenance}
        return sorted(seen)

    def plan(self, persona_id: str, *, session_id: str) -> SessionBrief:
        snap = load_snapshot(self._g)
        # Empty brain → cold start: generic openers only, no threads.
        if not snap.nodes:
            return SessionBrief(
                session_id=session_id,
                persona_id=persona_id,
                cold_start=True,
                open_threads=[],
                persona_summary="",
                reserve_threads=[],
            )

        report = CompletenessEngine(self._g, self._ont).assess()
        subgraph_ids = {
            nid
            for nid, card in snap.nodes.items()
            if any(p.said_by == persona_id for p in card.provenance)
        }
        persona_gaps = [
            g
            for g in report.gaps
            if g.node_id in subgraph_ids and g.kind not in _CROSS_PERSONA_GAP_KINDS
        ]
        # Cross-persona handoff/conflict threads, already routed to this persona (P9).
        cross_threads = CrossPersonaEngine(
            self._g, self._ont, now=self._now
        ).threads_for_persona(persona_id)
        threads = sorted(
            [*cross_threads, *threads_from_gaps(persona_gaps, now=self._now)],
            key=lambda t: (-t.priority, t.id),
        )

        brief_threads: list[BriefThread] = []
        for rank, t in enumerate(threads[: self._max], start=1):
            opener, followups = _opener_and_followups(t)
            brief_threads.append(
                BriefThread(
                    id=t.id,
                    goal=t.goal,
                    why=t.why,
                    priority=rank,
                    suggested_opener=opener,
                    followups=followups,
                )
            )
        reserve = [t.id for t in threads[self._max :]]
        summary = self._persona_summary(persona_id, subgraph_ids, snap, report)

        return SessionBrief(
            session_id=session_id,
            persona_id=persona_id,
            cold_start=False,
            open_threads=brief_threads,
            persona_summary=summary,
            reserve_threads=reserve,
        )

    def plan_all(self, *, session_id: str) -> list[SessionBrief]:
        """A brief for every contributing persona (cold start emits none)."""
        return [self.plan(pid, session_id=session_id) for pid in self.personas()]

    # --- persona summary ---

    def _persona_summary(self, persona_id, subgraph_ids, snap, report) -> str:
        cards = [snap.nodes[nid] for nid in subgraph_ids]
        roles = sorted(
            c.canonical_name for c in cards if c.type is NodeType.ROLE
        )
        activities = [c for c in cards if c.type is NodeType.ACTIVITY]
        # complete = activity with no missing-field gap attributed to it
        incomplete_ids = {
            g.node_id for g in report.gaps if g.kind is GapKind.MISSING_FIELD
        }
        complete = sum(1 for a in activities if a.id not in incomplete_ids)
        n_systems = sum(1 for c in cards if c.type is NodeType.SYSTEM)
        n_problems = sum(1 for c in cards if c.type is NodeType.PROBLEM)

        role_phrase = ", ".join(roles) if roles else "your role"
        parts = [f"As {role_phrase}, you've described {len(activities)} activit"
                 f"{'y' if len(activities) == 1 else 'ies'}"]
        if activities:
            open_n = len(activities) - complete
            parts.append(f"{complete} fully covered, {open_n} with open questions")
        if n_systems:
            parts.append(f"{n_systems} system{'s' if n_systems != 1 else ''}")
        if n_problems:
            parts.append(f"{n_problems} problem{'s' if n_problems != 1 else ''} raised")
        return "; ".join(parts) + "."


# --- opener + followup scaffolding (deterministic; an LLM may later enrich) -------------------

_FIELD_OPENERS: dict[str, str] = {
    "trigger": "Walk me through what kicks off '{name}' — what happens right before you start?",
    "inputs": "When you do '{name}', what do you need in hand to begin?",
    "system": "Where do you actually do '{name}' — which tool or screen?",
    "output": "When '{name}' is finished, what have you produced?",
    "next_handoff": "Once '{name}' is done, who picks it up next?",
    "exceptions": "What throws '{name}' off — the awkward cases that don't go to plan?",
    "rules": "Are there rules or policies you have to follow doing '{name}'?",
}

_FIELD_FOLLOWUPS: dict[str, list[dict[str, str]]] = {
    "trigger": [{"if": "they name one trigger", "ask": "Is that the only thing that starts it?"}],
    "inputs": [{"if": "they name an input", "ask": "Where does that come from — who or what?"}],
    "system": [{"if": "they name a system", "ask": "Anything done outside it, on paper or chat?"}],
    "output": [{"if": "they name an output", "ask": "Who receives or relies on it?"}],
    "next_handoff": [
        {"if": "they name a person/role", "ask": "How do you pass it to them — system or email?"}
    ],
    "exceptions": [{"if": "they describe an exception", "ask": "How often does that happen?"}],
    "rules": [{"if": "they name a rule", "ask": "What happens if it isn't met?"}],
}


def _opener_and_followups(t: OpenThread) -> tuple[str, list[dict[str, str]]]:
    name = t.node_name or "that"
    if t.kind == GapKind.MISSING_FIELD.value and t.field:
        opener = _FIELD_OPENERS.get(t.field, t.goal).format(name=name)
        return opener, list(_FIELD_FOLLOWUPS.get(t.field, []))
    if t.kind == GapKind.ONE_SIDED_HANDOFF.value:
        other = t.other_role_name or "the other team"
        return (
            f"You mentioned '{name}' hands off to {other} — can you confirm what they do with it?",
            [{"if": "they're unsure", "ask": f"Who would know how {other} handles it?"}],
        )
    if t.kind == GapKind.BROKEN_CHAIN.value:
        return (
            f"I'm not clear how '{name}' connects to the rest of the process — can you place it?",
            [{"if": "they place it", "ask": "What comes immediately before and after it?"}],
        )
    if t.kind == GapKind.UNRESOLVED_CONFLICT.value:
        return (
            f"I've heard different accounts of '{name}' — can you tell me how it actually works?",
            [{"if": "they clarify", "ask": "Is that always the case, or does it vary?"}],
        )
    # --- P9 cross-persona routed threads ---
    if t.kind == KIND_HANDOFF_CONFIRM:  # routed to the receiving persona
        giver = t.role_name or "another team"
        return (
            f"It sounds like {giver} hands '{name}' over to you — do you receive it, and what do "
            "you do with it next?",
            [
                {
                    "if": "they confirm receiving it",
                    "ask": "What state is it in when it reaches you — anything missing or redone?",
                }
            ],
        )
    if t.kind == KIND_HANDOFF_TRACE:  # receiver not interviewed yet; stays with the discoverer
        other = t.other_role_name or "the other team"
        return (
            f"You mentioned '{name}' hands off to {other} — can you confirm what they do with it?",
            [{"if": "they're unsure", "ask": f"Who would know how {other} handles it?"}],
        )
    if t.kind == KIND_CROSS_CONFLICT:  # routed to every contributor of a conflicting node
        return (
            f"I've heard different accounts of '{name}' — can you walk me through how it actually "
            "works for you?",
            [{"if": "they clarify", "ask": "Is that always the case, or does it depend?"}],
        )
    return t.goal, []
