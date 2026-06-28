# Warp Compass — Worker (key proxy)

A trivial **key-injecting forwarder** on Cloudflare's free edge. The PWA calls it; it attaches
the secret API keys and forwards to **DeepSeek** (live follow-ups) and **ElevenLabs** (STT/TTS).
Keys never reach the browser.

> **Status:** scaffold — routing/CORS/health wired; `/llm`, `/stt`, `/tts` return 501.
> Implement forwarders in Phase 6/7 (`../docs/plan/`).

## Prerequisites
- Node 20+

## Develop
```bash
cd worker
npm install
# local secrets for `wrangler dev`: create worker/.dev.vars (git-ignored)
#   DEEPSEEK_API_KEY=...
#   ELEVENLABS_API_KEY=...
npx wrangler dev        # http://localhost:8787  (try /health)
```

## Deploy (free)
```bash
npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put ELEVENLABS_API_KEY
npx wrangler deploy
```
Then set `ALLOWED_ORIGIN` in `wrangler.toml` to your Cloudflare Pages URL.
