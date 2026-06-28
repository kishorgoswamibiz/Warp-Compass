# PROGRESS — Warp Compass build board

> **This file is the single source of truth for build state.** Any agent (human or AI)
> picks up work here. **Read this top-to-bottom before doing anything**, then follow the
> protocol in [`AGENTS.md`](./AGENTS.md): claim a task → do it → update its row → append a
> handoff-log entry. The **Handoff log** at the bottom is append-only — never delete history,
> so no context is ever lost.

---

## Status snapshot

- **Phase:** **ALL 10 BUILD PHASES DONE** (P0–P10). The brain is feature-complete: ingest spine →
  completeness → Planner → live runner → PWA + key-proxy → voice (code) → sync cycle → connected
  cross-persona brain → **documentation generator (P10 DONE, live-verified vs Neo4j)**. The only
  remaining work is **owner actions** (no code blocked): **P7 (voice)** is code-complete in REVIEW
  pending the **STT eval gate** + a **plan-permitted ElevenLabs voice** (live TTS returned 402 — see
  Blockers); **P6 deploy** needs Cloudflare auth (`wrangler deploy` + Pages).
- **Overall:** ▰▰▰▰▰▰▰▰▰▰ ~100% of the build spine (P0–P10). Remaining = owner-only deploy + voice-gate
  actions; nothing in the queue is code-blocked.
- **Last updated:** 2026-06-29 · by `agent:opus-p10`
- **Verified:** brain `ruff` clean + `pytest -m "not neo4j"` **62 passed** / 3 neo4j skipped (**+7
  P10:** docgen E2E/SOP/register/filter/traceability); PWA `npm run typecheck` clean + **18 vitest**;
  **`npm run build` = installable PWA**; Worker typecheck clean. **P10 live-verified vs the real
  P2–P9 Neo4j graph:** `cli docgen --include-unverified` produced the full deliverable (Mermaid
  flowchart with status classes + sourced walkthrough + taxonomy-numbered category map + per-role SOPs);
  **default `cli docgen` hid the 10 unverified activities** (with a note) yet **still surfaced the
  conflicting event** and rendered the **corroborated "Employee" role as `confirmed`** (persona.demo +
  p_alice) — proving the P9 confidence promotion flows through to the docs.
- **Next up:** **No build phases remain.** Owner actions only: (a) **P7** — run the STT eval gate
  (`node scripts/stt-eval.mjs <dir>` from `pwa/`) + set a usable `ELEVENLABS_VOICE_ID` (or upgrade the
  plan), flipping P7 REVIEW → DONE; (b) **P6** — `wrangler deploy` + connect Cloudflare Pages to
  `pwa/dist` (needs CF auth). See the prioritized queue below.

## ▶ Resume here (start every session with this)

1. Open **Neo4j Desktop** → **Start** the local DB (data persists across restarts).
2. In a terminal, **`cd "C:\Users\Lenovo\Desktop\Warp Compass\brain"`** — uv/Python commands ONLY
   work from this folder (running elsewhere gives `No module named 'warp_compass_brain'`).
3. Sanity check: `uv run pytest -m "not neo4j" -q` → expect **62 passed**.
4. **All build phases (P0–P10) are DONE.** What remains is **owner actions** only (P7 voice gate +
   voice id; P6 Cloudflare deploy) — see *Next up*. To regenerate the deliverable: `uv run python -m
   warp_compass_brain.cli docgen [--include-unverified] [--out FILE]`. Keys are in `brain/.env`.
- **Build environment:** Python 3.12 + uv (`brain/`), Node 20 + npm (`pwa/`, `worker/`),
  **Neo4j Desktop** for the local graph (no Docker — runs only on the laptop). Verify steps in
  each package README and in `docs/10-implementation-plan.md`.

---

## Task board

Status legend: `TODO` · `IN-PROGRESS` · `BLOCKED` · `REVIEW` · `DONE`.
One row per build-order phase (full briefs in `docs/plan/`). Sub-tasks live in each phase doc.

| ID | Phase | Task | Status | Owner | Artifacts | Updated |
|----|-------|------|--------|-------|-----------|---------|
| P0 | 0 | Repo scaffold, contracts, docs, coordination board | DONE | agent:opus-setup | `contracts/`, `brain/`, `pwa/`, `worker/`, `docs/` | 2026-06-28 |
| P1 | 1 | Ontology + `GraphStore` (Neo4j) | DONE | agent:opus-setup | `contracts/ontology.json`, `brain/src/warp_compass_brain/{models,ontology,graphstore}` | 2026-06-28 |
| P2 | 2 | Extractor + resolve-or-create + create gate | DONE | agent:opus-setup | `brain/.../{llm,extractor,resolve,create_gate,ingest,queues,slugs,vectorindex,cli}.py` · 22 tests + live ingest verified | 2026-06-28 |
| P3 | 3 | Completeness ("satisfaction") engine + open threads | DONE | agent:opus-p3 | `brain/.../{completeness,threads}.py` + `GraphStore.{nodes_by_type,edges}` · 10 tests · live `cli completeness` | 2026-06-28 |
| P4 | 4 | Planner → per-persona Session Brief | DONE | agent:opus-p4 | `brain/.../planner.py` + `threads.threads_from_gaps` · 6 tests (schema-validated) · live `cli plan` | 2026-06-28 |
| P5 | 5 | Live runner (typed) consuming the brief | DONE | agent:opus-p5 | `pwa/src/runner/*` (runner/session/answerlog/prompts/llm/validate/harness) · 6 tests · live `v4-flash` session + `cli ingest-log` loop closed | 2026-06-28 |
| P6 | 6 | PWA shell + Cloudflare Pages host + Worker proxy | DONE | agent:opus-p6 | `worker/src/index.ts` (`/llm`) · `pwa/src/{App.tsx,screens/SessionScreen.tsx}` · `scripts/gen-icons.mjs` · dev proxy · live-verified (deploy = owner) | 2026-06-28 |
| P7 | 7 | Voice — ElevenLabs STT/TTS via the proxy | REVIEW | agent:opus-p7 | `worker/src/index.ts` (`/stt`,`/tts`) · `pwa/src/voice/*` · `SessionScreen` mic+TTS · `pwa/scripts/stt-eval.mjs` · seam/guard-verified (eval gate + paid ElevenLabs voice = owner) | 2026-06-29 |
| P8 | 8 | Sync bus + participant registry + daily cycle | DONE | agent:opus-p8 | `brain/.../bus/*` + `cycle.py` + `cli run-round` · `scripts/run-round.{sh,ps1}` · `pwa/src/sync/*` · 7 brain + 6 pwa tests · live full cycle vs Neo4j | 2026-06-29 |
| P9 | 9 | Cross-persona corroboration + conflict threads | DONE | agent:opus-p9 | `brain/.../crosspersona.py` + planner integration + `cli corroborate` · 10 tests · live-verified vs Neo4j | 2026-06-29 |
| P10 | 10 | Documentation generator (E2E process + SOPs + problems) | DONE | agent:opus-p10 | `brain/.../docgen/{traverse,render}.py` + `cli docgen` · 7 tests · live-verified vs Neo4j | 2026-06-29 |

