"""Graph → render-agnostic document models (docs/02 §11, phase-10 brief).

Pure traversal over a one-shot snapshot (``completeness.load_snapshot``), reusing the shared
``activity_flow`` so the end-to-end chain can never drift from the P3 completeness check, and the
``CompletenessEngine`` for the authoritative chain/gap verdict. Three deliverables come out:

1. **End-to-end process** — the connected ``Event → Activity → handoff/artifact → …`` flow across
   *all* personas, as a diagram model + an ordered narrative, with broken links surfaced as gaps
   (never bridged).
2. **Per-role SOPs** — the same facts scoped to one role.
3. **Problem register** — every ``Problem`` with its blocked activity, attributes, and any Desire.

Confidence is read off **provenance** (there is no ``NodeCard.status``): a node is ``confirmed``
iff it has a confirmed provenance and no conflicting one. By default only ``confirmed`` (and always
``conflicting`` — a known conflict is never hidden) is emitted; ``include_unverified`` adds the rest
with a visible marker. Every emitted node carries its provenance sources for traceability.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..completeness import (
    CompletenessEngine,
    GapKind,
    activity_flow,
    load_snapshot,
)
from ..graphstore.base import GraphStore
from ..models import ConfidenceStatus, EdgeType, NodeCard, NodeType
from ..ontology import Ontology

# --- render-agnostic models -------------------------------------------------------------------


@dataclass
class Source:
    """One traceable provenance source on a node (who said it, when, with what status)."""

    said_by: str
    ts: str
    status: str


@dataclass
class DocNode:
    """A graph node resolved for rendering, with its effective status + provenance sources."""

    id: str
    type: str
    name: str
    status: str
    codes: list[str]
    sources: list[Source]
    description: str = ""


@dataclass
class DiagramNode:
    id: str
    label: str
    kind: str  # "event" | "activity" | "artifact" | "gap_role"
    status: str
    gap: bool = False


@dataclass
class DiagramEdge:
    src: str
    dst: str
    label: str = ""
    dashed: bool = False


@dataclass
class DocGap:
    kind: str  # "broken_chain" | "dangling_handoff"
    detail: str
    node_id: str | None = None


@dataclass
class NarrativeStep:
    node: DocNode
    line: str  # the human sentence (without the source tag; render adds that)


@dataclass
class EndToEnd:
    diagram_nodes: list[DiagramNode]
    diagram_edges: list[DiagramEdge]
    narrative: list[NarrativeStep]
    gaps: list[DocGap]
    unbroken: bool
    hidden_count: int  # nodes withheld by the confidence filter


@dataclass
class SOPActivity:
    node: DocNode
    triggers: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    systems: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    handoffs: list[str] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    kpis: list[str] = field(default_factory=list)


@dataclass
class RoleSOP:
    role: DocNode
    activities: list[SOPActivity]


@dataclass
class ProblemEntry:
    node: DocNode
    affected_activities: list[str] = field(default_factory=list)
    frequency: str = ""
    impact: str = ""
    suspected_cause: str = ""
    desires: list[DocNode] = field(default_factory=list)


@dataclass
class CategorySection:
    code: str
    label: str
    nodes: list[DocNode]


@dataclass
class GeneratedDocs:
    end_to_end: EndToEnd
    sops: list[RoleSOP]
    problems: list[ProblemEntry]
    orphan_desires: list[DocNode]
    categories: list[CategorySection]
    include_unverified: bool


# --- confidence helpers -----------------------------------------------------------------------


def effective_status(card: NodeCard) -> ConfidenceStatus:
    """Rendered status, strongest evidence wins: conflicting > confirmed > unverified > proposed."""
    statuses = {p.status for p in card.provenance}
    if ConfidenceStatus.CONFLICTING in statuses:
        return ConfidenceStatus.CONFLICTING
    if ConfidenceStatus.CONFIRMED in statuses:
        return ConfidenceStatus.CONFIRMED
    if ConfidenceStatus.PROPOSED in statuses and ConfidenceStatus.UNVERIFIED not in statuses:
        return ConfidenceStatus.PROPOSED
    return ConfidenceStatus.UNVERIFIED


def _included(status: ConfidenceStatus, include_unverified: bool) -> bool:
    """confirmed + conflicting always render (a conflict is never silently hidden); the rest
    only with the flag."""
    if status in (ConfidenceStatus.CONFIRMED, ConfidenceStatus.CONFLICTING):
        return True
    return include_unverified


def _sources(card: NodeCard) -> list[Source]:
    latest: dict[str, Source] = {}
    for p in card.provenance:
        cur = latest.get(p.said_by)
        if cur is None or p.ts > cur.ts:
            latest[p.said_by] = Source(said_by=p.said_by, ts=p.ts, status=p.status.value)
    return [latest[k] for k in sorted(latest)]


# --- generator --------------------------------------------------------------------------------


class DocGenerator:
    """Builds the three deliverables from the current graph. Read-only and deterministic."""

    def __init__(
        self,
        graph: GraphStore,
        ontology: Ontology,
        *,
        include_unverified: bool = False,
    ) -> None:
        self._g = graph
        self._ont = ontology
        self._include = include_unverified

    def generate(self) -> GeneratedDocs:
        snap = load_snapshot(self._g)
        report = CompletenessEngine(self._g, self._ont).assess()
        return GeneratedDocs(
            end_to_end=self._end_to_end(snap, report),
            sops=self._sops(snap),
            problems=self._problems(snap),
            orphan_desires=self._orphan_desires(snap),
            categories=self._categories(snap),
            include_unverified=self._include,
        )

    # --- node helpers ---

    def _doc(self, card: NodeCard) -> DocNode:
        return DocNode(
            id=card.id,
            type=card.type.value,
            name=card.canonical_name,
            status=effective_status(card).value,
            codes=list(card.category_codes),
            sources=_sources(card),
            description=card.description,
        )

    def _show(self, card: NodeCard) -> bool:
        return _included(effective_status(card), self._include)

    def _name(self, snap, node_id: str) -> str:
        card = snap.nodes.get(node_id)
        return card.canonical_name if card is not None else node_id

    def _owning_role(self, snap, activity_id: str) -> NodeCard | None:
        for role_id in sorted(snap.inc(activity_id, EdgeType.PERFORMS)):
            role = snap.nodes.get(role_id)
            if role is not None and role.type is NodeType.ROLE:
                return role
        return None

    # --- 1) end-to-end process ---

    def _end_to_end(self, snap, report) -> EndToEnd:
        activities = [c for c in snap.nodes.values() if c.type is NodeType.ACTIVITY]
        ids = {a.id for a in activities}
        flow = activity_flow(ids, snap)

        shown = {a.id for a in activities if self._show(a)}
        hidden_count = len(ids) - len(shown)

        dia_nodes: dict[str, DiagramNode] = {}
        dia_edges: list[DiagramEdge] = []

        broken = {
            g.node_id for g in report.gaps if g.kind is GapKind.BROKEN_CHAIN
        }

        def add_activity_node(aid: str) -> None:
            if aid in dia_nodes:
                return
            card = snap.nodes[aid]
            role = self._owning_role(snap, aid)
            role_sfx = f"\n({role.canonical_name})" if role else ""
            dia_nodes[aid] = DiagramNode(
                id=aid,
                label=card.canonical_name + role_sfx,
                kind="activity",
                status=effective_status(card).value,
                gap=aid in broken,
            )

        for aid in shown:
            add_activity_node(aid)

        # Trigger edges: Event -> Activity (entry points).
        for aid in shown:
            for evt_id in snap.inc(aid, EdgeType.TRIGGERS):
                evt = snap.nodes.get(evt_id)
                if evt is None:
                    continue
                dia_nodes.setdefault(
                    evt_id,
                    DiagramNode(evt_id, evt.canonical_name, "event",
                                effective_status(evt).value),
                )
                dia_edges.append(DiagramEdge(evt_id, aid, "triggers"))

        # Continuation edges between shown activities (drop self-loops — an activity doesn't
        # meaningfully "continue to itself"; these arise from a generic role handing off to itself).
        for a in sorted(shown):
            for b in sorted(flow[a]):
                if b not in shown or b == a:
                    continue
                label, _kind = self._continuation_label(snap, a, b)
                dia_edges.append(DiagramEdge(a, b, label))

        # Final outputs: an artifact a shown exit activity PRODUCES that nobody consumes.
        consumed = {art for a in ids for art in snap.out(a, EdgeType.CONSUMES)}
        for aid in sorted(shown):
            if flow[aid]:
                continue  # not a terminal step
            for art_id in snap.out(aid, EdgeType.PRODUCES):
                if art_id in consumed:
                    continue
                art = snap.nodes.get(art_id)
                if art is None:
                    continue
                dia_nodes.setdefault(
                    art_id,
                    DiagramNode(art_id, art.canonical_name, "artifact",
                                effective_status(art).value),
                )
                dia_edges.append(DiagramEdge(aid, art_id, "produces"))

        # Gaps — surfaced, never bridged. Scoped to shown nodes so a hidden (unverified) node's
        # gap doesn't leak it into the confirmed-only view.
        gaps: list[DocGap] = []
        for g in report.gaps:
            if g.node_id is not None and g.node_id not in shown:
                continue
            if g.kind is GapKind.BROKEN_CHAIN:
                gaps.append(DocGap("broken_chain", g.detail, g.node_id))
            elif g.kind is GapKind.ONE_SIDED_HANDOFF:
                gaps.append(DocGap("dangling_handoff", g.detail, g.node_id))
                # draw the dangling handoff with a gap node, if the source is shown
                if g.node_id in shown and g.other_role_id:
                    gid = f"gap_{g.other_role_id}"
                    dia_nodes.setdefault(
                        gid,
                        DiagramNode(
                            gid,
                            f"{g.other_role_name or g.other_role_id}\n(not described)",
                            "gap_role",
                            "unverified",
                            gap=True,
                        ),
                    )
                    dia_edges.append(DiagramEdge(g.node_id, gid, "handoff?", dashed=True))

        narrative = self._narrative(snap, shown, flow)
        return EndToEnd(
            diagram_nodes=list(dia_nodes.values()),
            diagram_edges=dia_edges,
            narrative=narrative,
            gaps=gaps,
            unbroken=report.org.chain_unbroken,
            hidden_count=hidden_count,
        )

    def _continuation_label(self, snap, a: str, b: str) -> tuple[str, str]:
        # Prefer naming the bridging role (a handoff); else the shared artifact.
        for role_id in snap.out(a, EdgeType.HANDS_OFF_TO):
            if b in snap.out(role_id, EdgeType.PERFORMS):
                return f"handoff: {self._name(snap, role_id)}", "handoff"
        produced = set(snap.out(a, EdgeType.PRODUCES))
        for art in snap.out(b, EdgeType.CONSUMES):
            if art in produced:
                return self._name(snap, art), "artifact"
        return "then", "flow"

    def _narrative(self, snap, shown: set[str], flow) -> list[NarrativeStep]:
        order = _topo_order(shown, flow)
        steps: list[NarrativeStep] = []
        for aid in order:
            card = snap.nodes[aid]
            role = self._owning_role(snap, aid)
            who = role.canonical_name if role else "someone"
            triggers = [self._name(snap, e) for e in snap.inc(aid, EdgeType.TRIGGERS)]
            nexts = []
            for b in sorted(flow[aid]):
                if b in shown and b != aid:
                    label, _ = self._continuation_label(snap, aid, b)
                    nexts.append(f"{self._name(snap, b)} ({label})")
            line = f"**{card.canonical_name}** — performed by {who}"
            if triggers:
                line += f", triggered by {', '.join(triggers)}"
            if nexts:
                line += f"; continues to {', '.join(nexts)}"
            else:
                outputs = [
                    self._name(snap, art)
                    for art in snap.out(aid, EdgeType.PRODUCES)
                ]
                if outputs:
                    line += f"; produces {', '.join(outputs)} (final output)"
            steps.append(NarrativeStep(self._doc(card), line + "."))
        return steps

    # --- 2) per-role SOPs ---

    def _sops(self, snap) -> list[RoleSOP]:
        roles = sorted(
            (c for c in snap.nodes.values() if c.type is NodeType.ROLE),
            key=lambda r: r.id,
        )
        out: list[RoleSOP] = []
        for role in roles:
            if not self._show(role):
                continue
            acts = []
            for aid in sorted(snap.out(role.id, EdgeType.PERFORMS)):
                card = snap.nodes.get(aid)
                if card is None or card.type is not NodeType.ACTIVITY or not self._show(card):
                    continue
                acts.append(self._sop_activity(snap, card))
            if acts:
                out.append(RoleSOP(role=self._doc(role), activities=acts))
        return out

    def _sop_activity(self, snap, card: NodeCard) -> SOPActivity:
        aid = card.id
        exceptions = card.key_attributes.get("exceptions")
        return SOPActivity(
            node=self._doc(card),
            triggers=[self._name(snap, e) for e in snap.inc(aid, EdgeType.TRIGGERS)],
            inputs=[self._name(snap, x) for x in snap.out(aid, EdgeType.CONSUMES)],
            systems=[self._name(snap, x) for x in snap.out(aid, EdgeType.USES)],
            produces=[self._name(snap, x) for x in snap.out(aid, EdgeType.PRODUCES)],
            handoffs=[self._name(snap, x) for x in snap.out(aid, EdgeType.HANDS_OFF_TO)],
            approvals=[
                self._name(snap, x) for x in snap.out(aid, EdgeType.REQUIRES_APPROVAL_FROM)
            ],
            rules=[self._name(snap, x) for x in snap.out(aid, EdgeType.GOVERNED_BY)],
            exceptions=[str(exceptions)] if exceptions else [],
            kpis=[self._name(snap, x) for x in snap.out(aid, EdgeType.MEASURED_BY)],
        )

    # --- 3) problem register ---

    def _problems(self, snap) -> list[ProblemEntry]:
        problems = sorted(
            (c for c in snap.nodes.values() if c.type is NodeType.PROBLEM),
            key=lambda p: p.id,
        )
        desires = [c for c in snap.nodes.values() if c.type is NodeType.DESIRE]
        out: list[ProblemEntry] = []
        for prob in problems:
            if not self._show(prob):
                continue
            ka = prob.key_attributes
            linked_desires = [
                self._doc(d)
                for d in desires
                if str(d.key_attributes.get("relates_to_problem", ""))
                in (prob.id, prob.canonical_name)
            ]
            out.append(
                ProblemEntry(
                    node=self._doc(prob),
                    affected_activities=[
                        self._name(snap, a) for a in snap.out(prob.id, EdgeType.BLOCKS)
                    ],
                    frequency=str(ka.get("frequency", "")),
                    impact=str(ka.get("impact", "")),
                    suspected_cause=str(ka.get("suspected_cause", "")),
                    desires=linked_desires,
                )
            )
        return out

    def _orphan_desires(self, snap) -> list[DocNode]:
        out = []
        for d in sorted(
            (c for c in snap.nodes.values() if c.type is NodeType.DESIRE),
            key=lambda c: c.id,
        ):
            if self._show(d) and not d.key_attributes.get("relates_to_problem"):
                out.append(self._doc(d))
        return out

    # --- section numbering from category codes (§11) ---

    def _categories(self, snap) -> list[CategorySection]:
        sections: list[CategorySection] = []
        for code, label in self._ont.categories_sorted():
            members = [
                self._doc(c)
                for c in sorted(snap.nodes.values(), key=lambda n: n.id)
                if code in c.category_codes and self._show(c)
            ]
            if members:
                sections.append(CategorySection(code=code, label=label, nodes=members))
        return sections


# --- ordering ---------------------------------------------------------------------------------


def _topo_order(ids: set[str], flow: dict[str, set[str]]) -> list[str]:
    """Kahn topological order over the shown sub-flow; cycles/leftovers appended by id so the
    walk is always total and deterministic."""
    sub = {a: {b for b in flow.get(a, set()) if b in ids} for a in ids}
    indeg = {a: 0 for a in ids}
    for a in sub:
        for b in sub[a]:
            indeg[b] += 1
    ready = sorted(a for a in ids if indeg[a] == 0)
    order: list[str] = []
    seen: set[str] = set()
    while ready:
        a = ready.pop(0)
        if a in seen:
            continue
        seen.add(a)
        order.append(a)
        for b in sorted(sub[a]):
            indeg[b] -= 1
            if indeg[b] == 0:
                ready.append(b)
        ready.sort()
    for a in sorted(ids - seen):  # any node left in a cycle
        order.append(a)
    return order
