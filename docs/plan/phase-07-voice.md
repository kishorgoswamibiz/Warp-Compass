# Phase 7 — Voice (ElevenLabs STT/TTS via the proxy)

## Context Card — read THIS, skip the source
- **Integration point** @ `pwa/src/screens/SessionScreen.tsx`: the UI already drives `Runner` with typed input. Add mic capture → `/stt` → feed the transcript into the existing `runner.respond(text)`; speak `utterance` via `/tts`. Keep the **typed fallback** that's already there.
- **Worker pattern** @ `worker/src/index.ts`: `/stt` + `/tts` are **501 stubs** to implement. Reuse `cors(env)` + `json(body,status,env)` and mirror `handleLlm` (inject key → forward → pass body through). `Env` already has `ELEVENLABS_API_KEY`. Add ElevenLabs voice/model ids as `[vars]` in `worker/wrangler.toml` (like `DEEPSEEK_MODEL_LIVE`).
- **Provider seams** (new) @ `pwa/src/voice/{stt,tts}.ts`: mirror the `LLMProvider`/`WorkerLLMProvider` shape (`pwa/src/runner/llm/worker.ts`) — Worker-routed via the **relative** paths; the Vite dev proxy for `/stt,/tts → :8787` is **already wired** (P6). Browser TTS allowed in **dev only**.
- **ElevenLabs (confirm exact ids/endpoints before building):** STT = Scribe v2 (`POST https://api.elevenlabs.io/v1/speech-to-text`, multipart audio, header `xi-api-key`); TTS = v3/Flash (`POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`). Audio is turn-based (record locally → POST → transcript) — plain HTTP, no streaming.
- **Contract:** `answer-log.schema.json` — `raw_answer` is the **verbatim transcript** (permanent truth; accuracy > latency, `02 §4`); `audio_ptr` is the optional audio pointer.
- **⚠️ Gate first:** run Scribe on ~20 real messy recordings (Indian-accented, noisy, SKUs/jargon) and record accuracy in `PROGRESS.md` **before** committing the speech leg. Key already in `worker/.dev.vars`.
- **Run:** PWA from `pwa/` (`npm run dev`, mic needs HTTPS or localhost); Worker from `worker/` (`npm run dev`, :8787).

**Goal:** Make it voice-first. High-accuracy STT (the permanent Answer Log depends on it) and a
natural TTS voice, both behind provider seams and routed through the Worker (`02 §13, §17`).

**Depends on:** P6. **Package:** `pwa`, `worker`.

## ⚠️ Do this first
**STT eval gate:** run ElevenLabs Scribe on ~20 real, messy recordings (Indian-accented English,
background noise, SKUs/codes/CRM jargon) and confirm accuracy *before* committing. Vendor
benchmarks use clean audio; our conditions won't be. Record results in `PROGRESS.md`.

## Steps
1. **`STTProvider` / `TTSProvider` seams** (`pwa/src/voice/{stt,tts}.ts`): ElevenLabs impls
   (Scribe v2 for STT, v3/Flash for TTS). Browser TTS allowed **in dev only**.
2. **Worker `/stt`**: accept recorded audio (turn-based: record locally → POST → transcript),
   inject `ELEVENLABS_API_KEY`, return text. **Worker `/tts`**: text in → audio out.
3. **Mic capture** (`getUserMedia`): record a turn, show a calm listening state, send to `/stt`.
4. **Speak replies** via `/tts`; keep a consistent voice for every user regardless of device.
5. **Typed fallback** always available (mic denied / noisy).
6. **Accuracy > latency on STT** (asymmetric, `02 §4`): the transcript is permanent truth; a
   misheard word is corrupted forever. TTS may be plain.

## Files
`pwa/src/voice/*`, `worker/src/index.ts` (`/stt`, `/tts`).

## Test plan
- The eval-set transcription meets the agreed accuracy bar (gate).
- A spoken turn → correct transcript in the Answer Log; reply is spoken.
- Mic-denied path falls back to typing cleanly.

## Done when
A person can hold a natural spoken session on their phone; transcripts land faithfully in the
Answer Log; keys stay in the Worker.
