"""Resolve — retrieve existing candidates for a proposed node, then adjudicate same/conflict/new.

Retrieval combines alias matching (exact) + vector similarity, filtered to the SAME node type
(category overlap is a soft boost, not a hard filter, to protect recall). Adjudication is a
closed-choice LLM call (§7, §12): the model must justify a "new" verdict against each candidate.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ValidationError

from .llm.base import LLMError, LLMProvider
from .models import CandidateNode, EdgeType, NodeCard, NodeType
from .ontology import Ontology
from .vectorindex.base import VectorIndex

if False:  # typing only, avoid hard import cycle at runtime
    from .graphstore.base import GraphStore


class RetrievalCandidate(BaseModel):
    card: NodeCard
    score: float
    via: Literal["alias", "vector"]


class Adjudication(BaseModel):
    verdict: Literal["same", "conflict", "new"]
    match_id: str | None = None
    reason: str = ""


_ADJ_SYSTEM = """You decide whether a PROPOSED node is the SAME as an existing one, in CONFLICT
with one, or genuinely NEW. Respond ONLY as JSON:
{"verdict":"same|conflict|new","match_id":"<existing id or null>","reason":"<why>"}
- "same": the proposed node denotes the same real thing as an existing candidate (match_id set).
- "conflict": it refers to the same thing but asserts something incompatible (match_id set).
- "new": none of the candidates fit. To answer "new" you MUST briefly say why each candidate
  does not fit, in the reason.

Some entries carry a bracketed context line: who performs the work and which lifecycle stage it
sits in. WEIGH IT HEAVILY — it is usually the deciding evidence, because wording alone cannot
separate these:
- SAME performer AND same stage, with overlapping descriptions -> almost certainly "same", even
  when the two names look different ("Code Review" / "Review Checks" / "Code Quality Check" are
  one person describing one habit three ways).
- DIFFERENT stage, or a different performing role -> almost certainly "new", even when the two
  names look nearly identical. A demo in Discovery and a demo in UAT are different activities; the
  role that PROVIDES an estimate and the role that APPROVES it are doing different work.
