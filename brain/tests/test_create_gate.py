"""Phase 2 — the create gate's deterministic rules (no network)."""

from __future__ import annotations

from warp_compass_brain.create_gate import CreateGate
from warp_compass_brain.models import CandidateNode, NodeCard, NodeType
from warp_compass_brain.ontology import load_ontology
from warp_compass_brain.resolve import Adjudication, RetrievalCandidate

ONT = load_ontology()


def _cand(**kw) -> CandidateNode:
    base = dict(ref="n1", type=NodeType.ACTIVITY, canonical_name="Check stock", description="desc")
    base.update(kw)
    return CandidateNode(**base)


def _existing(score: float) -> RetrievalCandidate:
    card = NodeCard(
        id="act.check-stock",
        type=NodeType.ACTIVITY,
        canonical_name="Check stock",
        description="verify availability",
        category_codes=["02"],
    )
    return RetrievalCandidate(card=card, score=score, via="vector")


def test_similarity_ceiling_overrules_new():
    gate = CreateGate(ONT, similarity_ceiling=0.86)
    d = gate.decide(_cand(), [_existing(0.91)], Adjudication(verdict="new", reason="looks new"))
    assert d.action == "merge"
    assert d.match_id == "act.check-stock"


def test_below_ceiling_allows_create():
    gate = CreateGate(ONT, similarity_ceiling=0.86)
    d = gate.decide(_cand(), [_existing(0.40)], Adjudication(verdict="new", reason="distinct"))
    assert d.action == "create"


def test_missing_description_quarantines():
    gate = CreateGate(ONT)
    d = gate.decide(_cand(description="  "), [], Adjudication(verdict="new", reason="x"))
    assert d.action == "quarantine"


def test_default_category_assigned_when_empty():
    gate = CreateGate(ONT)
    d = gate.decide(_cand(category_codes=[]), [], Adjudication(verdict="new", reason="x"))
    assert d.action == "create"
    assert d.final_category_codes == ["02"]  # Activity default


def test_unregistered_code_routed_to_pending():
    gate = CreateGate(ONT)
    d = gate.decide(_cand(category_codes=["99.9"]), [], Adjudication(verdict="new", reason="x"))
    assert d.action == "create"
    assert d.pending_codes == ["99.9"]
    assert d.final_category_codes == ["02"]  # fell back to default since 99.9 unregistered


def test_same_and_conflict_passthrough():
    gate = CreateGate(ONT)
    same = gate.decide(_cand(), [_existing(0.5)], Adjudication(verdict="same", match_id="act.check-stock", reason="r"))
    assert same.action == "merge" and same.match_id == "act.check-stock"
    conf = gate.decide(_cand(), [_existing(0.5)], Adjudication(verdict="conflict", match_id="act.check-stock", reason="r"))
    assert conf.action == "conflict"
