# Phase 1 — Ontology + GraphStore  ✅ DONE

**Goal:** A controlled vocabulary (the completeness compass) and a Neo4j-backed graph store
behind a thin `GraphStore` seam — the foundation every later phase writes to.

**Status:** complete (agent:opus-setup, 2026-06-28).

## What was built
- `contracts/ontology.json` — 10 node types, 12 edge types, confidence statuses, taxonomy registry.
- `brain/src/warp_compass_brain/models.py` — `NodeType`/`EdgeType`/`ConfidenceStatus` enums,
  `Provenance`, `NodeCard` (slug-validated), `Edge`.
- `ontology.py` — loads + validates against the controlled vocabulary; helpers for the create gate.
- `graphstore/base.py` — `GraphStore` ABC; `graphstore/neo4j_store.py` — `Neo4jGraphStore`.
- `vectorindex/base.py` — `VectorIndex` ABC (interface only; impl in P2).
- `config.py`, `docker-compose.yml` (Neo4j Community), `.env.example`, tests.

## Acceptance criteria (met)
- `uv run pytest -m "not neo4j"` passes (ontology + model validation).
- With Neo4j up, `uv run pytest` round-trips a node (upsert→get), alias lookup, and an edge +
  neighbor traversal.
- `uv run ruff check .` clean.

## Notes for later phases
- Node identity is a slug (`role.sales-manager`); type is a Neo4j label; category codes are tags.
- The graph is **re-derivable** from the Answer Log — never hand-edit it.
- Extend `GraphStore` (not Neo4j directly) when a new query is needed, so the seam stays swappable.
