# Phase 4 — Planner → per-persona Session Brief

> **Status: ✅ DONE (2026-06-28, `agent:opus-p4`).** Implemented in
> `brain/src/warp_compass_brain/planner.py` (+ `threads.threads_from_gaps`); 6 schema-validated
> tests + live `cli plan`. Briefs validate against `contracts/session-brief.schema.json`. See ADR
> #17 and the PROGRESS handoff log for the modelling choices (persona = provenance `said_by`,
> integer-rank priority, deterministic openers, corroboration seam deferred to P9).

**Goal:** Generate each persona's next **Session Brief** just-in-time from the latest graph —
ranked open threads + a persona summary. Guidance, not a script (`02 §5, §10`).

**Depends on:** P3 (gaps/threads). **Package:** `brain`, `contracts`.

## Steps
1. **Gather inputs** (`planner.py`): for a persona, pull (a) its coverage gaps (P3), (b)
   unverified handoffs, (c) flagged conflicts, (d) newly-surfaced threads it raised in free
   narration but didn't finish.
2. **Add cross-persona corroboration** threads (verify the other side of a discovered handoff;
   reconcile a conflict) — the seam P9 deepens.
3. **Prioritize** by impact + recency; cap to a sensible number; rest → `reserve_threads`.
4. **Write each thread:** `goal`, `why`, `priority`, a `suggested_opener`, and likely conditional
   `followups` (a small LLM call may draft these — scaffolding, not rails).
5. **Persona summary:** a short evolving synopsis from the persona's subgraph.
6. **Emit a Session Brief** validated against `contracts/session-brief.schema.json`. On an empty
   brain, emit `cold_start: true` with no threads (only generic openers).
7. **Cold-start openers** list lives in a constant the runner also knows.

## Files
`brain/src/warp_compass_brain/planner.py` (+ brief serialization mirroring the schema)

## Test plan
- Empty graph → `cold_start: true`, zero threads, schema-valid.
- Seeded gaps → threads ordered by priority, each with opener + why; output validates against the
  JSON schema.
- A discovered one-sided handoff → a corroboration thread targeting the other persona appears.

## Done when
For any persona the planner emits a schema-valid, ranked, persona-scoped brief that a runner can
consume; cross-pollination falls out automatically because briefs are generated against the
shared graph.
