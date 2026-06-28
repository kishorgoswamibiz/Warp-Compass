"""Phase 1 — GraphStore round-trip tests.

These need a live Neo4j (``docker compose up -d`` + brain/.env), so they're marked
``@pytest.mark.neo4j`` and SKIP cleanly when no DB is reachable. Run all with:
    uv run pytest
Run only the no-DB suite with:
    uv run pytest -m "not neo4j"
"""

from __future__ import annotations

import pytest

from warp_compass_brain.config import get_settings
from warp_compass_brain.models import (
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)

pytestmark = pytest.mark.neo4j


def _reachable() -> bool:
    try:
        from neo4j import GraphDatabase

        s = get_settings()
        drv = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
        drv.verify_connectivity()
        drv.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def store():
    if not _reachable():
        pytest.skip("Neo4j not reachable — start it with `docker compose up -d`.")
    from warp_compass_brain.graphstore import Neo4jGraphStore

    s = Neo4jGraphStore()
    s.connect()
    # Clean slate for the test ids we use.
    s.query("MATCH (n:Node) WHERE n.id STARTS WITH 'test.' DETACH DELETE n")
    yield s
    s.query("MATCH (n:Node) WHERE n.id STARTS WITH 'test.' DETACH DELETE n")
    s.close()


def _prov() -> Provenance:
    return Provenance(
        said_by="persona.A",
        session_id="s_test",
        confidence=0.7,
        status=ConfidenceStatus.UNVERIFIED,
        ts="2026-03-12T15:04:21Z",
    )


def test_upsert_and_get_roundtrip(store):
    card = NodeCard(
        id="test.role-inventory-lead",
        type=NodeType.ROLE,
        canonical_name="Inventory Lead",
        aliases=["stock lead"],
        description="Receives orders, checks stock, escalates large ones.",
        category_codes=["02"],
        provenance=[_prov()],
    )
    store.upsert_node(card)
    got = store.get_node("test.role-inventory-lead")
    assert got is not None
    assert got.type is NodeType.ROLE
    assert got.canonical_name == "Inventory Lead"
    assert got.provenance and got.provenance[0].said_by == "persona.A"


def test_find_by_alias_case_insensitive(store):
    hits = store.find_by_alias("STOCK LEAD", node_type="Role")
    assert any(h.id == "test.role-inventory-lead" for h in hits)


def test_edge_and_neighbors(store):
    activity = NodeCard(
        id="test.act-check-stock",
        type=NodeType.ACTIVITY,
        canonical_name="Check stock",
        description="Verify stock availability for an incoming order.",
        category_codes=["02"],
        provenance=[_prov()],
    )
    store.upsert_node(activity)
    store.add_edge(
        Edge(
            type=EdgeType.PERFORMS,
            from_id="test.role-inventory-lead",
            to_id="test.act-check-stock",
            provenance=[_prov()],
        )
    )
    neigh = store.neighbors("test.role-inventory-lead", EdgeType.PERFORMS)
    assert any(n.id == "test.act-check-stock" for n in neigh)
