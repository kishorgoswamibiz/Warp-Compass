# Phase 10 — Documentation generator (the deliverables)

## Context Card — read THIS, skip the source
- **Data shapes (authoritative):** `contracts/node-card.schema.json` (every node), `contracts/ontology.json`
  (vocab + taxonomy). Read schemas, NOT the pydantic mirrors.
- **Graph reads you'll use** (`brain/.../graphstore/base.py`): `nodes_by_type(type:str)->list[NodeCard]`,
  `edges(edge_type:EdgeType|None)->list[Edge]`, `get_node(id)`, `neighbors(id, edge_type=None)`, and the
  raw escape hatch `query(cypher:str, params:dict|None)->list[dict]`. **Cheapest path: reuse
  `load_snapshot(graph)` from `completeness.py:139`** → `_Snapshot{nodes:dict[id,NodeCard],
  out_edges, in_edges}` with `.out(id, EdgeType)->list[to_id]` and `.inc(id, EdgeType)->list[from_id]`.
  In-memory traversal beats per-node Cypher (same choice P3/P9 made, ADR #16a).
- **The end-to-end chain is already built** — don't re-derive the flow graph. `CompletenessEngine._chain_analysis`
  @ `completeness.py:259` constructs the exact `Event TRIGGERS → Role PERFORMS Activity → HANDS_OFF_TO Role
  → …` flow (continuation = a handoff to a role that PERFORMS the next activity, OR producer→consumer via
  PRODUCES/CONSUMES on a shared Artifact) and computes entries (TRIGGERS), exits (no outflow), reachable,
  and `BROKEN_CHAIN` gaps. **For the headline doc, follow the same flow; surface its gaps, never bridge them.**
- **Models** (`models.py`): `NodeType` = Role, Activity, System, Artifact, Event, ApprovalPoint, Rule,
  Problem, Desire, KPI (`:18`). `EdgeType` = PERFORMS, USES, PRODUCES, CONSUMES, TRIGGERS,
  REQUIRES_APPROVAL_FROM, HANDS_OFF_TO, ESCALATES_TO, GOVERNED_BY, BLOCKS, MEASURED_BY, REPORTS_TO (`:33`).
  `NodeCard{id, type, canonical_name, aliases, description, category_codes:list[str], key_attributes:dict,
  provenance:list[Provenance]}`. `Provenance{said_by, session_id, confidence, status, ts}` (`:59`).
- **⚠️ Confidence lives on PROVENANCE, not a node field.** There is **no** `NodeCard.status`. A node is
  "confirmed" iff it has a `CONFIRMED` provenance entry and no `CONFLICTING` one (`ConfidenceStatus`:
  proposed/unverified/confirmed/conflicting @ `models.py:50`). Neo4j writes a denormalized `n.status` via
  `set_status`, but `get_node`/`nodes_by_type` do **NOT** read it back — **filter on provenance statuses**
  (this is how P3 `completeness._conflict_gaps` and P9 `crosspersona` both do it). P9's `corroborate()`
  promotes unverified→confirmed across personas; run it (or `cli corroborate --apply`) before generating
  if you want max `confirmed` coverage.
- **Section numbering (`02 §11`):** taxonomy is `ontology.json → taxonomy_registry.codes` = `[{code,label}]`
  (e.g. `{"code":"05","label":"Approvals"}`); a node carries `category_codes` (e.g. `["05"]`). `Ontology`
  (`ontology.py`) today exposes only `category_codes:set[str]` + `is_category_code()` — **add a small
  `code→label` accessor** (read `_data["taxonomy_registry"]["codes"]`) for titles; sub-numbering (`05.1`)
  is assigned at render time per the design.
- **Problem register:** `nodes_by_type("Problem")`; link to its activity via the `BLOCKS` edge
  (Problem -[BLOCKS]-> Activity), attached `Desire` nodes, and `KPI` via `MEASURED_BY`. Frequency/impact/
  cause live in the Problem's `key_attributes` + `description`; cite `provenance` for traceability.
- **CLI + tests:** add `cmd_docgen` mirroring `cmd_completeness` @ `cli.py` (build `Neo4jGraphStore(s)`,
  `connect()`, `load_ontology()`, run, `close()` in `finally`). Test with the `FakeGraphStore` in
  `tests/conftest.py` (toy connected org, a deliberately broken handoff, an unverified-vs-confirmed mix) —
  **no Neo4j/network**, like P3/P9. `FakeGraphStore.query` returns `[]`, so prefer `load_snapshot` traversal
  over raw Cypher in any code you want unit-tested.
- **Run:** `uv` from `brain/` (Neo4j Desktop Started for live). New work: `brain/.../docgen/{traverse.py,render.py}`.

**Goal:** Traverse the graph and emit the **headline end-to-end process** + per-level SOPs + a
problem register — living, traceable, `confirmed`-by-default (`02 §11`).

**Depends on:** P2 (richer after P9). **Package:** `brain`.

## Outputs (priority order)
1. **End-to-end process (headline).** Follow `Event TRIGGERS → Role PERFORMS Activity →
   HANDS_OFF_TO Role → …` across **all** personas into one connected process, first trigger →
   final output. Diagram (Mermaid) + narrative. **Broken links are surfaced as gaps, never
   silently bridged.**
2. **Per-level SOP.** The same traversal scoped to one role: activities, triggers, tools, handoffs,
   approvals, rules, exceptions, outputs. Diagram + narrative.
3. **Problem register.** Every `Problem` node with linked activity, provenance, frequency, impact,
   suspected cause, and any attached `Desire`.

## Steps
1. **Traversal queries** (`docgen/traverse.py`): Cypher via `GraphStore.query` for the chains above.
2. **Section numbering from category codes** (`02 §11`): `05 Approvals → 05.1 Discount approval …`
   — applied at output time, from the taxonomy registry.
3. **Confidence filter:** render `confirmed` only by default; a flag includes `unverified` with a
   visible marker (confidence surfacing).
4. **Traceability:** every statement links back to provenance (who said it, when).
5. **Renderers** (`docgen/render.py`): Markdown + Mermaid first; Word/PDF export is additive.
6. **Living:** regenerate on demand from the current graph (never a one-time export).

## Files
`brain/src/warp_compass_brain/docgen/{traverse.py,render.py}` (+ CLI hook in `cli.py`).

## Test plan
- Toy connected org → a single unbroken end-to-end diagram + narrative; section numbers follow
  the taxonomy.
- A deliberately broken handoff → the gap is shown explicitly, not bridged.
- `unverified` facts are hidden by default and shown (marked) with the flag.
- Every rendered claim resolves to a provenance source.

## Done when
The three deliverables generate from the graph, are traceable, render `confirmed` knowledge by
default, and the end-to-end process is one connected chain (or honestly shows where it breaks).