Context is absent for a node nobody has placed yet — then judge on wording, and prefer "new" only
if the described work genuinely differs, not merely because the phrasing does.
No prose outside the JSON."""


def _card_brief(c: NodeCard, context: str = "") -> str:
    al = f" (aka {', '.join(c.aliases)})" if c.aliases else ""
    return f'- id={c.id} type={c.type} name="{c.canonical_name}"{al}{context}: {c.description}'


def _candidate_brief(c: CandidateNode, context: str = "") -> str:
    al = f" (aka {', '.join(c.aliases)})" if c.aliases else ""
    return f'type={c.type} name="{c.canonical_name}"{al}{context}: {c.description}'


class Resolver:
    def __init__(
        self,
        graph: GraphStore,
        vector: VectorIndex,
        ontology: Ontology,
        llm: LLMProvider,
        top_k: int = 8,
    ) -> None:
        self._g = graph
        self._v = vector
        self._ont = ontology
        self._llm = llm
        self._top_k = top_k

    def retrieve(self, cand: CandidateNode) -> list[RetrievalCandidate]:
        found: dict[str, RetrievalCandidate] = {}

        # Exact-ish: alias / canonical-name matches in the graph (same type).
        for name in [cand.canonical_name, *cand.aliases]:
            for card in self._g.find_by_alias(name, cand.type.value):
                found.setdefault(
                    card.id, RetrievalCandidate(card=card, score=1.0, via="alias")
                )

        # Semantic: vector neighbors (same type only).
        text = f"{cand.canonical_name}. {cand.description}. aliases: {', '.join(cand.aliases)}"
        for nid, score in self._v.search(text, k=self._top_k):
            if nid in found:
                continue
            card = self._g.get_node(nid)
            if card is None or card.type != cand.type:
                continue
            found[nid] = RetrievalCandidate(card=card, score=float(score), via="vector")

        ranked = sorted(found.values(), key=lambda r: r.score, reverse=True)
        return ranked[: self._top_k]

    def node_context(self, card: NodeCard) -> str:
        """The bracketed *"[performed by X; in stage Y]"* line shown to the adjudicator (P17b).

        **Measured on the live graph, 06 Aug 2026.** Name + description alone cannot separate real
        duplicates from genuinely different work, because the two populations occupy the same cosine
        band — true duplicates 0.69–0.87, genuinely-distinct pairs 0.78–0.87:

        =======  ==================================================================
        0.874    ``create-project-timeline`` (pre-sales) vs ``manage-project-timelines``
                 (project-delivery) — DIFFERENT work, and the highest score of all
        0.808    ``give-demo`` (discovery) vs ``give-uat-demos`` (uat) — DIFFERENT
        0.785    ``provide-effort-estimation`` (Delivery Specialist) vs
                 ``approve-effort-estimation`` (Customer) — DIFFERENT
        0.862    ``code-review`` vs ``review-checks`` — the SAME habit, twice
        =======  ==================================================================

        No threshold separates those, which is why P17b raised ``similarity_ceiling`` instead of
        lowering it (ADR #41). The **stage** and the **performing role** do separate them cleanly,
        and neither was ever put in front of the adjudicator. This is that signal.

        Empty when nothing has placed the node yet — a first mention has no edges, and an empty
        string reads as "no evidence" rather than as evidence of absence.
        """
        bits: list[str] = []
        if card.type is NodeType.ACTIVITY:
            performers = sorted(
                role.canonical_name
                for role in self._incoming(card.id, EdgeType.PERFORMS)
            )
            if performers:
                bits.append(f"performed by {', '.join(performers)}")
            stages = sorted(
                s.canonical_name for s in self._g.neighbors(card.id, EdgeType.PART_OF)
            )
            if stages:
                bits.append(f"in stage {', '.join(stages)}")
        return f" [{'; '.join(bits)}]" if bits else ""

    def _incoming(self, node_id: str, edge_type: EdgeType) -> list[NodeCard]:
        """Nodes pointing AT ``node_id`` — ``GraphStore.neighbors`` only walks outward."""
        out: list[NodeCard] = []
        for e in self._g.edges(edge_type):
            if e.to_id != node_id:
                continue
            card = self._g.get_node(e.from_id)
            if card is not None:
                out.append(card)
        return out

    def adjudicate(
        self,
        cand: CandidateNode,
        retrieved: list[RetrievalCandidate],
        *,
        cand_context: str = "",
    ) -> Adjudication:
        """Closed-choice same/conflict/new call.

        ``cand_context`` is the proposed node's own *"[performed by …; in stage …]"* line, which the
        caller reads off the SAME extraction batch (the candidate has no edges in the graph yet —
        it isn't in the graph). Optional so the signature stays back-compatible.
        """
        if not retrieved:
            return Adjudication(verdict="new", reason="no existing candidates of this type")
        candidates_block = "\n".join(
            _card_brief(r.card, self.node_context(r.card)) for r in retrieved
        )
        user = (
            f"PROPOSED:\n{_candidate_brief(cand, cand_context)}\n\n"
            f"EXISTING CANDIDATES:\n{candidates_block}"
        )
        raw = self._llm.complete_json(_ADJ_SYSTEM, user)
        try:
            adj = Adjudication.model_validate(raw)
        except ValidationError as e:
            raise LLMError(f"adjudicator returned malformed JSON: {e}") from e
        # Guard: a same/conflict verdict must name a real candidate id.
        valid_ids = {r.card.id for r in retrieved}
        if adj.verdict in ("same", "conflict") and adj.match_id not in valid_ids:
            return Adjudication(
                verdict="new",
                reason=f"adjudicator gave {adj.verdict} but match_id not in candidates; "
                f"treating as new ({adj.reason})",
            )
        return adj
