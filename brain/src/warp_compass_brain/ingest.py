"""Ingest pipeline — orchestrates extract → resolve → create-gate → persist for one answer (§7).

Nodes are resolved first (building a ref→id map); relations are committed afterward, skipping any
whose endpoint was quarantined. Provenance is attached to every node and edge; confidence rises to
``confirmed`` once a node is corroborated by a second distinct persona.
"""

from __future__ import annotations

from pydantic import BaseModel

from .create_gate import CreateGate, GateDecision
from .extractor import Extractor
from .graphstore.base import GraphStore
from .models import (
    ConfidenceStatus,
    Edge,
    NodeCard,
    Provenance,
)
from .ontology import Ontology
from .queues import JsonlQueue
from .resolve import Resolver
from .slugs import mint_slug
from .vectorindex.base import VectorIndex


class IngestSummary(BaseModel):
    created: list[str] = []
    merged: list[str] = []
    conflicts: list[str] = []
    quarantined: int = 0
    edges: int = 0
    pending_codes: list[str] = []


class Ingestor:
    def __init__(
        self,
        graph: GraphStore,
        vector: VectorIndex,
        ontology: Ontology,
        extractor: Extractor,
        resolver: Resolver,
        gate: CreateGate,
        quarantine: JsonlQueue,
        pending_taxonomy: JsonlQueue,
        *,
        default_confidence: float = 0.7,
    ) -> None:
        self._g = graph
        self._v = vector
        self._ont = ontology
        self._extractor = extractor
        self._resolver = resolver
        self._gate = gate
        self._quarantine = quarantine
        self._pending = pending_taxonomy
        self._conf = default_confidence

    def ingest_answer(
        self, answer: str, *, persona_id: str, session_id: str, ts: str
    ) -> IngestSummary:
        summary = IngestSummary()
        extraction = self._extractor.extract(answer)
        ref_to_id: dict[str, str | None] = {}

        for cand in extraction.nodes:
            prov = Provenance(
                said_by=persona_id,
                session_id=session_id,
                confidence=self._conf,
                status=ConfidenceStatus.UNVERIFIED,
                ts=ts,
            )
            retrieved = self._resolver.retrieve(cand)
            adj = self._resolver.adjudicate(cand, retrieved)
            decision = self._gate.decide(cand, retrieved, adj)
            self._record_pending(decision, cand)

            if decision.action == "merge" and decision.match_id:
                ref_to_id[cand.ref] = self._merge(decision.match_id, cand, prov)
                summary.merged.append(decision.match_id)
            elif decision.action == "conflict" and decision.match_id:
                ref_to_id[cand.ref] = self._flag_conflict(decision.match_id, cand, prov)
                summary.conflicts.append(decision.match_id)
            elif decision.action == "create":
                ref_to_id[cand.ref] = self._create(cand, decision, prov)
                summary.created.append(ref_to_id[cand.ref])  # type: ignore[arg-type]
            else:  # quarantine
                ref_to_id[cand.ref] = None
                self._quarantine.append(
                    {
                        "candidate": cand.model_dump(),
                        "reason": decision.reason,
                        "said_by": persona_id,
                        "session_id": session_id,
                        "ts": ts,
                    }
                )
                summary.quarantined += 1
            summary.pending_codes.extend(decision.pending_codes)

        # Commit relations whose endpoints both resolved to real nodes.
        for rel in extraction.relations:
            a, b = ref_to_id.get(rel.from_ref), ref_to_id.get(rel.to_ref)
            if not a or not b:
                continue
            self._g.add_edge(
                Edge(
                    type=rel.type,
                    from_id=a,
                    to_id=b,
                    provenance=[
                        Provenance(
                            said_by=persona_id,
                            session_id=session_id,
                            confidence=self._conf,
                            status=ConfidenceStatus.UNVERIFIED,
                            ts=ts,
                        )
                    ],
                )
            )
            summary.edges += 1

        return summary

    # --- decision handlers ---

    def _create(self, cand, decision: GateDecision, prov: Provenance) -> str:
        slug = mint_slug(
            self._ont, cand.type, cand.canonical_name, lambda s: self._g.get_node(s) is not None
        )
        card = NodeCard(
            id=slug,
            type=cand.type,
            canonical_name=cand.canonical_name,
            aliases=list(dict.fromkeys(cand.aliases)),
            description=cand.description,
            category_codes=decision.final_category_codes,
            key_attributes=cand.key_attributes,
            provenance=[prov],
        )
        self._g.upsert_node(card)
        self._v.add(slug, self._card_text(card))
        return slug

    def _merge(self, match_id: str, cand, prov: Provenance) -> str:
        card = self._g.get_node(match_id)
        if card is None:  # raced/removed — treat as create fallback
            fallback = GateDecision(
                action="create",
                reason="merge target missing",
                final_category_codes=cand.category_codes or [],
            )
            return self._create(cand, fallback, prov)
        # absorb new surface forms as aliases (dedup, never re-add the canonical name)
        new_aliases = [cand.canonical_name, *cand.aliases]
        card.aliases = [
            a for a in dict.fromkeys([*card.aliases, *new_aliases]) if a != card.canonical_name
        ]
        card.provenance.append(prov)
        # corroboration by a second distinct persona → confirmed
        if len({p.said_by for p in card.provenance}) >= 2:
            for p in card.provenance:
                if p.status == ConfidenceStatus.UNVERIFIED:
                    p.status = ConfidenceStatus.CONFIRMED
        self._g.upsert_node(card)
        self._v.add(card.id, self._card_text(card))
        return card.id

    def _flag_conflict(self, match_id: str, cand, prov: Provenance) -> str:
        card = self._g.get_node(match_id)
        if card is not None:
            prov.status = ConfidenceStatus.CONFLICTING
            card.provenance.append(prov)
            self._g.upsert_node(card)
            self._g.set_status(match_id, ConfidenceStatus.CONFLICTING)
        return match_id

    def _record_pending(self, decision: GateDecision, cand) -> None:
        for code in decision.pending_codes:
            self._pending.append({"code": code, "proposed_for": cand.canonical_name})

    @staticmethod
    def _card_text(card: NodeCard) -> str:
        return f"{card.canonical_name}. {card.description}. aliases: {', '.join(card.aliases)}"
