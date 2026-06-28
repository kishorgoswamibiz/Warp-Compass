"""Neo4j Community implementation of ``GraphStore``.

Storage model:
  * Every node carries a generic ``:Node`` label (for the id uniqueness constraint)
    plus its ontology type as a second label (e.g. ``:Role``), so type filtering is a
    cheap label match and traversals stay Cypher-idiomatic.
  * Scalar card fields are stored as properties; ``aliases``/``category_codes`` as string
    lists; ``key_attributes`` and ``provenance`` are JSON-serialized (Neo4j can't store
    lists-of-maps natively).
  * Edges are typed relationships; the ontology EdgeType value is the relationship type.

All writes are idempotent (``MERGE`` on id / on the relationship triple).
"""

from __future__ import annotations

import json
from typing import Any

from neo4j import GraphDatabase

from ..config import Settings, get_settings
from ..models import ConfidenceStatus, Edge, EdgeType, NodeCard, NodeType, Provenance
from .base import GraphStore


def _card_to_props(card: NodeCard) -> dict[str, Any]:
    return {
        "id": card.id,
        "canonical_name": card.canonical_name,
        "aliases": list(card.aliases),
        "description": card.description,
        "category_codes": list(card.category_codes),
        "key_attributes": json.dumps(card.key_attributes),
        "provenance": [p.model_dump_json() for p in card.provenance],
    }


def _props_to_card(props: dict[str, Any], node_type: str) -> NodeCard:
    return NodeCard(
        id=props["id"],
        type=NodeType(node_type),
        canonical_name=props["canonical_name"],
        aliases=list(props.get("aliases") or []),
        description=props["description"],
        category_codes=list(props.get("category_codes") or []),
        key_attributes=json.loads(props.get("key_attributes") or "{}"),
        provenance=[
            Provenance.model_validate_json(p) for p in (props.get("provenance") or [])
        ],
    )


