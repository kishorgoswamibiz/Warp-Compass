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

**Retirement + orphan threads (P13).** Retiring someone never touches the graph (ADR #30), so their
knowledge — and their unanswered questions — stay. But because gaps are scoped to the persona's own
subgraph, a node only *they* ever touched would fall out of every brief and go silent forever. So a
node whose contributors are ALL retired is **orphaned**, and its gaps are offered to everyone still
in the engagement: capped, ranked below the person's own work, and framed in the third person
because they didn't say it. Offering one to several people is intentional — two independent answers
is exactly what promotes a fact to ``confirmed``. The pool is self-clearing: the moment a live
persona answers, that node gains live provenance and stops being orphaned.

**Role-scoped inheritance (P16a-bis, ADR #36).** Persona scoping answers *"which of MY nodes have
gaps?"* and has no answer to *"which of MY ROLE's nodes have gaps?"* — different questions the
moment a role has more than one holder. Three Business Analysts each describing a quarter leave
a quarter missing, and pre-P16a-bis nobody but the original speaker was ever asked about it, so a
role's coverage froze at whatever its first holder happened to say. So gaps on nodes performed by a
role the persona **declared** are inherited into their brief: capped, ranked below their own work
(same structural floor as orphans), and worded to ask for *their* version rather than a yes/no.

Firing the same gap at every holder is deliberate and cannot loop, because gaps are recomputed from
the graph each round — one holder answering removes it from everyone's next brief — and because a
second account is the thing that promotes a fact to ``confirmed`` or exposes a genuine difference in
how two people do the same job.

**The person stays the provenance key.** Only *scoping* is role-shaped; ``said_by`` is not. Keying
provenance by role would make two Business Analysts agreeing indistinguishable from one repeating
himself, and would delete peer-conflict detection along with it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .completeness import CompletenessEngine, GapKind, load_snapshot
from .crosspersona import (
    KIND_CROSS_CONFLICT,
    KIND_HANDOFF_CONFIRM,
    KIND_HANDOFF_SELF,
    KIND_HANDOFF_TRACE,
    CrossPersonaEngine,
)
from .graphstore.base import GraphStore
from .models import EdgeType, NodeType
from .ontology import Ontology
from .roles import REGISTRY_SAID_BY, resolve_declared_roles
from .threads import OpenThread, threads_from_gaps

# Handoff + conflict threads are owned by the cross-persona engine (P9), which routes them to the
# right persona (receiver for a handoff, every contributor for a conflict). The Planner therefore
# drops these gap kinds from its own gap→thread pass and pulls the routed versions instead.
_CROSS_PERSONA_GAP_KINDS = frozenset({GapKind.ONE_SIDED_HANDOFF, GapKind.UNRESOLVED_CONFLICT})

# Generic discovery openers for a first-ever session (empty brain). The live runner (P5) also
# knows this list; it is the only scaffolding when there's nothing in the graph yet.
# Ground-up by design (P12 owner feedback): the goal is the complete SOP of the role, walked in
# order — never leading with "most difficult/frustrating part" questions.
#
# ⚠ LIFECYCLE-ANCHORED, NEVER DAY-ANCHORED (P15b). No occurrence of the word "day" belongs here.
# "What do you do day to day" produces noise, not process — the owner's own answer as a BA was
# "I start my day checking my mails, but checking mail is not my job role." Real role work is
# per-project: pre-sales -> demo -> signing -> kickoff -> discovery -> BRD -> build -> UAT ->
# go-live -> support. Opener 1 is the Pass-A map question; 2-5 are Pass B, one stage at a time.
#
# ⚠ MUST STAY IN SYNC with `pwa/src/runner/prompts.ts` (see PROMPTS.md §2). Both copies are
# asserted against each other by tests on each side.
COLD_START_OPENERS: list[str] = [
    "To start, tell me about your role — what are you responsible for?",
    "Think of one piece of work from the moment it reaches the company to when it's delivered. "
    "Which parts of that journey do you touch?",
    "Take the earliest part you touch. What has to happen before it reaches you, and what tells "
    "you it's your turn?",
    "Inside that part, what do you actually do — step by step, in the order you do it?",
    "When your part is finished, what have you produced, and who picks it up?",
    "Is that something you do on every project, or only in certain cases?",
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
        orphan_max: int = 2,
        role_max: int = 4,
        retired_personas: set[str] | frozenset[str] | None = None,
        declared_roles: Mapping[str, Sequence[str]] | None = None,
        now: str | None = None,
    ) -> None:
        self._g = graph
        self._ont = ontology
        self._max = max_threads
        self._orphan_max = orphan_max
        self._role_max = role_max
        self._retired = frozenset(retired_personas or ())
        #: ``persona_id -> declared role titles``, from the bus (P16a-bis / ADR #36). Every LIVE
        #: participant appears, even one who declared nothing — the keys double as the roster of
        #: people who exist but may not have spoken yet (see `live_personas`).
        self._declared = {k: tuple(v) for k, v in (declared_roles or {}).items()}
        self._now = now

    def personas(self) -> list[str]:
        """Every persona that has contributed (distinct provenance ``said_by``), sorted.

        The seeded role registry is not a persona and never gets a brief: it is vocabulary, not
        somebody who can be interviewed (``roles.REGISTRY_SAID_BY``).
        """
        snap = load_snapshot(self._g)
        seen = {p.said_by for card in snap.nodes.values() for p in card.provenance}
        return sorted(seen - {REGISTRY_SAID_BY})

    def live_personas(self) -> list[str]:
        """Everyone a brief is for: contributors **∪** live participants, less the retired.

        Contributors alone is not enough, and the gap is the whole point of P16a-bis. Someone who
        has just joined has no provenance anywhere, so they are absent from ``personas()`` — and
        pre-P16a-bis that meant ``plan_all`` wrote them no brief and their first session fell back
        to generic cold-start openers, *even when their role had open questions waiting*. For the
        second holder of a role that is exactly backwards: they are the best-placed person in the
        engagement to answer, and the interview opened by asking them to introduce themselves.

        Retirement still wins over both sources. A retired person keeps their graph provenance
        forever (ADR #30) and has no bus folder, so they can appear in ``personas()`` and never in
        ``self._declared`` — the subtraction has to come last.
        """
        known = set(self.personas()) | set(self._declared)
        return sorted(known - self._retired)

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
            self._g, self._ont, now=self._now, declared_roles=self._declared
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
        # Open questions on THIS PERSON'S ROLES that they personally haven't touched (P16a-bis).
        # Appended after their own work for the same structural reason as orphans below: a question
        # about a colleague's account of your role must never outrank your own.
        role_ids = self._persona_role_ids(persona_id, snap)
        for t in self._role_threads(snap, report, subgraph_ids, role_ids)[: self._role_max]:
            opener, followups = _role_opener_and_followups(t)
            brief_threads.append(
                BriefThread(
                    id=f"role.{t.id}",
                    goal=t.goal,
                    why=_ROLE_WHY.format(role=t.role_name or "your role"),
                    priority=len(brief_threads) + 1,
                    suggested_opener=opener,
                    followups=followups,
                )
            )
        # Questions left behind by retired teammates, appended AFTER this person's own work so the
        # rank floor is structural: they can never outrank a thread about the person's own role.
        for t in self._orphan_threads(snap, report, subgraph_ids)[: self._orphan_max]:
            opener, followups = _orphan_opener_and_followups(t)
            brief_threads.append(
                BriefThread(
                    id=f"orphan.{t.id}",
                    goal=t.goal,
                    why=_ORPHAN_WHY,
                    priority=len(brief_threads) + 1,
                    suggested_opener=opener,
                    followups=followups,
                )
            )
        reserve = [t.id for t in threads[self._max :]]
        summary = self._persona_summary(persona_id, subgraph_ids, snap, report, role_ids)

        return SessionBrief(
            session_id=session_id,
            persona_id=persona_id,
            cold_start=False,
            open_threads=brief_threads,
            persona_summary=summary,
            reserve_threads=reserve,
        )

    def plan_all(self, *, session_id: str) -> list[SessionBrief]:
        """A brief for every contributing persona still in the engagement (cold start emits none).

        Retired personas are skipped here rather than filtered downstream: computing a brief costs
        a full completeness pass, and nobody would ever read it.
        """
        return [self.plan(pid, session_id=session_id) for pid in self.live_personas()]

    # --- role-inherited threads (P16a-bis) ---

    def _persona_role_ids(self, persona_id: str, snap) -> set[str]:
        """The Role node ids this persona **declared** at onboarding.

        **Declared, never inferred.** It is tempting to also count roles whose activities they have
        provenance on — but that is precisely the over-reach WC-R5 had to undo in
        ``alignment._persona_role``: an exec who merely *comments on* a Business Analyst's activity
        picks up provenance on it, and would then start inheriting the BA's entire question set. The
        onboarding multi-select is unambiguous and the person chose it themselves; contribution is a
        guess. Ownership in the other direction (``crosspersona._role_owner_personas``) unions the
        two because *being asked* is cheap and *never being asked* is the bug; here the cost is
        reversed, so this stays strict.
        """
        titles = self._declared.get(persona_id)
        if not titles:
            return set()
        role_cards = [c for c in snap.nodes.values() if c.type is NodeType.ROLE]
        return resolve_declared_roles(titles, role_cards)

    def _role_threads(
        self, snap, report, subgraph_ids: set[str], role_ids: set[str]
    ) -> list[OpenThread]:
        """Gaps on this person's ROLE's work that they personally never spoke about.

        The scenario, in the owner's words: *three BAs each describe a quarter of the role, so a
        quarter is still missing* — and that missing quarter is one gap on shared nodes, which
        should reach **every** holder. Persona scoping alone could only ever ask somebody about
        nodes they had already talked about, so the second and third BA were never asked and the
        role's coverage froze at whatever the first one happened to say.

        Two properties make firing at every holder safe rather than spammy, and both are already
        true — no ledger, no dedup pass, no way for this to loop:

        * gaps are recomputed from the graph every round, so the instant **any** holder answers, the
          gap is simply absent from everyone's next brief;
        * a second account on a node is *wanted* — two distinct personas is what promotes a fact to
          ``confirmed``, and if the two accounts disagree the ingest gate raises it as a conflict,
          which is a finding rather than a defect.

        Scope is the role's own work: activities it ``PERFORMS``, plus the Role node itself. Nodes
        the person already contributed to are excluded — those are their own gaps and are already in
        the brief above, at a higher rank.
        """
        if not role_ids:
            return []
        role_owned: set[str] = set(role_ids)
        for role_id in role_ids:
            role_owned.update(snap.out(role_id, EdgeType.PERFORMS))
        inherited = {
            nid for nid in role_owned if nid not in subgraph_ids and nid in snap.nodes
        }
        if not inherited:
            return []
        gaps = [
            g
            for g in report.gaps
            if g.node_id in inherited and g.kind not in _CROSS_PERSONA_GAP_KINDS
        ]
        return threads_from_gaps(gaps, now=self._now)

    # --- orphan threads (P13) ---

    def _orphan_threads(self, snap, report, subgraph_ids: set[str]) -> list[OpenThread]:
        """Gaps on nodes whose every contributor has been retired — nobody's subgraph owns them."""
        if not self._retired:
            return []
        orphan_ids = {
            nid
            for nid, card in snap.nodes.items()
            if nid not in subgraph_ids
            and card.provenance
            and {p.said_by for p in card.provenance} <= self._retired
        }
        if not orphan_ids:
            return []
        gaps = [
            g
            for g in report.gaps
            if g.node_id in orphan_ids and g.kind not in _CROSS_PERSONA_GAP_KINDS
        ]
        return threads_from_gaps(gaps, now=self._now)

    # --- persona summary ---

    def _persona_summary(self, persona_id, subgraph_ids, snap, report, role_ids=None) -> str:
        cards = [snap.nodes[nid] for nid in subgraph_ids]
        declared = sorted(
            snap.nodes[rid].canonical_name for rid in (role_ids or ()) if rid in snap.nodes
        )
        # Someone who has just joined has contributed nothing, so the graph knows only what they
        # declared. Saying "you've described 0 activities" to a person who has not been asked
        # anything yet reads as an accusation; name the role and let the threads do the work.
        if not cards:
            if declared:
                return f"As {', '.join(declared)}, you haven't described your work yet."
            return ""
        roles = sorted(
            c.canonical_name for c in cards if c.type is NodeType.ROLE
        ) or declared
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


# --- role-inherited copy (P16a-bis) -------------------------------------------------------------
# A question about work someone ELSE in your role described. The normal openers presume the person
# raised it themselves ("when you do 'X'...") which would be a small lie here, and the orphan copy
# ("a colleague who has since left") is the wrong story too — this colleague is still here.
#
# The copy has one job beyond politeness: ask for THEIR version rather than a yes/no. Two accounts
# of one node is what promotes a fact to `confirmed`, and if the two differ, that divergence is a
# finding. "Is that right?" throws both away; "how do you do it?" collects them.

_ROLE_WHY = (
    "Someone else working as {role} described this, but you haven't — and you may well do it "
    "differently. A second account either confirms it or surfaces a difference worth knowing about."
)

_ROLE_DONT_KNOW = {
    "if": "they don't do this part",
    "ask": "Understood — is that handled by someone else, or does it just not come up for you?",
}


def _role_opener_and_followups(t: OpenThread) -> tuple[str, list[dict[str, str]]]:
    name = t.node_name or "that step"
    role = t.role_name or "your role"
    if t.kind == GapKind.MISSING_FIELD.value and t.field:
        ask = _ROLE_FIELD_ASK.get(t.field, f"the {t.field}")
        return (
            f"Another {role} described '{name}', but we never captured {ask}. "
            f"How does that part go when you do it?",
            [_ROLE_DONT_KNOW],
        )
    if t.kind == GapKind.BROKEN_CHAIN.value:
        return (
            f"'{name}' came up from someone else working as {role}, but we can't see how it "
            "connects to the rest of the process. Where does it sit in your work?",
            [{"if": "they place it", "ask": "What comes immediately before and after it?"}],
        )
    return (
        f"Another {role} raised '{name}'. How does that work on your side?",
        [_ROLE_DONT_KNOW],
    )


_ROLE_FIELD_ASK: dict[str, str] = {
    "trigger": "what kicks it off",
    "inputs": "what's needed in hand to start it",
    "system": "which tool or screen it happens in",
    "output": "what it produces",
    "next_handoff": "who picks it up afterwards",
    "exceptions": "what throws it off",
    "rules": "what rules or policies govern it",
}


# --- orphan-thread copy (P13) -----------------------------------------------------------------
# A question inherited from someone who left. The normal openers presume ownership ("what do YOU
# need in hand") which would be plainly wrong here, so orphans get their own third-person copy —
# and an explicit escape hatch, because "I don't know" is a perfectly good answer to someone
# else's process.

_ORPHAN_WHY = (
    "Raised by a teammate who is no longer in the engagement. The question is still open about how "
    "the business works, so anyone who knows can close it."
)

_ORPHAN_DONT_KNOW = {
    "if": "they don't know",
    "ask": "No problem — who would be the right person to ask about that?",
}

_ORPHAN_FIELD_ASK: dict[str, str] = {
    "trigger": "what kicks it off",
    "inputs": "what's needed in hand to start it",
    "system": "which tool or screen it happens in",
    "output": "what it produces",
    "next_handoff": "who picks it up afterwards",
    "exceptions": "what throws it off",
    "rules": "what rules or policies govern it",
}


def _orphan_opener_and_followups(t: OpenThread) -> tuple[str, list[dict[str, str]]]:
    name = t.node_name or "that step"
    if t.kind == GapKind.MISSING_FIELD.value and t.field:
        ask = _ORPHAN_FIELD_ASK.get(t.field, f"the {t.field}")
        return (
            f"A colleague described '{name}' before they left the project, but we never captured "
            f"{ask}. Do you know how that part works?",
            [_ORPHAN_DONT_KNOW],
        )
    if t.kind == GapKind.BROKEN_CHAIN.value:
        return (
            f"'{name}' came up from a colleague who has since left, and we can't see how it "
            "connects to the rest of the process. Can you place it?",
            [{"if": "they place it", "ask": "What comes immediately before and after it?"}],
        )
    return (
        f"A colleague raised '{name}' before they left the project. Do you know how that works?",
        [_ORPHAN_DONT_KNOW],
    )


# --- opener + followup scaffolding (deterministic; an LLM may later enrich) -------------------

_FIELD_OPENERS: dict[str, str] = {
    "trigger": "Walk me through what kicks off '{name}' — what happens right before you start?",
    "inputs": "When you do '{name}', what do you need in hand to begin?",
    "system": "Where do you actually do '{name}' — which tool or screen?",
    "output": "When '{name}' is finished, what have you produced?",
    "next_handoff": "Once '{name}' is done, who picks it up next?",
    "exceptions": "What throws '{name}' off — the awkward cases that don't go to plan?",
    "rules": "Are there rules or policies you have to follow doing '{name}'?",
    # --- P15b: the lifecycle spine, cadence, and the org chart (plan §8.3) ---
    "cadence": "How often does '{name}' happen — every project, or only in certain cases?",
    "position": "Where does '{name}' sit in the journey — what comes just before, and just after?",
    "owner": "Who's accountable for '{name}' overall — not who does the tasks, who owns it?",
    "activities": "What actually happens during '{name}'? Walk me through it in order.",
    "exit_criteria": "How do you know '{name}' is done and it's safe to move on?",
    # These two name the role deliberately. A Role gap fires for any role in the persona's
    # subgraph — including one they merely *mentioned* — so copy addressed to "you" would ask a BA
    # about their own reporting line while pointing at the QA Head's node. The runner may reword an
    # opener (it's scaffolding, not rails) and knows whose role is whose from the identity block.
    "reports_to": "Who does the {name} report to, and who reports in to them?",
    "performs": "What are the main pieces of work the {name} handles?",
    "objective_for": "What is '{name}' meant to achieve?",
    "owner_role": "Whose goal is '{name}' — who's driving it?",
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
    # --- P15b ---
    "cadence": [{"if": "they say it varies", "ask": "What decides whether it happens or not?"}],
    "position": [
        {"if": "they name what comes next", "ask": "Does anything ever skip straight past it?"}
    ],
    "owner": [{"if": "they name someone", "ask": "Is that the same person who signs it off?"}],
    "activities": [{"if": "they list steps", "ask": "Which of those are yours, and which aren't?"}],
    "exit_criteria": [
        {"if": "they describe a check", "ask": "Who decides it's met — and what if it isn't?"}
    ],
    "reports_to": [{"if": "they name a manager", "ask": "Is anyone else at that same level?"}],
    "performs": [{"if": "they list work", "ask": "Which of those takes up the most time?"}],
    "objective_for": [{"if": "they state a goal", "ask": "How would you know it's been met?"}],
    "owner_role": [{"if": "they name a role", "ask": "Is that expectation written down anywhere?"}],
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
    if t.kind == KIND_HANDOFF_SELF:  # one person wearing both hats (P15a §4.5)
        giver = t.role_name or "your other role"
        recv = t.other_role_name or "your other role"
        return (
            f"You wear both hats here — when you switch from your {giver} hat to your {recv} hat, "
            f"what do you do with '{name}'?",
            [{"if": "they describe it", "ask": "Does anything get dropped or redone in it?"}],
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
