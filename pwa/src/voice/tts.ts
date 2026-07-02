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
 *
 * `onLevel` (optional, Phase 12) receives a smoothed 0–1 loudness reading ~60×/s while the audio
 * plays — the avatar drives its mouth from it. Metering is best-effort: if WebAudio is unavailable
 * or blocked, playback proceeds normally and `onLevel` simply never fires.
 */
export async function playAudioBlob(blob: Blob, onLevel?: (level: number) => void): Promise<void> {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  const stopMeter = onLevel ? attachLevelMeter(audio, onLevel) : undefined;
  try {
    await new Promise<void>((resolve, reject) => {
      audio.onended = () => resolve();
      audio.onerror = () => reject(new VoiceError("Audio playback failed."));
      void audio.play().catch(reject);
    });
  } finally {
    stopMeter?.();
    URL.revokeObjectURL(url);
  }
}

// One shared AudioContext: browsers cap how many a page may create, and TTS replies are frequent.
let meterCtx: AudioContext | undefined;

/** Route `audio` through an AnalyserNode and stream smoothed 0–1 levels to `onLevel`. */
function attachLevelMeter(audio: HTMLAudioElement, onLevel: (level: number) => void): () => void {
  try {
    meterCtx ??= new AudioContext();
    if (meterCtx.state === "suspended") void meterCtx.resume();
    const source = meterCtx.createMediaElementSource(audio);
    const analyser = meterCtx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    analyser.connect(meterCtx.destination); // MediaElementSource captures output; re-route to speakers
    const buf = new Uint8Array(analyser.frequencyBinCount);
    let raf = 0;
    let smooth = 0;
    const tick = () => {
      analyser.getByteTimeDomainData(buf);
      let peak = 0;
      for (let i = 0; i < buf.length; i++) peak = Math.max(peak, Math.abs(buf[i] - 128));
      smooth = smooth * 0.6 + Math.min(1, (peak / 128) * 1.6) * 0.4;
      onLevel(smooth);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      onLevel(0);
      try {
        source.disconnect();
        analyser.disconnect();
      } catch {
        /* already torn down */
      }
    };
  } catch {
    return () => onLevel(0); // no metering — the avatar falls back to its CSS talk loop
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
