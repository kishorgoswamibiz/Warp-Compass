# Warp Compass — Operator Manual (laptop, after every round of mobile sessions)

**Who this is for:** you, the operator, running the brain on your laptop. Mobile users just talk to
the PWA; their Answer Logs arrive in your Google Drive **automatically** (Phase 11). Your job each
round is to run the brain over the new answers and let the updated briefs sync back out.

> **The whole job in one line:** *Start Neo4j → open a terminal in `brain/` → run `run-round` → (optionally) `corroborate --apply` and `docgen`.*
> Users' next sessions then start warm on their own. Do this **once per round** (e.g. once a day),
> after people have done their sessions.

---

## 0. One-time prerequisites (already set up — verify only if something breaks)
- **Neo4j Desktop** installed, with a local database created and a password set in `brain/.env`.
- **`uv`** installed (Python package/venv manager).
- **`brain/.env`** contains `DEEPSEEK_API_KEY`, `ELEVENLABS_API_KEY`, `NEO4J_PASSWORD`, and
  **`BUS_ROOT`** = the local path of the Drive-synced engagement folder
  (e.g. `BUS_ROOT=G:\My Drive\warp-compass`).
- **Google Drive for Desktop** running, with the engagement folder on disk (Mirror mode, **or** Stream
  mode + the folder set *Available offline*). This is how mobile Answer Logs reach the laptop and how
  briefs go back.

If you ever move machines, redo these from `brain/README.md` + `apps-script/README.md`.

---

## 1. The round procedure (do these in order, every round)

### Step 1 — Make sure the new Answer Logs have synced down
Open the Drive folder in Explorer:
```
%BUS_ROOT%\participants\<someone>\answer_logs\
```
You should see the latest `s_*.json` files from today's sessions. If they aren't there yet, wait a
few seconds for Google Drive to sync (the Drive tray icon shows sync status). Files must be **on disk**
(green check / available offline), not cloud-only.

### Step 2 — Start Neo4j
Open **Neo4j Desktop** → **Start** your local database. (Data persists across restarts; you just press
Start after a reboot.)

### Step 3 — Open a terminal in the `brain/` folder
```powershell
cd "C:\Users\Lenovo\Desktop\Warp Compass\brain"
```
> ⚠️ **All `uv`/Python commands must run from `brain/`.** Running elsewhere gives
> `No module named 'warp_compass_brain'`.

### Step 4 — (optional, 10s) sanity check
```powershell
uv run pytest -m "not neo4j" -q
```
Expect **62 passed**. Skip if you're in a hurry.

### Step 5 — Run the round (the core step)
```powershell
uv run --extra vectors python -m warp_compass_brain.cli run-round
```
This does the whole cycle over the bus: **enumerate participants → register any new one → ingest each
NEW Answer Log into the one Neo4j graph → re-plan → write each persona's next Session Brief** into
their `briefs/` folder. It's **resumable** — already-ingested logs are skipped (tracked in each
`profile.json`), so re-running is safe and cheap.

> **`--extra vectors`**: uses local semantic embeddings for better dedup. **Pick one mode and stick
> with it** every round (always with, or always without). Mixing the two corrupts
> `brain/_state/vectors.sqlite` (see Troubleshooting).

### Step 6 — (recommended) promote confirmed knowledge + route conflicts
```powershell
uv run --extra vectors python -m warp_compass_brain.cli corroborate --apply
```
Confirms facts corroborated by ≥2 people and both-sided handoffs, and routes any conflicts as
reconciliation threads into the relevant people's next briefs. (Drop `--apply` to preview only.)

### Step 7 — (when you want the deliverable) generate the docs
```powershell
uv run --extra vectors python -m warp_compass_brain.cli docgen --out "..\deliverable.md"
```
Produces the **end-to-end process + per-role SOPs + problem register** as Markdown. Add
`--include-unverified` to also see not-yet-corroborated facts (marked as such). Default is
confirmed-only.

### Step 8 — Let the briefs sync back out
The briefs written in Step 5 are inside the Drive folder, so Google Drive uploads them automatically.
Confirm the Drive tray shows "up to date." **Nothing else to do** — each user's next session auto-pulls
their brief and starts warm.

