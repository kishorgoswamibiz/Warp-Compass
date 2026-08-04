# Warp Compass — Operator Manual (laptop, after every round of mobile sessions)

**Who this is for:** you, the operator, running the brain on your laptop. Mobile users just talk to
the PWA; their Answer Logs arrive in your Google Drive **automatically** (Phase 11). Your job each
round is to run the brain over the new answers and let the updated briefs sync back out.

> **The whole job in one line:** *Open a terminal in `brain/` → run `run-round` → (optionally) `corroborate --apply` and `docgen`.*
> Users' next sessions then start warm on their own. Do this **once per round** (e.g. once a day),
> after people have done their sessions. **No database to start — the graph is a folder of
> Markdown files** (P12) at `brain\_graph\` on local disk (P14; only the Answer Logs and briefs
> live in the Drive-synced folder).

---

## 0. One-time prerequisites (already set up — verify only if something breaks)
- **`uv`** installed (Python package/venv manager).
- **`brain/.env`** contains `DEEPSEEK_API_KEY`, `ELEVENLABS_API_KEY`, and
  **`BUS_ROOT`** = the local path of the Drive-synced engagement folder
  (e.g. `BUS_ROOT=G:\My Drive\warp-compass`).
- **Google Drive for Desktop** running, with the engagement folder on disk (Mirror mode, **or** Stream
  mode + the folder set *Available offline*). This is how mobile Answer Logs reach the laptop and how
  briefs go back. **Offline-available is required, not a nicety** — stream-only makes every round
  hundreds of blocking network round-trips, and a round will either hang or die with
  `OSError [WinError 1450] Insufficient system resources` (see §5 Troubleshooting).
- **`GRAPH_ROOT`** in `brain/.env` pointing at **local disk** (`brain\_graph`). The graph used to
  default into the Drive folder; P14 moved it out, because the pipeline rewrites node files hard
  enough to exhaust Drive's filesystem driver. Nothing needs it on Drive — the phones never read it.
- *(No Neo4j / no Docker / no database server — removed in P12.)*

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

### Step 2 — Open a terminal in the `brain/` folder
```powershell
cd "C:\Users\Lenovo\Desktop\Warp Compass\brain"
```
> ⚠️ **All `uv`/Python commands must run from `brain/`.** Running elsewhere gives
> `No module named 'warp_compass_brain'`.

### Step 3 — (optional, 10s) sanity check
```powershell
uv run pytest -q
```
Expect **100 passed** (the whole suite runs with no services now). Skip if you're in a hurry.

### Step 4 — Run the round (the core step)
```powershell
uv run --extra vectors python -m warp_compass_brain.cli run-round
```
This does the whole cycle over the bus: **enumerate participants → register any new one → ingest each
NEW Answer Log into the graph → re-plan → write each persona's next Session Brief** into
their `briefs/` folder. It's **resumable** — already-ingested logs are skipped (tracked in each
`profile.json`), so re-running is safe and cheap.

> **`--extra vectors`**: uses local semantic embeddings for better dedup. **Pick one mode and stick
> with it** every round (always with, or always without). Mixing the two corrupts
> `brain/_state/vectors.sqlite` (see Troubleshooting).

### Step 5 — (recommended) promote confirmed knowledge + route conflicts
```powershell
uv run --extra vectors python -m warp_compass_brain.cli corroborate --apply
```
Confirms facts corroborated by ≥2 people and both-sided handoffs, and routes any conflicts as
reconciliation threads into the relevant people's next briefs. (Drop `--apply` to preview only.)

### Step 6 — (when you want the deliverable) generate the docs
```powershell
uv run --extra vectors python -m warp_compass_brain.cli docgen --out "..\deliverable.md"
```
Produces the **end-to-end process + per-role SOPs + problem register** as Markdown. Add
`--include-unverified` to also see not-yet-corroborated facts (marked as such). Default is
confirmed-only.

### Step 7 — Let everything sync back out
The briefs from Step 4 — and the updated graph files — are inside the Drive folder, so Google Drive
uploads them automatically. Confirm the Drive tray shows "up to date." **Nothing else to do** — each
user's next session auto-pulls their brief and starts warm.

That's the round. 🎉

---

## 1b. Who's in the engagement (new in P13)

Each person declares their **name and role once**, on their own device, the first time they open the
app. That declaration becomes their folder name and their fingerprint on every fact they contribute,
so the Drive tree and the graph both read in plain English:

```
%BUS_ROOT%\participants\
    rahul-mehta-business-analyst-3c1f\   ← was p_3f9a1c8e-…
        README.md            ← name, role, first/last seen, session count
        profile.json · answer_logs\ · briefs\
