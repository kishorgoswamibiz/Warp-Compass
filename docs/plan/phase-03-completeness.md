# Phase 3 — Completeness ("satisfaction") engine

> **Status: ✅ DONE (2026-06-28, `agent:opus-p3`).** Implemented in
> `brain/src/warp_compass_brain/{completeness.py,threads.py}` on two new `GraphStore` bulk reads
> (`nodes_by_type`, `edges`); 10 tests + live `cli completeness --threads`. See ADR #16 and the
> PROGRESS handoff log for the modelling choices (notably the `next_handoff` endpoint exemption
> and the structural two-sided-handoff proxy).

**Goal:** Measure understanding against the ontology (not a vibe), and turn every gap into an
open thread. Two scores: per-persona and org-wide (`02 §9`).

**Depends on:** P2 (a populated graph). **Package:** `brain`.

## Steps
1. **Per-Activity coverage** (`completeness.py`): for each `Activity`, check the ontology
   completeness fields — trigger (`Event TRIGGERS`), inputs/outputs (`CONSUMES`/`PRODUCES`),
   system (`USES`), next handoff (`HANDS_OFF_TO`), exceptions, governing rules (`GOVERNED_BY`).
   Each missing field → a typed **gap**. Implement as Cypher via `GraphStore.query`.
2. **Per-persona score:** fraction of a role's activities that are fully described.
3. **Org-wide score:** all handoffs verified from **both** sides, all conflicts resolved, **and
   the end-to-end chain unbroken** (every step connects first-trigger → final-output, no dangling
   handoffs). End-to-end connectivity is a first-class check — a broken chain is a real defect.
4. **Gap → thread objects** (`threads.py`): each gap becomes a candidate open thread with a goal,
   a `why`, and a priority seed (impact + recency). These feed the Planner (P4).
5. **Satisfaction signal:** when both scores are high and the thread list is empty, report
   "satisfied" (BA can override). Thresholds are tunable (DECISION: open).

## Files
`brain/src/warp_compass_brain/{completeness.py,threads.py}`

## Test plan
- Seed a graph where one Activity lacks a trigger + a handoff → exactly those two gaps surface.
- A handoff present from only one side → org-wide score penalized; a corroboration thread emitted.
- A fully-described, fully-connected toy org → "satisfied".

## Done when
Coverage gaps are detected deterministically from the graph and rendered as prioritized threads;
the end-to-end-chain check flags broken links rather than silently bridging them.
