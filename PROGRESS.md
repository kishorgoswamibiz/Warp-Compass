# PROGRESS — Warp Compass build board

> **This file is the single source of truth for build state.** Any agent (human or AI)
> picks up work here. **Read this top-to-bottom before doing anything**, then follow the
> protocol in [`AGENTS.md`](./AGENTS.md): claim a task → do it → update its row → append a
> handoff-log entry. The **Handoff log** at the bottom is append-only — never delete history,
> so no context is ever lost.

---

## Status snapshot

- **Phase:** **P0–P14 DONE · P15a DONE · P15b/P15c TODO.** Feature-complete + deployed: ingest spine → completeness →
  Planner → live runner → PWA + key-proxy → **voice (live TTS+STT, Starter plan)** → sync cycle →
  connected cross-persona brain → documentation generator → **P11 automatic Google Drive sync** →
  **P12 OKF Markdown graph store (Neo4j REMOVED — no database server at all)** → **P13 declared
  identity + participant lifecycle** → **P14 Drive-backed-bus hardening**. The graph is a folder of
  readable Markdown files, now on **local disk** (`GRAPH_ROOT=brain/_graph`) rather than inside the
  Drive folder; people declare name + role once and are never asked again; folders and provenance
  name people, not UUIDs; and a person can be retired without the graph being touched.
  **P15a** adds the governed role registry: onboarding is a **multi-select of 10 canonical roles**,
  and their spoken synonyms ("the PM" → Delivery Specialist) are seeded into the graph so mentions
  resolve onto one node instead of forking. **Nothing is blocked.**
- **⚠ THE INTERVIEW IS STILL DAY-ANCHORED.** P15a shipped the identity half of P15; the half the
  owner actually asked for — interviewing by the **lifecycle stage** rather than the clock — is
  **P15b and has not started**. `contracts/ontology.json` still has no `Stage`/`Objective` node and
  no `PRECEDES`/`PART_OF` edge, and both copies of `COLD_START_OPENERS` still say *"map your day from
  the very beginning"*. Until P15b lands, a live session still produces the noise the owner reported
  (*"as a BA I start my day checking my mails, but checking mail is not my job role"*).
- **✅ Operator prerequisite (P14) — DONE 2026-08-03.** The Drive bus folder is **Available offline**
  (screenshot: `docs/images/drive-folder-available-offline.png`). The owner ran a green round and
  deleted the `G:\My Drive\warp-compass\graph` fallback copy; `brain/_graph` is now the only graph.
  `cli list-participants`, which hung >6 min on 2026-07-28, now returns instantly — the stream-only
  symptom is gone. See `brain/README.md` → "When the bus is on Google Drive".
- **⚠ ONE REAL GAP OPEN:** the **live Apps Script Web App is still the P11 version** — P13's
  `Code.gs` changes were committed but never deployed, so Drive `profile.json` files get no
  `role_title` and no per-folder `README.md`. Owner action, see Blockers.
- **Overall:** P0–P14 complete + deployed + sync live; **P15 is ~1/3 in** (P15a of P15a→b→c).
- **Last updated:** 04 Aug 2026 · by `agent:opus-p15a`
- **Verified (04 Aug 2026, P15a):** brain `ruff` clean + `pytest` **152 passed** (25 in the new
  `test_roles.py`, 3 new dual-hat tests in `test_crosspersona.py`); PWA `typecheck` +
  `typecheck:functions` clean + **61 vitest** (7 new `roles.test.ts`). **`cli seed-roles` run live
  against the real graph** — created 10 Role nodes in `brain/_graph/roles/`, then re-run to prove
  idempotency (`unchanged: 10`); spot-checked `role.delivery-specialist.md` carries `keywords:
  [Project Manager, PM, DS, Delivery Manager]` and `said_by: registry`. Embedder mode chosen and
  used: **`--extra vectors`** (fastembed 0.8.0, 384-dim).
- **Verified (2026-08-03):** brain `ruff` clean + `pytest` **124 passed**; PWA `typecheck` +
  `typecheck:functions` clean + **45 vitest** + `npm run build` installable; `cli list-participants`
  live against the Drive bus returns both participants **with roles** in under a second.
- **Verified (P14):** brain `ruff` clean + `pytest` **113 passed** (13 new `test_fsretry.py`, which
  injects `WinError 1450` rather than needing a real Drive mount); `cli completeness` re-run against
  the migrated local bundle returns the same 8 roles / 12 activities, so the move lost nothing.
- **Verified (P13):** brain `ruff` clean + `pytest` **100 passed** (the WHOLE suite — no DB/marker
  split anymore); PWA `npm run typecheck` clean + **45 vitest** + `npm run build` green; worker
  `typecheck` clean; the three new CLI commands smoke-tested against a scratch bus (dry-run,
  real run, and the refuse-without-`--yes` guard). Previously: `import neo4j` fails in the brain env
  (dependency really gone). **ElevenLabs Starter plan live-verified** (P11, unchanged): TTS→STT
  round-trip exact; Pages Functions `/tts` `/stt` `/llm` live. Deploy story unchanged: one
  git-connected Cloudflare Pages project (`pwa/` + `pwa/functions/`), `worker/` optional standalone.
- **Next up:** **P15b** — the interview rewrite (ontology `Stage`/`Objective`/`cadence`, Stage+Role
  completeness scoring, the lifecycle prompt rewrite in **both** prompt copies, the probe budget).
  Brief: `docs/plan/phase-15-lifecycle-and-alignment.md` §5–§8. **One owner action first: redeploy
  the Apps Script Web App** (see Blockers — it's still the P11 version, so `role_titles` cannot reach
  Drive). Otherwise operate it: `cli run-round` per round (Answer Logs arrive automatically via
  Drive sync), `cli docgen` for the deliverable. New in P13: `cli list-participants`,
  `cli retire-participant --id X`, `cli reset-engagement --yes`.
  **Before handing the app to a wider team**, run the clean-slate procedure in
  `OPERATOR-MANUAL.md` §1d. (`deliverable.md` was regenerated from the real graph on 2026-08-03 —
  the old `persona.demo`/`p_alice` test data is gone.)
- **Prompt tuning:** every prompt in the system is indexed with clickable line links in
  **`PROMPTS.md`** (repo root) — start there rather than grepping.

## ▶ Resume here (start every session with this)

1. In a terminal, **`cd "C:\Users\Lenovo\Desktop\Warp Compass\brain"`** — uv/Python commands ONLY
   work from this folder (running elsewhere gives `No module named 'warp_compass_brain'`).
2. Sanity check: `uv run pytest -q` → expect **113 passed** (no database needed — P12).
3. **All build phases (P0–P13) are DONE.** Operating routine is `OPERATOR-MANUAL.md`. To regenerate
   the deliverable: `uv run python -m warp_compass_brain.cli docgen [--include-unverified]
   [--out FILE]`. Keys are in `brain/.env`.
