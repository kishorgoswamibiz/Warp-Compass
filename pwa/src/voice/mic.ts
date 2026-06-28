/**
 * MicRecorder (Phase 7) — capture one spoken turn with the platform `MediaRecorder`.
 *
 * Turn-based (docs/02 §13): `start()` opens the mic and records; `stop()` ends the turn and returns
 * one audio blob to hand to the STT seam. Picks a mime the browser actually supports (Chrome/Android
 * → webm/opus; Safari/iOS → mp4) so the Worker forwards a format ElevenLabs accepts. The mic stream
 * is released on every stop so the OS recording indicator clears between turns.
 *
 * Mic permission can be denied or unavailable — callers must keep the typed fallback (the brief's
 * "typed fallback always available"). `isMicAvailable()` lets the UI decide whether to show the mic.
 */

import { VoiceError } from "./types";

/** True if this browser can capture mic audio at all (so the UI can hide the mic button if not). */
export function isMicAvailable(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined"
  );
}

/** First MediaRecorder mime type this browser supports, or "" to let it choose its default. */
function pickMime(): string {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return candidates.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

export class MicRecorder {
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];

  get recording(): boolean {
    return this.recorder?.state === "recording";
  }

  /** Open the mic and begin recording one turn. Throws `VoiceError` if mic access is unavailable. */
  async start(): Promise<void> {
    if (this.recording) return;
    if (!isMicAvailable()) throw new VoiceError("Microphone not available on this device/browser.");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      throw new VoiceError(`Microphone access denied: ${(e as Error).message}`);
    }
    const mimeType = pickMime();
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.recorder.start();
  }

  /** End the turn, release the mic, and return the recorded audio blob. */
  async stop(): Promise<Blob> {
    const rec = this.recorder;
    if (!rec) throw new VoiceError("Not recording.");
    const blob = await new Promise<Blob>((resolve) => {
      rec.onstop = () => resolve(new Blob(this.chunks, { type: rec.mimeType || "audio/webm" }));
      rec.stop();
    });
    this.release();
    return blob;
  }

  /** Abort without using the recording (e.g. the user cancels). Always releases the mic. */
  cancel(): void {
    if (this.recorder && this.recorder.state !== "inactive") {
      this.recorder.onstop = null;
      this.recorder.stop();
    }
    this.release();
  }

  private release(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.recorder = null;
    this.chunks = [];
  }
}