**Dependency spine:** P1→P2→P3→P4→P5→P6→P7; P8 needs P4+P5; P9 needs P2+P3+P4; P10 needs P2 (richer after P9).

---

## Active / claimed (avoid collisions)

_Nobody is actively working right now._ When you start, add a line:
`- P<id> · agent:<your-id> · since <date> · <one-line of what you're doing>`

---

## Blockers & open questions

- ✅ **RESOLVED — DeepSeek key.** Both `DEEPSEEK_API_KEY` and `ELEVENLABS_API_KEY` are set in
  `brain/.env` and working (live ingest succeeded).
- ✅ **RESOLVED — model IDs (both tiers).** `deepseek-v4-pro` (batch) and **`deepseek-v4-flash`
  (LIVE)** are both confirmed working: `cli check-models` lists both, and P5 ran a full live typed
  session on `v4-flash`. No fallback needed.
- ⚠️ **`brain/_state/vectors.sqlite` has mixed-dimension vectors** (256-dim hashing + 384-dim
  fastembed from runs that mixed embedder modes), so `ingest` against the existing store throws a
  matmul shape error. **Pick ONE embedder mode and stick with it** (run ingest *consistently* with
  or without `--extra vectors`); if it's already mixed, delete `brain/_state/vectors.sqlite` and
  re-ingest (the Neo4j graph and the raw Answer Logs are untouched — vectors are re-derivable).
- ⚠️ **Batch extractor (`v4-pro`) occasionally returns an empty/non-JSON completion** and the brain
  does **not** retry that specific case (the SDK retries HTTP errors, not an empty 200 body). It's
  transient — re-running usually succeeds. A small retry-on-empty in `DeepSeekProvider` would harden
  batch ingest (out of P5 scope; noted for a brain hardening pass).
- **Embeddings (optional, recommended).** Best semantic dedup needs `uv sync --extra vectors`
  (fastembed). Without it the pipeline uses a deterministic hashing fallback (lexical only) —
  works, weaker recall. Run ingest with `uv run --extra vectors ...` to use embeddings.
- ⚠️ **ElevenLabs account is on a plan that blocks library voices via the API (owner action).**
  Live `/tts` returned **`402 paid_plan_required`**: *"Free users cannot use library voices via the
  API."* The Worker forwarder is correct (it injected the key, reached ElevenLabs, and passed the
  upstream error straight through) — this is purely an account/voice-policy gate. **Fix:** either set
  `ELEVENLABS_VOICE_ID` (in `worker/wrangler.toml`) to a voice the plan permits (a premade/default or
  your own generated/cloned voice), or upgrade the plan. Then re-run the `/tts` smoke test to confirm
  audio bytes come back. The **same key likely gates STT** the same way — confirm during the eval.
- **STT eval not yet done (owner action).** Before flipping P7 → DONE, validate ElevenLabs Scribe on
  ~20 real, messy recordings (Indian-accented English, noise, SKUs/CRM jargon). A zero-dep harness is
  ready: from `pwa/`, `node scripts/stt-eval.mjs <dir-of-recordings>` (put a same-named `.txt` next to
  each clip for a WER; it reads the key from `worker/.dev.vars`). **Record the aggregate WER here.**
