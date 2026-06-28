# Phase 8 — Sync bus + participant registry + daily cycle

## Context Card — read THIS, skip the source
- **Data shapes (authoritative):** `contracts/answer-log.schema.json` (Runner→Brain; has both
  `participant_id` AND `persona_id` — prototype maps them 1:1) and `contracts/session-brief.schema.json`
  (Brain→Runner). Read the schemas, NOT the TS/pydantic mirrors.
- **Bus root already exists in config:** `Settings.bus_root: str = "./_bus"` @ `brain/.../config.py:56`
  (so a `FolderBus` defaults there). Other paths on `Settings`: `vector_db_path`, `quarantine_path`,
  `pending_taxonomy_path`, `planner_max_threads` — all `./_state/*`, git-ignored.
- **Ingest one answer:** `Ingestor.ingest_answer(answer: str, *, persona_id: str, session_id: str, ts: str) -> IngestSummary`
  @ `brain/.../ingest.py:61`. Provenance `said_by = persona_id` is set here — *this is what registers a persona*.
- **Reuse the wiring, don't rebuild it:** `_build_ingestor(settings) -> (graph, ingestor)` @
  `brain/.../cli.py:64` (connects Neo4j + DeepSeek + vector index). The existing **file consumer** is
  `cmd_ingest_log` @ `cli.py:107` — reads a log JSON, loops `entries[].raw_answer` through
  `ingest_answer`. `run-round` should loop the bus over this same pattern (new CLI command preferred
  over shelling out per file, so one Neo4j/DeepSeek connection is reused per round).
- **Planner (read-only):** `Planner(graph, ontology, *, max_threads=6, now=None)` @ `planner.py:91`;
  `.personas() -> list[str]` @ `:107` returns **every distinct provenance `said_by`** — i.e. the
  registry-from-the-graph is *already* derivable; `.plan(persona_id, *, session_id=...) -> SessionBrief`
  @ `:113`; `.plan_all(*, session_id=...) -> list[SessionBrief]` @ `:160`. `SessionBrief.to_dict()`
  is the contract-shaped dict to write into `briefs/`.
- **⚠️ No `Persona` node type exists (ADR #17).** A persona = its provenance `said_by`; ingesting a
  log auto-"registers" it. Step 3's "create its persona node" means: ensure `participants/{id}/profile.json`
  + the **participant→persona mapping** (prototype: `persona_id == participant_id`). **Do NOT invent a
  `:Persona` node** — that violates the ontology-constraint rule (AGENTS.md); if you truly need one,
  add it to `contracts/ontology.json` deliberately and bump the contract.
- **Resumability:** the graph is idempotent on re-ingest (merge by id), but to avoid re-running DeepSeek
  on already-ingested logs, track processed log filenames per participant (e.g. a `profile.json`
  `ingested_logs` list or a marker file) — that's the cheap resume key.
- **Run:** `uv` from `brain/` (Neo4j Desktop Started); `npm` from `pwa/`. Ingest **consistently** with
  OR without `--extra vectors` (mixed embedder dims corrupt `_state/vectors.sqlite` — see Blockers).
- **New deps?** Folder bus is stdlib (`pathlib`, `json`) — no new packages expected.

**Goal:** Wire the manual, free shared-folder bus and the auto-onboarding registry so **any number
of users** can be added anytime, and one batch round flows collect → process → distribute
(`02 §3.2, §3.4, §14`).

**Depends on:** P4 + P5. **Package:** `scripts`, `pwa`, `brain`.

## Bus layout (the folder IS the user registry)
```
/discovery-engagement/participants/{participant_id}/
  profile.json   answer_logs/   briefs/
```

## Steps
1. **`Bus` seam** (`brain/.../bus/base.py` + `folder.py`): list participants, read new answer
   logs, write briefs, read/write `profile.json`. Shared-folder impl now; sync endpoint later.
2. **PWA onboarding** (`pwa`): first launch mints `participant_id` (UUID or entered name), creates
   `participants/{id}/` with empty `answer_logs/`+`briefs/` and `profile.json`. Export writes the
   Answer Log to `answer_logs/`; import reads the latest brief from `briefs/`.
3. **Registry enumeration** (`brain`): on each run, enumerate `participants/*`, register any new
   id (create its persona node, 1:1), ingest every new Answer Log into the one graph.
4. **`run-round` orchestrator** (`scripts/run-round.sh` → calls a `brain` CLI): enumerate+register
   → ingest (P2) → completeness/conflict (P3/P9) → plan + write per-persona briefs (P4) →
   distribute. **Resumable** so a transient DeepSeek failure doesn't lose the round.
5. **Sequencing discipline:** one round per day; document operator steps (`scripts/README.md`).

## Files
`brain/src/warp_compass_brain/{bus/,cli.py}`, `scripts/run-round.sh`, `pwa/src/sync/*`.

## Test plan
- Drop two participants' logs in a temp bus → one `run-round` registers both, updates the single
  graph, and writes one persona-scoped brief each into their `briefs/`.
- Adding a brand-new participant folder → picked up automatically next run (no config).
- Kill mid-run → re-run resumes without duplicating nodes.

## Done when
The full daily cycle works for N users via the shared folder, new users self-onboard, and each
persona receives only its own brief.
