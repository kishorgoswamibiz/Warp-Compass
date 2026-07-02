"""GraphStore round-trip tests against the OKF Markdown bundle store (P12).

No database, no network — the store is a folder of Markdown files under a pytest tmp dir.
Covers the old Neo4j-store contract (upsert/get, alias find, edges/neighbors) plus the
OKF-specific invariants: survive a full reload from disk, idempotent edge MERGE, and the
two-way ``[[wiki-link]]`` sections written into BOTH endpoint files.
"""

from __future__ import annotations

import pytest

from warp_compass_brain.graphstore.okf_store import OkfGraphStore
from warp_compass_brain.models import (
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)


def _prov(said_by: str = "persona.A", status=ConfidenceStatus.UNVERIFIED) -> Provenance:
    return Provenance(
        said_by=said_by,
        session_id="s_test",
        confidence=0.7,
        status=status,
        ts="2026-03-12T15:04:21Z",
    )


def _role() -> NodeCard:
    return NodeCard(
        id="role.inventory-lead",
        type=NodeType.ROLE,
        canonical_name="Inventory Lead",
        aliases=["stock lead"],
        description="Receives orders, checks stock, escalates large ones.",
        category_codes=["02"],
        provenance=[_prov()],
    )


def _activity() -> NodeCard:
    return NodeCard(
        id="act.check-stock",
        type=NodeType.ACTIVITY,
        canonical_name="Check stock",
        description="Verify stock availability for an incoming order.",
        category_codes=["02"],
        key_attributes={"exceptions": "partial stock -> split order"},
        provenance=[_prov()],
    )


@pytest.fixture
def store(tmp_path):
    s = OkfGraphStore(tmp_path / "graph")
    s.connect()
    yield s
    s.close()


def test_upsert_and_get_roundtrip(store):
    store.upsert_node(_role())
    got = store.get_node("role.inventory-lead")
    assert got is not None
    assert got.type is NodeType.ROLE
    assert got.canonical_name == "Inventory Lead"
    assert got.aliases == ["stock lead"]
    assert got.provenance and got.provenance[0].said_by == "persona.A"


def test_find_by_alias_case_insensitive(store):
    store.upsert_node(_role())
    hits = store.find_by_alias("STOCK LEAD", node_type="Role")
    assert any(h.id == "role.inventory-lead" for h in hits)
    assert store.find_by_alias("stock lead", node_type="Activity") == []


def test_edge_and_neighbors(store):
    store.upsert_node(_role())
    store.upsert_node(_activity())
    store.add_edge(
        Edge(
            type=EdgeType.PERFORMS,
            from_id="role.inventory-lead",
            to_id="act.check-stock",
            provenance=[_prov()],
        )
    )
    neigh = store.neighbors("role.inventory-lead", EdgeType.PERFORMS)
    assert [n.id for n in neigh] == ["act.check-stock"]
    assert store.neighbors("act.check-stock", EdgeType.PERFORMS) == []


def test_bundle_survives_reload(tmp_path):
    root = tmp_path / "graph"
    with OkfGraphStore(root) as s:
        s.upsert_node(_role())
        s.upsert_node(_activity())
        s.add_edge(
            Edge(
                type=EdgeType.PERFORMS,
                from_id="role.inventory-lead",
                to_id="act.check-stock",
                provenance=[_prov()],
            )
        )

    with OkfGraphStore(root) as s2:
        got = s2.get_node("act.check-stock")
        assert got is not None
        assert got.key_attributes == {"exceptions": "partial stock -> split order"}
        assert got.provenance[0].ts == "2026-03-12T15:04:21Z"
        edges = s2.edges(EdgeType.PERFORMS)
        assert len(edges) == 1
        assert edges[0].from_id == "role.inventory-lead"
        assert edges[0].provenance[0].said_by == "persona.A"
        assert s2.nodes_by_type("Role")[0].canonical_name == "Inventory Lead"


def test_add_edge_is_idempotent_merge(store):
    store.upsert_node(_role())
    store.upsert_node(_activity())
    e = Edge(
        type=EdgeType.PERFORMS,
        from_id="role.inventory-lead",
        to_id="act.check-stock",
        provenance=[_prov()],
    )
    store.add_edge(e)
    flipped = e.model_copy(deep=True)
    flipped.provenance[0].status = ConfidenceStatus.CONFIRMED
    store.add_edge(flipped)  # MERGE: overwrites provenance, no duplicate
    edges = store.edges(EdgeType.PERFORMS)
    assert len(edges) == 1
    assert edges[0].provenance[0].status is ConfidenceStatus.CONFIRMED


def test_two_way_wiki_links_in_both_files(tmp_path):
    root = tmp_path / "graph"
    with OkfGraphStore(root) as s:
        s.upsert_node(_role())
        s.upsert_node(_activity())
        s.add_edge(
            Edge(
                type=EdgeType.PERFORMS,
                from_id="role.inventory-lead",
                to_id="act.check-stock",
                provenance=[_prov()],
            )
        )

    giver = (root / "roles" / "role.inventory-lead.md").read_text(encoding="utf-8")
    receiver = (root / "activities" / "act.check-stock.md").read_text(encoding="utf-8")
    # Outgoing link in the giver's file...
    assert "PERFORMS → [[act.check-stock]]" in giver
    # ...and the backlink in the receiver's file: both sides always see the relationship.
    assert "[[role.inventory-lead]]" in receiver
    assert "Backlinks" in receiver


def test_node_file_is_readable_okf(tmp_path):
    """The written file carries the OKF essentials: frontmatter with type + the
    keywords-and-description identity block an LLM uses for merge-vs-create decisions."""
    root = tmp_path / "graph"
    with OkfGraphStore(root) as s:
        s.upsert_node(_role())
    text = (root / "roles" / "role.inventory-lead.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "type: Role" in text
    assert "title: Inventory Lead" in text
    assert "keywords:" in text and "stock lead" in text
    assert "Receives orders, checks stock" in text
    assert "# Inventory Lead" in text  # human-readable body


def test_set_status_updates_provenance_and_file(tmp_path):
    root = tmp_path / "graph"
    with OkfGraphStore(root) as s:
        s.upsert_node(_role())
        s.set_status("role.inventory-lead", ConfidenceStatus.CONFLICTING)
        got = s.get_node("role.inventory-lead")
        assert got.provenance[-1].status is ConfidenceStatus.CONFLICTING
    text = (root / "roles" / "role.inventory-lead.md").read_text(encoding="utf-8")
    assert "status: conflicting" in text


def test_indexes_written_on_close(tmp_path):
    root = tmp_path / "graph"
    with OkfGraphStore(root) as s:
        s.upsert_node(_role())
    assert (root / "index.md").is_file()
    roles_index = (root / "roles" / "index.md").read_text(encoding="utf-8")
    assert "[[role.inventory-lead]]" in roles_index


def test_malformed_file_is_skipped_not_fatal(tmp_path, capsys):
    root = tmp_path / "graph"
    with OkfGraphStore(root) as s:
        s.upsert_node(_role())
    (root / "roles" / "broken.md").write_text("no frontmatter here", encoding="utf-8")
    with OkfGraphStore(root) as s2:
        assert s2.get_node("role.inventory-lead") is not None
        assert len(s2.nodes_by_type("Role")) == 1
    assert "skipping" in capsys.readouterr().err
