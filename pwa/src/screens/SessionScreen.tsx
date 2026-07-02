/**
 * SessionScreen — the live-runner UI. Voice-first as of Phase 7, avatar-first as of Phase 12: the
 * default view is a "stage" where an animated avatar listens, reacts, and speaks each question,
 * with the LLM's utterance appearing beneath it as the avatar's transcript. A chat-bubble
 * transcript of the whole conversation is one tap away (💬) and is shown automatically at
 * End & save so the person can review everything that was said. The typed path stays available
 * throughout (mic denied / noisy / unsupported).
 *
 * Wraps the P5 `Runner` in the installable app. Every live call (LLM + STT + TTS) goes through the
 * Cloudflare Worker key-proxy via relative paths, so NO key ever touches the browser (AGENTS.md,
 * DECISION #8). A spoken turn is: tap mic → record → `/stt` → the verbatim transcript becomes the
 * person's answer (the permanent Answer Log truth, §4) → `runner.respond` → the reply is spoken via
 * `/tts` while the avatar lip-syncs to the audio level. The avatar layer is presentation ONLY —
 * question generation, answer capture, and the Answer Log push are untouched. On a first-ever
 * session it cold-starts with generic openers; on close it builds a schema-shaped Answer Log and
 * auto-pushes it to the brain over the network (Phase 11; manual download remains as fallback).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Runner, WorkerLLMProvider } from "../runner";
import type { RunnerClock, SessionBrief } from "../runner";
import { Avatar, pickReaction } from "../avatar";
import type { AvatarState } from "../avatar";
import { downloadAnswerLog, getParticipant, pushAnswerLog } from "../sync";
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
type SyncState = "idle" | "pushing" | "pushed" | "exists" | "failed";
type View = "stage" | "chat";
interface Msg {
  who: "agent" | "person" | "error";
  text: string;
}

const clock: RunnerClock = { now: () => new Date().toISOString() };
const micSupported = isMicAvailable();
const REACTION_MS = 1100;

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
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [view, setView] = useState<View>("stage");
  const [speaking, setSpeaking] = useState(false);
  const [reaction, setReaction] = useState<string | null>(null);
  // Voice-first when a mic exists; muting only stops spoken replies, never the mic input.
  const [voiceOn, setVoiceOn] = useState(micSupported);
  const scrollRef = useRef<HTMLDivElement>(null);
  const avatarRef = useRef<SVGSVGElement>(null);
  const reactionTimer = useRef<ReturnType<typeof setTimeout>>();
  const meterLive = useRef(false); // did real audio levels arrive this utterance?

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
    return () => {
      micRef.current?.cancel();
      clearTimeout(reactionTimer.current);
    };
  }, [brief]);

  useEffect(() => {
    if (view === "chat" || status === "closed")
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, status, micState, view]);

  // The avatar's mouth: written straight to a CSS var on the <svg> (no React re-render per frame).
  const setMouth = useCallback((level: number) => {
    avatarRef.current?.style.setProperty("--wc-mouth", String(Math.max(0.12, level).toFixed(3)));
  }, []);

  // Speak a reply through the Worker /tts (prod) or the platform voice (dev only, no credits).
  // Best-effort: a TTS failure never blocks the conversation. While audio plays the avatar is in
  // its "speaking" state; the mouth follows the real audio level, with a synthetic wobble as the
  // fallback when no meter is available (dev voice, or WebAudio blocked).
  const speak = useCallback(
    async (text: string) => {
      if (!voiceOn) return;
      setSpeaking(true);
      meterLive.current = false;
      const synthetic = setInterval(() => {
        if (!meterLive.current) setMouth(0.25 + Math.random() * 0.6);
      }, 110);
      try {
        if (import.meta.env.DEV) {
          await browserTtsRef.current.speak(text);
        } else {
          await playAudioBlob(await ttsRef.current.synthesize(text), (level) => {
            meterLive.current = true;
            setMouth(level);
          });
        }
      } catch {
        /* spoken reply is optional; the text is already on screen */
      } finally {
        clearInterval(synthetic);
        setMouth(0);
        setSpeaking(false);
      }
    },
    [voiceOn, setMouth],
  );

  // Core turn: feed one answer (typed or transcribed) to the runner and surface/speak the reply.
  // The avatar acknowledges the answer with a micro-reaction while the runner thinks.
  const submit = useCallback(
    async (text: string) => {
      const runner = runnerRef.current;
      const t = text.trim();
      if (!runner || !t || status !== "active") return;
      setInput("");
      setMessages((m) => [...m, { who: "person", text: t }]);
      setStatus("thinking");
      setReaction(pickReaction(t));
      clearTimeout(reactionTimer.current);
      reactionTimer.current = setTimeout(() => setReaction(null), REACTION_MS);
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
    setView("chat"); // review the full conversation as a messaging thread before it's saved
    void speak(bye);
    // Auto-push the Answer Log to the brain over the network (Phase 11). The manual download stays
    // as the offline fallback if the push can't reach the sync endpoint.
    setSyncState("pushing");
    void pushAnswerLog(runner.log.build(), getParticipant())
      .then((r) => setSyncState(r.written === false ? "exists" : "pushed"))
      .catch(() => setSyncState("failed"));
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

  // What the avatar is doing right now (reactions override via the `reaction` prop).
  const avatarState: AvatarState = speaking
    ? "speaking"
    : micState === "listening"
      ? "listening"
      : status === "thinking" || micState === "transcribing"
        ? "thinking"
        : "idle";

  // The avatar's current line — the latest agent utterance, shown as its transcript on the stage.
  const lastAgentIdx = messages.map((m) => m.who).lastIndexOf("agent");
  const currentLine = lastAgentIdx >= 0 ? messages[lastAgentIdx].text : "";
  const lastMsg = messages[messages.length - 1];

  const stage = (
    <div className="wc-stage">
      <Avatar ref={avatarRef} state={avatarState} reaction={reaction} />
      <p className="wc-stage-hint">
        {micState === "listening"
          ? "Listening to you…"
          : micState === "transcribing"
            ? "Catching every word…"
            : status === "thinking"
              ? "Thinking about what you said…"
              : speaking
                ? "Speaking…"
                : " "}
      </p>
      {currentLine && (
        <div className="wc-transcript" key={lastAgentIdx}>
          {currentLine}
        </div>
      )}
      {lastMsg?.who === "error" && <div className="wc-msg wc-msg-error">{lastMsg.text}</div>}
    </div>
  );

  const chat = (
    <div className="wc-chat" ref={scrollRef}>
      {messages.map((m, i) => (
        <div key={i} className={`wc-msg wc-msg-${m.who}`}>
          {m.text}
        </div>
      ))}
      {status === "thinking" && <div className="wc-msg wc-msg-agent wc-thinking">…</div>}
      {micState === "listening" && <div className="wc-msg wc-msg-person wc-listening">●●●</div>}
    </div>
  );

  return (
    <div className="wc-session">
      <header className="wc-header">
        <span className="wc-logo">
          WARP<span className="wc-logo-thin">COMPASS</span>
        </span>
        {status !== "closed" && (
          <button
            className="wc-voice-toggle"
            onClick={() => setView((v) => (v === "stage" ? "chat" : "stage"))}
            title={view === "stage" ? "Show the conversation transcript" : "Back to the avatar"}
          >
            {view === "stage" ? "💬 Transcript" : "🙂 Avatar"}
          </button>
        )}
        {micSupported && status !== "closed" && (
          <button
            className="wc-voice-toggle wc-voice-toggle-next"
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

      {view === "chat" || status === "closed" ? chat : stage}

      {status === "closed" ? (
        <div className="wc-closed">
          <p className="wc-note">
            {syncState === "pushing" &&
              `Saving your ${entryCount} ${entryCount === 1 ? "answer" : "answers"} to the brain…`}
            {(syncState === "pushed" || syncState === "exists") &&
              `Sent to the brain — ${entryCount} ${entryCount === 1 ? "answer" : "answers"} captured. The next round folds them in and your updated brief arrives here automatically.`}
            {syncState === "failed" &&
              `Couldn't reach the brain just now — download your Answer Log and it'll be picked up next time (or hand it to your facilitator).`}
            {syncState === "idle" &&
              `Session captured — ${entryCount} ${entryCount === 1 ? "answer" : "answers"}.`}
          </p>
          <div className="wc-toolbar">
            {syncState === "failed" && (
              <button className="wc-pill" onClick={download}>
                Download Answer Log
              </button>
            )}
            {(syncState === "pushed" || syncState === "exists") && (
              <button className="wc-ghost" onClick={download}>
                Download a copy
              </button>
            )}
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
