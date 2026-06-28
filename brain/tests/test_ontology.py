"""Phase 1 — ontology vocabulary + node-card model tests (no DB required)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from warp_compass_brain.models import (
    ConfidenceStatus,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)
from warp_compass_brain.ontology import load_ontology


def test_ontology_loads_all_types():
    ont = load_ontology()
    # All 10 node types and 12 edge types from §6.2 are present.
    assert ont.node_types == {t.value for t in NodeType}
    assert ont.edge_types == {t.value for t in EdgeType}


def test_unknown_type_and_code_are_rejected():
    ont = load_ontology()
    assert ont.is_node_type("Role")
    assert not ont.is_node_type("Sandwich")
    assert ont.is_category_code("05.1")
    assert not ont.is_category_code("99.9")
    assert ont.validate_card_codes(["05.1", "99.9"]) == ["99.9"]


def test_edge_endpoints_match_models():
    ont = load_ontology()
    assert ont.edge_endpoints(EdgeType.PERFORMS) == ("Role", "Activity")
    assert ont.edge_endpoints("HANDS_OFF_TO") == ("Activity", "Role")


def test_slug_prefix_lookup():
    ont = load_ontology()
    assert ont.slug_prefix(NodeType.APPROVAL_POINT) == "appr"
    assert ont.slug_prefix("Role") == "role"


def test_node_card_valid():
    card = NodeCard(
        id="appr.discount-over-10pct",
        type=NodeType.APPROVAL_POINT,
        canonical_name="Discount approval above 10%",
        aliases=["discount sign-off", "the 10% thing"],
        description="Approval required when a quoted discount exceeds 10%.",
        category_codes=["05.1", "04"],
        key_attributes={"threshold": "10%"},
        provenance=[
            Provenance(
                said_by="persona.A",
                session_id="s_2026_0312_pm",
                confidence=0.8,
                status=ConfidenceStatus.UNVERIFIED,
                ts="2026-03-12T15:04:21Z",
            )
        ],
    )
    assert card.type is NodeType.APPROVAL_POINT
    assert "the 10% thing" in card.aliases


def test_node_card_rejects_bad_slug():
    with pytest.raises(ValidationError):
        NodeCard(
            id="Discount Approval",  # not a slug
            type=NodeType.APPROVAL_POINT,
            canonical_name="x",
            description="x",
            category_codes=["05.1"],
        )


def test_node_card_requires_category():
    with pytest.raises(ValidationError):
        NodeCard(
            id="appr.x",
            type=NodeType.APPROVAL_POINT,
            canonical_name="x",
            description="x",
            category_codes=[],  # min 1
        )
