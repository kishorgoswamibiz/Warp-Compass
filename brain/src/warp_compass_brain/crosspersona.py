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

Persona scoping = provenance ``said_by`` (ADR #17; there is no ``:Persona`` node). A persona *owns*
a role when it **declared that role at onboarding** (P16a, ADR #34; WC-28/ADR #42 made declaration
the only source rather than one of two) — merely *mentioning* a role, or describing what it does,
is not being it. Where there are no declarations at all — a pre-P15a bus, most unit tests —
ownership falls back to having contributed the role's activities, which is what P9 shipped with.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from .completeness import load_snapshot
from .graphstore.base import GraphStore
from .models import ConfidenceStatus, EdgeType, NodeType
from .ontology import Ontology
from .roles import REGISTRY_SAID_BY, resolve_declared_roles
from .threads import OpenThread

# Thread kinds this module mints (the Planner knows these for opener/followup scaffolding).
KIND_HANDOFF_CONFIRM = "handoff_confirm"   # routed to the RECEIVER: "do you receive X from A?"
KIND_HANDOFF_TRACE = "handoff_trace"       # routed to the DISCOVERER: receiver not interviewed yet
KIND_CROSS_CONFLICT = "cross_conflict"     # routed to every contributor of a conflicting node
KIND_HANDOFF_SELF = "handoff_self"         # giver AND receiver are the same person wearing two hats

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
    #: Same-altitude divergence — a data-quality problem, routed for reconciliation.
    conflicts: list[str] = field(default_factory=list)
    #: Cross-altitude divergence (P15c, ADR #32) — a FINDING. Deliberately **not** routed to
    #: anybody: both accounts are preserved and `docgen` reports them side by side.
    misalignments: list[str] = field(default_factory=list)


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

    def __init__(
        self,
        graph: GraphStore,
        ontology: Ontology,
        *,
        now: str | None = None,
        declared_roles: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self._g = graph
        self._ont = ontology
        self._now = now
        #: ``persona_id -> declared role titles`` from the bus (P16a / ADR #34). Absent in tests and
        #: on a pre-P15a bus, in which case ownership falls back to activity contribution alone.
        self._declared = {k: tuple(v) for k, v in (declared_roles or {}).items()}
        self._declared_owner_cache: dict[str, set[str]] | None = None

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

        # Node promotion: ≥2 distinct personas and not conflicting. The seeded-role registry is
        # excluded for the same reason ingest excludes it (P15a): it is vocabulary, not a witness,
        # and if the two passes disagreed the batch tier would promote what merge just refused.
        for nid, card in snap.nodes.items():
            personas = {p.said_by for p in card.provenance} - {REGISTRY_SAID_BY}
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
                # P15a §4.5 — multi-hat people hand work to themselves. When the persona receiving
                # this thread also owns the GIVING role, the standard copy tells them a stranger
                # handed it over, which reads as a bug and invites a "that's me" non-answer. The
                # question is still worth asking (the switch is where dual-hat work really leaks),
                # so route a differently-worded twin instead of suppressing it.
                #
                # ⚠ DECLARED on BOTH sides, never inferred (P17a, ADR #38). Describing what QA does
                # gives you provenance on QA's activities, which made a Solution Architect who
                # declared one role hear *"when you switch from your Quality Assurance Head hat…"*,
                # and a Business Analyst hear the Delivery Specialist version three times after
                # denying it twice — *"I told you I do not act as a delivery specialist. Why you're
                # not trying to understand?"*
                #
                # Since WC-28 (ADR #42) the receiving side is declared too, so `recv_personas` is
                # the same set the loop below iterates and `dual_hat` turns on the GIVING side
                # alone. Both memberships are kept explicit: on a declaration-less bus the loop
                # falls back to contribution, and the dual-hat copy must not follow it there.
                declared_owners = self._declared_owners(snap)
                giver_personas = (
                    declared_owners.get(giver_role_id, set()) if giver_role_id else set()
                )
                recv_personas = declared_owners.get(role_id, set())
                self_thread = replace(
                    thread,
                    id=f"thread.{KIND_HANDOFF_SELF}.{act_id}.{role_id}",
                    kind=KIND_HANDOFF_SELF,
                    goal=(
                        f"Describe what happens to '{act_name}' when you switch from your {giver} "
                        f"hat to your {recv_name} hat."
                    ),
                    why=(
                        f"You hold both {giver} and {recv_name}, so this handoff happens "
                        "inside one person — the step most likely to be tacit and undocumented."
                    ),
                )
                for persona in sorted(self._role_owner_personas(role_id, snap)):
                    dual_hat = persona in giver_personas and persona in recv_personas
                    routed.append(RoutedThread(persona, self_thread if dual_hat else thread))
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
        from .alignment import AlignmentEngine, derive_altitudes

        alt = derive_altitudes(snap)
        alignment = AlignmentEngine(self._g)

        routed: list[RoutedThread] = []
        for nid, card in snap.nodes.items():
            if not any(p.status is ConfidenceStatus.CONFLICTING for p in card.provenance):
                continue
            if alignment.is_misalignment(card, snap, alt):
                # P15c / ADR #32 — this divergence spans altitudes, so it is a FINDING, not a
                # defect. Routing a reconciliation thread here is exactly how the system used to
                # delete the exec-vs-doer signal the engagement exists to sell: every contributor
                # got asked "how does it actually work?" until one version survived. Record it and
                # ask nobody. `docgen` reports it with both accounts and who holds each.
                report.misalignments.append(nid)
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

    def _declared_owners(self, snap) -> dict[str, set[str]]:
        """``role_id -> personas who DECLARED that role at onboarding`` (P16a, ADR #34).

        Computed once per snapshot: resolution walks every Role card's aliases, and this is called
        per handoff edge.
        """
        if self._declared_owner_cache is not None:
            return self._declared_owner_cache
        role_cards = [c for c in snap.nodes.values() if c.type is NodeType.ROLE]
        owners: dict[str, set[str]] = {}
        for persona_id, titles in self._declared.items():
            for role_id in resolve_declared_roles(titles, role_cards):
                owners.setdefault(role_id, set()).add(persona_id)
        self._declared_owner_cache = owners
        return owners

    def _role_owner_personas(self, role_id: str, snap) -> set[str]:
        """Personas that *own* a role — **declared**, once the engagement knows who its people are.

        Merely mentioning a role (provenance on the Role node) is not owning it; that rule is as old
        as P9 and its test still stands. P16a added that **declaring** a role at onboarding is
        sufficient on its own (ADR #34), for a failure worth keeping in view: a person genuinely the
        Technical Specialist, whose dev work never earned a ``PERFORMS`` edge under that hat because
        the extractor cannot see who is speaking (phase-16 §2 Finding 1), owned nothing. A
        colleague's "I hand the build to the Technical Specialist" found no owner,
        ``_handoff_state`` returned ``route_discoverer``, and the **colleague** was asked *"who
        would know?"* every round while the real person was never asked at all.

        **What P17d changes: declaration REPLACES the activity inference, it no longer unions with
        it (WC-28, ADR #42).** Contributing a role's activities was the P9 proxy for holding it,
        from a time with one voice in the graph and no declarations to consult. It is the same
        WC-R5 over-reach that ADR #37 removed from ``planner._persona_summary`` and ADR #38 from the
        dual-hat copy — describing what a colleague's role does gives you provenance on that role's
        activities — and this was the last place still trusting it.

        It bit exactly as you would expect the moment two people were on the bus. Kishor said *"the
        Delivery Specialist creates the pre-sales timeline"*, which put his provenance on
        ``act.create-pre-sales-timeline``; ``role.delivery-specialist`` PERFORMS that activity; so
        the Business Analyst was an owner of the Delivery Specialist role, and **every one of the
        four handoff-confirm threads went to both people**. His brief opened with *"It sounds like
        Business Analysis Specialist hands 'Compile Final BRD' over to you — do you receive it?"* —
        a question about the handoff **he had just described making**, addressed to him as its
        recipient. Two more were addressed to an Account Management Specialist and a Solution
        Architect, roles nobody in the engagement holds at all.

        The narrow fix (prefer declared owners, fall back per-role) fixes only the first of those:
        a role with **no** declared holder would still resolve to whoever described its work, so the
        AMS and SA threads would keep going to both. A role nobody declared has not been interviewed
        — which is precisely what ``route_discoverer`` means — so the fallback has to go.

        The activity inference survives only where there is no declaration to consult: a pre-P15a
        bus, or a graph loaded with no bus at all (most unit tests). ``lifecycle.declared_roles``
        lists **every** live participant, including one who ticked nothing, so on any real bus this
        is the declared path and the fallback is dead code.

        The trade (phase-16 R1) is unchanged and now load-bearing: tick a role you don't hold and
        you become its routing target — which ``cli coverage`` surfaces as a declared owner with no
        activities, rather than hiding it.
        """
        if self._declared:
            owners = self._declared_owners(snap).get(role_id, set())
        else:
            owners = set()
            for act_id in snap.out(role_id, EdgeType.PERFORMS):
                card = snap.nodes.get(act_id)
                if card is not None:
                    owners.update(p.said_by for p in card.provenance)
        # The registry is vocabulary, not a person who can be asked anything (see `roles.py`).
        return owners - {REGISTRY_SAID_BY}

    def _source_personas(self, activity_id: str, snap) -> set[str]:
        card = snap.nodes.get(activity_id)
        return {p.said_by for p in card.provenance} if card is not None else set()