class Neo4jGraphStore(GraphStore):
    """Concrete GraphStore backed by Neo4j Community."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._driver = None

    # --- lifecycle ---

    def connect(self) -> None:
        # Silence "label/relationship does not exist" notifications: bulk reads legitimately probe
        # ontology types that may have no instances yet (e.g. before any KPI is ingested).
        self._driver = GraphDatabase.driver(
            self._s.neo4j_uri,
            auth=(self._s.neo4j_user, self._s.neo4j_password),
            notifications_min_severity="OFF",
        )
        self._ensure_schema()

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self) -> Neo4jGraphStore:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _session(self):
        if self._driver is None:
            raise RuntimeError("GraphStore not connected; call connect() first.")
        return self._driver.session(database=self._s.neo4j_database)

    def _ensure_schema(self) -> None:
        with self._session() as s:
            s.run(
                "CREATE CONSTRAINT node_id_unique IF NOT EXISTS "
                "FOR (n:Node) REQUIRE n.id IS UNIQUE"
            )

    # --- nodes ---

    def upsert_node(self, card: NodeCard) -> None:
        props = _card_to_props(card)
        # The second label (node type) is validated against the enum, so f-string is safe.
        label = card.type.value
        cypher = (
            f"MERGE (n:Node {{id: $id}}) SET n += $props SET n:{label} "
            "RETURN n.id AS id"
        )
        with self._session() as s:
            s.run(cypher, id=card.id, props=props)

    def get_node(self, node_id: str) -> NodeCard | None:
        cypher = "MATCH (n:Node {id: $id}) RETURN n, labels(n) AS labels"
        with self._session() as s:
            rec = s.run(cypher, id=node_id).single()
        if rec is None:
            return None
        return _props_to_card(dict(rec["n"]), _type_label(rec["labels"]))

    def find_by_alias(self, name: str, node_type: str | None = None) -> list[NodeCard]:
        type_filter = f":{node_type}" if node_type else ""
        cypher = (
            f"MATCH (n:Node{type_filter}) "
            "WHERE toLower(n.canonical_name) = toLower($name) "
            "   OR any(a IN n.aliases WHERE toLower(a) = toLower($name)) "
            "RETURN n, labels(n) AS labels"
        )
        with self._session() as s:
            recs = list(s.run(cypher, name=name))
        return [_props_to_card(dict(r["n"]), _type_label(r["labels"])) for r in recs]

    def add_provenance(self, node_id: str, provenance: Provenance) -> None:
        cypher = (
            "MATCH (n:Node {id: $id}) "
            "SET n.provenance = coalesce(n.provenance, []) + $p "
            "RETURN n.id AS id"
        )
        with self._session() as s:
            s.run(cypher, id=node_id, p=provenance.model_dump_json())

    def set_status(self, node_id: str, status: ConfidenceStatus) -> None:
        cypher = "MATCH (n:Node {id: $id}) SET n.status = $status RETURN n.id AS id"
        with self._session() as s:
            s.run(cypher, id=node_id, status=status.value)

    # --- edges ---

    def add_edge(self, edge: Edge) -> None:
        rel = edge.type.value  # validated enum -> safe in f-string
        prov = [p.model_dump_json() for p in edge.provenance]
        cypher = (
            "MATCH (a:Node {id: $from_id}), (b:Node {id: $to_id}) "
            f"MERGE (a)-[r:{rel}]->(b) "
            "SET r.provenance = $prov "
            "RETURN type(r) AS t"
        )
        with self._session() as s:
            s.run(cypher, from_id=edge.from_id, to_id=edge.to_id, prov=prov)

    def neighbors(self, node_id: str, edge_type: EdgeType | None = None) -> list[NodeCard]:
        rel = f":{edge_type.value}" if edge_type else ""
        cypher = (
            f"MATCH (n:Node {{id: $id}})-[{rel}]->(m:Node) "
            "RETURN m, labels(m) AS labels"
        )
        with self._session() as s:
            recs = list(s.run(cypher, id=node_id))
        return [_props_to_card(dict(r["m"]), _type_label(r["labels"])) for r in recs]

    # --- bulk reads ---

    def nodes_by_type(self, node_type: str) -> list[NodeCard]:
        # node_type is an ontology label; validate it so it's safe to inline.
        if node_type not in {t.value for t in NodeType}:
            raise ValueError(f"unknown node type: {node_type!r}")
        cypher = f"MATCH (n:Node:{node_type}) RETURN n, labels(n) AS labels"
        with self._session() as s:
            recs = list(s.run(cypher))
        return [_props_to_card(dict(r["n"]), _type_label(r["labels"])) for r in recs]

    def edges(self, edge_type: EdgeType | None = None) -> list[Edge]:
        rel = f":{edge_type.value}" if edge_type else ""
        cypher = (
            f"MATCH (a:Node)-[r{rel}]->(b:Node) "
            "RETURN a.id AS from_id, b.id AS to_id, type(r) AS t, "
            "r.provenance AS prov"
        )
        with self._session() as s:
            recs = list(s.run(cypher))
        out: list[Edge] = []
        for r in recs:
            out.append(
                Edge(
                    type=EdgeType(r["t"]),
                    from_id=r["from_id"],
                    to_id=r["to_id"],
                    provenance=[
                        Provenance.model_validate_json(p) for p in (r["prov"] or [])
                    ],
                )
            )
        return out

    # --- escape hatch ---

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        with self._session() as s:
            return [dict(r) for r in s.run(cypher, **(params or {}))]

    def upsert_nodes(self, cards) -> None:
        for c in cards:
            self.upsert_node(c)


def _type_label(labels: list[str]) -> str:
    """Pick the ontology type label (the one that isn't the generic ``Node`` marker)."""
    for lbl in labels:
        if lbl != "Node":
            return lbl
    raise ValueError(f"node has no ontology type label: {labels!r}")
