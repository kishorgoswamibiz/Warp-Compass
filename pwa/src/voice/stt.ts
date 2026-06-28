/**
 * WorkerSTTProvider — the PRODUCTION speech-to-text seam for the shipped PWA.
 *
 * The browser never holds keys (AGENTS.md, DECISION #8): it POSTs the recorded audio blob as the
 * raw request body to the Cloudflare Worker `/stt`, which injects `ELEVENLABS_API_KEY` + the Scribe
 * model and returns `{ text }`. The relative path works in dev (Vite proxy → :8787) and prod
 * (same origin as the deployed Worker) with no code change — never hardcode a host.
 *
 * Accuracy-first (docs/02 §4): the transcript is the permanent Answer Log truth, so a misheard word
 * is corrupted forever. We send the full-quality recorded turn, not low-latency streamed audio.
 */

import { VoiceError } from "./types";
import type { STTProvider } from "./types";

export interface WorkerSTTOptions {
  /** Base URL of the Worker proxy, e.g. "" (same origin) or "http://localhost:8787". */
  baseUrl?: string;
  /** Endpoint path; defaults to "/stt". */
  path?: string;
}

export class WorkerSTTProvider implements STTProvider {
  private readonly url: string;

  constructor(opts: WorkerSTTOptions = {}) {
    const base = (opts.baseUrl ?? "").replace(/\/$/, "");
    this.url = `${base}${opts.path ?? "/stt"}`;
  }

  async transcribe(audio: Blob): Promise<string> {
    if (audio.size === 0) throw new VoiceError("No audio recorded.");
    let resp: Response;
    try {
      resp = await fetch(this.url, {
        method: "POST",
        // Raw bytes; the Worker wraps them in the multipart form ElevenLabs expects. The mime type
        // tells the Worker the recording format (MediaRecorder picks webm/opus or mp4 by browser).
        headers: { "Content-Type": audio.type || "audio/webm" },
        body: audio,
      });
    } catch (e) {
      throw new VoiceError(`Worker /stt request failed: ${(e as Error).message}`);
    }
    if (!resp.ok) {
      throw new VoiceError(`Worker /stt HTTP ${resp.status}: ${await resp.text()}`);
    }
    const data = (await resp.json()) as { text?: string };
    return (data.text ?? "").trim();
  }
}