```

See the roster at any time:

```powershell
uv run python -m warp_compass_brain.cli list-participants
```

> **Ids are permanent.** A person's id is stamped into every fact they contribute, so it is never
> rewritten. If someone typos their name, they can correct it in the app — the *display* name
> updates everywhere, the id stays. That's intentional (ADR #29).

---

## 1c. Removing one person (a seat changes hands)

> **Which one do I want?**
> · One person leaves / a device changes hands → **this section**.
> · Wiping everything to start a fresh testing phase → **§1d**.
> · Just resetting the phone, keeping their answers → only Step 3 below.

**What removal does and doesn't do.** It moves their folder out of the engagement and records that
they've gone. **It does not touch the knowledge graph** — everything they told you stays (ADR #30),
because context is shared (one activity routinely carries facts from a Business Analyst *and* a
Project Manager) and because a half-described process is still an open question about *your
business*, which didn't leave. Any node only they ever touched becomes an **orphan thread**, offered
to whoever is still here, phrased in the third person: *"A colleague described 'Reconcile invoices'
before they left, but we never captured what kicks it off. Do you know how that part works?"* The
moment someone answers, it stops being orphaned.

It takes about a second and **costs nothing** — no LLM calls.

### Step 1 — Find their id

```powershell
cd "C:\Users\Lenovo\Desktop\Warp Compass\brain"
uv run python -m warp_compass_brain.cli list-participants
```
```
  ●  Asha Rao — Sales Rep  `asha-rao-sales-rep-9f21`   logs: 4  briefs: 2  last seen 2026-07-28
  ●  Rahul Mehta — Business Analyst  `rahul-mehta-business-analyst-3c1f`   logs: 3  briefs: 1
```
Or just look at the folder names in `%BUS_ROOT%\participants\` — since P13 they're readable.

### Step 2 — Remove them (pick ONE path)

#### Path A — the command (recommended)

```powershell
# always preview first — this changes nothing
uv run python -m warp_compass_brain.cli retire-participant --id rahul-mehta-business-analyst-3c1f --dry-run

# then do it
uv run python -m warp_compass_brain.cli retire-participant --id rahul-mehta-business-analyst-3c1f
```

Add `--hard-delete` to delete the folder instead of archiving it. Google Drive's 30-day trash is
the backstop either way.

#### Path B — entirely by hand, in Windows Explorer

Do this if the CLI isn't available, or you just prefer watching the files move.

1. **Open** `%BUS_ROOT%\participants\` (e.g. `G:\My Drive\warp-compass\participants\`).
2. **Create** `%BUS_ROOT%\_archive\` if it isn't there yet.
3. **Move** the folder `rahul-mehta-business-analyst-3c1f\` into `_archive\`, and **rename** it to
   include today's date so the archive sorts chronologically:
   ```
   %BUS_ROOT%\_archive\rahul-mehta-business-analyst-3c1f__2026-07-28\
   ```
   *(Or simply delete the folder if you don't want a copy — Drive keeps it in trash for 30 days.)*
4. **Create or edit** `%BUS_ROOT%\_retired.json` in Notepad. If the file doesn't exist, create it
   with exactly this, swapping in the id:
   ```json
   {
     "retired": [
       { "id": "rahul-mehta-business-analyst-3c1f" }
     ]
   }
   ```
   If it already exists, add another `{ "id": "..." }` object to the `retired` list (mind the comma
   between entries). **Only `id` is required.** The extra fields below just make
   `list-participants` read nicely:
   ```json
   {
     "retired": [
       {
         "id": "rahul-mehta-business-analyst-3c1f",
         "display_name": "Rahul Mehta",
         "role_title": "Business Analyst",
         "retired_at": "2026-07-28T09:12:00+00:00"
       }
     ]
   }
   ```
5. **Wait for the Drive tray icon** to show "up to date."

> **If you skip step 4, nothing breaks.** The next `run-round` prints a loud warning — *"persona X
> has no participant folder and no retirement record"* — and writes them no brief. The manual path
> is fail-safe: the worst outcome is noise, never lost data or a resurrected folder.
>
> **A corrupt `_retired.json` is also safe** — it's read tolerantly, treated as "nobody retired",
> and the loud warning tells you. Just don't hand-edit it while a round is running.

### Step 3 — On the device

The new person taps **"Not you? Switch user"** on the landing screen, then declares their own name
and role. They get a fresh folder and start clean.

This is device-local only — it never deletes anything from the records, which is exactly why Steps 2
and 3 are separate. Handing over a phone without Step 2 is fine (the old person's data simply
stays); doing Step 2 without Step 3 means the old device would recreate its folder on its next push.

### Step 4 — Confirm

```powershell
uv run python -m warp_compass_brain.cli list-participants
```
They should now show as `⏸ … retired <date>`. Run your next round normally — no brief is written for
them, their folder is **not** recreated, and their leftover questions start appearing at the bottom
of everyone else's briefs.

### Bringing someone back

Move their folder from `%BUS_ROOT%\_archive\<id>__<date>\` back to `%BUS_ROOT%\participants\<id>\`
(drop the `__<date>` suffix from the name). That's all — the folder is the registry, so a leftover
entry in `_retired.json` is ignored automatically once the folder exists again. Tidy the entry if
you like; nothing depends on it.

---

## 1d. Wiping everything to start a fresh testing phase

Use this before handing the app to a wider team, or between test rounds when you want a clean slate.
**Everything below is destructive and intentional.** Nothing is recoverable except through Google
Drive's 30-day trash — so if any of it matters, copy `%BUS_ROOT%` somewhere safe first.

### Path A — the command (recommended)

```powershell
cd "C:\Users\Lenovo\Desktop\Warp Compass\brain"

