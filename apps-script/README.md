# Warp Compass — Drive-sync Web App (owner setup)

This is the free, serverless bridge that connects every user's phone to the one brain — **without any
end user ever logging into Google**. The script runs under **your** Google account; the phones just
send JSON. You set this up **once**. After that, users only ever open the PWA link, and the daily
`cli run-round` on your laptop is the only thing you run.

```
Phone (PWA) ──▶ Cloudflare Pages Function (/sync/*) ──▶ THIS Web App (runs as you) ──▶ your Drive
                                                                                          │  Drive for Desktop
Laptop brain ◀── FolderBus (unchanged) ◀── mirrored /participants/{id}/... ◀──────────────┘
```

Everything the script needs is in this folder: `Code.gs` (the logic) and `appsscript.json` (the
manifest that makes it a public-anonymous web app).

---

## One-time setup — do these in order

### 1. Create the engagement folder in Google Drive
1. In [Google Drive](https://drive.google.com), create a folder, e.g. **`warp-compass`**. This is the
   **root** — the script creates `participants/{id}/…` inside it.
2. Open the folder and copy its **folder ID** from the URL:
   `https://drive.google.com/drive/folders/`**`1AbC…XyZ`** ← that trailing id is `ROOT_FOLDER_ID`.

### 2. Get that folder onto your laptop's disk (Google Drive for Desktop)
The brain reads real files, so the `warp-compass` folder must live on disk — **not** stream-only.
Either mode works:
1. Install **Google Drive for Desktop** and sign in with the **same** Google account.
2. Make the folder local, **one** of:
   - **Mirror files** mode (mirrors your whole Drive to disk), **or**
   - **Stream files** mode **+** right-click the `warp-compass` folder in the Drive (`G:\`) →
     **Offline access → Available offline** — keeps just that folder synced to disk. ✅ *This is what
     the owner uses; confirmed syncing.*
3. Note the local path, e.g. `G:\My Drive\warp-compass` (Windows). You'll point the brain at it.

### 3. Create the Apps Script project
1. Go to [script.google.com](https://script.google.com) → **New project**.
2. Replace the default `Code.gs` contents with **this repo's `apps-script/Code.gs`** (paste it whole).
3. Show the manifest: **Project Settings (⚙) → tick “Show ‘appsscript.json’ manifest file”**. Open
   `appsscript.json` in the editor and replace it with **this repo's `apps-script/appsscript.json`**
   (this is what sets *access: anyone, even anonymous*).

### 4. Set the two script properties
**Project Settings (⚙) → Script properties → Add script property**, add both:

| Property | Value |
|---|---|
| `ROOT_FOLDER_ID` | the folder id from step 1 |
| `SHARED_SECRET` | a long random string you invent (e.g. 32+ chars) — you'll reuse it in step 6 |

### 5. Deploy as a Web App
1. **Deploy → New deployment → ⚙ → Web app**.
2. **Execute as:** *Me (your account)* — this is what lets phones skip Google login.
3. **Who has access:** *Anyone* (shows as *Anyone, even anonymous*).
4. **Deploy** → Google asks you to **authorize** → grant the **Drive** permission (you'll see an
   “unverified app” screen because it's your own script — click *Advanced → Go to … (unsafe)*; it's
   your own code).
5. Copy the **Web app URL** — it ends in **`/exec`**. That's your `APPS_SCRIPT_URL`.

> Re-deploying: **Deploy → Manage deployments → ✎ (edit) → Version: New version → Deploy** keeps the
> **same** `/exec` URL. Creating a *New deployment* instead mints a new URL (you'd have to update the
> Cloudflare secret).

### 6. Give the two values to Cloudflare Pages
In the Cloudflare dashboard → your **warp-compass** Pages project → **Settings → Variables and
Secrets**, add two **secrets**:

| Secret | Value |
|---|---|
| `APPS_SCRIPT_URL` | the `/exec` URL from step 5 |
| `SYNC_SHARED_SECRET` | the **same** string you set as `SHARED_SECRET` in step 4 |

(Or via CLI from `pwa/`: `npx wrangler pages secret put APPS_SCRIPT_URL` and `… SYNC_SHARED_SECRET`.)
For local `npm run dev:cf`, put the same two into `pwa/.dev.vars` (see `pwa/.dev.vars.example`).

### 7. Point the brain at the mirrored folder
On the laptop, set the bus root to the Drive-mirrored path (from step 2). Either in `brain/.env`:
```
BUS_ROOT=G:\My Drive\warp-compass
```
…or pass `--bus "G:\My Drive\warp-compass"` to `cli run-round`. **No brain code changes** — `FolderBus`
reads/writes this tree and Drive syncs it in both directions.

---

## Verify it end-to-end
1. Open the deployed PWA, run a short session, tap **End & save** → you should see *“Sent to the
   brain.”* (not the download fallback).
2. On the laptop, the file appears at
   `…\warp-compass\participants\{your-id}\answer_logs\{session}.json` once Drive syncs (seconds).
3. Run `cd brain && uv run python -m warp_compass_brain.cli run-round` → it ingests and writes a brief
   into `participants/{your-id}/briefs/`.
4. Reopen the PWA and tap **Start a session** → it should say *“Loading your brief…”* and begin warm
   (cross-pollinated), with no manual import.

## Security notes
- The `SHARED_SECRET` is what stops a random person with the PWA URL from writing to your Drive — it
  lives only in Cloudflare (server-side) and in the script properties, never in the browser.
- **Rotate it** any time: change `SHARED_SECRET` in script properties **and** `SYNC_SHARED_SECRET` in
  Cloudflare to the same new value.
- Answer Logs are **write-once** — the script refuses to overwrite an existing `{session_id}.json`, so
  the immutable source of truth can't be tampered with through the endpoint.

## (Optional) manage the script from the CLI with `clasp`
If you'd rather not copy-paste: `npm i -g @google/clasp`, `clasp login`, then from `apps-script/`:
`clasp create --type webapp` (once) and `clasp push` to upload `Code.gs`/`appsscript.json`. Deploy
still happens from the web editor (steps 4-5) so you can set access + authorize.
