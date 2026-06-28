"""Completeness ("satisfaction") engine — measures understanding against the ontology, not a
vibe (docs/02 §9, phase-03 brief).

It does two things deterministically from the graph:

* **Per-Activity coverage.** For each ``Activity`` it checks the ontology completeness fields
  (trigger, inputs, system, output, next handoff, exceptions, governing rules). Every missing
  field is a typed :class:`Gap`.
* **Two scores.** A *per-persona* score (the fraction of a role's activities that are fully
  described) and an *org-wide* score that folds together handoff coverage (every handoff
  verified from both sides), conflict resolution (no node left ``conflicting``), and — a
  first-class check — whether the **end-to-end chain is unbroken** (every step connects from a
  first trigger to a final output, with no dangling handoffs).

Gaps feed the thread generator (:mod:`warp_compass_brain.threads`), which the Planner (P4) turns
into per-persona Session Briefs. The engine only *reads* the graph through :class:`GraphStore`;
all scoring is pure Python over an in-memory snapshot so it is trivially testable without a DB.

Design note (DECISION #16): "verified from both sides" is approximated structurally — a handoff
``Activity -[HANDS_OFF_TO]-> Role`` counts as two-sided when the receiving role performs at least
one activity (the receiving side is described in the graph). A receiving role with no activities
is a one-sided / dangling handoff. The graph is re-derivable, so this proxy tightens for free as
the receiving persona is interviewed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

from .graphstore.base import GraphStore
from .models import ConfidenceStatus, Edge, EdgeType, NodeCard, NodeType
from .ontology import Ontology

# --- field → graph-check mapping for an Activity ----------------------------------------------
#
# The ontology names the completeness fields; this engine knows how each maps onto the graph.
# "edge" fields are satisfied by the presence of a relationship; ``direction`` says whether the
# Activity is the source ("out": Activity -[edge]-> X) or target ("in": X -[edge]-> Activity).
# "attribute" fields are satisfied by a truthy key on the Activity's ``key_attributes`` (there is
# no edge type for them in the ontology).

_ACTIVITY_EDGE_FIELDS: dict[str, tuple[EdgeType, str]] = {
    "trigger": (EdgeType.TRIGGERS, "in"),          # Event -> Activity
    "inputs": (EdgeType.CONSUMES, "out"),          # Activity -> Artifact
    "system": (EdgeType.USES, "out"),              # Activity -> System
    "output": (EdgeType.PRODUCES, "out"),          # Activity -> Artifact
    "next_handoff": (EdgeType.HANDS_OFF_TO, "out"),  # Activity -> Role
    "rules": (EdgeType.GOVERNED_BY, "out"),        # Activity -> Rule
}
_ACTIVITY_ATTR_FIELDS: frozenset[str] = frozenset({"exceptions"})


class GapKind(StrEnum):
    """The shape of a completeness defect."""

    MISSING_FIELD = "missing_field"          # an Activity lacks an ontology completeness field
    ONE_SIDED_HANDOFF = "one_sided_handoff"  # a handoff whose receiving side isn't described
    BROKEN_CHAIN = "broken_chain"            # an Activity off the first-trigger→final-output path
    UNRESOLVED_CONFLICT = "unresolved_conflict"  # a node still flagged conflicting


@dataclass(frozen=True)
class Gap:
    """One typed completeness defect, traceable to a node and (where relevant) a role."""

    kind: GapKind
    detail: str
    node_id: str | None = None
    node_name: str | None = None
    field: str | None = None           # set for MISSING_FIELD
    role_id: str | None = None         # the role this gap is attributed to (for per-persona)
    role_name: str | None = None
    other_role_id: str | None = None   # the *receiving* role (set for ONE_SIDED_HANDOFF)
    other_role_name: str | None = None
    latest_ts: str | None = None       # most recent provenance ts on the node (recency seed)


@dataclass
class PersonaScore:
    """How fully a single role's activities are described."""

    role_id: str
    role_name: str
    activities_total: int
    activities_complete: int
    gaps: list[Gap] = field(default_factory=list)

    @property
    def score(self) -> float:
        if self.activities_total == 0:
            return 1.0  # nothing claimed yet → vacuously complete (no activities to describe)
        return self.activities_complete / self.activities_total


@dataclass
class OrgScore:
    """Org-wide completeness: handoffs both-sided, conflicts resolved, chain unbroken."""

    handoff_coverage: float       # fraction of handoffs verified from both sides
    conflict_resolution: float    # fraction of nodes not left conflicting
    chain_connectivity: float     # fraction of activities on a trigger→output path
    chain_unbroken: bool

    @property
    def score(self) -> float:
        return round(
            (self.handoff_coverage + self.conflict_resolution + self.chain_connectivity) / 3, 4
        )