- **Build environment:** Python 3.12 + uv (`brain/`), Node 20 + npm (`pwa/`, `worker/`).
  **No database server** — the graph is an OKF Markdown bundle at `GRAPH_ROOT` (P14: local disk,
  `brain/_graph`; see `docs/plan/phase-12-okf-store.md`). Verify steps in each package README and in
  `docs/10-implementation-plan.md`.

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
| P7 | 7 | Voice — ElevenLabs STT/TTS via the proxy | DONE | agent:opus-p7 | `pwa/functions/_shared.ts` (`/stt`,`/tts`) · `pwa/src/voice/*` · `SessionScreen` mic+TTS · `pwa/scripts/stt-eval.mjs` · **live TTS+STT 200 on Starter plan** (field-WER eval = recommended QA) | 2026-06-29 |
| P8 | 8 | Sync bus + participant registry + daily cycle | DONE | agent:opus-p8 | `brain/.../bus/*` + `cycle.py` + `cli run-round` · `scripts/run-round.{sh,ps1}` · `pwa/src/sync/*` · 7 brain + 6 pwa tests · live full cycle vs Neo4j | 2026-06-29 |
| P9 | 9 | Cross-persona corroboration + conflict threads | DONE | agent:opus-p9 | `brain/.../crosspersona.py` + planner integration + `cli corroborate` · 10 tests · live-verified vs Neo4j | 2026-06-29 |
| P10 | 10 | Documentation generator (E2E process + SOPs + problems) | DONE | agent:opus-p10 | `brain/.../docgen/{traverse,render}.py` + `cli docgen` · 7 tests · live-verified vs Neo4j | 2026-06-29 |
| P11 | 11 | Automatic Google Drive sync (kill manual export/import) | DONE | agent:opus-p11 | `apps-script/*` · `pwa/functions/{_sync.ts,sync/*}` · `pwa/src/sync/remote.ts` (+6 tests) · auto push/pull wired · **owner Google setup DONE + tested end-to-end** (runbook in phase-11 doc) | 2026-07-01 |
| P12 | 12 | OKF Markdown graph store — Neo4j removed; interviewer refocused on end-to-end SOP | DONE | agent:fable-p12 | `brain/.../graphstore/okf_store.py` (replaces `neo4j_store.py`) · `config.graph_root` · `scripts/migrate_neo4j_to_okf.py` · prompts (`prompts.ts`, `planner.py`, `extractor.py`) · 72 tests all-green no-DB · ADR #28 · `docs/plan/phase-12-okf-store.md` · `OKF-vs-Neo4j-report.md` | 2026-07-02 |

| P13 | 13 | Declared identity (name+role once) + participant lifecycle (retire / reset) | DONE | agent:opus-p13 | `pwa/src/sync/participant.ts` · `pwa/src/screens/OnboardingCard.tsx` · `pwa/src/runner/{prompts,session,runner,answerlog}.ts` · `apps-script/Code.gs` (README.md + `role_title`) · `brain/.../lifecycle.py` · `bus/{base,folder}.py` retirement · `cycle.py` Finding 1 · `planner.py` orphan pool · `docgen/render.py` names · 3 new CLI commands · 99 brain + 45 pwa tests · ADRs #29/#30 · `docs/plan/phase-13-identity-and-lifecycle.md` | 2026-07-28 |

| P14 | 14 | Survive a Google-Drive-backed bus: graph moved to local disk + FS retry | DONE | agent:opus-p14 | `brain/.../fsretry.py` (new) · `bus/folder.py` + `graphstore/okf_store.py` all I/O retried · `config.py` `fs_retry_*` · `GRAPH_ROOT` now local (`brain/_graph`) · 13 new tests (113 total) · `brain/README.md` "When the bus is on Google Drive" · `DEPLOY.md` | 2026-07-28 |