That's the round. 🎉

---

## 2. How to know it worked
- **Step 5 output** lists each participant and how many logs were ingested (`created / merged / edges`),
  and `0` new for anyone with nothing new (that's correct — resume working).
- New/updated `*.json` files appear under `participants/<id>/briefs/`.
- Reopening the PWA as a user shows **"Loading your brief…"** then starts warm (not cold).
- `docgen` output reflects the latest answers.

Quick read-only peeks (no writes):
```powershell
uv run python -m warp_compass_brain.cli completeness --threads   # scores + what's still missing
uv run python -m warp_compass_brain.cli plan --persona <persona_id>   # preview one brief
```

---

## 3. Useful commands (reference)
All from `brain/`, prefixed with `uv run [--extra vectors] python -m warp_compass_brain.cli`:

| Command | What it does |
|---|---|
| `run-round [--bus PATH] [--session ID]` | The full round (Step 5). `--bus` overrides `BUS_ROOT`. |
| `corroborate [--apply]` | Cross-person confirmation + conflict routing (Step 6). |
| `docgen [--include-unverified] [--out FILE]` | Generate the deliverable docs (Step 7). |
| `completeness [--threads]` | Score the graph vs the ontology; list open threads. |
| `plan [--persona ID] [--session ID]` | Emit per-persona Session Brief(s) from the graph. |
| `ingest-log <path>` | Ingest a single Answer Log file by path (manual one-off). |
| `check-models` | List which DeepSeek models your key can access. |

---

## 4. Troubleshooting
| Symptom | Cause → Fix |
|---|---|
| `No module named 'warp_compass_brain'` | You're not in `brain/`. `cd` into it and re-run. |
| `run-round` sees no participants / 0 logs | Drive hasn't synced, or wrong `BUS_ROOT`. Check the folder in Explorer; confirm files are on disk (available offline); verify `BUS_ROOT` in `brain/.env`. |
| Connection refused / Neo4j errors | Neo4j Desktop database isn't **Started**. Start it (Step 2). |
| `matmul`/shape error on ingest | Mixed embedder dimensions in `brain/_state/vectors.sqlite`. Delete that file and re-run (the graph + raw logs are untouched — vectors rebuild). Then always use the **same** `--extra vectors` choice. |
| Extractor returned empty / non-JSON | Transient DeepSeek hiccup. Just re-run `run-round` (it's resumable; done logs are skipped). |
| `429` / rate limit from DeepSeek | Wait a moment and re-run; the round resumes where it stopped. |
| Users still see the old app / "Import a brief file" always | Their installed PWA is on a **cached build**. Fully close & reopen the app (or reload twice); the service worker auto-updates. The import button now appears **only** when the auto-pull fails. |
| A user's session shows the **Download Answer Log** fallback | Their push couldn't reach the sync endpoint. Check the two Cloudflare Pages secrets (`APPS_SCRIPT_URL`, `SYNC_SHARED_SECRET`) are set for **Production**; see `docs/plan/phase-11-drive-sync.md` runbook. The user can download + you drop the file into their `answer_logs/` manually as a stopgap. |

---

## 5. Rules of thumb
- **One round per round of sessions** (e.g. daily): collect all → `run-round` → briefs go back. A user's
  second session the same day won't see others' input until the next round. This sequencing is
  intentional (cross-pollination lands after a batch).
- **Answer Logs are immutable** — never hand-edit them. The graph is **re-derivable** from them: if the
  extractor/ontology improves, you can rebuild the graph by re-ingesting, no re-interviewing.
- **Never edit the Neo4j graph by hand.** Let the pipeline own it.
- **Keep the embedder mode consistent** every round (`--extra vectors` or not — don't mix).
- The **deliverable** (`docgen`) is generated on demand; run it whenever you want the current picture.

---
*Deeper reference: `docs/plan/phase-11-drive-sync.md` (sync architecture + debugging runbook),
`PROGRESS.md` (build state), `apps-script/README.md` (Google setup), `DEPLOY.md` (PWA deploy).*
