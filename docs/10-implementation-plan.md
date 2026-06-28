# Warp Compass — Master Implementation Plan

> The build roadmap. *What* and *why* live in `00`–`02`; this is the *sequenced how-to-build*.
> Each phase below has a one-paragraph charter and acceptance criteria; the full step-by-step
> brief is in `docs/plan/phase-NN-*.md`. Live status is in `../PROGRESS.md`.

## Principles that shape the order (from `02 §16`)

Build the **brain on typed text first** — voice and sync are layers added once the intelligence
works. Get extraction/resolution/completeness right on plain text; it de-risks everything. Wire
every external dependency behind its interface from day one so vendor and transport swaps stay cheap.

## Phase map & dependencies

```
P1 ─► P2 ─► P3 ─► P4 ─► P5 ─► P6 ─► P7
                 │           ▲
                 ├─► P9      │
                 └────────► P8 (needs P4+P5)
P2 ─► P10 (richer after P9)
```

| Phase | Charter (one line) | Depends on | Package |
|-------|--------------------|------------|---------|
| **1. Ontology + GraphStore** ✅ | Controlled vocabulary + Neo4j store behind `GraphStore`. | — | `brain`, `contracts` |
| **2. Extractor + resolve/create-gate** | Raw answer → candidates → adjudicate → create gate → graph. The anti-hallucination spine. | P1 | `brain` |
| **3. Completeness engine** | Score each Activity vs the ontology; emit gap threads + per-persona/org scores. | P2 | `brain` |
| **4. Planner → Session Brief** | Turn gaps/conflicts/new-threads into a ranked, persona-scoped brief. | P3 | `brain`, `contracts` |
| **5. Live runner (typed)** | Consume a brief, converse over text: openers, redirect, reconcile, one-probe, free narration. Writes Answer Log. | P4 | `pwa` (logic; text only) |
| **6. PWA shell + host + proxy** | Wrap the runner in the installable app; Cloudflare Pages host; Worker key proxy. | P5 | `pwa`, `worker` |
| **7. Voice** | ElevenLabs STT/TTS through the proxy, behind `STTProvider`/`TTSProvider`. | P6 | `pwa`, `worker` |
| **8. Sync bus + registry** | Export/import via shared folder; participant registry; the daily batch cycle for any N users. | P4, P5 | `scripts`, `pwa`, `brain` |
| **9. Cross-persona corroboration + conflicts** | Verify handoffs from both sides; surface cross-persona conflicts as future threads. | P2, P3, P4 | `brain` |
| **10. Documentation generator** | Traverse the graph → end-to-end process (headline) + per-level SOPs + problem register. | P2 (richer after P9) | `brain` |
| *Later* | Streaming STT · networked v1 · persona auto-merge · markdown-wiki projection. | — | — |

## Global acceptance (the prototype is "done enough" when)

- A handful of people can each install the PWA from a link, do a ~45-min voice session, and
  export an Answer Log without the operator touching their device.
- One batch round ingests **all** logs into a single Neo4j graph, raises completeness, verifies
  at least one handoff from both sides, and writes each persona a sharper Session Brief.
- The generator emits **one connected end-to-end process** + per-level SOPs + a problem register,
  rendering `confirmed` knowledge by default, every statement traceable to a source.
- Re-running the pipeline over stored Answer Logs rebuilds the graph with no re-interviewing.

## Cross-cutting requirements (apply to every phase)

- **Cost guard:** only DeepSeek + ElevenLabs may be paid. Embeddings run locally.
- **Resumability:** the batch run must survive a transient DeepSeek 429/outage without losing a
  round (retry + backoff honoring `Retry-After`; checkpoint progress).
- **Provenance + confidence on every fact**; docs render `confirmed`-only by default.
- **Swap seams stay thin:** `GraphStore`, `VectorIndex`, `STTProvider`, `TTSProvider`,
  `LLMProvider`, `Bus`.

## Verifying Phase 1 (done) end-to-end

```bash
cd brain && uv sync && uv run ruff check . && uv run pytest -m "not neo4j"   # green
docker compose up -d && cp .env.example .env && uv run pytest                # incl. neo4j round-trip
# Neo4j Browser http://localhost:7474 shows the test Role/Activity + PERFORMS edge.
```
