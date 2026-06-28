/**
 * SessionScreen — the live-runner UI. Voice-first as of Phase 7, with the typed path always
 * available as the fallback (mic denied / noisy / unsupported).
 *
 * Wraps the P5 `Runner` in the installable app. Every live call (LLM + STT + TTS) goes through the
 * Cloudflare Worker key-proxy via relative paths, so NO key ever touches the browser (AGENTS.md,
 * DECISION #8). A spoken turn is: tap mic → record → `/stt` → the verbatim transcript becomes the
 * person's answer (the permanent Answer Log truth, §4) → `runner.respond` → the reply is spoken via
 * `/tts`. On a first-ever session it cold-starts with generic openers; on close it builds a
 * schema-shaped Answer Log to hand to the brain (the automated sync bus is P8).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Runner, WorkerLLMProvider } from "../runner";
import type { RunnerClock, SessionBrief } from "../runner";
import { downloadAnswerLog, getParticipant } from "../sync";
import {
  BrowserTTSProvider,
  MicRecorder,
  WorkerSTTProvider,
  WorkerTTSProvider,
  isMicAvailable,
  playAudioBlob,
} from "../voice";

type Status = "active" | "thinking" | "paused" | "closed";
type MicState = "idle" | "listening" | "transcribing";
interface Msg {
  who: "agent" | "person" | "error";
  text: string;
}

const clock: RunnerClock = { now: () => new Date().toISOString() };
const micSupported = isMicAvailable();

function newColdBrief(personaId: string): SessionBrief {
  const d = new Date();
  const stamp = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(
    d.getDate(),
  ).padStart(2, "0")}_${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")}`;
  return {
    session_id: `s_${stamp}`,
    persona_id: personaId,
    schema_version: "1.0.0",
    cold_start: true,
    persona_summary: "",
    open_threads: [],
    reserve_threads: [],
  };
}

/** `brief` is an imported Session Brief from the bus (P8); omit it for a fresh cold-start session. */
export function SessionScreen({ onExit, brief }: { onExit: () => void; brief?: SessionBrief }) {
  const runnerRef = useRef<Runner | null>(null);
  const micRef = useRef<MicRecorder | null>(null);
  const sttRef = useRef(new WorkerSTTProvider());
  const ttsRef = useRef(new WorkerTTSProvider());
  const browserTtsRef = useRef(new BrowserTTSProvider());
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<Status>("active");
  const [micState, setMicState] = useState<MicState>("idle");
  // Voice-first when a mic exists; muting only stops spoken replies, never the mic input.
  const [voiceOn, setVoiceOn] = useState(micSupported);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Build the runner once and emit the opening utterance.
  useEffect(() => {
    // Stable participant id across sessions; the bus folder is keyed by it (P8). An imported brief
    // (from the bus) cross-pollinates this session; otherwise we cold-start.
    const participant = getParticipant();
    const sessionBrief = brief ?? newColdBrief(participant.persona_id);
    const runner = new Runner(sessionBrief, new WorkerLLMProvider(), clock, {
      participantId: participant.participant_id,
    });
    runnerRef.current = runner;
    micRef.current = new MicRecorder();
    setMessages([{ who: "agent", text: runner.start() }]);
    // Note: the opener isn't auto-spoken — browser autoplay needs a user gesture; replies (which
    // follow a tap) are spoken.
    return () => micRef.current?.cancel();
  }, [brief]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, status, micState]);

  // Speak a reply through the Worker /tts (prod) or the platform voice (dev only, no credits).
  // Best-effort: a TTS failure never blocks the conversation.
  const speak = useCallback(
    async (text: string) => {
      if (!voiceOn) return;
      try {
        if (import.meta.env.DEV) {
          await browserTtsRef.current.speak(text);
        } else {
          await playAudioBlob(await ttsRef.current.synthesize(text));
        }
      } catch {
        /* spoken reply is optional; the text is already on screen */
      }
    },
    [voiceOn],
  );

  // Core turn: feed one answer (typed or transcribed) to the runner and surface/speak the reply.
  const submit = useCallback(
    async (text: string) => {
      const runner = runnerRef.current;
      const t = text.trim();
      if (!runner || !t || status !== "active") return;
      setInput("");
      setMessages((m) => [...m, { who: "person", text: t }]);
      setStatus("thinking");
      try {
        const { utterance } = await runner.respond(t);
        setMessages((m) => [...m, { who: "agent", text: utterance }]);
        setStatus("active");
        void speak(utterance);
      } catch (e) {
        setMessages((m) => [
          ...m,
          { who: "error", text: `Couldn't reach the assistant: ${(e as Error).message}` },
        ]);
        setStatus("active");
      }
    },
    [status, speak],
  );

  const send = useCallback(() => void submit(input), [submit, input]);

  // Tap to start recording; tap again to stop → transcribe → submit. The typed box stays usable.
  const toggleMic = useCallback(async () => {
    const mic = micRef.current;
    if (!mic || status !== "active") return;
    if (micState === "idle") {
      try {
        await mic.start();
        setMicState("listening");
      } catch (e) {
        setMessages((m) => [...m, { who: "error", text: (e as Error).message + " You can type instead." }]);
        setMicState("idle");
      }
      return;
    }
    if (micState === "listening") {
      setMicState("transcribing");
      try {
        const transcript = await sttRef.current.transcribe(await mic.stop());
        setMicState("idle");
        if (transcript) await submit(transcript);
        else
          setMessages((m) => [
            ...m,
            { who: "error", text: "Didn't catch that — try again or type your answer." },
          ]);
      } catch (e) {
        setMicState("idle");
        setMessages((m) => [
          ...m,
          { who: "error", text: `Transcription failed: ${(e as Error).message}. You can type instead.` },
        ]);
      }
    }
  }, [status, micState, submit]);

  const endSession = useCallback(() => {
    const runner = runnerRef.current;
    if (!runner) return;
    micRef.current?.cancel();
    setMicState("idle");
    const bye = runner.close();
    setMessages((m) => [...m, { who: "agent", text: bye }]);
    setStatus("closed");
    void speak(bye);
  }, [speak]);

  const download = useCallback(() => {
    const runner = runnerRef.current;
    if (!runner) return;
    // Bus filename convention (P8): drop this into your participants/{id}/answer_logs/ folder.
    downloadAnswerLog(runner.log.build());
  }, []);

  const entryCount = runnerRef.current?.log.count() ?? 0;
  const busy = status !== "active" || micState === "transcribing";
  const micLabel =
    micState === "listening" ? "● Listening — tap to stop" : micState === "transcribing" ? "Transcribing…" : "🎤 Speak";

  return (
    <div className="wc-session">
      <header className="wc-header">
        <span className="wc-logo">
          WARP<span className="wc-logo-thin">COMPASS</span>
        </span>
        {micSupported && status !== "closed" && (
          <button
            className="wc-voice-toggle"
            onClick={() => setVoiceOn((v) => !v)}
            title={voiceOn ? "Mute spoken replies" : "Speak replies"}
          >
            {voiceOn ? "🔊 Voice on" : "🔇 Voice off"}
          </button>
        )}
        <button className="wc-link" onClick={onExit}>
          ← exit
        </button>
      </header>

      <div className="wc-chat" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`wc-msg wc-msg-${m.who}`}>
            {m.text}
          </div>
        ))}
        {status === "thinking" && <div className="wc-msg wc-msg-agent wc-thinking">…</div>}
        {micState === "listening" && <div className="wc-msg wc-msg-person wc-listening">●●●</div>}
      </div>

      {status === "closed" ? (
        <div className="wc-closed">
          <p className="wc-note">
            Session captured — {entryCount} {entryCount === 1 ? "answer" : "answers"}. Download the
            Answer Log and drop it into your <code>answer_logs/</code> folder on the shared bus — the
            next round folds it into the brain and sends back your updated brief.
          </p>
          <div className="wc-toolbar">
            <button className="wc-pill" onClick={download}>
              Download Answer Log
            </button>
            <button className="wc-ghost" onClick={onExit}>
              Done
            </button>
          </div>
        </div>
      ) : (
        <div className="wc-composer">
          <textarea
            className="wc-input"
            placeholder={
              status === "paused"
                ? "Paused — tap Resume to continue"
                : micState === "listening"
                  ? "Listening… tap the mic to stop"
                  : "Speak, or type your answer…"
            }
            value={input}
            disabled={status !== "active" || micState !== "idle"}
            rows={2}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <div className="wc-toolbar">
            {micSupported && (
              <button
                className={`wc-mic${micState === "listening" ? " wc-mic-live" : ""}`}
                onClick={() => void toggleMic()}
                disabled={status !== "active" || micState === "transcribing"}
              >
                {micLabel}
              </button>
            )}
            <button className="wc-pill" onClick={send} disabled={busy || !input.trim()}>
              Send
            </button>
            {status === "paused" ? (
              <button className="wc-ghost" onClick={() => setStatus("active")}>
                Resume
              </button>
            ) : (
              <button
                className="wc-ghost"
                onClick={() => {
                  micRef.current?.cancel();
                  setMicState("idle");
                  setStatus("paused");
                }}
                disabled={busy}
              >
                Pause
              </button>
            )}
            <button className="wc-ghost" onClick={endSession} disabled={busy}>
              End &amp; save
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
