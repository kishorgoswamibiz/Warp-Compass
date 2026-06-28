/**
 * Voice provider seams (Phase 7) — mirror the runner's `LLMProvider` shape (one minimal, swappable
 * interface per capability; AGENTS.md "Everything swappable"). The shipped PWA routes both through
 * the Cloudflare Worker so the ElevenLabs key never reaches the browser (AGENTS.md, DECISION #8).
 *
 * Turn-based by design (docs/02 §13): record a whole turn → POST → transcript; text → audio blob.
 * No streaming/WebSocket in the prototype.
 */

/** Speech → text. Accuracy-first: the transcript becomes the permanent Answer Log truth (§4). */
export interface STTProvider {
  /** Transcribe one recorded turn. Returns the verbatim transcript (trimmed). */
  transcribe(audio: Blob): Promise<string>;
}

/** Text → speech. May be plain (latency over fidelity, §4). */
export interface TTSProvider {
  /** Synthesize speech for one utterance. Returns an audio blob to play. */
  synthesize(text: string): Promise<Blob>;
}

export class VoiceError extends Error {}
