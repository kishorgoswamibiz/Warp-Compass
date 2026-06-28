"""Cross-persona corroboration + conflict routing (docs/02 §8, §10, phase-09 brief).

This is what makes the brain genuinely *connected* rather than a pile of single-source accounts.
It does two batch-tier things the per-answer ingest gate can't, both over a one-shot in-memory
snapshot (pure, deterministic, DB-free in tests):

* **Bidirectional handoff verification.** P3 only knows a handoff is "two-sided" structurally (the
  receiving role performs *something*). P9 checks the *specific* flow: did the receiving persona
  describe picking up **this** work (an activity of theirs CONSUMES an artifact the giving activity
  PRODUCES)? Three outcomes per ``HANDS_OFF_TO`` edge:
    - **confirmed** — receiver consumes the giver's output → both sides agree; promote the edge.
    - **route_receiver** — the receiver is an active persona but hasn't connected this handoff →
      put a confirmation thread in the *receiver's* next brief ("do you receive X from A?").
    - **route_discoverer** — nobody has been interviewed as the receiving role yet → keep the
      thread with the discoverer ("who picks X up / who'd know?"), the P3/P4 fallback.

* **Conflict routing.** A node flagged ``CONFLICTING`` (by the ingest gate, including across
  sessions) is turned into a reconciliation thread routed to **every** persona that contributed to
  it — not silently averaged away, and not just shown to one owner.

The Planner (P4) pulls each persona's routed threads at high priority. ``corroborate()`` is the
companion *write* pass (confidence promotion) the operator/cycle runs; everything else is read-only.

Persona scoping = provenance ``said_by`` (ADR #17; there is no ``:Persona`` node). A persona
*owns* a role when it performs that role's activities — mentioning a role is not being it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .completeness import load_snapshot
from .graphstore.base import GraphStore
from .models import ConfidenceStatus, EdgeType, NodeType
from .ontology import Ontology
from .threads import OpenThread

# Thread kinds this module mints (the Planner knows these for opener/followup scaffolding).
KIND_HANDOFF_CONFIRM = "handoff_confirm"   # routed to the RECEIVER: "do you receive X from A?"
KIND_HANDOFF_TRACE = "handoff_trace"       # routed to the DISCOVERER: receiver not interviewed yet
KIND_CROSS_CONFLICT = "cross_conflict"     # routed to every contributor of a conflicting node

# Priority seeds (floats; the Planner re-ranks gap + cross threads together, highest first).
# Cross-persona threads lead a brief: a contradiction or an unverified handoff matters more than a
# missing detail. The discoverer trace keeps the old one-sided-handoff weight so it sits where it
# used to among the gap threads.
_CONFLICT_PRIORITY = 1.5
_CONFIRM_PRIORITY = 1.4
_TRACE_PRIORITY = 0.7


@dataclass
class RoutedThread:
    """An open thread tagged with the persona whose brief it belongs in."""

    persona_id: str
    thread: OpenThread


@dataclass
class HandoffState:
    """The corroboration verdict for one ``HANDS_OFF_TO`` edge."""

    from_activity: str
    to_role: str
    state: str  # "confirmed" | "route_receiver" | "route_discoverer"


@dataclass
class CrossPersonaReport:
    """Read-only assessment: routed threads + per-handoff verdicts + conflicting node ids."""

    routed: list[RoutedThread] = field(default_factory=list)
    handoffs: list[HandoffState] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class CorroborationResult:
    """What the write pass changed."""

    promoted_nodes: list[str] = field(default_factory=list)     # unverified -> confirmed
    confirmed_handoffs: list[tuple[str, str]] = field(default_factory=list)  # (activity, role)
    routed_receiver: int = 0
    routed_discoverer: int = 0
    conflicts: int = 0


class CrossPersonaEngine:
    """Corroborates handoffs across personas, routes conflicts. Read-only except ``corroborate``."""

    def __init__(self, graph: GraphStore, ontology: Ontology, *, now: str | None = None) -> None:
        self._g = graph
        self._ont = ontology
        self._now = now

    # --- read-only assessment -----------------------------------------------------------------

    def assess(self) -> CrossPersonaReport:
        snap = load_snapshot(self._g)
        report = CrossPersonaReport()
        report.routed.extend(self._handoff_threads(snap, report))
        report.routed.extend(self._conflict_threads(snap, report))
        return report

    def threads_for_persona(self, persona_id: str) -> list[OpenThread]:
        """Cross-persona threads that belong in ``persona_id``'s brief, highest-priority first."""
        threads = [rt.thread for rt in self.assess().routed if rt.persona_id == persona_id]
        threads.sort(key=lambda t: (-t.priority, t.id))
        return threads

    # --- write pass (confidence promotion) ----------------------------------------------------

    def corroborate(self) -> CorroborationResult:
        """Apply evidence-based confidence movement to the graph (idempotent).

        * A node corroborated by ≥2 distinct personas, with no conflicting account, has its
          ``unverified`` provenance promoted to ``confirmed`` (the batch-tier re-assertion of the
          per-answer merge promotion).
        * A handoff confirmed from both sides has its edge provenance promoted to ``confirmed``.

        Conflicting nodes are left as-is — only a source resolves a conflict; we just route it.
        """
        snap = load_snapshot(self._g)
        result = CorroborationResult()

        # Node promotion: ≥2 distinct personas and not conflicting.
        for nid, card in snap.nodes.items():
            personas = {p.said_by for p in card.provenance}
            conflicting = any(p.status is ConfidenceStatus.CONFLICTING for p in card.provenance)
            if len(personas) >= 2 and not conflicting:
                fresh = self._g.get_node(nid)
                if fresh is None:
                    continue
                changed = False
                for p in fresh.provenance:
                    if p.status is ConfidenceStatus.UNVERIFIED:
                        p.status = ConfidenceStatus.CONFIRMED
                        changed = True
                if changed:
                    self._g.upsert_node(fresh)
                    result.promoted_nodes.append(nid)

        # Handoff edges: promote the confirmed ones; tally the rest. Apply the same validity
        # guards as the read path so the two views never disagree.
        for edge in self._g.edges(EdgeType.HANDS_OFF_TO):
            if not self._valid_handoff(edge.from_id, edge.to_id, snap):
                continue
            state = self._handoff_state(edge.from_id, edge.to_id, snap)
            if state == "confirmed":
                changed = False
                for p in edge.provenance:
                    if p.status is ConfidenceStatus.UNVERIFIED:
                        p.status = ConfidenceStatus.CONFIRMED
                        changed = True
                if changed:
                    self._g.add_edge(edge)  # idempotent MERGE; re-persists the flipped provenance
                result.confirmed_handoffs.append((edge.from_id, edge.to_id))
            elif state == "route_receiver":
                result.routed_receiver += 1
            else:
                result.routed_discoverer += 1

        result.conflicts = sum(
            1
            for card in snap.nodes.values()
            if any(p.status is ConfidenceStatus.CONFLICTING for p in card.provenance)
        )
        return result

    # --- handoff corroboration ----------------------------------------------------------------

    def _valid_handoff(self, act_id: str, role_id: str, snap) -> bool:
        """A real handoff to corroborate: a known activity -> a Role, not a self-handoff."""
        act = snap.nodes.get(act_id)
        recv_role = snap.nodes.get(role_id)
        if act is None or recv_role is None or recv_role.type is not NodeType.ROLE:
            return False
        giver_role_id, _ = self._owning_role(act_id, snap)
        return giver_role_id != role_id

    def _handoff_threads(self, snap, report: CrossPersonaReport) -> list[RoutedThread]:
        routed: list[RoutedThread] = []
        for act_id, role_id in self._edges(snap, EdgeType.HANDS_OFF_TO):
            if not self._valid_handoff(act_id, role_id, snap):
                continue
            act = snap.nodes.get(act_id)
            recv_role = snap.nodes.get(role_id)
            giver_role_id, giver_role_name = self._owning_role(act_id, snap)

            state = self._handoff_state(act_id, role_id, snap)
            report.handoffs.append(HandoffState(act_id, role_id, state))
            if state == "confirmed":
                continue

            act_name = act.canonical_name
            recv_name = recv_role.canonical_name
            if state == "route_receiver":
                # Ask the receiving persona(s) to confirm picking this up.
                giver = giver_role_name or "another role"
                thread = OpenThread(
                    id=f"thread.{KIND_HANDOFF_CONFIRM}.{act_id}.{role_id}",
                    kind=KIND_HANDOFF_CONFIRM,
                    goal=f"Confirm whether you receive '{act_name}' from {giver}.",
                    why=(
                        f"{giver} described handing '{act_name}' off to you, but your account "
                        "doesn't yet show you picking it up — confirming both sides closes the "
                        "end-to-end chain."
                    ),
                    priority=_CONFIRM_PRIORITY,
                    node_id=act_id,
                    node_name=act_name,
                    role_id=giver_role_id,
                    role_name=giver_role_name,
                    other_role_id=role_id,
                    other_role_name=recv_name,
                )
                for persona in sorted(self._role_owner_personas(role_id, snap)):
                    routed.append(RoutedThread(persona, thread))
            else:  # route_discoverer — receiver not interviewed yet; keep with the source persona
                thread = OpenThread(
                    id=f"thread.{KIND_HANDOFF_TRACE}.{act_id}.{role_id}",
                    kind=KIND_HANDOFF_TRACE,
                    goal=(
                        f"Verify the handoff from '{act_name}' to {recv_name}, "
                        f"from {recv_name}'s side."
                    ),
                    why=(
                        f"A handoff is only trustworthy when both sides confirm it; {recv_name} "
                        "hasn't described picking this up, so the end-to-end chain dangles here."
                    ),
                    priority=_TRACE_PRIORITY,
                    node_id=act_id,
                    node_name=act_name,
                    role_id=giver_role_id,
                    role_name=giver_role_name,
                    other_role_id=role_id,
                    other_role_name=recv_name,
                )
                for persona in sorted(self._source_personas(act_id, snap)):
                    routed.append(RoutedThread(persona, thread))
        return routed

    def _handoff_state(self, act_id: str, role_id: str, snap) -> str:
        """confirmed | route_receiver | route_discoverer for a HANDS_OFF_TO act -> role."""
        if self._receiver_acknowledges(act_id, role_id, snap):
            return "confirmed"
        if self._role_owner_personas(role_id, snap):
            return "route_receiver"
        return "route_discoverer"

    def _receiver_acknowledges(self, act_id: str, role_id: str, snap) -> bool:
        """True when the receiving role performs an activity that CONSUMES an artifact the giving
        activity PRODUCES — i.e. the receiver described picking up *this* work."""
        produced = set(snap.out(act_id, EdgeType.PRODUCES))
        if not produced:
            return False
        for recv_act in snap.out(role_id, EdgeType.PERFORMS):
            if produced.intersection(snap.out(recv_act, EdgeType.CONSUMES)):
                return True
        return False

    # --- conflict routing ---------------------------------------------------------------------

    def _conflict_threads(self, snap, report: CrossPersonaReport) -> list[RoutedThread]:
        routed: list[RoutedThread] = []
        for nid, card in snap.nodes.items():
            if not any(p.status is ConfidenceStatus.CONFLICTING for p in card.provenance):
                continue
            report.conflicts.append(nid)
            thread = OpenThread(
                id=f"thread.{KIND_CROSS_CONFLICT}.{nid}",
                kind=KIND_CROSS_CONFLICT,
                goal=f"Reconcile the conflicting accounts of '{card.canonical_name}'.",
                why=(
                    f"More than one person described '{card.canonical_name}' differently, so the "
                    "graph holds it as conflicting until a source resolves it — rather than "
                    "quietly averaging the two accounts away."
                ),
                priority=_CONFLICT_PRIORITY,
                node_id=nid,
                node_name=card.canonical_name,
            )
            for persona in sorted({p.said_by for p in card.provenance}):
                routed.append(RoutedThread(persona, thread))
        return routed

    # --- helpers ------------------------------------------------------------------------------

    def _edges(self, snap, edge_type: EdgeType) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for edges in snap.out_edges.values():
            for e in edges:
                if e.type is edge_type:
                    out.append((e.from_id, e.to_id))
        return out

    def _owning_role(self, activity_id: str, snap) -> tuple[str | None, str | None]:
        """The first role that PERFORMS this activity (giver attribution)."""
        for role_id in sorted(snap.inc(activity_id, EdgeType.PERFORMS)):
            role = snap.nodes.get(role_id)
            if role is not None:
                return role.id, role.canonical_name
        return None, None

    def _role_owner_personas(self, role_id: str, snap) -> set[str]:
        """Personas that *own* a role: those that contributed the activities it performs.

        Merely mentioning a role (provenance on the Role node) is not owning it — the persona who
        *is* the role is the one whose interview produced its activities.
        """
        personas: set[str] = set()
        for act_id in snap.out(role_id, EdgeType.PERFORMS):
            card = snap.nodes.get(act_id)
            if card is not None:
                personas.update(p.said_by for p in card.provenance)
        return personas

    def _source_personas(self, activity_id: str, snap) -> set[str]:
        card = snap.nodes.get(activity_id)
        return {p.said_by for p in card.provenance} if card is not None else set()