@dataclass
class CompletenessReport:
    """The full assessment: every gap, both score breakdowns, and the satisfaction verdict."""

    gaps: list[Gap]
    persona_scores: list[PersonaScore]
    org: OrgScore
    satisfied: bool


# --- in-memory snapshot -----------------------------------------------------------------------


@dataclass
class _Snapshot:
    nodes: dict[str, NodeCard]
    out_edges: dict[str, list[Edge]]   # from_id -> edges
    in_edges: dict[str, list[Edge]]    # to_id   -> edges

    def out(self, node_id: str, edge_type: EdgeType) -> list[str]:
        return [e.to_id for e in self.out_edges.get(node_id, []) if e.type == edge_type]

    def inc(self, node_id: str, edge_type: EdgeType) -> list[str]:
        return [e.from_id for e in self.in_edges.get(node_id, []) if e.type == edge_type]


def load_snapshot(graph: GraphStore) -> _Snapshot:
    """Pull every node and edge into memory once, so scoring stays pure and round-trip-free."""
    nodes: dict[str, NodeCard] = {}
    for nt in NodeType:
        for card in graph.nodes_by_type(nt.value):
            nodes[card.id] = card
    out_edges: dict[str, list[Edge]] = defaultdict(list)
    in_edges: dict[str, list[Edge]] = defaultdict(list)
    for e in graph.edges():
        out_edges[e.from_id].append(e)
        in_edges[e.to_id].append(e)
    return _Snapshot(nodes=nodes, out_edges=dict(out_edges), in_edges=dict(in_edges))


def activity_flow(ids: set[str], snap: _Snapshot) -> dict[str, set[str]]:
    """The activity continuation graph: ``A -> B`` when work flows from A to B.

    Two ways work continues (docs/02 §9): a **handoff** (A ``HANDS_OFF_TO`` a role that
    ``PERFORMS`` B) or an **artifact** (A ``PRODUCES`` an artifact B ``CONSUMES``). The single
    source of truth for "what comes next" — the completeness chain check (P3) and the doc
    generator's end-to-end traversal (P10) both build on this so they can't drift.
    """
    flow: dict[str, set[str]] = {a: set() for a in ids}
    for a in ids:
        for role_id in snap.out(a, EdgeType.HANDS_OFF_TO):
            for b in snap.out(role_id, EdgeType.PERFORMS):
                if b in ids:
                    flow[a].add(b)
    producers: dict[str, set[str]] = defaultdict(set)
    consumers: dict[str, set[str]] = defaultdict(set)
    for a in ids:
        for art in snap.out(a, EdgeType.PRODUCES):
            producers[art].add(a)
        for art in snap.out(a, EdgeType.CONSUMES):
            consumers[art].add(a)
    for art, prod in producers.items():
        for p in prod:
            for c in consumers.get(art, set()):
                if c != p:
                    flow[p].add(c)
    return flow


