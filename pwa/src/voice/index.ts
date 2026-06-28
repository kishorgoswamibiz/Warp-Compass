/**
 * Public API of the voice leg (Phase 7). The PWA imports the seams from here.
 *
 * Production path: `WorkerSTTProvider` + `WorkerTTSProvider` (relative `/stt`,`/tts` → the Worker;
 * keys live only in the Worker, AGENTS.md). `BrowserTTSProvider` is a DEV-ONLY fallback — never the
 * shipped voice. `MicRecorder` captures one turn; the typed fallback always stays available.
 */

export type { STTProvider, TTSProvider } from "./types";
export { VoiceError } from "./types";
export { WorkerSTTProvider } from "./stt";
export type { WorkerSTTOptions } from "./stt";
export { WorkerTTSProvider, BrowserTTSProvider, playAudioBlob } from "./tts";
export type { WorkerTTSOptions } from "./tts";
export { MicRecorder, isMicAvailable } from "./mic";