| P15a | 15 | Role registry (10 roles + aliases) + multi-select onboarding + `seed-roles` | DONE | agent:opus-p15a | `contracts/roles.json` (new) · `brain/.../roles.py` + `cli seed-roles` (new) · `pwa/src/sync/roles.ts` + parity test (new) · `OnboardingCard.tsx` role chips · `participant.ts` `role_titles[]` + derived `role_title` mirror · `extractor.py` `KNOWN ROLES` block · `ingest.py` + `crosspersona.py` exclude `said_by:registry` from corroboration (R3) · `crosspersona.py`/`planner.py` dual-hat self-handoff copy (`KIND_HANDOFF_SELF`) · `Code.gs` + `_sync.ts` + `remote.ts` `role_titles` to Drive · **152 brain + 61 pwa tests** · ADR #33 · `seed-roles` **run live** (10 nodes) | 04 Aug 2026 |
| P15b | 15 | Lifecycle-anchored interviewing: ontology `Stage`/`Objective`/`cadence` + Stage/Role completeness scoring + prompt rewrite + probe budget | TODO | — | **Brief:** `docs/plan/phase-15-lifecycle-and-alignment.md` §5, §6, §8. Nothing started: `contracts/ontology.json` has no `Stage`/`Objective`/`PART_OF`/`PRECEDES`/`cadence`; `completeness.py` still scores Activities **only** (so `Role.completeness_fields` stays dead code and the org chart never closes — this is what blocks derived altitude); **both** `COLD_START_OPENERS` copies (`prompts.ts`, `planner.py`) still say "day"; `session.ts` `probed` is still a `Set`, so the 3-probes-per-stage-thread budget (§8.5) isn't in. Also §8.4 `cli coverage`. | 04 Aug 2026 |
| P15c | 15 | Alignment diagnostic: derived altitude, misalignment-vs-conflict, gap-and-recommendation report | TODO | — | **Brief:** `docs/plan/phase-15-lifecycle-and-alignment.md` §7. Needs P15b's stages first. No `alignment.py` yet; `ingest.py` does not yet snapshot each contributor's `description` onto `Provenance` (the retention ADR #23 deferred, and the precondition for retaining both accounts); `docgen/` has no stage-spine diagram and no Gaps & Recommendations section. ADRs #31/#32 are written but marked pending. | 04 Aug 2026 |

**Dependency spine:** P1→P2→P3→P4→P5→P6→P7; P8 needs P4+P5; P9 needs P2+P3+P4; P10 needs P2 (richer after P9); **P11 needs P8** (reuses the FolderBus layout + registry); **P12 swaps P1's store in place** (everything behind `GraphStore` untouched); **P13 needs P8+P11** (identity keys the bus folder; retirement is a bus operation); **P14 hardens P8+P12** (the bus is the only thing that still needs to be on Drive).

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
- ✅ **DECIDED + RESOLVED (04 Aug 2026) — the embedder mode is `--extra vectors`, permanently.**
  The clean slate left `brain/_state/` empty, so the choice was free and has now been made: **every**
  brain command runs `uv run --extra vectors ...` (fastembed 0.8.0, 384-dim). Do **not** run a single
  command without it — that is precisely how the mixed-dimension defect below was created. The
  owner's ruling; `seed-roles` was run this way.
- ✅ **RESOLVED (04 Aug 2026) — the order-critical `seed-roles` step is DONE.** `brain/_graph` was
  recreated by `cli seed-roles` and holds the **10 canonical Role nodes with their aliases**, so the
  next `run-round` resolves "the PM" onto `Delivery Specialist` from the first answer instead of
  forking. Re-running is safe (idempotent — `unchanged: 10`). **Re-run it after any edit to
  `contracts/roles.json`.**
- ⚠️ **The one remaining participant's `role_titles` is still unverified.**
  `kishor-goswami-business-analysis-specia-f25b` onboarded as free text before the multi-select
  existed. Their `profile.json` could not be read during P15 planning (the Drive folder read hung),
  and R6 below makes a missing `role_title` likely. Confirm with `cli list-participants` once the
  Apps Script is redeployed; the recovery source is the Answer Log's identity-seed entry, never the
  truncated participant id.
- ✅ **RESOLVED by the clean slate (2026-08-04) — mixed-dimension vectors.** The owner ran
  `OPERATOR-MANUAL.md` §1d (`cli reset-engagement`), so `brain/_state/` was **emptied** and
  `GRAPH_ROOT` (`brain/_graph`) removed — the 52 node files were deleted from the working tree
  (still in git `HEAD`, so recoverable). One participant remains on the bus
  (`kishor-goswami-business-analysis-specia-f25b`). Original note kept for context:
- ⚠️ **`brain/_state/vectors.sqlite` has mixed-dimension vectors** (256-dim hashing + 384-dim
  fastembed from runs that mixed embedder modes), so `ingest` against the existing store throws a
  matmul shape error. **Pick ONE embedder mode and stick with it** (run ingest *consistently* with
  or without `--extra vectors`); if it's already mixed, delete `brain/_state/vectors.sqlite` and
  re-ingest (the Neo4j graph and the raw Answer Logs are untouched — vectors are re-derivable).
- ⚠️ **OPEN (owner, 5 min) — the live Apps Script Web App is the P11 version, not P13.** Evidence:
  both live `profile.json` files carry `display_name` but **no `role_title`**, and neither
  participant folder has the `README.md` that P13's `Code.gs` renders. So P13's Drive-readability
  work has never actually run. Consequences: `list-participants`/`docgen` showed `?` instead of the
  role, and the human-readable per-folder README is missing. **Fix:** Apps Script editor → *Manage
  deployments* → edit the existing deployment → **New version** (keeps the same `/exec` URL, so no
  Cloudflare secret change). The two existing profiles were **backfilled by hand on 2026-08-03**
  (roles recovered verbatim from each Answer Log's identity-seed entry), so `list-participants` is
  correct today — but the **next** push from a phone will write a profile with no `role_title` again
  until the redeploy happens.
- ✅ **RESOLVED (2026-08-03) — batch extractor empty/non-JSON completion.** `DeepSeekProvider.
  complete_json` now re-asks on an unparseable 200 body (`LLM_JSON_ATTEMPTS`, default 3, exponential
  backoff via `LLM_JSON_BASE_DELAY`), warns to stderr per retry, and re-raises the *last* parse
  error so the failure mode is unchanged when it genuinely can't parse. HTTP errors still raise
  immediately (the SDK already retried those). 7 tests in `test_deepseek_json_retry.py` cover
  empty-then-success, prose-then-success, give-up, `attempts=1`, the one-call happy path, fenced
  JSON, and a JSON *array* being a hard error worth retrying.
- **Embeddings (optional, recommended).** Best semantic dedup needs `uv sync --extra vectors`
  (fastembed). Without it the pipeline uses a deterministic hashing fallback (lexical only) —
  works, weaker recall. Run ingest with `uv run --extra vectors ...` to use embeddings.
- ✅ **RESOLVED (2026-06-29) — ElevenLabs plan gate.** Owner bought the **Starter** plan; the `402
  paid_plan_required` is gone. Verified live **TTS + STT both 200** (a TTS→STT round-trip with the
  default voice `21m00Tcm4TlvDq8ikWAM` + `scribe_v2` returned the exact sentence), confirmed **twice**:
  direct ElevenLabs API call, and through the new **Pages Functions** `/tts` (35 KB audio) + `/stt`
  (perfect transcript). No code/config change needed; swap `ELEVENLABS_VOICE_ID` later for a custom
  voice if desired.
- **STT field-accuracy eval (recommended QA, not blocking).** The Scribe endpoint is verified
  working, but only on clean audio. Before fully trusting the permanent-truth transcript leg, run it
  on ~20 real messy recordings (Indian-accented English, noise, SKUs/CRM jargon): from `pwa/`, `node
  scripts/stt-eval.mjs <dir>` (same-named `.txt` per clip gives a WER; reads the key from
  `worker/.dev.vars`). Record the aggregate WER here when done.
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

_All build phases (P0–P10) are DONE; P7 voice verified live._ One owner step + optional QA:

1. **Deploy (owner, one-time):** connect the repo to **Cloudflare Pages** → it auto-deploys on every
   push thereafter. Full step-by-step in **`DEPLOY.md`**: push to GitHub → Pages → Connect to Git
   (root dir `pwa`, build `npm run build`, output `dist`) → add the 2 secrets (`DEEPSEEK_API_KEY`,
   `ELEVENLABS_API_KEY`) → first build → tighten `ALLOWED_ORIGIN` to the Pages URL. The repo is already
   git-initialized + committed; just add a remote and `git push`.
2. **Optional QA — STT field-accuracy:** run `node scripts/stt-eval.mjs <dir>` from `pwa/` over ~20
   real messy recordings and record the WER in Blockers (the endpoint is verified; this measures
   accuracy on field audio).
3. **Optional — custom voice:** set `ELEVENLABS_VOICE_ID` in `pwa/wrangler.toml` to your own voice and
   push (the default "Rachel" already works on the Starter plan).

---

## Handoff log (append-only · newest on top)

### 04 Aug 2026 · agent:opus-p15a — P15a LANDED (role registry, multi-select identity, seed-roles run live). P15b/P15c still untouched.

- **Picked up an interrupted session, not a clean start.** The previous session had written most of
  P15a's code but committed nothing and logged nothing: `PROGRESS.md` still said P15 was
  *"TODO (plan approved, no code yet)"* while 25 files were modified/untracked on disk. First action
  was to establish what was actually there — brain **146 passed** / PWA **61 passed**, `ruff` and both
  `typecheck`s clean — rather than trusting the board. **If you inherit this repo mid-phase, diff
  before you read the status line.**
- **What the interrupted session had already built (verified, not assumed), and it is good work:**
  `contracts/roles.json` matching plan §4.1 exactly (10 roles, CEO/COO present, "Sales" as an AMS
  alias); `roles.py` + `cli seed-roles` (idempotent, `--dry-run`, tops up aliases on an existing node,
  and *adopts* a node already sitting at a different id rather than minting a rival); the PWA chip
  list with a parity test against the contract; `Participant.role_titles[]`; the extractor's
  `KNOWN ROLES` block correctly worded as a **preference**; and **R3 handled in both places** —
  `said_by: "registry"` is excluded from the distinct-persona corroboration count in `ingest.py`
  *and* `crosspersona.py`, so a seeded role can never read as corroborated by a real person.
- **One design improvement over the plan worth knowing:** §10 called for editing `lifecycle.py` to
  read `role_titles` with a `role_title` fallback. That turned out to be unnecessary and was
  correctly skipped — `role_title` is now a **derived `" / "`-joined mirror** of `role_titles`, so
  every P13-era reader (`lifecycle.py`, `Code.gs`'s README, `cli list-participants`) keeps working
  with **zero** changes. Fewer readers to keep in sync is strictly better; don't "finish" §10 later.
- **Finished the four loose ends P15a was missing.**
  (1) **Dual-hat self-handoff copy (§4.5).** A Delivery Specialist who also does sales hands work to
  themselves, and the standard copy told them *"another team handed it to you"*. Implemented as a new
  thread kind `KIND_HANDOFF_SELF` minted in `crosspersona.py` when the receiving persona also owns the
  **giving** role, with its own opener in `planner._opener_and_followups` (*"when you switch from your
  X hat to your Y hat…"*). Chose a distinct kind over passing the persona into the copy function
  because the thread is minted once and routed per-persona — a kind keeps `_opener_and_followups(t)`
  pure and matches the existing dispatch. 3 tests, including the negative control that a **genuine**
  second person still gets the stranger copy.
  (2) **The end-to-end alias-routing test (§11 item 3).** Runs the real `Resolver` + real
  `CrossPersonaEngine`: seeded, "Project Manager" is determined by an exact alias hit (`via="alias"`,
  score 1.0) and the `handoff_confirm` thread lands in the **Delivery Specialist's** brief; unseeded,
  the forked role has no owner and the BA gets `handoff_trace` — *"who would know?"* — while the DS is
  never asked.
  (3) ADRs **#31–#33** in `docs/DECISIONS.md`, (4) `PROMPTS.md` §5c/§6/§7 and `DATA-CONTRACTS.md` §7.
- **Killed one dishonest test while writing it.** My first negative-case test asserted the unseeded
  verdict *is* `"new"`, propped up by a stub LLM that agreed with whatever retrieval ranked first.
  That passes for the wrong reason: with one Role node in the graph the lexical index returns it as a
  neighbour **whatever** its similarity, so the outcome really depends on what the adjudicating model
  decides about "Project Manager" vs "Delivery Specialist" — which is the actual problem, not a
  determinable fact. Rewrote it to assert the load-bearing truth instead: without the alias table
  **no exact match protects the decision** (`[r.via for r in retrieved] == ["vector"]`, score < 0.9),
  and split the routing consequence into its own test that starts from an already-forked node. Plan
  §4.3's prose slightly overstates this — it says retrieval "returns nothing relevant", which is true
  of relevance but not of emptiness.
- **Operational steps actually performed (both were owner decisions this session):**
  **Embedder mode fixed at `--extra vectors`** (fastembed 0.8.0, 384-dim) — the clean slate made the
  choice free and it is now permanent; running one command without the flag re-creates the
  mixed-dimension defect. Then **`cli seed-roles` run live**: dry-run first (10 creates, nothing
  pre-existing), applied, `brain/_graph` recreated with 10 role nodes, re-run to prove idempotency
  (`unchanged: 10`). Spot-checked `role.delivery-specialist.md`: `keywords: [Project Manager, PM, DS,
  Delivery Manager]`, `said_by: registry`, `status: unverified`. **The order-critical migration step
  in plan §9 is therefore closed.**
- **Verified:** brain `ruff` clean + `pytest` **152 passed** (was 124 pre-P15a); PWA `typecheck` +
  `typecheck:functions` clean + **61 vitest** (was 45).
- **Next: P15b, and it is the half the owner actually asked for.** P15a was the identity plumbing;
  the interview is **still day-anchored**. Nothing in §5/§6/§8 has been started — no `Stage` or
  `Objective` in the ontology, no `PART_OF`/`PRECEDES`, no `cadence`; `completeness.py` still scores
  Activities only (so `Role.completeness_fields` remains dead code, the org chart never closes, and
  derived altitude stays impossible); both `COLD_START_OPENERS` copies still say *"map your day"*; and
  `session.ts`'s `probed` is still a `Set`, so the 3-probes-per-stage-thread budget isn't in.
- **Gotchas:** (1) **`ruff format` is NOT this repo's discipline** — untouched files like
  `completeness.py` fail `ruff format --check`. Only `ruff check` (E501 at 100 cols) is the gate;
  don't "fix" formatting repo-wide, it'll bury a real diff. (2) **Editing `contracts/roles.json` is a
  three-step change, not one:** update the contract, mirror it into `pwa/src/sync/roles.ts`
  (`roles.test.ts` fails loudly on drift), **and re-run `cli seed-roles`** or the new alias never
  reaches the graph. (3) **A wrong alias is worse than a missing one** — a missing synonym forks a
  role (visible, fixable), a synonym attached to the wrong role silently **merges two real roles into
  one node** and cannot be unwound, since node ids are stamped into provenance and every edge. This is
  why "MD", "Founder" and "Operations Head" are deliberately absent from the CEO/COO entries. (4) The
  participant id is minted from the **first** selected role only and never moves — adding a hat later
  is correct and must not re-mint (ADR #29). (5) `brain/_graph/` is tracked, so seeding shows up as 12
  new files in the diff; that's intended.

### 2026-08-03 · agent:opus-p15 — P15 designed and planned (no code yet): lifecycle interviewing, multi-role identity, alignment diagnostic
- **Owner's design ruling, from field experience.** The interviewer keeps asking day-to-day questions
  ("what's the first piece of work that lands on your plate") and the owner's own answer as a BA was
  *"I check my mails — which is not my job role."* Real role work is **per-project, not daily**:
  pre-sales → signing → kickoff → discovery → BRD → build → UAT → go-live → support. **The unit of the
  interview becomes the lifecycle STAGE, not the clock.** End goal is explicitly to replace an
  EY/PwC-style engagement, so the deliverable is **SOP + gap-and-recommendation report**.
- **Three of my proposals were rejected by the owner, correctly — recorded in the plan §1.2 so nobody
  re-adds them.** (a) A special "that's not mine, X does it" routing mechanism — unnecessary,
  `crosspersona.py:306 _role_owner_personas()` already routes the question into X's brief. (b)
  Altitude-specific prompts — "no bifurcation between what question the CEO gets and what the
  developer gets"; the graph differentiates, not a script. (c) A declared seniority/`level` field —
  altitude is **derived** from `REPORTS_TO` depth instead, which is strictly better and needs nothing
  predefined. Multi-client separation deferred (one client for now).
- **New requirement: multi-select roles at onboarding**, from a fixed list of 8 the owner supplied
  (BA Specialist, Technical Specialist, Solution Architect, Delivery Specialist, Account Management
  Specialist, QA Head, QA Specialist, Finance). The owner's CEO confirmed some Delivery Specialists
  also do sales, so one person must be able to hold several roles.
- **Answered the owner's "are synonyms needed?" question: yes, load-bearing** — traced in plan §4.3.
  `find_by_alias` is an **exact** whole-string match (`okf_store.py:135`), and the vector fallback
  embedder is lexical-only, so without an alias table "the PM" resolves to *new* Role node
  (`resolve.py:97`), `_role_owner_personas` finds no owner, `_handoff_state` returns
  `route_discoverer`, and the BA gets asked "who would know?" **forever** while the real Delivery
  Specialist is never asked. The alias table is the precondition for the routing design the owner
  chose. Registry goes in `contracts/roles.json`, consumed by the PWA chips, a new `cli seed-roles`,
  and the extractor prompt.
- **Four code-verified defects the plan fixes.** (1) The day-framing lives in 4 layers and has already
  leaked into the graph — `evt.start-of-day.md` is a real node. (2) No `Stage` node, so
  `activity_flow()` guesses order from artifact plumbing → the current `deliverable.md` reports 3
  false broken chains and hides 21 activities. (3) **`Role.completeness_fields` is dead code** —
  `assess()` scores Activities only, so `REPORTS_TO` is never asked about and the org chart never
  closes (this is what blocks derived altitude). (4) Divergence is engineered away: `CONFLICTING` →
  reconciliation thread routed to every contributor, i.e. the system deletes exactly the
  exec-vs-doer signal the engagement sells.
- **Owner closed all three open questions (2026-08-04):** "Sales" is an **alias** of Account
  Management Specialist (not a 9th role); **CEO and COO added** as roles 9–10 (which also gives
  altitude derivation a natural root — the CEO is the role with no outgoing `REPORTS_TO`); probe
  budget **3 per stage thread** confirmed. Plan §4.1/§8.5 updated from "open" to "decided".
- **Discovered while checking the live graph: the owner has run the clean slate.** `brain/_graph` is
  gone (52 files deleted from the working tree, still in git `HEAD`), `brain/_state/` is empty, and
  the bus holds one participant. **This deleted the hardest part of P15's migration before it was
  written:** the old graph's role nodes were named with what are now *aliases*
  (`role.business-analyst`, `role.account-manager`, `role.quality-analyst`, `role.development-team`),
  and node ids are stamped into provenance and every edge, so they could not have been renamed in
  place — a rebuild from Answer Logs was the only clean route. Plan §9 rewritten accordingly: the
  only remaining migration step is **run `seed-roles` before the next `run-round`**, or that round's
  answers fork role nodes before the aliases exist to catch them. `evt.start-of-day` is already gone.
- **Could not verify the remaining participant's `profile.json`** — the Drive folder read hung (the
  P14 stream-only symptom; not retried). So whether it carries `role_title` is unknown, and R6 (Apps
  Script still on the P11 build) makes its absence likely.
- **Did NOT write code.** Plan only: `docs/plan/phase-15-lifecycle-and-alignment.md` (sub-phases,
  ontology diff, full rewritten prompt text, migration, files, test plan, ADRs #31–#33, 6 risks).
  **Open for the owner:** is "Sales" its own 9th role or an alias of Account Management Specialist?
  Is a CEO/leadership role needed (the owner intends to interview the CEO, but the supplied list has
  no exec entry and free text disappears once the field is a fixed multi-select)? **Assumed** (§8.5,
  needs a field test): probe budget 3 per stage thread, 30-word cap kept.

### 2026-08-03 · agent:opus-p15 — P14 operator step confirmed; profile `role_title` defect found; prompts indexed
- **Owner confirmed P14's must-dos are done:** bus folder set **Available offline**, a full round ran
  green, and the `G:\My Drive\warp-compass\graph` fallback copy was deleted. Independently verified:
  `brain/_graph` is the live bundle (52 files / 94,607 B — grown from P14's 32 / 44,784, so it is
  being written), the Drive path is gone, `GRAPH_ROOT` is the absolute local path and `BUS_ROOT` is
  `G:\My Drive\warp-compass`. **`cli list-participants` returned in under a second** — the same
  command that hung >6 min on 2026-07-28. P14's hang is closed.
- **Found the profile.json defect the owner half-remembered — it was real.** Both live profiles had
  `display_name` but **no `role_title`**, and neither participant folder had P13's `README.md`. Root
  cause is **not** brain code: `git show 36cd115^:apps-script/Code.gs` proves the pre-P13 script
  merged only `display_name`, so **the Apps Script Web App was never redeployed after P13**. The
  brain side is innocent and correct — `lifecycle.py` reads `role_title` properly, and
  `cycle.py`'s read-merge-write preserves it. **Did:** backfilled both profiles, taking each role
  **verbatim from the Answer Log's identity-seed entry** (`"I'm Ajay Delivery, I'm the Delivery
  Specialist / Project Manager."`) rather than un-slugging the participant id, which is lossy
  (`…-business-analysis-specia-f25b` is truncated). `list-participants` now prints both roles.
  The redeploy is still required or the next phone push regresses it — logged in Blockers.
- **Also confirmed the P14 `read_profile` data-loss guard is correctly in place** (`folder.py`
  `_read_json_any` → `read_text_or_none`: absent/malformed still reads `{}`, a busy drive raises).
  Both profiles have intact `ingested_logs` matching their answer-log count, so no round ever
  re-ingested through the empty-profile path. No money was burned.
- **Added `PROMPTS.md`** (repo root) — an index of every prompt with `file#Lnn` links, ordered by how
  much each changes the felt conversation, plus a "the conversation starts badly → edit §2 vs §5 vs
  §3" decision tree. Written because prompt copy lives in 7 places across 2 languages and the owner
  wants to iterate on interview quality without reading source.
- **Housekeeping:** regenerated `deliverable.md` from the real graph (the committed copy still had
  `persona.demo`/`p_alice` test data — now 0 matches) and deleted the stray `brain/deliverable.md`
  duplicate; moved `referrence images/Folder available offline.png` →
  `docs/images/drive-folder-available-offline.png` and embedded it in `brain/README.md`'s Drive
  section; committed `brain/_graph/` per P14 gotcha 4 (it was drifting untracked, and now that the
  Drive copy is deleted git is its only version history).
- **Verified:** brain `ruff` clean + **124 pytest**; PWA `typecheck` + `typecheck:functions` clean +
  **45 vitest** + `npm run build` installable.
- **Next:** owner redeploys the Apps Script (Manage deployments → edit → New version — same `/exec`
  URL, no Cloudflare secret change). Then prompt tuning via `PROMPTS.md`.
- **Gotchas:** (1) **The repo is not the deployment for `apps-script/`.** It's the one component
  Cloudflare's git integration does NOT auto-deploy — a `Code.gs` commit does nothing until someone
  redeploys it by hand, which is exactly how P13's changes sat dormant for 6 days. Treat any future
  `Code.gs` edit as an owner action, not a push. (2) **The identity-seed entry is the recovery source
  for a lost `role_title`** — `identityAnswer()` writes the role verbatim into the Answer Log's first
  entry, so it survives even when the profile doesn't. Don't reconstruct roles from participant ids;
  the slug is truncated to a fixed width. (3) `brain/_graph/` is now tracked — expect graph churn in
  every future diff after a round. That's intended (version history per
  `OKF-vs-Neo4j-report.md` §3), but don't `git add -A` mid-round or you'll commit a half-written
  bundle.

### 2026-07-28 · agent:opus-p14 — Drive-backed bus hardening; P14 → DONE
- **Symptom reported:** `cli run-round` ran a long time, then died at `cycle.py:148` →
  `bus.ensure_participant` → `mkdir(parents=True, exist_ok=True)` with
  `OSError [WinError 1450] Insufficient system resources` on a participant folder that *already
  existed*. Both the `mkdir` and `exist_ok`'s fallback `is_dir()` raised.
- **Diagnosed:** not a code bug. `G:` is Google Drive for Desktop mounted through **Dokan**, a
  user-mode FS driver; when its request pool is exhausted, *every* operation on the drive fails
  with 1450 — reads and `stat` too, which is why an `exist_ok=True` mkdir could die. Evidence:
  Drive's own `drive_fs.txt` logged `Slow operation AsyncDokanGetDeleteApproval` and
  `AsyncDokanFindFiles` on that exact participant path; nonpaged pool 1.1 GB; 0.7 GB of 13.9 GB RAM
  free; the folder is **stream-only** (`G:` used = 0.00 GB, no content cache) despite
  `DEPLOY.md` requiring offline-available. Amplifier: the OKF store rewrites a whole node file per
  touch, rewrites BOTH endpoints per `add_edge`, and 11 `index.md` on close — every one an
  `os.replace`, which costs Drive a *delete-approval round-trip*. Hundreds per round.
- **Did (owner-approved options A + C; owner is doing B themselves):**
  - **A — graph off Drive.** Copied the 32-file bundle `G:\My Drive\warp-compass\graph` →
    `brain/_graph` (verified: same tree, 44,784 bytes) and set `GRAPH_ROOT` in `brain/.env`. The
    bundle is brain-private (the PWA never reads it), so ~95% of Drive writes are simply gone. The
    Drive copy was left in place as a fallback — **delete it once a round has been observed green.**
  - **C — `fsretry.py`.** `retry_fs` / `read_text_or_none` / `atomic_write_text`, retrying a
    documented set of transient winerrors (1450, 5, 6, 32, 33, 1453, 1816) with exponential backoff
    (6 attempts / ~15s, `FS_RETRY_ATTEMPTS` + `FS_RETRY_BASE_DELAY`), then re-raising the original
    error untouched. Every I/O call in `bus/folder.py` and `graphstore/okf_store.py` now goes
    through it, and the two duplicate `_atomic_write` implementations collapsed into one.
  - Fixed a **latent data-loss bug** found on the way (see gotcha 1).
  - Docs: `brain/README.md` gained "When the bus is on Google Drive"; `DEPLOY.md` step 1 now says
    to keep `GRAPH_ROOT` local; `.env.example` explains why.
- **Next:** owner makes the Drive folder **Available offline** (option B), then run
  `uv run --extra vectors python -m warp_compass_brain.cli run-round`. If it's green, delete
  `G:\My Drive\warp-compass\graph`. Optional follow-up (option D, not done): batch graph writes —
  mark nodes dirty and flush once at `close()` instead of writing on every `upsert_node`/`add_edge`.
  That's an order-of-magnitude cut and speeds up local runs too, but it needs the commit points in
  `cycle.py:173-175` reordered first, or a crash mid-round marks logs `ingested` with no graph
  writes behind them.
- **Gotchas:** (1) **Tolerant reads must not tolerate a busy drive.** `read_profile` and
  `_parse_node_file` both caught `OSError` and returned empty/`None`, which is right for a
  half-synced file and catastrophic for 1450: an empty `profile.json` makes `cycle` treat an
  existing participant as brand new, re-ingesting every Answer Log through DeepSeek (real money) and
  overwriting the real profile; a dropped node file gets re-created empty by the next
  `upsert_node`, losing its provenance. `read_text_or_none` now separates "genuinely absent" from
  "drive busy" — absence still returns empty, a persistent transient error raises. `OSError` was
  removed from `_parse_node_file`'s except tuple deliberately. (2) **Retrying only helps when Drive
  *raises*.** If it *blocks* instead, the round hangs regardless — `cli list-participants` hung
  >6 min on `G:` during this session. Only option B fixes that, which is why it isn't optional.
  (3) The graph is now at a path relative to `brain/` in `.env.example` (`./_graph`) — running uv
  from anywhere else silently starts a *second, empty* graph. `brain/.env` uses an absolute path to
  avoid this; keep it that way. (4) `_graph/` is deliberately NOT gitignored (`_state/` and `_bus/`
  are), so git can give the bundle the version history `OKF-vs-Neo4j-report.md` §3 recommends —
  it's currently untracked, so either commit it or add it to `.gitignore`; don't leave it drifting.
  (5) `test_fsretry.py` injects fake `OSError`s with `.winerror` set and `base_delay=0`, so the
  suite needs no Drive mount and doesn't actually sleep.

### 2026-07-28 · agent:opus-p13 — Phase 13 (declared identity + participant lifecycle); P13 → DONE
- **Did:** (1) **Identity is declared once per device.** A typed onboarding card
  (`pwa/src/screens/OnboardingCard.tsx`) collects name + role before the first session;
  `sync/participant.ts` mints a readable, filesystem-safe slug from them
  (`rahul-mehta-business-analyst-3c1f`) that is **immutable after minting** and doubles as the
  Drive folder name and the graph's provenance `said_by`. `getParticipant()` now returns
  `Participant | null` and `App.tsx` gates on it; a pre-P13 `p_<uuid>` record reads as
  not-onboarded and is re-minted (old id kept as `previous_id`).
  (2) **The role question is gone for good.** `session.ts` drops `COLD_START_OPENERS[0]` when an
  identity exists, `runner.start()` greets by first name ("Hi Rahul — you're the Business
  Analyst. …" cold / "Welcome back, Rahul. …" warm), and `buildUserPrompt` repeats a
  `WHO YOU'RE TALKING TO` block **every turn** so the model can't re-ask twenty turns in.
  (3) **The graph learns the role at turn zero** — the onboarding answer is seeded as the Answer
  Log's first entry (`appendSeed`), gated by an `identity_seeded_at` stamp so only the first log
  that actually reaches the brain carries it. `answerCount()` keeps the UI's "N answers" honest.
  (4) **Drive is readable** — `role_title` flows through `remote.ts` → `_sync.ts` → `Code.gs`,
  which now also renders a per-folder `README.md` (name, role, first/last seen, session count) and
  writes the profile *after* the log so the count is current. `docgen` renders
  "Rahul Mehta (Business Analyst)" via `lifecycle.persona_display_names`.
  (5) **Retirement, without touching the graph (ADR #30)** — `lifecycle.py` +
  `retire-participant` / `list-participants` / `reset-engagement`; bus gains
  `_retired.json` + `_archive/`.
- **Two defects found while building, both fixed (they're why this phase wasn't trivial):**
  **Finding 1** — `cycle.py:104` fell back to the persona id when distributing briefs, and
  `write_brief`'s `mkdir(parents=True)` then **recreated the folder the operator had just
  archived**, silently undoing every retirement. Removed the fallback; a brief now goes only to a
  live participant, and a persona with no folder is either *retired* (silent, counted) or
  *missing* (loud warning — that distinction is the entire reason `_retired.json` exists rather
  than inferring retirement from an absent folder). Regression test asserts the folder is still
  gone after a round.
  **Finding 2** — gaps are scoped to a persona's own subgraph, so a node only a retired person
  ever touched fell out of every brief and went **permanently silent**. Added the orphan thread
  pool in `planner.py`: nodes whose contributors are all retired are re-offered to every live
  persona, capped (`planner_orphan_max`, default 2), ranked below their own work, and phrased in
  the third person with an "I don't know / who would know?" escape hatch. Self-clearing — one
  answer from a live persona and the node stops being orphaned.
- **Also caught in smoke testing:** `reset-engagement --bus <scratch>` resolved the graph root and
  the `_state/` paths from *settings*, not from the bus it was pointed at — so resetting a scratch
  bus deleted the real graph root's siblings and wiped `brain/_state/vectors.sqlite`. It did wipe
  mine during testing (harmless — gitignored, rebuilds on next ingest, and it was stale June test
  data). Both now scope correctly: the graph resolves against the given bus, and `_state/` is only
  cleared when resetting the *configured* bus. Regression test added.
- **Two more defects found on post-implementation review, both fixed:** (a) the **download
  fallback marked the identity as seeded** — if the operator then never dropped that file into
  `answer_logs/`, the Role node was lost and no later session would re-seed it. Only a successful
  *push* marks it now; erring the other way costs one duplicate introduction that merges harmlessly.
  (b) **A restored participant silently got no briefs** — folder back from `_archive/` but marker
  still in `_retired.json` meant `cycle` mapped them while the Planner excluded them.
  `lifecycle.effective_retired()` now defines retired as *marked AND absent from the bus*, so the
  folder wins. Both have regression tests (**100 brain tests** now).
- **Risk register (as built)** is `docs/plan/phase-13-identity-and-lifecycle.md` §14. The two worth
  a decision before real client data: **readable ids are guessable** (P13 traded an unguessable
  UUID for a slug + 4 hex, so any legitimate app user could push into another's folder — fine for
  trusted colleagues, needs a per-participant token otherwise), and **one human can become two
  personas** (re-onboarding after clearing site data splits their knowledge, and corroboration can
  read the halves as two voices).
- **Next:** Nothing blocked. Before the wider-team rollout run `OPERATOR-MANUAL.md` §1d
  (clean slate) — and note **`deliverable.md` is committed with old test data** (`persona.demo`,
  `p_alice`); regenerate or blank it so a new teammate doesn't read it as a real sample.
- **Gotchas:** (1) **Participant ids are immutable** — they're stamped into provenance; correct a
  typo'd name via `display_name` only, never the id (ADR #29). (2) The seeded identity entry's
  `raw_answer` is assembled from form fields, a documented deviation from strict verbatim-ness,
  chosen over editing the frozen `answer-log.schema.json` (`additionalProperties: false`).
  (3) A successor in the same seat reads as a **second corroborating voice**, mildly inflating
  confidence — accepted; a `replaces:` lineage field would fix it if it ever matters.
  (4) `test_lifecycle.py::test_retiring_leaves_the_graph_byte_identical` hashes the graph tree
  before/after — if that ever fails, ADR #30 has been broken and the whole cost/risk argument for
  this design goes with it.

### 2026-07-02 · agent:fable-p12 — Phase 12 (OKF graph store, Neo4j removed) + interviewer refocus; P12 → DONE
- **Did:** (1) **Replaced Neo4j with an OKF Markdown bundle store** — new
  `graphstore/okf_store.py` (`OkfGraphStore`): one `.md` per node under `{GRAPH_ROOT}` (default
  `{BUS_ROOT}/graph`, i.e. Drive-synced for free); YAML frontmatter = machine truth
  (`title`⇔canonical_name, `keywords`⇔aliases, description, status, category_codes,
  key_attributes, provenance, **outgoing `edges` with per-edge provenance**); generated body =
  human/LLM view (timestamped Facts + two-way `[[wiki-links]]`: Links on the giver, Backlinks on
  the receiver — `add_edge` rewrites BOTH files). Whole bundle loads into memory on `connect()`;
  atomic write-through; `index.md` per type regenerated on `close()`; idempotent MERGE semantics
  kept. Deleted `neo4j_store.py`, the `neo4j` dep, `NEO4J_*` config (→ `GRAPH_ROOT`), the
  `GraphStore.query()` Cypher escape hatch, and the `neo4j` pytest marker — **the full suite (72)
  now runs with zero services**. One-off migration: `scripts/migrate_neo4j_to_okf.py`
  (standalone, `uv run --with neo4j`). (2) **Interviewer refocus (owner field feedback):**
  SYSTEM_PROMPT (pwa `prompts.ts`) now states the end goal — a complete 0→100 SOP per role —
  with a ground-up chronological method ("what happens next?"), and forbids leading with
  difficult/frustrating questions; COLD_START_OPENERS (mirrored in `planner.py`) rewritten as a
  chronological walk, frustration opener removed. (3) **Extractor = active editor:** distill
  (never transcribe), 1–3 sentence what+why descriptions, keyword identifiers, and **personal
  names abstracted to organizational roles**. (4) Docs: ADR #28, `docs/plan/phase-12-okf-store.md`,
  OPERATOR-MANUAL rewritten (no DB start step; "Reading the knowledge graph" section), READMEs,
  `.env.example`. Decision analysis in `OKF-vs-Neo4j-report.md` (repo root).
- **Next:** operate as usual (`run-round` → `corroborate --apply` → `docgen`). If old Neo4j data
  matters, run the migration script once, else rebuild from Answer Logs (clear `ingested_logs`).
  Neo4j Desktop can be uninstalled. Optional: sample-bundle smoke test on real engagement data.
- **Gotchas:** (1) The graph bundle's **bodies are generated** — hand-edits get clobbered on the
  next write; frontmatter is the truth. (2) `add_edge` silently no-ops if an endpoint id is
  missing (same contract as the old Cypher `MATCH…MERGE`). (3) A malformed `.md` is skipped with
  a `[okf-store] WARNING` (tolerant reads); its edges drop until fixed. (4) The old
  `pytest -m "not neo4j"` filter is obsolete — just `uv run pytest`. (5) `vectors.sqlite` stays
  under `brain/_state/` (local, rebuildable) — do NOT move it into the Drive folder.

Each entry: `### <date> · agent:<id>` then **Did / Next / Gotchas**. Never edit past entries.

### 2026-07-01 · agent:opus-p11 — verified live deploy + import-button UX fix + operator manual
- **Did:** (1) **Verified P11 is live in production** by probing `warp-compass.pages.dev`: `/health`
  → `{ok:true,…}`, and `/sync/brief?participant_id=diagnostic_probe` → **`{ok:true,brief:null}`** —
  proving the `/sync/*` Functions are deployed, the Pages secrets are wired (no `server_misconfigured`),
  and Apps Script responds correctly. Sync backend confirmed working end-to-end. (2) **Fixed the
  "Import a brief file" confusion** — it was rendered *unconditionally* (intentional fallback, but it
  read as "sync isn't working"). Now the landing shows only **Start a session**; the manual
  *Start without a brief* / *Import a brief file* fallback appears **only when the automatic pull
  fails** (`pullFailed` state in `App.tsx`). (3) Bumped the `/health` phase string `p10`→`p11`.
  (4) **Added `OPERATOR-MANUAL.md`** (repo root) — the step-by-step laptop routine to run after each
  round of mobile sessions (start Neo4j → `run-round` → `corroborate --apply` → `docgen`), with a
  troubleshooting table incl. the PWA service-worker cache note. **Verified:** typecheck (src +
  functions) clean, **24 vitest**, build installable. Committed + pushed.
- **Next:** Nothing blocked. (If a user still sees the old UI, it's the cached service worker — fully
  reopen the installed PWA to pick up the new bundle.)
- **Gotchas:** (1) The import button was **never** a deploy failure — it was always-rendered by design;
  now fallback-only. (2) `registerType:"autoUpdate"` (vite-plugin-pwa) updates the SW in the
  background; a client on the old cached bundle needs a full reopen/second load to get new code.

### 2026-07-01 · agent:opus-p11 — Phase 11 owner setup complete; P11 → DONE
- **Did:** Owner completed the Google setup end-to-end and **tested it working**: created the Drive
  root, deployed the Apps Script Web App (execute-as-owner / access-anyone) with `ROOT_FOLDER_ID` +
  `SHARED_SECRET`, set the `APPS_SCRIPT_URL` + `SYNC_SHARED_SECRET` Pages secrets, and set `BUS_ROOT`.
  **Drive-mode clarification:** the folder is on disk via **Stream mode + “Available offline”** (NOT
  full mirror) — confirmed syncing; corrected the “must mirror” wording across `apps-script/README.md`,
  `phase-11-drive-sync.md`, `DEPLOY.md`. Added a **self-contained deployment record + debugging runbook**
  (request-flow trace, file map, config reference, end-to-end test, symptom→cause→fix table, hard
  constraints) to `docs/plan/phase-11-drive-sync.md` so any future agent can debug the sync standalone.
  Committed + pushed to GitHub `kishorgoswamibiz/Warp-Compass` (auto-deploys via Cloudflare Pages).
- **Next:** Nothing blocked. Optional future items: transcript-Doc mirror (ADR #27b, deferred),
  semantic batch conflict detection (ADR #23), STT field-WER eval.
- **Gotchas:** Same as the code-complete entry below, except **(1) is corrected**: the Drive folder
  must be **on disk** (Mirror mode OR Stream + *Available offline*), not stream-only.

### 2026-07-01 · agent:opus-p11 — Phase 11 (automatic Google Drive sync); P11 → REVIEW (code complete)
- **Did:** Removed the manual export/import — the PWA now syncs to the brain over the network, reusing
  the P8 `FolderBus` layout so the **brain side needs zero code change**. New **`apps-script/`**
  (`Code.gs` + `appsscript.json` + `README.md`): a Google Apps Script **Web App deployed *Execute-as:
  me / access: anyone*** that writes/reads the owner's Drive in the exact `participants/{id}/
  {profile.json, answer_logs/, briefs/}` layout — **so no end user ever logs into Google**. Answer logs
  are **write-once** (immutability); `profile.json` writes **merge** (never clobber the brain's
  `ingested_logs`). New Pages Functions **front door** (`pwa/functions/_sync.ts` +
  `sync/{answer-log,brief}.ts`, `Env` += `APPS_SCRIPT_URL`/`SYNC_SHARED_SECRET`) forward to the Web App
  with the shared secret injected server-side (secret off the client; also follows Apps Script's 302).
  New PWA **`RemoteBus`** (`pwa/src/sync/remote.ts`): **auto-push** the Answer Log on session close
  (`SessionScreen`) and **auto-pull** the latest brief on start (`App.tsx`); the manual download/import
  stays as the offline fallback. **Verified:** PWA `typecheck` + `typecheck:functions` clean, **24
  vitest** (+6 `remote.test.ts`), `npm run build` installable. ADR #27.
- **Next:** **Owner one-time Google setup** (the only thing left — flips P11 REVIEW → DONE): follow the
  7-step checklist in `apps-script/README.md` / `docs/plan/phase-11-drive-sync.md` — create the Drive
  root, mirror via Drive-for-Desktop, deploy the Web App, set `ROOT_FOLDER_ID`+`SHARED_SECRET` script
  props, add `APPS_SCRIPT_URL`+`SYNC_SHARED_SECRET` Pages secrets, set `BUS_ROOT` in `brain/.env`.
- **Gotchas:** (1) **The Drive folder must be on disk, not stream-only** — either Mirror mode or Stream
  + folder set *Available offline* (owner verified the latter). (2) **Apps Script always returns HTTP 200** (ContentService can't set status); outcomes are in
  the JSON `ok` field and the Pages Function maps them to real status. (3) Sync only works under
  **`npm run dev:cf`** locally (the `/sync/*` Functions aren't in the split Vite+worker mode). (4) The
  Web App URL only changes if you create a *new* deployment — use *Manage deployments → edit → New
  version* to keep the same `/exec` URL (else update the Cloudflare secret). (5) `BUS_ROOT` maps to
  `Settings.bus_root` (`cli.py:174` = `args.bus or s.bus_root`), so env or `--bus` both work.

### 2026-06-29 · agent:opus-deploy — ElevenLabs verified + streamlined deploy; P7 → DONE
- **Did:** (1) **Verified ElevenLabs on the new Starter plan** — the `402` is gone. A TTS→STT
  round-trip (default voice `21m00Tcm4TlvDq8ikWAM` + `scribe_v2`) returned the exact sentence, proven
  both via a direct API call and through the new Pages Functions (`/tts` 35 KB audio, `/stt` perfect
  transcript). Flipped **P7 REVIEW → DONE** (voice leg works end-to-end). (2) **Streamlined the deploy
  to GitHub→Cloudflare-Pages.** Moved the key-proxy into **`pwa/functions/`** (Pages Functions:
  `llm.ts`/`stt.ts`/`tts.ts`/`health.ts` + canonical `_shared.ts`) so the PWA **and** its proxy are one
  git-connected Pages project on a single origin — relative `/llm,/stt,/tts` unchanged, every `git
  push` auto-deploys. Added `pwa/wrangler.toml` (Pages config + non-secret vars), `pwa/.dev.vars.example`,
  pwa scripts `dev:cf`/`deploy`/`typecheck:functions`, and devdeps `@cloudflare/workers-types` +
  `wrangler`. Rewrote `worker/src/index.ts` to import the **same** `_shared.ts` (zero duplicated proxy
  logic; kept as an optional standalone). Wrote **`DEPLOY.md`** (one-time setup + the `git push`
  workflow). `git init` + first commit (verified no secrets staged; added `.gitattributes` for LF).
  **Verified:** functions+src+worker typecheck, build installable, 18 vitest, and **all 4 endpoints live
  via `wrangler pages dev`** (incl. `/llm` real DeepSeek). ADR #26.
- **Next:** **Owner connects the repo to Cloudflare Pages once** (DEPLOY.md); thereafter updates are
  `git push`. Optional: STT field-WER eval; custom voice id.
- **Gotchas:** (1) **Single source of truth for the proxy = `pwa/functions/_shared.ts`.** The Pages
  route files and `worker/src/index.ts` both import it (the worker via `../../pwa/functions/_shared`).
  Edit proxy behaviour there only. (2) **Secrets are NOT committed** (`.gitignore` covers `brain/.env`,
  `**/.dev.vars`); set `DEEPSEEK_API_KEY` + `ELEVENLABS_API_KEY` in the Pages dashboard (or `wrangler
  pages secret put`). Non-secret vars live in `pwa/wrangler.toml`. (3) **Pages build settings:** root
  dir `pwa`, build `npm run build`, output `dist`; functions auto-detected from `pwa/functions/`.
  (4) Local full-stack dev = `npm run dev:cf` (needs `pwa/.dev.vars`); the old split (`wrangler dev` in
  `worker/` + Vite proxy) still works. (5) `worker/` is now optional — production is Pages Functions.
  (6) `tsc -b` (pwa build) only covers `src/`; functions are compiled by Cloudflare (esbuild strips
  types, won't catch type errors) — run `npm run typecheck:functions` before pushing proxy changes.

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
