# Phase 11 — Automatic Google Drive sync (kill the manual export/import)

> **One-line goal:** make every user's phone talk to the one brain **with no manual file
> hand-off** — the PWA pushes its Answer Log and pulls its Session Brief over the network,
> and the laptop brain reads/writes the *same* tree automatically. This is the "networked v1"
> bus the design always anticipated (`02 §2(B)`, `§13` — *"`Bus` → shared cloud folder now
> (alt: sync endpoint later)"*), built the lightweight way.

> **Build status (2026-07-01):** **CODE COMPLETE.** Apps Script (`apps-script/`), the Pages
> Functions (`pwa/functions/sync/*` + `_sync.ts`), the PWA `RemoteBus` (`pwa/src/sync/remote.ts`,
> auto-push on close + auto-pull on start), and tests are done — PWA typecheck + functions typecheck
> clean, **24 vitest pass**, build installable. **Remaining = owner one-time Google setup** (the
> checklist below / `apps-script/README.md`). Decisions locked: **(1) Pages-Function proxy** (not
> browser-direct); **(2) transcript Docs deferred** — JSON stays the sole canonical raw store.

## Context Card — read THIS, skip the source

- **The seam already exists and does NOT change.** `Bus` ABC @ `brain/src/warp_compass_brain/bus/base.py`
  (`list_participants`, `ensure_participant`, `read_profile`, `write_profile`, `list_answer_logs`,
  `read_answer_log`, `write_brief`). `FolderBus` @ `bus/folder.py` implements it over a directory tree:
  `{root}/participants/{participant_id}/{profile.json, answer_logs/*.json, briefs/*.json}`. Writes are
  atomic (temp + `os.replace`); reads are tolerant. **The daily cycle** (`cycle.py` `RoundRunner`,
  driven by `cli run-round`) enumerates that tree, ingests **new** logs (tracked in
  `profile.ingested_logs`), and writes one brief per persona back into `briefs/`.
- **What's manual today (DECISION #8 / ADR #21e):** the **phone** can't touch the shared folder, so
  export = the PWA *downloads* the Answer Log and the operator drops it into `answer_logs/`; import =
  the operator copies a brief out of `briefs/` and the user file-picks it. See `pwa/src/sync/bus.ts`
  (`downloadAnswerLog`, `parseBriefFile`) and `participant.ts` (stable `participant_id` in
  `localStorage`, `persona_id == participant_id`).
- **The contracts are authoritative and unchanged:** `contracts/answer-log.schema.json` (Runner→Brain,
  immutable source of truth) and `contracts/session-brief.schema.json` (Brain→Runner). Raw text =
  Answer Log JSON. **Do not** move the canonical store off these schemas.
- **Hard constraint (memory `warp-compass-tooling-prefs`):** end users only ever open the **PWA link** —
  **no install, no Google login** on their device. Laptop-side setup by the owner is fine. Lightweight
  over heavy infra; no Docker.
- **The proxy pattern to mirror:** live API calls already go through **Cloudflare Pages Functions** in
  `pwa/functions/` (`llm.ts`/`stt.ts`/`tts.ts` + canonical `_shared.ts`), same origin, secrets in the
  Pages dashboard (see `DEPLOY.md`). The sync endpoint reuses this exact shape.

**Depends on:** P8 (bus + registry + cycle). **Packages:** `pwa`, `pwa/functions`, new `apps-script/`,
docs. **Brain code change:** ideally **none** (see Step 1).

---

## The idea in one picture

```
 PHONE (PWA, end user — link only)        OWNER'S GOOGLE ACCOUNT              OWNER'S LAPTOP (the brain)
 ┌───────────────────────────┐    ┌──────────────────────────────┐   ┌──────────────────────────────┐
 │ session ends → push log    │    │  Apps Script Web App           │   │  Google Drive for Desktop      │
 │ launch → pull latest brief │    │  (runs AS owner, DriveApp)     │   │  mirrors the tree to disk      │
 │                            │POST│   doPost → write answer log    │   │            │                   │
 │  RemoteBus client ─────────┼───►│   doGet  → return latest brief │◄─►│  /participants/{id}/...        │
 │            ▲               │ GET│   into /participants/{id}/...  │Drv│            │ (real files)      │
 └────────────┼──────────────┘    └──────────────────────────────┘sync└────────────┼──────────────────┘
              │ same-origin /sync                                                    │ FolderBus (UNCHANGED)
   ┌──────────┴───────────┐                                                ┌─────────┴──────────┐
   │ Cloudflare Pages Fn  │  holds Apps Script URL + shared secret         │ cli run-round       │
   │  pwa/functions/sync  │  (forwards POST/GET, clean CORS)               │ ingest → plan → brief│
   └──────────────────────┘                                                └─────────────────────┘
```

**Why this is the right shape:**
1. The **laptop side is free.** Point `bus_root` at a **Google Drive for Desktop** mirrored folder and
   `FolderBus` + `run-round` already work with **zero code change** — Drive syncs the files in/out.
2. The **only real gap is the phone**, and a browser can't write the owner's Drive. An **Apps Script
   Web App that executes as the owner** bridges that gap **without any end-user Google login** — exactly
   the "seamless, link-only" constraint. This *is* the "thin always-on sync endpoint" of v1, but free
   and serverless.
3. It drops onto the existing `Bus` seam and the existing Pages-Functions proxy pattern — additive, not
   a rewrite (ADR #8: *"a networked endpoint swaps in behind the same two ops"*).

---

## How raw text is stored (the answer to "Drive or Docs?")

- **Canonical = Answer Log JSON in Drive.** `participants/{id}/answer_logs/{session_id}.json`, exactly
  the `answer-log.schema.json` shape, **write-once / never overwritten**. This preserves the immutable
  source of truth and graph re-derivability (ADR #4). This is what the brain ingests.
- **Google Docs = optional human mirror, never the source.** The Apps Script *may also* render a
  readable transcript Doc per session into `participants/{id}/transcripts/` for the BA to skim. It is
  derived, disposable, and never read by the brain. (Recommended as a Step-5 nicety, not load-bearing.)
- **Why not store raw text as a Doc and parse it back?** It would break the schema contract, lose
  per-entry provenance (`thread_id`, `kind`, `ts`, `audio_ptr`), and make ingest fragile. JSON stays the
  truth; Docs are for eyes only.

---

## Manual setup you (the owner) do in Google — one-time checklist

This is the **only** work left; the code is done. Full click-by-click (with screenshots-worth of
detail) is in **`apps-script/README.md`** — this is the summary.

| # | Where | Do this | Produces |
|---|-------|---------|----------|
| 1 | **Google Drive** | Create a root folder, e.g. `warp-compass`. Copy its **folder id** from the URL. | `ROOT_FOLDER_ID` |
| 2 | **Drive for Desktop (laptop)** | Get the folder onto disk: either **Mirror files** mode, or **Stream** mode + right-click the folder → **Offline access → Available offline** (owner uses the latter — confirmed syncing). Note the local path. | e.g. `G:\My Drive\warp-compass` |
| 3 | **script.google.com** | New project → paste `apps-script/Code.gs`; show the manifest (Project Settings) and paste `apps-script/appsscript.json`. | the Web App source |
| 4 | **Apps Script → Project Settings → Script properties** | Add `ROOT_FOLDER_ID` (from #1) and `SHARED_SECRET` (a long random string you invent). | the script's config |
| 5 | **Apps Script → Deploy → New deployment → Web app** | *Execute as: Me*; *Who has access: Anyone*. Authorize the Drive scope. Copy the **`/exec`** URL. | `APPS_SCRIPT_URL` |
| 6 | **Cloudflare Pages → Settings → Variables and Secrets** | Add secrets `APPS_SCRIPT_URL` (from #5) and `SYNC_SHARED_SECRET` (**same** value as #4's `SHARED_SECRET`). | production wiring |
| 7 | **Laptop `brain/.env`** | Set `BUS_ROOT=<the mirrored path from #2>` (or pass `--bus`). **No code change.** | brain reads/writes the synced tree |

**Why no end-user login:** the Web App runs **as you** (step 5, *Execute as: Me*), so each phone just
POSTs JSON through the Pages Function — users never see a Google consent screen; they still only open
the PWA link (the seamless, link-only constraint). The `SHARED_SECRET` (held only in Cloudflare +
script properties, never in the browser) is what stops a stranger with the URL from writing to your
Drive.

**Verify** (also in the README): run a session → *“Sent to the brain.”* → the JSON appears under
`participants/{id}/answer_logs/` on the laptop → `cli run-round` writes a brief → reopening the PWA
shows *“Loading your brief…”* and starts warm — no manual step anywhere.

---

## ✅ Deployment record + debugging runbook (hand this to any agent)

> **Self-contained.** Everything an agent needs to debug the Phase-11 sync without re-reading the whole
> codebase. As of **2026-07-01** the sync is **fully deployed and owner-tested end to end.**

### What the owner completed (all live)
1. **Drive root folder** created; its id is in the Apps Script `ROOT_FOLDER_ID` script property.
2. **Google Drive for Desktop** = **Stream mode + the engagement folder marked “Available offline”**
   (NOT full mirror). Owner confirmed the folder stays synced to the local `G:\`-style path on disk.
3. **`brain/.env`** → `BUS_ROOT` points at that local path.
4. **Apps Script Web App** deployed: *Execute as: owner*, *Access: anyone*; script properties
   `ROOT_FOLDER_ID` + `SHARED_SECRET` set; Drive scope authorized.
5. **Cloudflare Pages secrets** `APPS_SCRIPT_URL` + `SYNC_SHARED_SECRET` set (`SYNC_SHARED_SECRET` ==
   the script's `SHARED_SECRET`).
6. Code pushed to **GitHub `kishorgoswamibiz/Warp-Compass`** → Cloudflare Pages auto-builds/deploys.

### Request flow (trace a failure to one hop)
```
PUSH (session close):
  PWA pushAnswerLog()  ── POST /sync/answer-log ─►  Pages Fn handleSyncPush (_sync.ts)
     └ adds SYNC_SHARED_SECRET, action=push_answer_log ── POST ─► Apps Script doPost (Code.gs)
          └ verifies secret ─► DriveApp writes participants/{id}/answer_logs/{session}.json (write-once)
  ── Drive for Desktop syncs the file down ─►  laptop  ──  cli run-round → FolderBus reads it → ingest

PULL (session start):
  PWA pullLatestBrief() ── GET /sync/brief?participant_id=… ─► Pages Fn handleSyncPull
     └ adds secret, action=pull_brief ── GET ─► Apps Script doGet ─► returns newest briefs/*.json
  cli run-round wrote that brief; Drive synced it up; PWA starts warm.
```

### File map (where each piece lives)
| Concern | File |
|---|---|
| Drive read/write, write-once, profile-merge | `apps-script/Code.gs` |
| Web App manifest (access=anyone, execute-as-owner) | `apps-script/appsscript.json` |
| Owner setup + rotate secret | `apps-script/README.md` |
| Secret-injecting forwarder + CORS | `pwa/functions/_sync.ts` |
| Route glue | `pwa/functions/sync/{answer-log,brief}.ts` |
| Env typing (`APPS_SCRIPT_URL`, `SYNC_SHARED_SECRET`) | `pwa/functions/_shared.ts` |
| Phone client (push/pull) | `pwa/src/sync/remote.ts` (+ `remote.test.ts`) |
| Auto-push on close | `pwa/src/screens/SessionScreen.tsx` (`endSession`) |
| Auto-pull on start | `pwa/src/App.tsx` (`startSession`) |
| Brain bus (unchanged) | `brain/src/warp_compass_brain/bus/folder.py`; `cli.py:174` (`args.bus or s.bus_root`) |

### Config reference (names only — never paste secret values into git)
- **Apps Script script properties:** `ROOT_FOLDER_ID`, `SHARED_SECRET`.
- **Cloudflare Pages secrets:** `APPS_SCRIPT_URL`, `SYNC_SHARED_SECRET` (+ existing `DEEPSEEK_API_KEY`,
  `ELEVENLABS_API_KEY`). Non-secret vars in `pwa/wrangler.toml`.
- **Local dev (`npm run dev:cf`):** the same four in `pwa/.dev.vars` (git-ignored).
- **Brain:** `BUS_ROOT` in `brain/.env` = the on-disk Drive path.

### End-to-end test (run to confirm health)
1. Open the deployed PWA → run a short session → **End & save** → expect **“Sent to the brain.”**
   (the download-fallback button means push failed — see troubleshooting).
2. Laptop: the JSON appears under `…\warp-compass\participants\{id}\answer_logs\` within seconds.
3. `cd brain && uv run python -m warp_compass_brain.cli run-round` → ingests + writes a brief into
   `participants/{id}/briefs/`.
4. Reopen the PWA → **Start a session** → expect **“Loading your brief…”** then a warm start.

### Troubleshooting (symptom → likely cause → fix)
| Symptom | Likely cause | Fix |
|---|---|---|
| PWA shows the **download fallback** ("couldn't reach the brain") | Pages secret missing, or Apps Script rejected the secret | Confirm `APPS_SCRIPT_URL` + `SYNC_SHARED_SECRET` in Pages **= exactly** the script's `SHARED_SECRET`; check the Function log |
| Response `{"ok":false,"error":"unauthorized"}` | Secret mismatch between Pages and script properties | Re-set both to the same value (rotate) |
| `{"error":"server_misconfigured"}` from `/sync/*` | Pages secrets not set for this environment (Prod vs Preview) | Add both secrets to **both** Production and Preview |
| Push OK but file **never appears on laptop** | Folder is stream-only, or wrong `BUS_ROOT` | Mark the folder **Available offline**; confirm `BUS_ROOT` = the exact local path |
| `{"written":false,"reason":"exists"}` | Same `session_id` pushed twice (write-once by design) | Not an error — the log already exists; the graph is idempotent anyway |
| `run-round` sees 0 new logs | Drive not synced yet, or logs already in `profile.ingested_logs` | Wait for sync; re-ingest is safe (idempotent) |
| Brief never loads on start (always cold) | No brief yet (no `run-round` since the session), or pull failed | Run `run-round`; check `/sync/brief` returns `{"ok":true,"brief":…}` |
| `{"error":"...ROOT_FOLDER_ID..."}` | Script property unset | Set `ROOT_FOLDER_ID` to the Drive folder id |
| Web App URL 404 / stale | A *new deployment* minted a new `/exec` URL | Prefer *Manage deployments → edit → New version* (keeps URL), or update `APPS_SCRIPT_URL` |

### Hard constraints to respect when changing this
- **Answer Logs are write-once** (immutable source of truth) — never make `doPost` overwrite them.
- **`profile.json` writes MERGE** — never clobber the brain's `ingested_logs` resume key.
- **Apps Script always returns HTTP 200**; success/failure is in the JSON `ok` field (the Pages Fn maps
  it to a real status). Don't rely on the Apps Script HTTP status.
- **Secrets never in the browser or in git** — only in Pages env + script properties.
- **Edit proxy/CORS behaviour only in `_shared.ts`/`_sync.ts`.**

---

## Steps (implementation — DONE; kept for reference)

### 1. Laptop ← Drive: zero-code path (do this first; it already works)
- Install **Google Drive for Desktop** on the owner's laptop; get the engagement folder onto disk —
  either **Mirror files** mode, or **Stream** mode with the folder right-clicked → **Available
  offline** (the owner uses Stream + Available offline; confirmed it stays synced) — so files are real
  on disk for Python to read (stream-only won't work).
- Point the brain at it: set `bus_root` (config `Settings.bus_root`, default `./_bus`) to the mirrored
  path, e.g. `G:\My Drive\warp-compass\discovery-engagement`. **No `FolderBus` change.**
- Verify: drop a hand-made `participants/p_test/answer_logs/s_test.json` in Drive on another machine →
  it appears on the laptop → `cli run-round` ingests it and writes a brief back → the brief syncs up.
- *(Deferred alt, only if the owner refuses Drive Desktop):* a brain-side `DriveBus(Bus)` using the
  Drive API + a service account. More code + OAuth; **not** recommended for the prototype — Drive
  Desktop is the lightweight win and keeps `FolderBus` as the one implementation.

### 2. The Apps Script Web App (`apps-script/`)
Check the script **into the repo** as the source of the deployed web app.
- `appsscript.json` — manifest; `webapp.executeAs: USER_DEPLOYING` (the owner), `access: ANYONE`.
- `Code.gs`:
  - `doPost(e)` — body `{ participant_id, profile?, answer_log }` + a shared-secret header/field.
    Resolve/create the Drive folder tree `participants/{participant_id}/answer_logs/`; **write-once**:
    if `{session_id}.json` exists, refuse (or suffix), never overwrite (immutability). Upsert
    `profile.json` (merge display name, created_at). Return `{ ok, written }`.
  - `doGet(e)` — query `{ participant_id, secret, [since] }`. Return the **latest** brief JSON from
    `participants/{participant_id}/briefs/` (by name/mtime), or `{ brief: null }` if none.
  - Helpers: secret check (reject otherwise), a small `getOrCreateFolder(path)`, size guard.
- Deploy: **Deploy → New deployment → Web app**, *Execute as: Me*, *Who has access: Anyone*. Copy the
  `/exec` URL. Re-deploy = new version (note: the URL is stable per deployment; document re-deploy in
  the README). Add `apps-script/README.md` with these click-steps + how to rotate the secret.

### 3. Cloudflare Pages Function `pwa/functions/sync.ts` (the clean front door)
Mirror `_shared.ts` style.
- `POST /sync/answer-log` → forward body to the Apps Script `/exec` with the secret injected
  server-side; return its result. `GET /sync/brief?participant_id=…` → forward as a GET.
- Secrets/vars: `APPS_SCRIPT_URL`, `SYNC_SHARED_SECRET` (Pages dashboard secrets, like the existing
  API keys); add to `pwa/wrangler.toml` non-secret notes + `pwa/.dev.vars.example`.
- **Why proxy instead of calling Apps Script from the browser:** (a) Apps Script `/exec` 302-redirects
  to `googleusercontent.com` and is awkward for browser CORS/preflight; (b) the shared secret stays
  off the client, so a random with the PWA URL can't spam the owner's Drive; (c) it's the same
  same-origin pattern as `/llm,/stt,/tts`, so dev (`npm run dev:cf`) and prod work unchanged.

### 4. PWA `RemoteBus` client + auto wiring (`pwa/src/sync/`)
- New `remote.ts`: `pushAnswerLog(log): Promise<void>` (POST `/sync/answer-log`) and
  `pullLatestBrief(participantId): Promise<SessionBrief | null>` (GET `/sync/brief`). Behind a small
  `RemoteBus` interface so it's testable (vitest) and swappable.
- **Wire into the flow (replace the manual hops):**
  - On session **close** → `pushAnswerLog(log)` automatically (with a spinner + retry). **Keep
    `downloadAnswerLog` as an offline fallback** (push failed → offer the download, queue for retry).
  - On **launch / new session** → `pullLatestBrief(participant_id)`; if present, start the runner with
    it (auto cross-pollination). Remove the manual file-pick from the happy path (keep `parseBriefFile`
    as the offline import fallback).
- `participant.ts` is unchanged (the stable `participant_id` is the routing key the endpoint needs).
- Optionally send `profile` (display name) on the first push so the registry shows a friendly name.

### 5. (Optional) Human-readable transcript Doc
In `doPost`, after writing the JSON, also create/update a Google Doc transcript in
`participants/{id}/transcripts/` (agent utterance + raw answer per entry). Pure convenience for the BA;
the brain ignores it. Gate behind a manifest flag so it's trivial to turn off.

### 6. Docs + decision
- `apps-script/README.md` (deploy + secret rotation), update `DEPLOY.md` (the two new Pages secrets +
  the Drive-Desktop one-time setup), update `docs/02-technical-approach.md §3.1/§13` to mark the bus as
  "networked via Apps Script + Drive Desktop", and append **ADR #27** (this approach + why Apps-Script-
  as-owner over browser Drive OAuth, why Drive Desktop over a `DriveBus`, why JSON-as-truth over Docs).
  Add a P11 row to `PROGRESS.md`.

---

## Files

```
apps-script/{Code.gs, appsscript.json, README.md}                        DONE — the Web App source + owner setup guide
pwa/functions/_sync.ts                                                    DONE — forwarder (handleSyncPush/handleSyncPull)
pwa/functions/sync/{answer-log.ts, brief.ts}                              DONE — Pages Function routes /sync/answer-log, /sync/brief
pwa/functions/_shared.ts                                                  DONE — Env += APPS_SCRIPT_URL, SYNC_SHARED_SECRET
pwa/{wrangler.toml, .dev.vars.example}                                    DONE — document the two new secrets
pwa/src/sync/{remote.ts, remote.test.ts, index.ts}                        DONE — RemoteBus client (+6 tests) + barrel export
pwa/src/{App.tsx, screens/SessionScreen.tsx}                             DONE — auto-pull on start / auto-push on close; manual fallback kept
brain/.env (BUS_ROOT → Drive-mirrored path)                              OWNER — config only, NO FolderBus code change
docs/02-technical-approach.md, docs/DECISIONS.md #27, DEPLOY.md, PROGRESS.md   docs
```

---

## Test plan
- **Endpoint unit (Pages Fn):** POST forwards body + injects secret; GET forwards `participant_id`;
  missing/<wrong> secret → 401; oversized body → 413. (vitest + a mocked Apps Script.)
- **RemoteBus (PWA, vitest):** `pushAnswerLog` posts the schema-valid log; `pullLatestBrief` parses a
  brief and returns `null` cleanly when none; push failure falls back to download without losing data.
- **Apps Script (manual + `clasp` if used):** write-once refuses to overwrite an existing
  `{session_id}.json`; first POST mints the folder tree + `profile.json`; `doGet` returns the latest
  brief; bad secret rejected.
- **End-to-end (the real win):** two phones (or two browser profiles) each finish a session → both logs
  land in Drive with **no manual step** → laptop `cli run-round` ingests both into the one graph and
  writes each persona's brief → each phone's next launch **auto-pulls its own** brief and is
  cross-pollinated by the other persona's input. No download, no file-pick, no copy anywhere.
- **Offline/failure:** kill the network at close → the log is queued + downloadable; reconnect → push
  succeeds, no double-write (idempotent on `session_id`).

## Done when
Any number of users, each with only the PWA link, run sessions whose Answer Logs reach the one brain and
whose next Session Briefs come back **entirely automatically** — the operator's only job is running
`cli run-round` (and even that can be a scheduled task). The `Bus` contract, the schemas, and the brain
pipeline are unchanged; only the transport became networked.

---

## Risks & decisions
- **Abuse of an "Anyone" web app.** Mitigate with the shared secret (held only in the Pages Function),
  a body-size cap, and write-once logs. Participant ids are client-minted (already true); a bad actor
  with the secret could still pollute — acceptable at prototype trust level; rotate the secret if leaked.
- **Apps Script quotas.** Generous for prototype scale (tens of users, a handful of sessions/day); note
  the daily URL-fetch / runtime limits in the README; the batch cadence (one round/day) stays well under.
- **Drive Desktop folder must be on disk, not stream-only.** Either Mirror mode or Stream + the folder
  set **"Available offline"** works (owner verified the latter). Documented in Step 1.
- **Immutability.** The endpoint must never overwrite an Answer Log (the source of truth). Briefs are
  overwrite-OK (latest wins). Enforced in `doPost`.
- **Re-deploy churn.** A new Apps Script deployment can change the `/exec` URL; keep the URL in a Pages
  secret so rotating it is a dashboard edit, not a PWA rebuild.
- **Decisions (locked 2026-07-01):**
  1. **Front door = Pages-Function proxy** (`pwa/functions/sync/*` → Apps Script). Secret hidden
     server-side, clean CORS, and it side-steps Apps Script's cross-origin 302 redirect (the Function
     follows it; a browser can't cleanly). Matches the existing key-proxy pattern.
  2. **Transcript Docs deferred.** JSON Answer Logs remain the sole canonical raw store; the optional
     Google-Doc human mirror (Step 5) is not built. Additive later behind the same `doPost`.
```
