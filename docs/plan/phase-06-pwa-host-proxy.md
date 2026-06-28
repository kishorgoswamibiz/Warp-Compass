# Phase 6 — PWA shell + Cloudflare Pages host + Worker proxy

> **Status: ✅ DONE (code + local verify; 2026-06-28, `agent:opus-p6`).** Worker `/llm` forwarder
> implemented (`worker/src/index.ts`) — injects `DEEPSEEK_API_KEY` + model, forwards to DeepSeek,
> CORS-locked; live-verified (`/health` 200, `/llm` returns a real `deepseek-v4-flash` completion).
> PWA session UI (`pwa/src/App.tsx`, `pwa/src/screens/SessionScreen.tsx`) drives the P5 `Runner`
> via `WorkerLLMProvider` (relative `/llm`); Vite dev-proxies `/llm,/stt,/tts → :8787`. Real PWA
> icons generated (`pwa/scripts/gen-icons.mjs` → `public/icon-{192,512}.png` + `favicon.svg`).
> `npm run build` produces an installable PWA (manifest + SW + precached icons); typecheck + 6
> tests clean; worker typecheck clean. **Full seam Runner→Worker→DeepSeek verified.** ADR #19.
> **Owner action remaining:** `wrangler deploy` + connect Cloudflare Pages to `pwa/dist`, set
> `ALLOWED_ORIGIN` to the Pages URL, `wrangler secret put DEEPSEEK_API_KEY` (needs your CF account).

## Context Card — read THIS, skip the source
- **Data shapes (authoritative):** `contracts/session-brief.schema.json`, `contracts/answer-log.schema.json`. TS mirrors live in `pwa/src/runner/types.ts`.
- **Runner public API** (browser-safe) @ `pwa/src/runner/index.ts`:
  - `new Runner(brief: SessionBrief, llm: LLMProvider, clock: RunnerClock, opts?: {participantId?})`
  - `runner.start(): string` · `runner.respond(answer): Promise<TurnResult>` · `runner.close(): string`
  - `runner.log.build(): AnswerLog` · `runner.session` (cursor/covered state)
  - `RunnerClock = { now(): string }` (ISO-8601) · `TurnResult = { utterance, decision, effectiveAction }`
- **Production LLM seam** @ `pwa/src/runner/llm/worker.ts`: `new WorkerLLMProvider({ baseUrl?, path? })` —
  POSTs `{ messages:[{role,content}], temperature, response_format:{type:"json_object"} }` to `${baseUrl}/llm`
  and expects an **OpenAI-shaped** reply `{ choices:[{ message:{ content } }] }`. (Do NOT ship `DirectDeepSeekProvider`.)
- **Worker** @ `worker/src/index.ts`: `/llm` is a **501 stub** to implement; `Env = { DEEPSEEK_API_KEY, ELEVENLABS_API_KEY, DEEPSEEK_BASE_URL, ALLOWED_ORIGIN }`; `cors(env)` + `json(body,status,env)` helpers already exist. Forward to `POST ${DEEPSEEK_BASE_URL}/chat/completions` with header `Authorization: Bearer <key>`; the **worker** injects `model` (live id **`deepseek-v4-flash`**, CONFIRMED) + key. Secrets local: `worker/.dev.vars`; vars in `worker/wrangler.toml`.
- **Theme:** `docs/THEME.md` + `pwa/src/styles/theme.css` (`wc-*` classes). `pwa/src/App.tsx` is a placeholder shell to replace.
- **Dev proxy:** add `server.proxy["/llm"] = "http://localhost:8787"` in `pwa/vite.config.ts` so the dev PWA reaches the Worker.
- **Run:** PWA from `pwa/`: `npm run dev` (5173) · `npm run build` · `npm run typecheck` · `npm test`. Worker from `worker/`: `npm run dev` (wrangler, 8787). Deploy (`wrangler deploy` + Pages) is an **owner action** (needs their Cloudflare auth).

**Goal:** Wrap the typed runner in the installable app, host it on Cloudflare Pages, and route all
live calls through the Worker key proxy. Still text (voice is P7).

**Depends on:** P5. **Package:** `pwa`, `worker`.

## Steps
1. **PWA shell** (`pwa`): session screen (uses the P5 runner), brief-driven conversation view,
   typed input, pause/resume, graceful close. Apply the theme (`docs/THEME.md`). Real PWA icons.
2. **Install & offline:** confirm `vite-plugin-pwa` manifest + service worker; installable on
   Android + iOS; app shell works offline (live calls obviously need network).
3. **Worker `/llm`** (`worker/src/index.ts`): implement the DeepSeek forwarder — inject
   `DEEPSEEK_API_KEY`, forward to `${DEEPSEEK_BASE_URL}` (OpenAI-compatible), return the response.
   CORS locked to the Pages origin. Plain HTTP (turn-based; no streaming needed, `02 §3.3`).
4. **Wire the runner** to call the Worker `/llm` instead of any direct LLM access. **No keys in
   the browser** — verify via network inspection.
5. **Deploy:** Cloudflare Pages for `pwa/dist`; `wrangler deploy` for the Worker; set
   `ALLOWED_ORIGIN` + secrets.

## Files
`pwa/src/{App.tsx, screens/*, runner/*}`, `worker/src/index.ts`, deploy config.

## Test plan
- `npm run build` produces an installable PWA; Lighthouse PWA checks pass.
- A typed session in the deployed app drives DeepSeek **only** through the Worker (no key leaks).
- `/health` ok; `/llm` returns a real completion; CORS rejects other origins.

## Done when
The app is reachable via a link, installs on a phone, and runs a full typed session through the
proxy with keys never present client-side.