# preview — changes nothing, prints exactly what would go
uv run python -m warp_compass_brain.cli reset-engagement --dry-run

# do it (refuses to run without --yes)
uv run python -m warp_compass_brain.cli reset-engagement --yes
```

Add `--keep-archive` to preserve `_archive\` (previously retired people's folders).

That clears: every participant folder · the whole graph · `_retired.json` · `_archive\` · the local
vector and review-queue state.

> **Clearing the vectors along with the graph is the point of doing it in one command.** A graph
> rebuilt from scratch against a stale embedding table throws confusing `matmul`/shape errors rather
> than an obvious "you missed a step."

### Path B — entirely by hand

**In the Drive folder** (`%BUS_ROOT%`, e.g. `G:\My Drive\warp-compass\`):

1. Delete **everything inside** `participants\` (keep the `participants` folder itself — or don't,
   it's recreated automatically).
2. Delete the whole `graph\` folder.
3. Delete `_retired.json`.
4. Delete the `_archive\` folder.
5. **Wait for the Drive tray icon to show "up to date"** — the deletions have to reach Google Drive,
   not just your disk. Deleted files sit in Drive's trash for 30 days.

**In the repo** (`C:\Users\Lenovo\Desktop\Warp Compass\brain\_state\`):

6. Delete `vectors.sqlite`.
7. Delete `quarantine.jsonl` and `pending_taxonomy.jsonl` if they exist.

   PowerShell equivalent for steps 6–7:
   ```powershell
   Remove-Item "C:\Users\Lenovo\Desktop\Warp Compass\brain\_state\*" -Force -ErrorAction SilentlyContinue
   ```

### Both paths — the two steps no script can do for you

8. **Clear every test device.** Open the app on each phone/browser you've tested with and tap
   **"Not you? Switch user"** (or clear the site's data in browser settings).

   This is **not cosmetic**. A device still holding a pre-reset identity will **recreate its
   participant folder** on its next push, quietly repopulating the bus you just cleaned. Do this
   before anyone opens the app again.

9. **Deal with `deliverable.md`.** It's committed to the repo and currently holds old test data
   (`persona.demo`, `p_alice`). Either regenerate it —
   ```powershell
   uv run --extra vectors python -m warp_compass_brain.cli docgen --out "..\deliverable.md"
   ```
   — or blank it, so a new teammate doesn't read it as a real sample.

### Confirm it's clean

```powershell
uv run python -m warp_compass_brain.cli list-participants   # "No participants yet."
uv run --extra vectors python -m warp_compass_brain.cli run-round
```
`run-round` should report zero participants and write no briefs. Once someone runs a session,
`brain\_graph\index.md` starts filling in again from zero.

### Before the team installs

- The Cloudflare Pages **Production** secrets are set: `DEEPSEEK_API_KEY`, `ELEVENLABS_API_KEY`,
  `APPS_SCRIPT_URL`, `SYNC_SHARED_SECRET`.
- Each tester **fully closes and reopens** the PWA once, so the service worker takes the new build
  instead of serving a cached one.
- Send them the URL and one line of instruction: *"Open it, type your name and role once, then just
  talk to it."* There is nothing else for them to set up.

---

## 2. Reading the knowledge graph (new in P12)

The graph itself is now **human-readable Markdown** at `GRAPH_ROOT` — on local disk since P14:
```
brain\_graph\
    index.md            ← start here: counts + links per node type
    roles\ · activities\ · systems\ · artifacts\ · events\ · rules\ · problems\ · ...