class CompletenessEngine:
    """Scores the graph against the ontology and emits typed gaps. Read-only."""

    def __init__(
        self,
        graph: GraphStore,
        ontology: Ontology,
        *,
        persona_threshold: float = 0.9,
        org_threshold: float = 0.9,
    ) -> None:
        self._g = graph
        self._ont = ontology
        self._persona_threshold = persona_threshold
        self._org_threshold = org_threshold

    def assess(self) -> CompletenessReport:
        snap = load_snapshot(self._g)
        activities = [c for c in snap.nodes.values() if c.type is NodeType.ACTIVITY]

        # Artifacts consumed by some activity — used to tell a "final output" (consumed by
        # nobody, so it leaves the process) from an intermediate one.
        consumed: set[str] = {
            art for a in activities for art in snap.out(a.id, EdgeType.CONSUMES)
        }

        # 1) Per-activity field coverage.
        field_gaps: dict[str, list[Gap]] = {}  # activity_id -> its missing-field gaps
        for act in activities:
            field_gaps[act.id] = self._activity_field_gaps(act, snap, consumed)

        # 2) End-to-end chain + dangling handoffs.
        chain = self._chain_analysis(activities, snap)

        # 3) Conflicts (any node left flagged conflicting).
        conflict_gaps = self._conflict_gaps(snap)

        # 4) Per-persona scores. A role's activity is "complete" iff it has no missing-field gap.
        persona_scores = self._persona_scores(snap, field_gaps)

        # 5) Org score.
        org = self._org_score(activities, snap, chain)

        all_gaps = [
            *(g for gs in field_gaps.values() for g in gs),
            *chain.gaps,
            *conflict_gaps,
        ]
        satisfied = (
            not all_gaps
            and org.score >= self._org_threshold
            and all(ps.score >= self._persona_threshold for ps in persona_scores)
        )
        return CompletenessReport(
            gaps=all_gaps, persona_scores=persona_scores, org=org, satisfied=satisfied
        )

    # --- per-activity field coverage ---

    def _activity_field_gaps(
        self, act: NodeCard, snap: _Snapshot, consumed: set[str]
    ) -> list[Gap]:
        fields = self._ont.completeness_fields(NodeType.ACTIVITY)
        role_id, role_name = self._owning_role(act.id, snap)
        latest = _latest_ts(act)
        gaps: list[Gap] = []
        for f in fields:
            if self._field_present(act, f, snap, consumed):
                continue
            gaps.append(
                Gap(
                    kind=GapKind.MISSING_FIELD,
                    detail=f"Activity '{act.canonical_name}' is missing its {f}.",
                    node_id=act.id,
                    node_name=act.canonical_name,
                    field=f,
                    role_id=role_id,
                    role_name=role_name,
                    latest_ts=latest,
                )
            )
        return gaps

    def _field_present(
        self, act: NodeCard, field_name: str, snap: _Snapshot, consumed: set[str]
    ) -> bool:
        if field_name in _ACTIVITY_ATTR_FIELDS:
            return bool(act.key_attributes.get(field_name))
        if field_name == "next_handoff":
            # A handoff is satisfied either by an explicit HANDS_OFF_TO, or when this activity is
            # a legitimate process endpoint — it PRODUCES a final output (an artifact no other
            # activity consumes), i.e. the work leaves the org rather than passing to a next role.
            if snap.out(act.id, EdgeType.HANDS_OFF_TO):
                return True
            return any(art not in consumed for art in snap.out(act.id, EdgeType.PRODUCES))
        spec = _ACTIVITY_EDGE_FIELDS.get(field_name)
        if spec is None:
            # Field named in the ontology but unmapped here — treat as unknowable, not missing,
            # so a vocabulary change can't silently mark everything incomplete.
            return True
        edge_type, direction = spec
        present = snap.out(act.id, edge_type) if direction == "out" else snap.inc(act.id, edge_type)
        return bool(present)

    # --- end-to-end chain ---

    def _chain_analysis(self, activities: list[NodeCard], snap: _Snapshot) -> _ChainResult:
        ids = {a.id for a in activities}
        names = {a.id: a.canonical_name for a in activities}

        # Flow graph over activities (shared with the doc generator, P10) — A -> B when work
        # continues from A to B via a handoff or a produced→consumed artifact.
        flow = activity_flow(ids, snap)

        # dangling-handoff detection: a handoff whose receiving role performs no activity we know of
        gaps: list[Gap] = []
        for a in ids:
            for role_id in snap.out(a, EdgeType.HANDS_OFF_TO):
                receiving = [p for p in snap.out(role_id, EdgeType.PERFORMS) if p in ids]
                if not receiving:
                    role = snap.nodes.get(role_id)
                    src_role_id, src_role_name = self._owning_role(a, snap)
                    gaps.append(
                        Gap(
                            kind=GapKind.ONE_SIDED_HANDOFF,
                            detail=(
                                f"Handoff from '{names[a]}' to "
                                f"'{role.canonical_name if role else role_id}' is one-sided: "
                                "the receiving role performs no activity we know of."
                            ),
                            node_id=a,
                            node_name=names[a],
                            role_id=src_role_id,
                            role_name=src_role_name,
                            other_role_id=role_id,
                            other_role_name=role.canonical_name if role else role_id,
                            latest_ts=_latest_ts(snap.nodes.get(a)),
                        )
                    )

        # entries = triggered by an Event; exits = no outgoing flow (terminal / final output)
        entries = {a for a in ids if snap.inc(a, EdgeType.TRIGGERS)}
        exits = {a for a in ids if not flow[a]}

        reachable = _bfs(entries, flow)
        rflow = _reverse(flow, ids)
        can_reach_exit = _bfs(exits, rflow)
        on_path = reachable & can_reach_exit

        connectivity = (len(on_path) / len(ids)) if ids else 1.0
        unbroken = bool(ids) and bool(entries) and bool(exits) and on_path == ids and not gaps

        for a in sorted(ids - on_path):
            gaps.append(
                Gap(
                    kind=GapKind.BROKEN_CHAIN,
                    detail=(
                        f"Activity '{names[a]}' is not on any path from a first trigger to a "
                        "final output — the end-to-end chain is broken here."
                    ),
                    node_id=a,
                    node_name=names[a],
                    role_id=self._owning_role(a, snap)[0],
                    role_name=self._owning_role(a, snap)[1],
                    latest_ts=_latest_ts(snap.nodes.get(a)),
                )
            )
        return _ChainResult(gaps=gaps, connectivity=connectivity, unbroken=unbroken)

    # --- conflicts ---

    def _conflict_gaps(self, snap: _Snapshot) -> list[Gap]:
        gaps: list[Gap] = []
        for card in snap.nodes.values():
            if any(p.status is ConfidenceStatus.CONFLICTING for p in card.provenance):
                role_id, role_name = (
                    self._owning_role(card.id, snap)
                    if card.type is NodeType.ACTIVITY
                    else (None, None)
                )
                gaps.append(
                    Gap(
                        kind=GapKind.UNRESOLVED_CONFLICT,
                        detail=(
                            f"{card.type.value} '{card.canonical_name}' has conflicting accounts "
                            "that need reconciling."
                        ),
                        node_id=card.id,
                        node_name=card.canonical_name,
                        role_id=role_id,
                        role_name=role_name,
                        latest_ts=_latest_ts(card),
                    )
                )
        return gaps

    # --- scores ---

    def _persona_scores(
        self, snap: _Snapshot, field_gaps: dict[str, list[Gap]]
    ) -> list[PersonaScore]:
        scores: list[PersonaScore] = []
        roles = [c for c in snap.nodes.values() if c.type is NodeType.ROLE]
        for role in sorted(roles, key=lambda r: r.id):
            act_ids = [
                a for a in snap.out(role.id, EdgeType.PERFORMS) if a in field_gaps
            ]
            complete = sum(1 for a in act_ids if not field_gaps[a])
            gaps = [g for a in act_ids for g in field_gaps[a]]
            scores.append(
                PersonaScore(
                    role_id=role.id,
                    role_name=role.canonical_name,
                    activities_total=len(act_ids),
                    activities_complete=complete,
                    gaps=gaps,
                )
            )
        return scores

    def _org_score(
        self, activities: list[NodeCard], snap: _Snapshot, chain: _ChainResult
    ) -> OrgScore:
        # handoff coverage: fraction of HANDS_OFF_TO edges whose receiving role performs ≥1 activity
        act_ids = {a.id for a in activities}
        handoffs = [
            e for es in snap.out_edges.values() for e in es if e.type is EdgeType.HANDS_OFF_TO
        ]
        if handoffs:
            two_sided = sum(
                1
                for e in handoffs
                if any(p in act_ids for p in snap.out(e.to_id, EdgeType.PERFORMS))
            )
            handoff_coverage = two_sided / len(handoffs)
        else:
            handoff_coverage = 1.0

        total_nodes = len(snap.nodes) or 1
        conflicting = sum(
            1
            for c in snap.nodes.values()
            if any(p.status is ConfidenceStatus.CONFLICTING for p in c.provenance)
        )
        conflict_resolution = (total_nodes - conflicting) / total_nodes

        return OrgScore(
            handoff_coverage=round(handoff_coverage, 4),
            conflict_resolution=round(conflict_resolution, 4),
            chain_connectivity=round(chain.connectivity, 4),
            chain_unbroken=chain.unbroken,
        )

    # --- helpers ---

    def _owning_role(self, activity_id: str, snap: _Snapshot) -> tuple[str | None, str | None]:
        """The first role that PERFORMS this activity (for per-persona attribution)."""
        for role_id in sorted(snap.inc(activity_id, EdgeType.PERFORMS)):
            role = snap.nodes.get(role_id)
            if role is not None:
                return role.id, role.canonical_name
        return None, None


@dataclass
class _ChainResult:
    gaps: list[Gap]
    connectivity: float
    unbroken: bool


def _latest_ts(card: NodeCard | None) -> str | None:
    if card is None or not card.provenance:
        return None
    return max(p.ts for p in card.provenance)


def _bfs(starts: set[str], adj: dict[str, set[str]]) -> set[str]:
    seen = set(starts)
    stack = list(starts)
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, set()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _reverse(adj: dict[str, set[str]], ids: set[str]) -> dict[str, set[str]]:
    rev: dict[str, set[str]] = {a: set() for a in ids}
    for a, outs in adj.items():
        for b in outs:
            rev.setdefault(b, set()).add(a)
    return rev
