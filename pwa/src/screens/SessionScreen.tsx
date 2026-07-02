/**
 * SessionScreen — the live-runner UI. Voice-first as of Phase 7, bot-first as of Phase 12: the
 * default view is a "stage" where the WarpBot robot listens, reacts, and speaks each question,
 * with the LLM's utterance appearing beneath it as the bot's transcript (plus topic chips, per
 * the PWA Bot Sample reference). A chat-bubble transcript of the whole conversation is one tap
 * away (💬) and is shown automatically at End & save. The typed path stays available throughout.
 *
 * Liveliness is director-driven (src/avatar/director.ts): keyword-triggered gestures on submit
 * AND while typing (the bot leans in when it spots process words, writes problems on its notepad),
 * plus random idle antics so it never freezes. All of it is presentation ONLY — question
 * generation, answer capture, and the Answer Log push are untouched.
 *
 * Wraps the P5 `Runner` in the installable app. Every live call (LLM + STT + TTS) goes through the
 * Cloudflare Worker key-proxy via relative paths, so NO key ever touches the browser (AGENTS.md,
 * DECISION #8). A spoken turn is: tap mic → record → `/stt` → the verbatim transcript becomes the
 * person's answer (the permanent Answer Log truth, §4) → `runner.respond` → the reply is spoken via
 * `/tts` while the bot's equalizer mouth tracks the audio level. On a first-ever session it
 * cold-starts with generic openers; on close it builds a schema-shaped Answer Log and auto-pushes
 * it to the brain (Phase 11; manual download remains as the offline fallback).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Runner, WorkerLLMProvider } from "../runner";
import type { RunnerClock, SessionBrief } from "../runner";
import { WarpBot, chipsFor, glanceAt, reactToAnswer, useIdleAntics } from "../avatar";
import type { BotGesture, BotState } from "../avatar";
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
const REACTION_MS = 1500;
const GLANCE_COOLDOWN_MS = 8000;

/** What tapping a topic chip drops into the input as a sentence starter. */
const CHIP_STARTERS: Record<string, string> = {
  "My role": "My role is ",
  "Daily tasks": "On a typical day, I ",
  "Key responsibilities": "I'm responsible for ",
  "Pain points": "The biggest problem is ",
  "Tools & systems": "We use ",
  "The process": "It starts when ",
  "People & handoffs": "After me, it goes to ",
  Approvals: "It needs approval from ",
  "When it happens": "It happens every ",
  Numbers: "Roughly ",
  Wishes: "I wish ",
};

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
  const [gesture, setGesture] = useState<BotGesture | null>(null);
  // Voice-first when a mic exists; muting only stops spoken replies, never the mic input.
  const [voiceOn, setVoiceOn] = useState(micSupported);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const botRef = useRef<SVGSVGElement>(null);
  const reactionTimer = useRef<ReturnType<typeof setTimeout>>();
  const gestureTimer = useRef<ReturnType<typeof setTimeout>>();
  const lastGlanceAt = useRef(0);
  const meterLive = useRef(false); // did real audio levels arrive this utterance?
  // Live mirrors for async callbacks (auto-listen fires after `speak` resolves, when the
  // closure's state may be stale — e.g. the person tapped End & save mid-utterance).
  const statusRef = useRef<Status>("active");
  statusRef.current = status;
  const micStateRef = useRef<MicState>("idle");
  micStateRef.current = micState;
  // Hands-free loop: after the bot finishes speaking, re-arm the mic — but only when the
  // previous answer came by voice, so typing users are never hijacked mid-thought.
  const lastAnswerWasVoice = useRef(false);

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
      clearTimeout(gestureTimer.current);
    };
  }, [brief]);

  useEffect(() => {
    if (view === "chat" || status === "closed")
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, status, micState, view]);

  // One-shot act on top of the current state; a new gesture replaces the running one.
  const playGesture = useCallback((g: BotGesture, ms = 2600) => {
    clearTimeout(gestureTimer.current);
    setGesture(null); // retrigger CSS animations even for the same gesture twice
    requestAnimationFrame(() => setGesture(g));
    gestureTimer.current = setTimeout(() => setGesture(null), ms);
  }, []);

  // The bot's equalizer mouth: written straight to a CSS var on the <svg> (no re-render per frame).
  const setMouth = useCallback((level: number) => {
    botRef.current?.style.setProperty("--wc-mouth", String(Math.max(0.12, level).toFixed(3)));
  }, []);

  // Speak a reply through the Worker /tts (prod) or the platform voice (dev only, no credits).
  // Best-effort: a TTS failure never blocks the conversation. While audio plays the bot is in its
  // "speaking" state; the mouth follows the real audio level, with a synthetic wobble fallback
  // when no meter is available (dev voice, or WebAudio blocked).
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

  // Start recording. Silent mode is the hands-free auto-arm: it must never surface an error or
  // fire when the session moved on (guards read the live refs, not the render closure).
  const startMic = useCallback(async (silent: boolean) => {
    const mic = micRef.current;
    if (!mic || statusRef.current !== "active" || micStateRef.current !== "idle") return;
    try {
      await mic.start();
      setMicState("listening");
    } catch (e) {
      if (!silent)
        setMessages((m) => [...m, { who: "error", text: (e as Error).message + " You can type instead." }]);
    }
  }, []);

  // Core turn: feed one answer (typed or transcribed) to the runner and surface/speak the reply.
  // The director picks how the bot acknowledges it (notes down problems, nods at people words…).
  // A voice-given answer keeps the conversation hands-free: when the spoken reply finishes, the
  // mic re-arms by itself (the mic button is the stop if the person wants a breather).
  const submit = useCallback(
    async (text: string, viaVoice = false) => {
      const runner = runnerRef.current;
      const t = text.trim();
      if (!runner || !t || status !== "active") return;
      lastAnswerWasVoice.current = viaVoice;
      setInput("");
      setMessages((m) => [...m, { who: "person", text: t }]);
      setStatus("thinking");
      const r = reactToAnswer(t);
      setReaction(r.bubble);
      clearTimeout(reactionTimer.current);
      reactionTimer.current = setTimeout(() => setReaction(null), REACTION_MS);
      if (r.gesture) playGesture(r.gesture, r.gesture === "note" ? 3000 : 2200);
      try {
        const { utterance } = await runner.respond(t);
        setMessages((m) => [...m, { who: "agent", text: utterance }]);
        setStatus("active");
        void speak(utterance).then(() => {
          if (lastAnswerWasVoice.current && micSupported) void startMic(true);
        });
      } catch (e) {
        setMessages((m) => [
          ...m,
          { who: "error", text: `Couldn't reach the assistant: ${(e as Error).message}` },
        ]);
        setStatus("active");
      }
    },
    [status, speak, playGesture, startMic],
  );

  const send = useCallback(() => void submit(input, false), [submit, input]);

  // While typing: if a domain keyword shows up mid-sentence, the bot visibly perks up (throttled
  // so it stays charming instead of twitchy).
  const onType = useCallback(
    (value: string) => {
      setInput(value);
      if (value.length < 8 || Date.now() - lastGlanceAt.current < GLANCE_COOLDOWN_MS) return;
      const g = glanceAt(value);
      if (g) {
        lastGlanceAt.current = Date.now();
        playGesture(g === "note" ? "lean" : g, 1800); // saving the notepad for the actual submit
      }
    },
    [playGesture],
  );

  // Tap to start recording; tap again to stop → transcribe → submit. The typed box stays usable.
  // A stop with nothing said is a quiet cancel (the hands-free loop auto-arms the mic, so an
  // intentional "not now" tap must not scold the person); it re-arms on the next spoken reply.
  const toggleMic = useCallback(async () => {
    const mic = micRef.current;
    if (!mic || status !== "active") return;
    if (micState === "idle") return void startMic(false);
    if (micState === "listening") {
      setMicState("transcribing");
      try {
        const audio = await mic.stop();
        if (audio.size === 0) {
          setMicState("idle"); // instant cancel — nothing was recorded, nothing to say about it
          return;
        }
        const transcript = await sttRef.current.transcribe(audio);
        setMicState("idle");
        if (transcript) await submit(transcript, true);
      } catch (e) {
        setMicState("idle");
        setMessages((m) => [
          ...m,
          { who: "error", text: `Transcription failed: ${(e as Error).message}. You can type instead.` },
        ]);
      }
    }
  }, [status, micState, submit, startMic]);

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

  // What the bot is doing right now (one-shot gestures layer on top via the `gesture` prop).
  const botState: BotState = speaking
    ? "speaking"
    : micState === "listening"
      ? "listening"
      : status === "thinking" || micState === "transcribing"
        ? "thinking"
        : "idle";

  // Random idle life — only on the stage, only when nothing real is happening.
  useIdleAntics(
    view === "stage" && status === "active" && botState === "idle" && !reaction,
    (g) => playGesture(g, g === "note" ? 3000 : 2000),
  );

  // The bot's current line — the latest agent utterance, shown as its transcript on the stage.
  const lastAgentIdx = messages.map((m) => m.who).lastIndexOf("agent");
  const currentLine = lastAgentIdx >= 0 ? messages[lastAgentIdx].text : "";
  const lastMsg = messages[messages.length - 1];
  const chips = chipsFor(currentLine);

  const stage = (
    <div className="wc-stage">
      <WarpBot ref={botRef} state={botState} gesture={gesture} reaction={reaction} />
      <p className="wc-stage-hint">
        {micState === "listening"
          ? "Listening to you…"
          : micState === "transcribing"
            ? "Catching every word…"
            : status === "thinking"
              ? "Thinking about what you said…"
              : " "}
      </p>
      {currentLine && (
        <div className="wc-transcript" key={lastAgentIdx}>
          {currentLine}
          <span className={`wc-wavehint${speaking ? " wc-wavehint-live" : ""}`} aria-hidden>
            <i />
            <i />
            <i />
            <i />
            <i />
          </span>
        </div>
      )}
      {lastMsg?.who === "error" && <div className="wc-msg wc-msg-error">{lastMsg.text}</div>}
      {status === "active" && micState === "idle" && (
        <div className="wc-chips wc-topic-chips">
          {chips.map((c) => (
            <button
              key={c}
              className="wc-chip wc-chip-tap"
              onClick={() => {
                setInput((v) => v || CHIP_STARTERS[c] || `${c}: `);
                inputRef.current?.focus();
              }}
            >
              {c}
            </button>
          ))}
        </div>
      )}
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
        <div className="wc-header-actions">
          {status !== "closed" && (
            <button
              className="wc-iconbtn"
              onClick={() => setView((v) => (v === "stage" ? "chat" : "stage"))}
              title={view === "stage" ? "Show the conversation transcript" : "Back to the bot"}
            >
              <span className="wc-iconbtn-ico">{view === "stage" ? "💬" : "🤖"}</span>
              {view === "stage" ? "Transcript" : "Bot"}
            </button>
          )}
          {micSupported && status !== "closed" && (
            <button
              className="wc-iconbtn"
              onClick={() => setVoiceOn((v) => !v)}
              title={voiceOn ? "Mute spoken replies" : "Speak replies"}
            >
              <span className="wc-iconbtn-ico">{voiceOn ? "🔊" : "🔇"}</span>
              {voiceOn ? "Voice on" : "Voice off"}
            </button>
          )}
          <button className="wc-iconbtn" onClick={onExit}>
            <span className="wc-iconbtn-ico">↪</span>
            Exit
          </button>
        </div>
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
          <div className="wc-inputwrap">
            <textarea
              ref={inputRef}
              className="wc-input"
              placeholder={
                status === "paused"
                  ? "Paused — tap Resume to continue"
                  : micState === "listening"
                    ? "Listening… tap the mic to stop"
                    : "Speak or type your answer…"
              }
              value={input}
              disabled={status !== "active" || micState !== "idle"}
              rows={2}
              onChange={(e) => onType(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            {micSupported && (
              <button
                className={`wc-micfab${micState === "listening" ? " wc-micfab-live" : ""}`}
                onClick={() => void toggleMic()}
                disabled={status !== "active" || micState === "transcribing"}
                title={
                  micState === "listening"
                    ? "Tap to stop and send"
                    : micState === "transcribing"
                      ? "Transcribing…"
                      : "Tap to speak"
                }
              >
                {micState === "listening" ? "■" : micState === "transcribing" ? "…" : "🎤"}
              </button>
            )}
          </div>
          <div className="wc-toolbar">
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
                ⏸ Pause
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
