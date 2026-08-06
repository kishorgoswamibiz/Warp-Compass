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
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)
from .ontology import Ontology
from .queues import JsonlQueue
from .resolve import Resolver
from .roles import REGISTRY_SAID_BY
from .slugs import mint_slug
from .vectorindex.base import VectorIndex


def _candidate_context(cand, extraction) -> str:
    """The proposed node's *"[performed by X; in stage Y]"* line, read off its own batch (P17b).

    `Resolver.node_context` can only describe nodes that are already in the graph; a candidate is
    by definition not, so its stage and performer have to come from the sibling refs the extractor
    emitted alongside it. Without this the adjudicator sees the discriminating evidence for every
    existing card and none for the thing it is judging — which is worse than symmetric ignorance,
    because "no stage given" then reads as a difference.
    """
    if cand.type is not NodeType.ACTIVITY:
        return ""
    names = {n.ref: n.canonical_name for n in extraction.nodes}
    performers = sorted(
        names[r.from_ref]
        for r in extraction.relations
        if r.type is EdgeType.PERFORMS and r.to_ref == cand.ref and r.from_ref in names
    )
    stages = sorted(
        names[r.to_ref]
        for r in extraction.relations
        if r.type is EdgeType.PART_OF and r.from_ref == cand.ref and r.to_ref in names
    )
    bits = []
    if performers:
        bits.append(f"performed by {', '.join(performers)}")
    if stages:
        bits.append(f"in stage {', '.join(stages)}")
    return f" [{'; '.join(bits)}]" if bits else ""


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
                # P15c: keep THIS person's own words about the node. `_merge` below overwrites
                # nothing but aliases, yet the surviving card carries only the FIRST contributor's
                # description — so without this snapshot a later divergence has nothing to quote.
                # This is the retention step ADR #23 said would be needed.
                account=cand.description,
            )
            retrieved = self._resolver.retrieve(cand)
            adj = self._resolver.adjudicate(
                cand, retrieved, cand_context=_candidate_context(cand, extraction)
            )
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
        # corroboration by a second distinct persona → confirmed. A seeded registry role is
        # vocabulary, not testimony (P15a), so it must never be one of the two voices — otherwise
        # every role would read as corroborated the moment one person mentioned it.
        if len({p.said_by for p in card.provenance} - {REGISTRY_SAID_BY}) >= 2:
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