```
Every node is one file: YAML frontmatter (type, keywords, description, status, provenance, edges)
plus a generated body with timestamped **Facts**, and two-way **Links / Backlinks** (`[[node-id]]`).
Open any file in a text editor. It is no longer browsable from drive.google.com — use `git log`
on `brain/_graph/` instead, which gives you per-node history the Drive copy never had.

> **Don't hand-edit the graph files** — the pipeline owns them and regenerates their bodies on every
> write. They're for *reading* (you, other agents, the docgen). The graph stays re-derivable from
> the immutable Answer Logs either way.

---

## 3. How to know it worked
- **Step 4 output** lists each participant and how many logs were ingested (`created / merged / edges`),
  and `0` new for anyone with nothing new (that's correct — resume working).
- New/updated `*.json` files appear under `participants/<id>/briefs/`.
- New/updated `*.md` files appear under `graph\` (check `graph\index.md` counts went up).
- Reopening the PWA as a user shows **"Loading your brief…"** then starts warm (not cold).
- `docgen` output reflects the latest answers.

Quick read-only peeks (no writes):
```powershell
uv run python -m warp_compass_brain.cli completeness --threads   # scores + what's still missing
uv run python -m warp_compass_brain.cli plan --persona <persona_id>   # preview one brief
```

---

## 4. Useful commands (reference)
All from `brain/`, prefixed with `uv run [--extra vectors] python -m warp_compass_brain.cli`:

| Command | What it does |
|---|---|
| `run-round [--bus PATH] [--session ID]` | The full round (Step 4). `--bus` overrides `BUS_ROOT`. |
| `corroborate [--apply]` | Cross-person confirmation + conflict routing (Step 5). |
| `docgen [--include-unverified] [--out FILE]` | Generate the deliverable docs (Step 6). Since P15c this includes a **Gaps & Recommendations** section: cross-level misalignments (both accounts quoted), structural findings, and open questions. |
| `completeness [--threads]` | Score the graph vs the ontology; list open threads. |
| `coverage [--json]` | **Stage x role matrix (P15b) — "who do we invite next?"** Flags any lifecycle stage nobody who works in it has been interviewed about. |
| `seed-roles [--dry-run] [--roles PATH]` | Seed `contracts/roles.json` into the graph. **Run before the first round**, and again after editing the registry (P15a). |
| `plan [--persona ID] [--session ID]` | Emit per-persona Session Brief(s) from the graph. |
| `ingest-log <path>` | Ingest a single Answer Log file by path (manual one-off). |
| `check-models` | List which DeepSeek models your key can access. |
| `list-participants` | Who's in the engagement — live, then retired (§1b). |
| `retire-participant --id ID [--dry-run] [--hard-delete]` | Remove one person; the graph is untouched (§1c). |
| `reset-engagement --yes [--dry-run] [--keep-archive]` | **Destructive:** wipe everything and start clean (§1d). |

---

## 5. Troubleshooting
| Symptom | Cause → Fix |
|---|---|
| `No module named 'warp_compass_brain'` | You're not in `brain/`. `cd` into it and re-run. |
| `run-round` sees no participants / 0 logs | Drive hasn't synced, or wrong `BUS_ROOT`. Check the folder in Explorer; confirm files are on disk (available offline); verify `BUS_ROOT` in `brain/.env`. |
| `OSError [WinError 1450] Insufficient system resources` | **Google Drive's filesystem driver gave up**, not your laptop. Once its request pool is exhausted every operation on `G:` fails — including `stat` and `mkdir` on folders that plainly exist. Fix, in order: (1) set the engagement folder **Available offline** (or switch Drive to *Mirror files*) — this is the actual fix; (2) confirm `GRAPH_ROOT` in `brain/.env` points at local disk, not into the Drive folder; (3) quit and relaunch Google Drive to reset the driver; (4) close memory hogs — the failure needs both drive churn *and* low free RAM. Since P14 the brain retries these automatically, so you'll usually see `[fs-retry] WARNING: … sync drive busy, retrying` instead of a crash. Re-running is always safe: done logs are skipped. |
| `run-round` hangs for minutes with no output | Same root cause as the row above, but Drive is *blocking* rather than erroring, so retries can't help. Ctrl-C, make the folder available offline, re-run. Nothing is lost — the round is resumable. |
| `[fs-retry] WARNING: … sync drive busy, retrying` on most rounds | The round survived, but the Drive folder is still stream-only. Set it **Available offline**. Raise `FS_RETRY_ATTEMPTS` in `brain/.env` only as a stopgap. |
| `[okf-store] WARNING: skipping unreadable node file …` | A graph file got corrupted (e.g. a bad hand-edit or an interrupted write). The round continues without it. Fix: `git checkout` the file if `brain/_graph/` is committed, or delete it and rebuild from Answer Logs (clear `ingested_logs` in the affected `profile.json`, re-run `run-round`). |
| Graph looks wrong / want a clean rebuild | The graph is **re-derivable**: delete `brain\_graph\`, clear each participant's `ingested_logs` in `profile.json`, then `run-round` (costs LLM calls). |
| `matmul`/shape error on ingest | Mixed embedder dimensions in `brain/_state/vectors.sqlite`. Delete that file and re-run (the graph + raw logs are untouched — vectors rebuild). Then always use the **same** `--extra vectors` choice. |
| Extractor returned empty / non-JSON | Transient DeepSeek hiccup. Just re-run `run-round` (it's resumable; done logs are skipped). |
| `429` / rate limit from DeepSeek | Wait a moment and re-run; the round resumes where it stopped. |
| Users still see the old app / "Import a brief file" always | Their installed PWA is on a **cached build**. Fully close & reopen the app (or reload twice); the service worker auto-updates. The import button now appears **only** when the auto-pull fails. |
| A user's session shows the **Download Answer Log** fallback | Their push couldn't reach the sync endpoint. Check the two Cloudflare Pages secrets (`APPS_SCRIPT_URL`, `SYNC_SHARED_SECRET`) are set for **Production**; see `docs/plan/phase-11-drive-sync.md` runbook. The user can download + you drop the file into their `answer_logs/` manually as a stopgap. |
| Still have old data in Neo4j from before P12 | One-off migration: `uv run --with neo4j python ..\scripts\migrate_neo4j_to_okf.py` (Neo4j must be running once more for the copy). Or just rebuild from Answer Logs (above). Then uninstall Neo4j Desktop. |
| `run-round` warns *"persona X has no participant folder … and no retirement record"* | The graph holds their knowledge but the bus doesn't have them. Almost always Drive hasn't synced their folder down yet — check Explorer and re-run. If they really have left, `retire-participant --id X` so the round stops asking. **No brief was written**, so nothing is lost by re-running. |
| An archived participant's folder keeps coming back | You're on a pre-P13 build. Update; P13 stopped `run-round` recreating folders for personas that aren't on the bus. |
| A user is asked their name/role again | Their device's identity was cleared (Switch user, cleared site data, or a fresh install/browser). Re-declaring mints a **new** id and a new folder. Retire the old one — otherwise the same human exists as two personas, and cross-persona corroboration can read their two halves as two independent voices confirming each other. |
| A restored participant gets no briefs | Fixed in P13 — a folder that exists overrides a stale `_retired.json` entry. If you're on an older build, delete their entry from `%BUS_ROOT%\_retired.json`. |
| Orphan threads keep coming back round after round | Nobody has answered them yet, and the highest-priority ones re-surface each round. That's intended. To turn the pool down or off, set `PLANNER_ORPHAN_MAX=1` (or `0`) in `brain/.env`. |
| Someone typo'd their name at onboarding | Harmless. The id is permanent by design, but the display name is what appears in `README.md`, the roster, and the deliverable — correcting it in the app propagates on their next sync. |

---

## 6. Rules of thumb
- **One round per round of sessions** (e.g. daily): collect all → `run-round` → briefs go back. A user's
  second session the same day won't see others' input until the next round. This sequencing is
  intentional (cross-pollination lands after a batch).
- **Answer Logs are immutable** — never hand-edit them. The graph is **re-derivable** from them: if the
  extractor/ontology improves, you can rebuild the graph by re-ingesting, no re-interviewing.
- **Read the graph freely, never hand-edit it.** Let the pipeline own the files.
- **Keep the embedder mode consistent** every round (`--extra vectors` or not — don't mix).
- The **deliverable** (`docgen`) is generated on demand; run it whenever you want the current picture.

---
*Deeper reference: `docs/plan/phase-12-okf-store.md` (the OKF graph store + why Neo4j was removed),
`docs/plan/phase-11-drive-sync.md` (sync architecture + debugging runbook), `PROGRESS.md` (build
state), `apps-script/README.md` (Google setup), `DEPLOY.md` (PWA deploy).*
