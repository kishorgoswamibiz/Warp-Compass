"""The create gate — deterministic rules that DISPOSE of what the LLM proposed (§7).

The LLM never both invents a node and commits it. Given a candidate, its retrieval, and the
adjudication, the gate returns one action:

  merge       — same as an existing node (or "new" overruled by the similarity ceiling)
  conflict    — same thing, incompatible assertion → flag + queue a follow-up
  create      — genuinely new and well-formed → mint + commit
  quarantine  — failed a rule (kept for BA review, never discarded)

It also routes proposed-but-unregistered category codes to the pending-taxonomy queue, and
auto-assigns a sensible default category when the LLM left it empty (so well-formed nodes aren't
quarantined merely for a missing tag).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .models import CandidateNode, NodeType
from .ontology import Ontology
from .resolve import Adjudication, RetrievalCandidate

# Fallback category per node type, used only when the extractor proposed none.
_DEFAULT_CATEGORY: dict[NodeType, str] = {
    NodeType.EVENT: "01",
    NodeType.ACTIVITY: "02",
    NodeType.SYSTEM: "03",
    NodeType.ROLE: "04",
    NodeType.APPROVAL_POINT: "05",
    NodeType.RULE: "06",
    NodeType.ARTIFACT: "07",
    NodeType.PROBLEM: "09",
    NodeType.DESIRE: "09",
    NodeType.KPI: "10",
}


class GateDecision(BaseModel):
    action: Literal["merge", "conflict", "create", "quarantine"]
    match_id: str | None = None
    reason: str
    final_category_codes: list[str] = []  # for create
    pending_codes: list[str] = []  # unregistered codes routed to pending-taxonomy


class CreateGate:
    def __init__(self, ontology: Ontology, similarity_ceiling: float = 0.86) -> None:
        self._ont = ontology
        self._ceiling = similarity_ceiling

    def decide(
        self,
        cand: CandidateNode,
        retrieved: list[RetrievalCandidate],
        adj: Adjudication,
    ) -> GateDecision:
        # 1) Trust same/conflict verdicts (resolve.adjudicate already validated match_id).
        if adj.verdict == "same":
            return GateDecision(action="merge", match_id=adj.match_id, reason=adj.reason)
        if adj.verdict == "conflict":
            return GateDecision(action="conflict", match_id=adj.match_id, reason=adj.reason)

        # 2) verdict == "new" — apply the brakes.

        # 2a) Similarity ceiling: overrule "new" if an existing same-type node is too close.
        if retrieved:
            top = retrieved[0]
            if top.score >= self._ceiling:
                return GateDecision(
                    action="merge",
                    match_id=top.card.id,
                    reason=f"create-gate override: closest candidate score {top.score:.2f} "
                    f">= ceiling {self._ceiling:.2f} ({adj.reason})",
                )

        # 2b) Vocabulary check: type must be a real ontology type.
        if not self._ont.is_node_type(cand.type):
            return GateDecision(
                action="quarantine", reason=f"unknown node type {cand.type!r}"
            )

        # 2c) Category codes: split registered vs unregistered; unregistered → pending queue.
        registered = [c for c in cand.category_codes if self._ont.is_category_code(c)]
        pending = [c for c in cand.category_codes if not self._ont.is_category_code(c)]
        if not registered:
            registered = [_DEFAULT_CATEGORY[cand.type]]  # auto-assign a default tag

        # 2d) Minimum completeness: name + description + type + >=1 category.
        if not cand.canonical_name.strip() or not cand.description.strip():
            return GateDecision(
                action="quarantine",
                reason="incomplete: needs non-empty canonical_name and description",
                pending_codes=pending,
            )

        return GateDecision(
            action="create",
            reason=adj.reason or "genuinely new, well-formed",
            final_category_codes=registered,
            pending_codes=pending,
        )
