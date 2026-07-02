"""One-off migration: copy an existing Neo4j Warp Compass graph into an OKF Markdown bundle.

The brain no longer depends on the `neo4j` package (P12), so this standalone script pulls it
in ad hoc. Run FROM the brain/ folder (so the package + .env resolve):

    uv run --with neo4j python ..\\scripts\\migrate_neo4j_to_okf.py
    uv run --with neo4j python ..\\scripts\\migrate_neo4j_to_okf.py --out "G:\\...\\graph"

Reads every node + relationship over bolt (NEO4J_* read from brain/.env or flags), rebuilds
NodeCards/Edges exactly as the old Neo4jGraphStore stored them (key_attributes + provenance
were JSON-serialized strings), and writes the bundle via OkfGraphStore. Idempotent — writes
merge on id, so re-running is safe. After verifying the bundle, Neo4j can be uninstalled.

If you don't have the old data (or don't care): skip this. The graph is re-derivable from the
immutable Answer Logs — clear `ingested_logs` in each participant's profile.json and run-round.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "brain" / "src"))

from warp_compass_brain.config import get_settings, resolve_graph_root  # noqa: E402
from warp_compass_brain.graphstore.okf_store import OkfGraphStore  # noqa: E402
from warp_compass_brain.models import (  # noqa: E402
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "warpcompass"))
    ap.add_argument("--database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    ap.add_argument("--out", default=None, help="bundle root (default: settings graph root)")
    args = ap.parse_args()

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print(
            "neo4j driver not installed — run via: uv run --with neo4j python ...",
            file=sys.stderr,
        )
        return 2

    out = args.out or resolve_graph_root(get_settings())
    type_values = {t.value for t in NodeType}

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    nodes: list[NodeCard] = []
    edges: list[Edge] = []
    with driver.session(database=args.database) as session:
        for rec in session.run("MATCH (n:Node) RETURN n, labels(n) AS labels"):
            props = dict(rec["n"])
            label = next(lb for lb in rec["labels"] if lb in type_values)
            nodes.append(
                NodeCard(
                    id=props["id"],
                    type=NodeType(label),
                    canonical_name=props["canonical_name"],
                    aliases=list(props.get("aliases") or []),
                    description=props["description"],
                    category_codes=list(props.get("category_codes") or []),
                    key_attributes=json.loads(props.get("key_attributes") or "{}"),
                    provenance=[
                        Provenance.model_validate_json(p)
                        for p in (props.get("provenance") or [])
                    ],
                )
            )
        for rec in session.run(
            "MATCH (a:Node)-[r]->(b:Node) "
            "RETURN a.id AS from_id, b.id AS to_id, type(r) AS t, r.provenance AS prov"
        ):
            edges.append(
                Edge(
                    type=EdgeType(rec["t"]),
                    from_id=rec["from_id"],
                    to_id=rec["to_id"],
                    provenance=[
                        Provenance.model_validate_json(p) for p in (rec["prov"] or [])
                    ],
                )
            )
    driver.close()

    with OkfGraphStore(out) as store:
        for card in nodes:
            store.upsert_node(card)
        for edge in edges:
            store.add_edge(edge)

    print(f"migrated {len(nodes)} nodes + {len(edges)} edges -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
