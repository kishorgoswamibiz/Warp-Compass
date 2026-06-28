# Warp Compass — PWA (interaction plane)

The installable, voice-first conversation app (one codebase, Android + iOS). It runs the
**fast live runner** and holds **no graph** — all deep understanding is the brain's job.
React + Vite + TypeScript.

> **Status:** scaffold only. The live runner (Phase 5), host/proxy wiring (Phase 6), and
> voice (Phase 7) are specified in `../docs/plan/`. Track progress in `../PROGRESS.md`.

## Prerequisites
- Node 20+

## Develop
```bash
cd pwa
npm install
npm run dev        # http://localhost:5173
npm run build      # production build (installable PWA in dist/)
npm run preview    # preview the build
npm run typecheck
```

## Hard rules (from the design)
- **Never embed API keys.** All live calls (DeepSeek follow-ups, ElevenLabs STT/TTS) route
  through the Cloudflare **Worker** proxy in `../worker/`.
- The runner only ever **writes** the Answer Log (`../contracts/answer-log.schema.json`) and
  **reads** its Session Brief (`../contracts/session-brief.schema.json`). It never reads the graph.

## TODO before first real use
- Replace placeholder PWA icons (`icon-192.png`, `icon-512.png` referenced in the manifest).
- Build the session screen + mic capture (`getUserMedia`) — Phase 5/7.
