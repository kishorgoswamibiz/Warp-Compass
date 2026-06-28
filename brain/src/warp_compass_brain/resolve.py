"""Resolve — retrieve existing candidates for a proposed node, then adjudicate same/conflict/new.

Retrieval combines alias matching (exact) + vector similarity, filtered to the SAME node type
(category overlap is a soft boost, not a hard filter, to protect recall). Adjudication is a
closed-choice LLM call (§7, §12): the model must justify a "new" verdict against each candidate.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ValidationError

from .llm.base import LLMError, LLMProvider
from .models import CandidateNode, NodeCard
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
No prose outside the JSON."""


def _card_brief(c: NodeCard) -> str:
    al = f" (aka {', '.join(c.aliases)})" if c.aliases else ""
    return f'- id={c.id} type={c.type} name="{c.canonical_name}"{al}: {c.description}'


def _candidate_brief(c: CandidateNode) -> str:
    al = f" (aka {', '.join(c.aliases)})" if c.aliases else ""
    return f'type={c.type} name="{c.canonical_name}"{al}: {c.description}'


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

    def adjudicate(
        self, cand: CandidateNode, retrieved: list[RetrievalCandidate]
    ) -> Adjudication:
        if not retrieved:
            return Adjudication(verdict="new", reason="no existing candidates of this type")
        candidates_block = "\n".join(_card_brief(r.card) for r in retrieved)
        user = (
            f"PROPOSED:\n{_candidate_brief(cand)}\n\n"
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
