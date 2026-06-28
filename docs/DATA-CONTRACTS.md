# Warp Compass — Data Contracts

The machine-readable source of truth lives in `../contracts/` (JSON Schemas + `ontology.json`).
The Python brain mirrors these in `brain/src/warp_compass_brain/models.py`; the TS planes will
share them too. **If you change a contract, bump its version and flag it loudly in `PROGRESS.md`.**

## 1. The ontology (the completeness compass) — `contracts/ontology.json`

Not a list of questions — the internal definition of "what a complete picture looks like". The
LLM may only ever **choose from** these; anything new goes to a review queue.

**Node types (10):** `Role`, `Activity`, `System`, `Artifact`, `Event`, `ApprovalPoint`, `Rule`,
`Problem`, `Desire`, `KPI`.

**Edge types (12):** `PERFORMS` (Role→Activity), `USES` (Activity→System), `PRODUCES`,
`CONSUMES` (Activity↔Artifact), `TRIGGERS` (Event→Activity), `REQUIRES_APPROVAL_FROM`
(Activity→Role), `HANDS_OFF_TO` (Activity→Role), `ESCALATES_TO` (Role→Role), `GOVERNED_BY`
(Activity→Rule), `BLOCKS` (Problem→Activity), `MEASURED_BY` (Activity→KPI), `REPORTS_TO` (Role→Role).

**Completeness fields** (per node type) drive the gap detector in Phase 3 — e.g. an `Activity` is
"complete" when its trigger, inputs, system, output, next handoff, exceptions, and rules are known.

**Taxonomy registry:** governed hierarchical **category codes** (e.g. `05`, `05.1`) used as a
many-to-many tag — these become the **section numbering of the final document** (Phase 10).

## 2. Identity vs Type vs Category — three different jobs (§6.3)

A graph is not a tree, so one hierarchical code can't do all three. We separate:

- **Identity** — a stable, never-reused slug: `role.sales-manager`, `appr.discount-over-10pct`.
- **Type** — a fixed enum from the ontology.
- **Category code** — a governed, many-to-many tag from the taxonomy registry.

This keeps a Role a *single reusable node* that many approvals/escalations point to via edges —
no duplicate-role sprawl.

## 3. Node card — `contracts/node-card.schema.json`

The compact canonical record every node carries; what gets embedded and what the adjudicator
LLM reads when deciding "same or new". Key fields: `id`, `type`, `canonical_name`, **`aliases`**
(the dedup superpower), `description`, `category_codes`, `key_attributes`, `provenance[]`.

## 4. Confidence lifecycle (§6.5)

Status only rises with evidence:
`proposed → unverified (one source) → confirmed (corroborated by another persona/BA) → conflicting`.
The doc generator renders **`confirmed` only** by default — truth rises, noise stagnates.

## 5. Answer Log (runner → brain) — `contracts/answer-log.schema.json`

Immutable, append-only, **source of truth**. One file per session, one persona per session (no
diarization). Each entry: `thread_id` (or null for free narration), `kind` (`guided` |
`free_narration`), `agent_utterance`, **`raw_answer`** (verbatim — permanent), optional
`audio_ptr`, `ts`. The runner only ever writes this.

## 6. Session Brief (brain → runner) — `contracts/session-brief.schema.json`

The persona-scoped memory view + **ranked open threads**. **Guidance, not a script** — the runner
may reword and deviate. Each thread: `goal`, `why`, `priority`, `suggested_opener`, conditional
`followups`. On `cold_start: true` (empty brain) there are **no threads** — only generic openers.

## Versioning

Each schema carries a `schema_version` (start `1.0.0`). Backward-incompatible changes bump major;
because the graph is re-derivable, an extractor/ontology improvement just means re-running the
pipeline over stored Answer Logs — no re-interviewing.
