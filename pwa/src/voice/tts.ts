/**
 * Text-to-speech seams (Phase 7).
 *
 * `WorkerTTSProvider` is the PRODUCTION seam: the browser POSTs `{ text }` to the Cloudflare Worker
 * `/tts`, which injects `ELEVENLABS_API_KEY` + a consistent voice id and returns the audio bytes
 * (AGENTS.md, DECISION #8). One voice for every user regardless of device (docs/02 §13).
 *
 * `BrowserTTSProvider` is a DEV-ONLY fallback using the platform `speechSynthesis` (no key, no
 * ElevenLabs credits burned while iterating). It must NOT be the shipped path — device voices are
 * inconsistent. Pick the provider by `import.meta.env.DEV` at the call site.
 */

import { VoiceError } from "./types";
import type { TTSProvider } from "./types";

export interface WorkerTTSOptions {
  /** Base URL of the Worker proxy, e.g. "" (same origin) or "http://localhost:8787". */
  baseUrl?: string;
  /** Endpoint path; defaults to "/tts". */
  path?: string;
}

export class WorkerTTSProvider implements TTSProvider {
  private readonly url: string;

  constructor(opts: WorkerTTSOptions = {}) {
    const base = (opts.baseUrl ?? "").replace(/\/$/, "");
    this.url = `${base}${opts.path ?? "/tts"}`;
  }

  async synthesize(text: string): Promise<Blob> {
    const t = text.trim();
    if (!t) throw new VoiceError("Nothing to speak.");
    let resp: Response;
    try {
      resp = await fetch(this.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: t }),
      });
    } catch (e) {
      throw new VoiceError(`Worker /tts request failed: ${(e as Error).message}`);
    }
    if (!resp.ok) {
      throw new VoiceError(`Worker /tts HTTP ${resp.status}: ${await resp.text()}`);
    }
    return await resp.blob();
  }
}

/**
 * Play an audio blob and resolve when it finishes (or rejects on a playback error). Used by the UI
 * to speak a Worker-synthesized reply. Kept here so the audio lifecycle (object URL create/revoke)
 * lives in one place.
 */
export async function playAudioBlob(blob: Blob): Promise<void> {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  try {
    await new Promise<void>((resolve, reject) => {
      audio.onended = () => resolve();
      audio.onerror = () => reject(new VoiceError("Audio playback failed."));
      void audio.play().catch(reject);
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** DEV-ONLY: speak via the platform speech synthesis (no key, no credits). Not shipped. */
export class BrowserTTSProvider implements TTSProvider {
  async synthesize(): Promise<Blob> {
    throw new VoiceError("BrowserTTSProvider speaks directly; call speak() instead of synthesize().");
  }

  /** Speak via the Web Speech API; resolves when the utterance ends. */
  async speak(text: string): Promise<void> {
    const t = text.trim();
    if (!t || typeof speechSynthesis === "undefined") return;
    await new Promise<void>((resolve) => {
      const u = new SpeechSynthesisUtterance(t);
      u.onend = () => resolve();
      u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
  }
}
