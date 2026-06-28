# Phase 9 — Cross-persona corroboration + conflict threads

## Context Card — read THIS, skip the source
- **Data shapes (authoritative):** `contracts/session-brief.schema.json` (what threads become in a
  brief — `additionalProperties:false`, so don't add fields), `contracts/node-card.schema.json`.
- **Status vocabulary:** `ConfidenceStatus` (`UNVERIFIED="unverified"`, `CONFIRMED="confirmed"`,
  `CONFLICTING="conflicting"`) @ `brain/.../models.py:50`. `Provenance{said_by, status, confidence, ...}`
  @ `:59`. `EdgeType.HANDS_OFF_TO="HANDS_OFF_TO"` @ `models.py:42`.
- **⚠️ Half of this phase ALREADY EXISTS at ingest — extend, don't duplicate:**
  - `Ingestor._merge` @ `ingest.py:149` **already promotes `UNVERIFIED → CONFIRMED` when ≥2 distinct
    `said_by`** corroborate a node (`ingest.py:164-168`). That's exact-match corroboration (step 3).
  - `Ingestor._flag_conflict` @ `ingest.py:173` sets `CONFLICTING` when the **create-gate** returns a
    `conflict` action (exact-match collision). P9 adds the **batch cross-graph** comparison beyond what
    the gate catches (semantically-contradictory accounts of the *same* node, step 2).
- **P3 already surfaces these as gaps — P9 ROUTES them:**
  - `GapKind.ONE_SIDED_HANDOFF` @ `completeness.py:55` is emitted with `other_role_id/other_role_name`
    = the **receiving** role (`completeness.py:279-290`); `GapKind.UNRESOLVED_CONFLICT` @ `_conflict_gaps`
    `completeness.py:342`. `Gap{kind, node_id, field, role_id, other_role_id, other_role_name}` (frozen)
    @ `completeness.py:64`.
  - `threads.threads_from_gaps(gaps) -> list[OpenThread]` @ `threads.py:66`; `OpenThread{kind, goal, why,
    priority, node_id, role_id, other_role_id, other_role_name, field}` @ `threads.py:44`;
    `build_threads(report)` @ `threads.py:61`.
- **The routing seam (the core P9 change):** today (ADR #17e) a one-sided handoff appears in the
  **discoverer's** brief naming the receiving role. P9 must route it to the **receiver's** brief:
  `Planner.plan(persona_id, *, session_id)` @ `planner.py:113` scopes threads to a persona by
  provenance `said_by`; add a pull for threads whose **`other_role_id == persona_id`** (the receiver),
  with high priority + a clear `why`. Persona scoping = provenance `said_by` (ADR #17; no `:Persona` node).
- **GraphStore reads/writes you'll use:** `nodes_by_type(type)`, `edges(edge_type=None)`,
  `set_status(node_id, status)`, `add_provenance(node_id, prov)`, `get_node(id)` (see `graphstore/base.py`
  + the `FakeGraphStore` in `tests/conftest.py` for test wiring).
- **Bidirectional handoff confirm:** a handoff is "both-sided" today only as a **structural proxy** (the
  receiving role performs ≥1 activity, ADR #16c). P9 upgrades it to an explicit corroboration: a thread
  asks B "do you receive X from A?"; mark the edge/handoff `confirmed` only when both directions agree.
- **Run:** `uv` from `brain/` (Neo4j Desktop Started). New work is `brain/.../crosspersona.py` +
  Planner integration. Add tests with the `FakeGraphStore`/`FakeLLM` fakes (no DB/network), like P3/P4.

**Goal:** Make the brain genuinely *connected* — verify handoffs from both sides and turn
cross-session / cross-persona disagreements into future threads rather than averaging them away
(`02 §8, §10`).

**Depends on:** P2 + P3 + P4. **Package:** `brain`.

## Steps
1. **Handoff corroboration** (`crosspersona.py`): when role A's activity `HANDS_OFF_TO` role B,
   generate a thread for **B** ("do you receive X from A?") and vice-versa until both sides confirm.
   Mark the handoff `confirmed` only when corroborated from both directions.
2. **Cross-session/cross-persona conflict detection** (batch tier of `02 §8`): compare a new
   fact against the global graph; on contradiction, set the node `conflicting` and emit a
   reconciliation thread to the relevant persona(s). (Within-session conflicts stay live in P5.)
3. **Confidence promotion:** corroboration by another persona/BA raises `unverified → confirmed`;
   contradiction drops to `conflicting`.
4. **Feed the Planner:** these corroboration/conflict threads flow into P4 briefs with high
   priority and a clear `why`.

## Files
`brain/src/warp_compass_brain/crosspersona.py` (+ planner integration).

## Test plan
- A one-sided handoff produces a corroboration thread for the other persona; once both sides
  agree, status flips to `confirmed`.
- Two personas describing the same step incompatibly → node `conflicting` + reconciliation thread.
- No false conflicts on mere paraphrases (dedup from P2 handles those first).

## Done when
Handoffs are verified bidirectionally, conflicts are tracked and routed (never silently merged),
and confidence statuses move correctly with evidence.
