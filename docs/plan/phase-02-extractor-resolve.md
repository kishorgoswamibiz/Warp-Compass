# Phase 2 — Extractor + resolve-or-create + create gate

> **Status:** ✅ DONE (agent:opus-setup, 2026-06-28). `ruff` clean; 22 tests pass with an
> in-memory graph + scripted LLM; **live `cli ingest` verified** — real nodes created in Neo4j
> using `deepseek-v4-pro`. (The LIVE model `deepseek-v4-flash` is first exercised in P5.)

**Goal:** Turn a raw answer into graph nodes/edges **without the LLM ever inventing and committing
in one step**. The LLM *proposes*; deterministic rules *dispose*. This is the anti-hallucination
spine (`02 §7`).

## What was built (deviations from the brief below noted)
- `llm/` — `LLMProvider` ABC + `DeepSeekProvider` (OpenAI-compatible, JSON mode, retry/backoff).
- `extractor.py` — constrained to the ontology; **parses node-by-node and drops invalid items**
  instead of failing the whole answer (pydantic enum validation would otherwise reject all).
- `vectorindex/` — `LocalVectorIndex` (portable sqlite brute-force cosine, no native extension) +
  `FastEmbedEmbedder` (ONNX, lazy/optional) with a zero-dep `HashingEmbedder` fallback.
- `resolve.py` — alias+vector retrieval (type-filtered; category is a soft signal, not a hard
  filter, to protect recall) + closed-choice adjudicator with a match_id validity guard.
- `create_gate.py` — similarity ceiling, vocab check, **auto-assigns a default category** when the
  LLM left it empty (so good nodes aren't quarantined for a missing tag), min-completeness, quarantine.
- `ingest.py` — orchestrator; merge absorbs aliases + raises confidence to `confirmed` on a 2nd
  persona. `queues.py`, `slugs.py`, `cli.py` (`check-models`/`extract`/`ingest`).

**Depends on:** P1 (`GraphStore`, ontology, models). **Package:** `brain`.

## Pipeline to implement
`raw answer → extract candidates (LLM) → retrieve candidates → adjudicate (LLM, closed choice)
→ {same: merge | conflict: flag | new: create gate} → persist + provenance`

## Steps
1. **`LLMProvider` seam** (`brain/.../llm/base.py` + `deepseek.py`): OpenAI-compatible client,
   `v4-pro` for batch; retry + exponential backoff honoring `Retry-After`; strict-JSON helper.
   Confirm current model IDs (DECISION #7).
2. **Extractor** (`extractor.py`): prompt from `02 §12`; input = an Answer Log entry + the allowed
   types; output = candidate nodes (type, canonical_name, description, suggested category_codes,
   key_attributes) + relations. Constrained to the ontology; empty list if nothing fits.
3. **VectorIndex concrete impl** (`vectorindex/sqlite_vec.py`): local `sentence-transformers`
   embeddings (DECISION #11) + sqlite-vec (brute-force cosine fallback). Wire `add`/`search`.
4. **Candidate retrieval** (`resolve.py`): combine `GraphStore.find_by_alias` + vector `search`,
   filtered to **same type + overlapping category**. Top-K cards to the adjudicator.
5. **Adjudicator** (LLM, closed choice, `02 §12`): returns `{verdict: same|conflict|new,
   match_id, reason}`; to say "new" it must justify why each candidate doesn't fit.
6. **Create gate** (`create_gate.py`, deterministic): **similarity ceiling** (overrule "new" if
   closest score ≥ threshold → route to merge/review); **vocabulary check** (type ∈ ontology;
   category ∈ registry, else → pending-taxonomy queue); **min completeness** (name+desc+type+≥1
   category). Failures → **quarantine** (not discarded).
7. **Persist:** mint slug (`ontology.slug_prefix` + kebab of name, ensure unique), commit node +
   edges via `GraphStore`, append provenance, set initial confidence status.
8. **Queues:** simple JSON/sqlite stores for quarantine + pending-taxonomy (BA review later).

## Files
`brain/src/warp_compass_brain/{llm/,extractor.py,resolve.py,create_gate.py,vectorindex/sqlite_vec.py,queues.py}`

## Test plan
- Unit: extractor returns valid candidates on a sample answer (mock LLM); create gate rejects
  unknown type/code, enforces similarity ceiling and min-completeness, routes to quarantine.
- Integration (`-m neo4j`): ingest two paraphrased answers about the same approval → **one** node
  with merged aliases + two provenance records (dedup works).
- A conflicting pair → node flagged `conflicting`, follow-up queued.

## Done when
Pasting a short transcript produces a clean, deduped subgraph with provenance; no node is created
that fails the gate; `ruff` + tests green.