- **PWA icons** are placeholders (`pwa` manifest references missing `icon-192/512.png`).
- ⚠️ **Semantic batch conflict detection is deferred (P9 boundary, ADR #23).** P9 *routes* conflicts
  (gate-flagged `CONFLICTING` nodes → reconciliation threads to every contributor) and verifies
  handoffs bidirectionally, but does **not** newly detect *contradictory accounts of an already-merged
  node*. Reason: merge keeps **one** canonical card (absorbs aliases + appends provenance; it does not
  retain each persona's competing description/`key_attributes`), so there's nothing to compare two
  accounts *from*. To add it later: retain per-persona claims (e.g. snapshot the candidate's
  description/key_attributes onto each provenance entry at ingest), then a batch LLM/structural pass can
  flag semantic disagreement. Exact-match contradictions are still caught at ingest by the create gate.

---

## Next up (prioritized queue)

_All build phases (P0–P10) are DONE._ Only owner actions remain:

1. **P7 owner actions (flip REVIEW → DONE):** (a) run the **STT eval gate** — `node
   scripts/stt-eval.mjs <dir>` from `pwa/` over ~20 real messy recordings; record the WER in
   Blockers. (b) Set a **usable `ELEVENLABS_VOICE_ID`** (or upgrade the plan) so `/tts` returns audio,
   then confirm a spoken turn end-to-end on a phone.
2. **P6 owner action:** `wrangler deploy` the Worker + connect Cloudflare Pages to `pwa/dist`; set
   `ALLOWED_ORIGIN` to the Pages URL and `wrangler secret put DEEPSEEK_API_KEY` +
   `wrangler secret put ELEVENLABS_API_KEY`.

---

## Handoff log (append-only · newest on top)

Each entry: `### <date> · agent:<id>` then **Did / Next / Gotchas**. Never edit past entries.

### 2026-06-29 · agent:opus-p10 — Phase 10 (Documentation generator); P10 → DONE · **BUILD COMPLETE**
- **Did:** Built the deliverable generator — the graph turned into living, traceable docs. New
  `brain/.../docgen/` package: **`traverse.py`** (`DocGenerator(graph, ontology,
  include_unverified=False).generate() -> GeneratedDocs`) walks a one-shot snapshot into
  render-agnostic models for (1) the **end-to-end process** (a Mermaid `flowchart` model + an ordered,
  topologically-sorted **narrative**, with gaps surfaced), (2) **per-role SOPs** (each activity's
  trigger/inputs/systems/outputs/handoffs/approvals/rules/exceptions/KPIs), and (3) a **problem
  register** (each `Problem` + its `BLOCKS` activity, frequency/impact/cause from `key_attributes`, and
  linked `Desire`s); **`render.py`** (`render_markdown(docs)`) emits Markdown + Mermaid with status
  classes. **Reuse, no drift:** extracted **`activity_flow(ids, snap)`** into `completeness.py` so the
  P3 chain check and the P10 traversal share one flow builder, and docgen consumes
  `CompletenessEngine.assess()` for the authoritative gap/unbroken verdict. **Confidence:** status read
  off **provenance** (no `NodeCard.status`); default renders `confirmed` + always `conflicting`
  (never hides a known conflict), `--include-unverified` adds the rest marked; gaps scoped to shown
  nodes so a hidden node can't leak. **Section numbering** from the taxonomy via new
  `Ontology.category_label()`/`categories_sorted()`. New **`cli docgen [--include-unverified]
  [--out FILE]`**. **Verified:** `ruff` clean + **62 pytest** (+7 docgen: connected-chain, taxonomy
  numbering, broken-handoff-surfaced, confidence filter, conflict-always-shown, traceability, problem
  register). **LIVE vs the real P2–P9 Neo4j graph:** `--include-unverified` produced the full
  deliverable (flowchart + sourced walkthrough + category map + SOPs); **default mode hid the 10
  unverified activities** (with a note) yet **still surfaced the conflicting event** and rendered the
  **corroborated `Employee` role as `confirmed`** (persona.demo + p_alice) — proving P9's promotion
  flows through. ADRs #24, #25.
- **Next:** **No build phases remain — the build spine (P0–P10) is complete.** Remaining work is
  **owner actions only** (not code-blocked): **P7** voice gate (STT eval + a plan-permitted
  `ELEVENLABS_VOICE_ID`) → flips P7 REVIEW → DONE; **P6** Cloudflare deploy (`wrangler deploy` + Pages).
- **Gotchas:** (1) **`activity_flow` is now the single source of truth for "what continues to what"**
  (`completeness.py`); `_chain_analysis` calls it. If you change continuation semantics, both the
  completeness chain check AND the docs move together — re-run `test_completeness` + `test_docgen`.
  (2) **Confidence is provenance-only** — there is no `NodeCard.status`; `effective_status()` is
  conflicting>confirmed>unverified>proposed. Default docs hide unverified but **always show conflicts**
  (the P9 ethos). Run `cli corroborate --apply` first if you want more nodes promoted to `confirmed`
  before generating. (3) **Self-loops are dropped in the diagram/narrative only** (a generic role like
  "Employee" hands off to itself in the real graph) — `activity_flow` itself is unchanged so P3 scoring
  is untouched; don't "fix" it by editing `activity_flow`. (4) **Desire↔Problem has no ontology edge**
  (only `Problem -[BLOCKS]-> Activity`); the register links a Desire via its
  `key_attributes["relates_to_problem"]`, else lists it as an orphan "wished-for outcome" (ADR #25).
  (5) `traverse` resolves section labels so `render` is ontology-free; keep new renderers (Word/PDF)
  behind the same `GeneratedDocs` models. (6) Live docs written to scratch during verification (not the
  repo). Run uv from `brain/`, Neo4j Started.

### 2026-06-29 · agent:opus-p9 — Phase 9 (Cross-persona corroboration + conflict threads); P9 → DONE
- **Did:** Made the brain *connected* — handoffs verified from both sides, conflicts routed to everyone
  involved instead of averaged away. New `brain/.../crosspersona.py` (`CrossPersonaEngine`, read-only
  except `corroborate()`): over a one-shot snapshot (reuses `completeness.load_snapshot`) it (1)
  classifies every `HANDS_OFF_TO` edge as **confirmed** / **route_receiver** / **route_discoverer** —
  "confirmed" = the receiving role performs an activity that CONSUMES an artifact the giving activity
  PRODUCES (artifact linkage = the real bidirectional signal, upgrading P3's structural proxy); (2)
  routes a `handoff_confirm` thread to the **receiving persona** when the receiver is active but hasn't
  linked the flow, falling back to a `handoff_trace` thread on the **discoverer** when the receiver
  isn't interviewed yet; (3) routes a `cross_conflict` reconciliation thread to **every** persona that
  contributed to a `CONFLICTING` node; (4) `corroborate()` writes evidence-based promotions
  (≥2-persona non-conflicting node → `confirmed` via `upsert_node`; both-sided handoff **edge** →
  `confirmed` via idempotent re-`add_edge`). **Planner integration** (`planner.py`): drops
  `ONE_SIDED_HANDOFF`/`UNRESOLVED_CONFLICT` gaps from its own gap pass and pulls
  `CrossPersonaEngine.threads_for_persona(persona)` instead (cross threads outrank gap threads), with
  openers/followups for the 3 new kinds; planner stays **read-only**. New **`cli corroborate
  [--apply]`** (read-only verdicts by default; `--apply` writes promotions). Made
  `FakeGraphStore.add_edge` idempotent (merge on the (type,from,to) triple) to match Neo4j. **Verified:**
  `ruff` clean + **55 pytest** (+10: 9 `test_crosspersona` covering the full handoff matrix + conflict
  routing + promotion + no-false-conflict-on-paraphrase, +1 planner receiver-routing test). **LIVE vs
  the real P2–P8 Neo4j graph:** `cli corroborate` → `enter-order-into-crm→warehouse` **confirmed**,
  `escalate-order→manager` **route_receiver**, `evt.customer-order-received-by-email` **conflict**;
  `--apply` promoted the confirmed handoff edge; `cli plan` brief now leads **#1 cross_conflict, #2
  handoff_confirm**, gap threads after. ADRs #22, #23.
- **Next:** **P10 — Documentation generator** (`docs/plan/phase-10-doc-generator.md`, Context Card
  written). Deps P2 DONE. Reuse `load_snapshot` + P3's `_chain_analysis` flow; render
  `confirmed`-by-default with provenance traceability; show broken links, don't bridge them.
- **Gotchas:** (1) **A persona *owns* a role iff it contributed that role's activities** (provenance on
  the performed activities), NOT by appearing on the Role node — mentioning a role ≠ being it. This is
  the linchpin of receiver-routing; don't "simplify" it to said_by-on-the-role-node (that re-breaks the
  existing one-sided test, where persona.A merely *mentions* the warehouse role). (2) **Confidence lives
  on provenance, never a `NodeCard.status` field** — there is no such field; filter on provenance
  `status`. Neo4j's denormalized `n.status`/`r.status` are write-only (never read back by
  `get_node`/`edges`), so I confirm handoff edges by flipping the **edge provenance** and re-`add_edge`
  (idempotent MERGE overwrites `r.provenance`) — **no `set_edge_status` seam was added** (none needed,
  none has a reader). (3) **`crosspersona` now owns handoff + conflict threads in the Planner**; the
  matching gaps still exist in `completeness`/`cli completeness` for scoring — that's intentional, not a
  duplicate. If you add a new handoff/conflict thread kind, wire its opener in `planner._opener_and_followups`.
  (4) **Semantic batch conflict detection is deferred (ADR #23 + Blockers)** — the data model keeps one
  canonical card per node, so there's no per-persona text to compare; P9 routes gate-flagged conflicts,
  it doesn't newly detect contradictory accounts of a merged node. (5) `corroborate()` and `assess()`
  share `_valid_handoff` guards so the read and write views never disagree on the handoff set. (6) My
  live `--apply` flipped one handoff edge's provenance to `confirmed` in the **owner's dev Neo4j graph**
  (same harmless, re-derivable pattern as prior live tests). (7) Run uv from `brain/`, Neo4j Started.

### 2026-06-29 · agent:opus-p8 — Phase 8 (Sync bus + participant registry + daily cycle); P8 → DONE
- **Did:** Wired the manual shared-folder bus and the auto-onboarding registry so **any number of
  users** flow through one batch round (collect → register → ingest → plan → distribute). **Brain:**
  new `bus/` package — `Bus` ABC (`base.py`) + `FolderBus` (`folder.py`, tolerant reads / atomic
  writes over `participants/{id}/{profile.json, answer_logs/, briefs/}`); `cycle.py` with
  `RoundRunner` (dependency-injected ingestor + planner, so the cycle logic is testable without
  Neo4j/network) — enumerates the bus (**the folder IS the registry**), auto-mints `profile.json` for
  any new participant, ingests only **new** Answer Logs (tracked in `profile.ingested_logs` → resume),
  re-plans, and writes each persona's brief into its folder. New CLI `run-round [--bus] [--session]`
  reuses `_build_ingestor`. **scripts:** `run-round.sh` + `run-round.ps1` now drive the CLI; updated
  `scripts/README.md`. **PWA:** `src/sync/` — `participant.ts` (STABLE participant id in localStorage,
  persona 1:1, injectable storage) replacing P6's per-session random UUID; `bus.ts` (Answer-Log
  filename convention + `downloadAnswerLog` + `parseBriefFile`); wired into `SessionScreen` (stable
  ids, bus-named download) and `App.tsx` (shows the participant, **imports a brief** from the bus to
  cross-pollinate the next session). **Verified:** brain `ruff` clean + **45 pytest** (+7: 4 bus, 3
  cycle); PWA typecheck + **18 vitest** (+6 sync) + `npm run build` installable. **LIVE vs Neo4j:**
  `run-round` over a scratch bus auto-registered `p_alice`, ingested its log (4 created / 1 merged / 5
  edges, real DeepSeek), wrote a per-persona brief to each folder; a **re-run ingested 0** (resume
  confirmed; `profile.json` lists `ingested_logs`). ADR #21.
- **Next:** **P9 — Cross-persona corroboration + conflict threads** (`docs/plan/phase-09-cross-persona-conflict.md`,
  Context Card written). Deps P2+P3+P4 DONE.
- **Gotchas:** (1) **Persona = provenance `said_by`; persona 1:1 with participant** (ADR #17). The
  registry is the folder; ingesting a log registers the persona. There is **no `:Persona` node** —
  don't add one without bumping the ontology contract. (2) **Brief routing fallback:** a graph persona
  with no originating bus participant (e.g. `persona.demo`, created by manual `cli ingest` in earlier
  phases) gets a best-effort folder `participants/{persona_id}/briefs/`. Benign — in the real flow
  `persona_id == participant_id` so routing is identity; only legacy/manually-seeded personas create
  these. (3) **Resume key = `profile.ingested_logs`**, persisted after *each* log so a mid-round crash
  never re-ingests (and re-ingest is idempotent anyway — the graph merges by id). (4) **Use a fresh
  `VECTOR_DB_PATH`** for live ingest to dodge the pre-existing mixed-dim `_state/vectors.sqlite`
  blocker (I set it to a scratch file). (5) My live test added `p_alice`'s nodes to the **owner's dev
  Neo4j graph** (same pattern as P2/P5 live verifications) — harmless and re-derivable; delete that
  persona's nodes if you want a pristine graph. (6) The round does register→ingest→plan→distribute;
  the explicit **completeness/conflict** sub-step in the brief is folded into planning today (the
  Planner derives threads from gaps) — the standalone **conflict pass is P9**. (7) PWA can't write the
  shared folder directly; export = download + the operator drops the file into `answer_logs/` (manual
  stand-in, DECISION #8). Run uv from `brain/`, Neo4j Started.

### 2026-06-29 · agent:opus-p7 — Phase 7 (Voice: ElevenLabs STT/TTS via the proxy); P7 → REVIEW
- **Did:** Built the voice leg behind provider seams, all routed through the Worker (keys never in the
  browser). **Worker** (`worker/src/index.ts`): implemented `/stt` (browser POSTs the **raw audio
  blob**; the Worker wraps it in the multipart form ElevenLabs Scribe expects, injects
  `ELEVENLABS_API_KEY` + `ELEVENLABS_STT_MODEL`, returns `{text}`) and `/tts` (`{text}` in → inject
  key + `ELEVENLABS_VOICE_ID`/`ELEVENLABS_TTS_MODEL` → audio bytes out), mirroring `handleLlm` and
  passing upstream errors straight through with CORS. Added the four `ELEVENLABS_*` `[vars]` to
  `wrangler.toml`. **PWA** (`pwa/src/voice/`): `types.ts` (`STTProvider`/`TTSProvider`/`VoiceError`),
  `stt.ts` (`WorkerSTTProvider`), `tts.ts` (`WorkerTTSProvider` + `playAudioBlob` + dev-only
  `BrowserTTSProvider`), `mic.ts` (`MicRecorder` over `MediaRecorder` + `isMicAvailable`), barrel
  `index.ts`. **Wired into `SessionScreen`:** tap-to-talk mic (record → `/stt` → feeds the existing
  `runner.respond`), spoken replies via `/tts` (dev: Web Speech), a voice on/off toggle, and the
  **typed fallback fully intact**. Added an STT **eval-gate harness** `pwa/scripts/stt-eval.mjs`
  (zero-dep WER over a folder of recordings). **Verified:** PWA `npm run typecheck` clean +
  **12 vitest** (6 new voice) + `npm run build` installable; Worker typecheck clean; **live vs
  `wrangler dev`:** `/health` 200 (p7), `/tts` reached ElevenLabs with the key injected and returned
  the real upstream body (`402 paid_plan_required` — see Gotchas), guard paths 400/405/204 all
  correct. ADR #20.
- **Next:** **P8 — Sync bus + participant registry + daily cycle** (`docs/plan/phase-08-sync-registry.md`,
  Context Card written). Independently, the **owner** finishes P7: run the STT eval gate and set a
  usable `ELEVENLABS_VOICE_ID` (or upgrade the plan), then P7 REVIEW → DONE.
- **Gotchas:** (1) **Live TTS/STT audio is NOT yet confirmed** — the account returns `402
  paid_plan_required` ("Free users cannot use library voices via the API"). The forwarder is correct
  (auth + endpoint + shape all worked; a bad key would be 401). Fix = a plan-permitted
  `ELEVENLABS_VOICE_ID` or an upgrade, then re-smoke `/tts`. The same key probably gates Scribe too —
  confirm during the eval. (2) **STT eval gate is mandatory before DONE** — vendor numbers use clean
  audio; field audio (Indian-accented, noisy, SKUs) must be measured. Harness ready (see Blockers).
  (3) **`audio_ptr` stays `null`** — no blob store yet; the transcript is the truth, a recording
  pointer waits for P8 storage. (4) **Ship `WorkerSTT/TTSProvider`**; `BrowserTTSProvider` is dev-only
  (picked via `import.meta.env.DEV`) so iterating doesn't burn credits. (5) Browser sends audio as a
  **raw body** (not multipart) so the only CORS header is `Content-Type` — the Worker builds the
  multipart form; don't "fix" this by multiparting in the browser. (6) Added `vite/client` to
  `tsconfig` `types` so `import.meta.env` typechecks. (7) Worker dev on :8787; stop stale
  `wrangler`/`workerd` if a port lingers.

### 2026-06-28 · agent:opus-p6 — Phase 6 (PWA shell + Worker `/llm` proxy); P6 → DONE + **context-economy process**
- **Did (P6):** Wrapped the P5 runner in the installable app and routed live calls through the key
  proxy. **Worker** (`worker/src/index.ts`): implemented the `/llm` DeepSeek forwarder — injects
  `DEEPSEEK_API_KEY` + model (new `DEEPSEEK_MODEL_LIVE` var, `deepseek-v4-flash`), forwards to
  `${DEEPSEEK_BASE_URL}/chat/completions`, passes the OpenAI-shaped body straight back, CORS via
  `ALLOWED_ORIGIN`; `/stt`+`/tts` stay 501 (P7). Added `worker/.dev.vars.example`. **PWA**: replaced
  the placeholder `App.tsx` with a landing→session flow and built `pwa/src/screens/SessionScreen.tsx`
  — a themed chat UI that drives `Runner` via **`WorkerLLMProvider`** (relative `/llm`, so **no key
  in the browser**), cold-starts, supports pause/resume + graceful close, and downloads the Answer
  Log on close (manual hand-off until the P8 sync bus). Added a Vite **dev proxy** `/llm,/stt,/tts →
  :8787`. Generated **real PWA icons** with a zero-dep PNG encoder (`pwa/scripts/gen-icons.mjs` →
  `public/icon-{192,512}.png` + `favicon.svg`). **Verified:** PWA typecheck + 6 tests + `npm run
  build` (installable: manifest + SW + precached icons); worker typecheck; live `/health` 200 and
  `/llm` → real `v4-flash` completion; **full seam `Runner→Worker→DeepSeek` run end-to-end**. ADR #19.
- **Did (process — applies to ALL future agents):** Added a **Context economy** section to
  `AGENTS.md` (rules: each phase brief opens with a verbatim-signature **Context Card**; point at
  `contracts/` not code mirrors; ration `Explore` agents; restrict search to `*/src`+`contracts`+
  `docs`; docs = pointers not re-narrated code; never trim the handoff log). Wired it into the loop
  (steps 4 + 7: read the Card first; **write the next phase's Card at handoff**). Backfilled Context
  Cards on the **P6 and P7** briefs. *Reason:* P5 pickup cost ~120k tokens, almost all of it
  re-deriving exact code shapes from source — the Card moves those shapes into the doc so pickup
  drops to a target ~30–50k. This does **not** compromise dev: cards are pointers + signatures, so
  they don't drift or duplicate source.
- **Next:** **P7 — Voice** (`docs/plan/phase-07-voice.md`, has a Context Card). **Run the STT eval
  gate first.** Implement Worker `/stt`+`/tts` (mirror `handleLlm`), `pwa/src/voice/{stt,tts}.ts`
  seams, mic capture into `SessionScreen`. Or do the **P6 deploy owner-action** (`wrangler deploy` +
  Pages, needs Cloudflare auth).
- **Gotchas:** (1) **Ship only `WorkerLLMProvider`** in the browser; `DirectDeepSeekProvider` is the
  Node-harness verifier (keys-in-Worker rule). (2) Relative `/llm` works in dev (Vite proxy → :8787)
  AND prod (same origin as the Pages-hosted Worker) — don't hardcode a host. (3) Local Worker secrets
  live in `worker/.dev.vars` (git-ignored `**/.dev.vars`); I created it from `brain/.env` for the
  live test. (4) `wrangler dev` runs on :8787; if a stale one lingers, stop `wrangler`/`workerd`
  processes. (5) Deploy is the only unfinished P6 item — it needs the owner's Cloudflare account.
  (6) Icons are regenerable via `node scripts/gen-icons.mjs` if the brand mark changes.

### 2026-06-28 · agent:opus-p5 — Phase 5 (live runner, typed text-only); P5 → DONE
- **Did:** Built the **live interaction plane as text-first** in `pwa/src/runner/` — it consumes a
  Session Brief, converses over *session context only*, and writes an Answer Log. It holds **no
  graph** (§4.1). Modules: `types.ts` (TS mirror of the brief + answer-log contracts, the per-turn
  `LiveDecision`, and the `LLMProvider` seam), `prompts.ts` (the `v4-flash` live prompt per §12 +
  `COLD_START_OPENERS` mirrored from `planner.py`), `session.ts` (in-memory brief + transcript +
  thread cursor + covered/probed sets), `runner.ts` (turn loop: classify → choose action → emit →
  log; deterministic cold-start opener + thread advancement; the **one-probe rule enforced in code**
  — "LLM proposes, rules dispose"), `answerlog.ts` (contract-shaped builder), `validate.ts`
  (Node-only ajv validation vs `contracts/answer-log.schema.json`), and three providers under
  `llm/`: `FakeLLMProvider` (scripted, tests), `DirectDeepSeekProvider` (Node fetch → DeepSeek;
  **verification harness only**), `WorkerLLMProvider` (the **production seam** the PWA uses — POSTs
  to the Worker `/llm`, keys never in the browser). Plus `harness.ts` (typed console/scripted
  driver) and `index.ts` (browser-safe public API for P6). Added vitest + tsx + ajv to `pwa`
  (scripts `test`, `session`; `vitest.config.ts`; `node` in tsconfig types). On the **brain** side
  added one small consumer of the answer-log contract: `cli ingest-log <path>` (reads a log file,
  feeds each `raw_answer` through the existing `ingest_answer` pipeline). **`npm run typecheck`
  clean + 6 vitest tests pass; brain `ruff` clean + 38 pytest pass.** **LIVE-verified:** confirmed
  `deepseek-v4-flash` via `cli check-models`, ran a full typed session on it (cold-start opener,
  vague→one probe, tangent→redirect, graceful close) → **schema-valid Answer Log**, then closed the
  loop: `cli ingest-log` re-derived the graph (2 created, **5 merged into the existing P2–P4
  graph**, 6 edges). Decisions: `docs/DECISIONS.md` #18.
- **Next:** **P6 — PWA shell + host + Worker proxy** (`docs/plan/phase-06-pwa-host-proxy.md`).
  Implement the Worker **`/llm` forwarder** (inject `DEEPSEEK_API_KEY`, forward to DeepSeek, return
  the OpenAI-shaped body) — `WorkerLLMProvider` already targets it. Build the UI shell that drives
  `Runner` (replace `harness.ts`); add a Vite dev proxy `/llm` → `localhost:8787`.
- **Gotchas:** (1) **Two providers by design:** the shipped PWA must use `WorkerLLMProvider`
  (keys-in-Worker rule, ADR #8); `DirectDeepSeekProvider` reads the key locally and is **only** for
  the laptop verification harness — never import it into the browser app. (2) The **one-probe rule
  lives in `runner.ts`**, not the prompt — the model may *ask* to probe twice but the guard covers
  the thread and advances; preserve this (it's the testable "exactly one probe" behavior). (3)
  Answer-log entry semantics: a drifted (tangent) answer is logged `free_narration`/`thread_id:null`;
  a cold-start answer is `guided` with `thread_id:null` (no thread yet) — both schema-valid. (4)
  **Vector-store dim mismatch & batch empty-completion** bit the loop-closer (see Blockers) — they're
  pre-existing brain/_state issues, **not** P5; I verified ingest on a fresh scratch `VECTOR_DB_PATH`
  to avoid mutating the owner's `_state`. The batch `v4-pro` extractor is slow (~reasoning) so a
  5-entry ingest can exceed a 3-min timeout; ingest fewer entries or raise the timeout. (5) Run uv
  from `brain/`; Neo4j Desktop Started; `npm` commands from `pwa/`.

### 2026-06-28 · agent:opus-p4 — Phase 4 (Planner → Session Brief); P4 → DONE
- **Did:** Built the Planner that emits each persona's next **Session Brief** just-in-time from the
  live graph. New `brain/src/warp_compass_brain/planner.py`: `Planner.plan(persona_id, session_id)`
  → `SessionBrief` (cold_start handling, persona summary, ranked `open_threads` with integer rank +
  `suggested_opener` + conditional `followups`, overflow → `reserve_threads`); `plan_all()` for one
  brief per contributing persona; `personas()`; and a shared `COLD_START_OPENERS` constant the P5
  runner will also use. Refactored `threads.py` to expose `threads_from_gaps(gaps)` (Planner scopes
  to one persona's gaps) and to name the receiving role in corroboration copy; added
  `other_role_id/name` to `Gap`/`OpenThread`. Added `planner_max_threads` setting and a `cli plan
  [--persona] [--session]` command. **Persona scoping = provenance `said_by` membership** (a
  persona's subgraph = nodes it contributed to); cross-pollination falls out because briefs read
  the shared graph. Added `jsonschema` (dev) to validate briefs against
  `contracts/session-brief.schema.json`. **`ruff` clean; 38 passed / 3 neo4j skipped** (6 new,
  schema-validated). **Live-verified:** `cli plan` produced a real schema-shaped brief for
  `persona.demo` (3 activities, ranked threads, openers/followups). Also confirmed the P3
  `notifications_min_severity="OFF"` fix silences the Neo4j label warnings (DB was up this time).
  Decisions: `docs/DECISIONS.md` #17.
- **Next:** **P5 — Live runner (typed)** (`docs/plan/phase-05-live-runner-typed.md`). It consumes a
  `SessionBrief` (+ `COLD_START_OPENERS` on an empty brain) and is the **first use of the LIVE model
  `deepseek-v4-flash`** — run `cli check-models` to confirm that id first.
- **Gotchas:** (1) Brief `priority` is an **integer rank** (1 = pull first), per the schema — not
  the float impact score from P3; the Planner converts by sorted rank. (2) "Newly-surfaced
  free-narration threads" (brief step 1d) aren't parsed from Answer Logs — they're already encoded
  as gaps on the nodes the persona just created, and surface via the recency term. (3) Cross-persona
  corroboration here is the basic seam: a one-sided handoff shows up in the *discoverer's* brief
  naming the receiving role; routing it to the receiver's brief is **P9**. (4) `BriefThread`/
  `SessionBrief` are the schema-facing shape — don't add fields not in
  `session-brief.schema.json` (it's `additionalProperties: false`); internal routing data lives on
  `OpenThread`/`Gap` instead. (5) Run uv from `brain/`, Neo4j Desktop Started.

### 2026-06-28 · agent:opus-p3 — Phase 3 (completeness + thread engine); P3 → DONE
- **Did:** Built the completeness ("satisfaction") engine and the gap→thread generator.
  New: `brain/src/warp_compass_brain/completeness.py` (`CompletenessEngine.assess()` → per-Activity
  field coverage vs the ontology's `completeness_fields`, per-persona scores = fraction of a role's
  activities fully described, and an org score folding **handoff coverage + conflict resolution +
  end-to-end chain connectivity**, plus a `satisfied` verdict) and `threads.py`
  (`build_threads()` → prioritized `OpenThread`s with goal/why and an impact+recency priority seed).
  Extended `GraphStore` with two bulk reads — `nodes_by_type` + `edges` — implemented in
  `Neo4jGraphStore` (Cypher) and the test `FakeGraphStore` (renamed its internal edge list to
  `_edges` to free the method name). Added `Ontology.completeness_fields()`, two
  `*_satisfied_threshold` settings, and a `cli completeness [--threads]` command. The engine reads
  a one-shot in-memory snapshot, so all scoring is pure/deterministic and DB-free in tests.
  **`ruff` clean; 32 passed / 3 neo4j skipped** (10 new). **Live-verified:** `cli completeness
  --threads` ran against the real P2 graph (scored Employee/Manager personas, surfaced 18 gaps,
  emitted correctly-ranked threads). Decisions in `docs/DECISIONS.md` #16.
- **Next:** **P4 — Planner / Session Brief** (`docs/plan/phase-04-planner-briefs.md`). It consumes
  `build_threads(report)`: group threads by `role_id`, prioritize, write each persona's brief.
- **Gotchas:** (1) **`next_handoff` is satisfied by a HANDS_OFF_TO edge OR a final-output**
  (an artifact no activity consumes) — a terminal step isn't a gap. (2) "Both-sided handoff" is a
  **structural proxy** (receiving role performs ≥1 activity) until persona→role mapping exists.
  (3) Conflicts are detected from a node's *provenance* statuses (a `CONFLICTING` entry), matching
  how Phase-2 ingest flags them. (4) `Neo4jGraphStore.connect()` now sets
  `notifications_min_severity="OFF"` to silence "label does not exist" warnings when bulk-reading
  ontology types with no instances yet — driver accepted it; re-running with the DB up should show
  clean output (the DB stopped right after my successful live run, so this cosmetic bit is the one
  thing not re-confirmed visually). (5) Run uv from `brain/`, Neo4j Desktop must be Started.

### 2026-06-28 · agent:opus-setup — Phase 2 LIVE-VERIFIED; P2 → DONE
- **Did:** Owner saved the API keys and ran `cli ingest` for real — nodes were created in Neo4j
  (confirmed in Neo4j Browser). This used the default batch model **`deepseek-v4-pro`**, so that
  ID is valid for the account. Flipped P2 REVIEW → DONE; cleared the key/model-ID blockers;
  updated `docs/DECISIONS.md` (#15) and the phase-02 brief. Both keys (`DEEPSEEK_API_KEY`,
  `ELEVENLABS_API_KEY`) are set in `brain/.env`.
- **Next:** **P3 — Completeness engine** (`docs/plan/phase-03-completeness.md`). Nothing blocks it.
- **Gotchas:** (1) **Run uv/Python from `brain/`** — owner hit `No module named 'warp_compass_brain'`
  by running from `C:\Users\Lenovo`. `uv run` discovers the project only inside `brain/`. (2)
  `deepseek-v4-flash` (LIVE model) is NOT yet exercised — first used in P5; classic fallback
  `deepseek-chat` via `.env` if it 404s. (3) Add `--extra vectors` to `uv run` for semantic
  embeddings; otherwise the hashing fallback is used (works, weaker dedup). (4) Don't paste my
  example `...` literally — it's a placeholder for a real sentence.

### 2026-06-28 · agent:opus-setup — Phase 2 (extract → resolve → create-gate → persist)
- **Did:** Built the anti-hallucination ingest spine. New in `brain/src/warp_compass_brain/`:
  `llm/` (`LLMProvider` ABC + `DeepSeekProvider`, OpenAI-compatible, JSON mode, retry/backoff),
  `extractor.py` (constrained to ontology; parses node-by-node, drops invalid, never fails the
  whole answer), `vectorindex/` (`LocalVectorIndex` = portable sqlite brute-force cosine +
  `FastEmbedEmbedder` with a zero-dep `HashingEmbedder` fallback), `resolve.py` (alias+vector
  retrieval filtered by type; closed-choice adjudicator with a match_id guard), `create_gate.py`
  (similarity ceiling, vocab check, default-category assignment, min-completeness, quarantine),
  `queues.py` (quarantine + pending-taxonomy JSONL), `slugs.py`, `ingest.py` (orchestrator:
  nodes→ref map→relations; merge absorbs aliases + raises confidence to `confirmed` on a 2nd
  persona), `cli.py` (`check-models`, `extract`, `ingest`). Added `CandidateNode/Relation/
  ExtractionResult` to `models.py`; config fields (model IDs, similarity ceiling, top-k,
  embeddings, queue paths); deps `openai`+`numpy` (main), `fastembed` (extra `vectors`).
  Tests: `test_extractor/_create_gate/_resolve/_ingest.py` with an in-memory `FakeGraphStore` +
  scripted `FakeLLM` (in `tests/conftest.py`). **`ruff` clean; 22 passed / 3 neo4j skipped.**
- **Next:** Owner finishes live verification (save key → `check-models` → live `ingest`), then
  flip P2 to DONE. Then **P3 — Completeness engine** (`docs/plan/phase-03-completeness.md`):
  score each Activity vs ontology completeness fields via `GraphStore.query` Cypher, emit gap
  threads + per-persona/org scores incl. the unbroken end-to-end-chain check.
- **Gotchas:** (1) DeepSeek model IDs `v4-pro`/`v4-flash` are UNCONFIRMED — `check-models` reveals
  the truth; classic fallback `deepseek-reasoner`/`deepseek-chat` via `.env`. (2) Without
  `--extra vectors`, dedup uses the lexical hashing embedder (works, weaker recall) — install
  fastembed for semantic matching. (3) Extractor `_sanitize` was replaced by per-item parsing
  because pydantic enum validation otherwise rejects a whole answer on one bad node type.
  (4) Tests import fakes via `from conftest import ...` (pytest puts tests/ on sys.path) — not a
  relative import. (5) `cli ingest` writes vectors to `brain/_state/` and queues to `_state/*.jsonl`
  (gitignored).

### 2026-06-28 · agent:opus-setup
- **Did:** Bootstrapped the project from the three design docs. Created the monorepo
  (`brain/`, `pwa/`, `worker/`, `contracts/`, `scripts/`, `docs/`); the language-neutral
  **contracts** (`ontology.json`, answer-log / session-brief / node-card JSON Schemas);
  **Phase-1 code** — pydantic models, ontology loader/validator, `GraphStore` ABC +
  `Neo4jGraphStore`, `VectorIndex` ABC (interface only), config, `docker-compose.yml` (Neo4j
  Community), and tests (`test_ontology.py` no-DB; `test_graphstore.py` marked `neo4j`).
  Scaffolded the React+Vite+TS PWA (theme + placeholder screen + manifest) and the Cloudflare
  Worker key-proxy stub (`/health` works; `/llm`,`/stt`,`/tts` → 501). Wrote all planning docs
  and this board.
- **Next:** P2. Implement the extractor (DeepSeek `v4-pro`, JSON-only, constrained to the
  ontology), candidate retrieval (alias + vector + same-type/category), the closed-choice
  adjudicator, and the deterministic **create gate** (similarity ceiling, vocabulary check,
  min-completeness, quarantine). Wire the `VectorIndex` concrete impl (sentence-transformers +
  sqlite-vec) here. Follow `docs/plan/phase-02-extractor-resolve.md`.
- **Gotchas:** (1) The graph is **re-derivable** from the raw Answer Log — keep raw logs
  immutable; never hand-edit the graph. (2) Honor the plane contract: the runner only *writes*
  Answer Logs, the brain only *reads* them; the phone never touches the graph. (3) Local
  embeddings (not a cloud API) keep the cost model intact — only DeepSeek + ElevenLabs are paid.
  (4) Run `uv run pytest -m "not neo4j"` for fast feedback without Docker.
- **Environment caveats (this machine, 2026-06-28):** `uv` was **not installed**, so verification
  used a plain `python -m venv .venv` + `pip` (Python 3.13.7). uv remains the intended tool —
  `uv sync` should just work once installed; the pip-venv is a stopgap.

### 2026-06-28 · agent:opus-setup — graph DB = Neo4j Desktop (no Docker)
- **Did:** Owner has no Docker and wants a light, prototype-friendly setup. Decided the local
  graph runs on **Neo4j Desktop** (DECISION #13). Updated `brain/README.md` (added a Neo4j Desktop
  setup section), `brain/.env.example` (`NEO4J_PASSWORD=change-me`), root `README.md`, and the
  build-environment line above. `docker-compose.yml` stays as an optional alternative.
- **Next:** Owner to install Neo4j Desktop, create + Start a local DB, set `NEO4J_PASSWORD` in
  `brain/.env`, then run `uv run pytest` (or `.venv` python) to exercise the 3 live GraphStore
  tests. Until then the fast suite (`-m "not neo4j"`) is the green bar.
- **Gotchas:** Neo4j Desktop = data persists on disk across restarts; you just press **Start**
  after a reboot (the process stops, the data doesn't). Connection defaults (`bolt://localhost:7687`,
  user `neo4j`) already match `config.py`; only the password needs setting. Neo4j is laptop-only —
  end users never install anything, just the PWA.
