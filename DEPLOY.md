# Deploying Warp Compass

**One command to update, forever: `git push`.** This guide sets up a GitHub → Cloudflare Pages
pipeline so the app (PWA **and** its API key-proxy) deploys automatically on every push.

---

## What gets deployed (and what doesn't)

| Part | Where it runs | Deployed? |
|------|---------------|-----------|
| **PWA** (`pwa/`, the phone app) | Cloudflare Pages (static) | ✅ via this pipeline |
| **Key proxy** (`pwa/functions/`, `/llm` `/stt` `/tts`) | Cloudflare Pages **Functions** (same project, same origin) | ✅ via this pipeline |
| **Brain** (`brain/`, the Python graph engine) | Your laptop + Neo4j Desktop | ❌ runs locally only (by design — see `docs/02`) |
| `worker/` (standalone Worker) | optional | ❌ not needed; kept for a separate-origin/local setup |

The PWA calls `/llm`, `/stt`, `/tts` as **relative** paths. Because the Functions live in the same
Pages project, they share the PWA's origin — so the same code works in dev and prod with **no URLs to
configure**. API keys live only in the Functions (Cloudflare environment), never in the browser.

---

## One-time setup (~10 minutes)

### 1. Push the repo to GitHub
From the repo root:
```bash
git init                       # if not already a repo
git add -A
git commit -m "Warp Compass"
git branch -M main
git remote add origin https://github.com/<you>/warp-compass.git   # create this empty repo on github.com first
git push -u origin main
```
> Secrets are safe: `.gitignore` already excludes `brain/.env`, `**/.dev.vars`, `_state/`, `_bus/`,
> `node_modules/`, `dist/`. Nothing secret is committed. (Verify with `git status` before the first push.)

### 2. Connect Cloudflare Pages to the GitHub repo
In the Cloudflare dashboard → **Workers & Pages → Create → Pages → Connect to Git** → pick the repo, then set:

| Setting | Value |
|---|---|
| **Production branch** | `main` |
| **Root directory** | `pwa` |
| **Framework preset** | Vite |
| **Build command** | `npm run build` |
| **Build output directory** | `dist` |

(Functions are auto-detected from `pwa/functions/` — nothing to configure. The non-secret vars come
from `pwa/wrangler.toml`, already committed.)

### 3. Add the two secrets
Pages project → **Settings → Variables and secrets** → add (for **Production** *and* **Preview**):
- `DEEPSEEK_API_KEY`
- `ELEVENLABS_API_KEY`

(Same values as in `brain/.env`. Or from the CLI: `cd pwa && npx wrangler pages secret put DEEPSEEK_API_KEY`.)

### 4. Deploy + verify
The connect step kicks off the first build. When it's live (`https://warp-compass.pages.dev` or your
custom domain):
- `https://<your-url>/health` → `{"ok":true,...}`
- Open on a phone, **install** the PWA, run a session (text works immediately; voice works because
  the ElevenLabs key is set).

### 5. Lock down CORS (after you know the URL)
Edit `pwa/wrangler.toml` → set `ALLOWED_ORIGIN` from `"*"` to your Pages URL, then `git push`. Done.

---

## The ongoing workflow (this is the whole point)

```bash
# make changes, then:
git add -A && git commit -m "what changed" && git push
```
Cloudflare rebuilds and deploys automatically. Pushing to a **branch / PR** gets its own **preview
URL** to test before merging to `main`. No `wrangler deploy`, no manual steps.

**Before pushing**, optionally run the local checks:
```bash
cd pwa && npm run typecheck && npm run typecheck:functions && npm test && npm run build
```

---

## Local development

- **Full stack (closest to prod)** — Functions + PWA together:
  ```bash
  cd pwa
  cp .dev.vars.example .dev.vars     # then fill in the two keys (git-ignored)
  npm run dev:cf                      # wrangler pages dev in front of Vite
  ```
- **UI only / split** — plain Vite + the standalone Worker (`worker/`):
  ```bash
  cd worker && npm run dev            # wrangler dev on :8787 (reads worker/.dev.vars)
  cd pwa    && npm run dev            # Vite on :5173, proxies /llm,/stt,/tts → :8787
  ```

---

## Alternative: deploy from your machine (no GitHub)
If you ever want to push a build directly:
```bash
cd pwa
npx wrangler login                 # one time, interactive
npm run deploy                     # = npm run build && wrangler pages deploy dist
```
GitHub-connected auto-deploy is recommended for maintenance; this is just a manual fallback.

---

## Notes & gotchas
- **Editing the proxy:** all `/llm` `/stt` `/tts` logic is in `pwa/functions/_shared.ts` (single
  source of truth — the route files and the standalone `worker/` both import it). Change it there.
- **Changing the voice:** set `ELEVENLABS_VOICE_ID` in `pwa/wrangler.toml` (or the dashboard) and push.
  No code change. `eleven_v3` (model) gives more expressive speech if you want it.
- **The brain isn't deployed.** Generate the docs/process locally (`cd brain && uv run python -m
  warp_compass_brain.cli docgen`), run the daily sync round (`cli run-round`), etc. The PWA only
  produces Answer Logs; the brain ingests them on your laptop.
- **Rollbacks:** Cloudflare Pages keeps every deployment — roll back to any previous one from the
  dashboard in one click.
