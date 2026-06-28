/**
 * Prompt design for the live runner (docs/02 §12 "Live runner", hot path, `deepseek-v4-flash`).
 *
 * One cheap call per turn: classify the person's last answer (clear / vague / tangent / don't-know)
 * and produce the next utterance (opener / redirect / probe / reconcile / acknowledge / close),
 * using ONLY the Session Brief and this session's transcript. It must NOT reference or query the
 * graph — that line is what keeps it fast (§4.1).
 *
 * The brief is *scaffolding the model is guided by, not rails it is locked into.*
 */

import type { LiveDecision, SessionBrief, TranscriptTurn } from "./types";

/**
 * Generic discovery openers for a first-ever session (empty brain). Mirrors the brain's
 * `COLD_START_OPENERS` in `planner.py` — the only scaffolding when there's nothing in the graph
 * yet. (Cross-language constant duplicated by design; both sides reference docs/02 §4.1.)
 */
export const COLD_START_OPENERS: readonly string[] = [
  "To start, tell me about your role — what are you responsible for day to day?",
  "Walk me through a normal day, from the first thing that lands on your plate.",
  "Where does your work come from, and where does it go when you're done?",
  "What tools or systems do you spend the most time in?",
  "What's the most frustrating part of the process for you right now?",
];

export const SYSTEM_PROMPT = `You are Warp Compass, a warm, sharp interviewer mapping how one person's work really happens. You speak in their own words, one short question at a time, like a curious colleague — never a form to fill in.

You are given a SESSION BRIEF (the evolving picture of this person plus a ranked list of open threads to pull on) and the TRANSCRIPT of this session so far. The brief is guidance you may deviate from to follow the conversation; it is NOT a fixed questionnaire and you must never read a list of questions aloud.

Each turn you do two things:
1) CLASSIFY the person's most recent answer:
   - "clear": a usable, specific answer.
   - "vague": too general to be useful ("it depends", "the usual stuff").
   - "tangent": they drifted off the current thread's intent.
   - "dont_know": they don't know / aren't the right person to ask.
2) Decide the next ACTION and write the next UTTERANCE:
   - "opener": open the next thread (or, with no threads, a generic discovery question). Lead with the brief's highest-priority uncovered thread.
   - "redirect": they drifted — steer back to the current thread's intent, in your own words, gently.
   - "probe": ONE short follow-up to sharpen a vague answer. Never probe the same thread twice.
   - "reconcile": you noticed this answer contradicts something earlier in THIS session — name both, ask which is right.
   - "acknowledge": they volunteered free narration — capture it, acknowledge warmly, optionally one clarifier.
   - "close": wrap up warmly; say you'll process this before next time. Use only when told the session is ending.

Hard rules:
- Reference ONLY the brief and this session's transcript. You have NO access to any database, graph, or other sessions. Never claim to "look something up".
- One question per turn. Keep it under 30 words. Plain, spoken language.
- Skip what the transcript shows is already covered.
- Set "active_thread_id" to the brief thread id your next utterance addresses, or null (generic opener / free narration).
- Set "thread_complete" true only when the thread just discussed is genuinely well covered.

Respond with ONLY a JSON object, no prose:
{"classification":"clear|vague|tangent|dont_know","action":"opener|redirect|probe|reconcile|acknowledge|close","utterance":"<the next thing you say>","active_thread_id":"<thread id or null>","thread_complete":<true|false>}`;

export interface UserPromptInput {
  brief: SessionBrief;
  transcript: TranscriptTurn[];
  /** Threads already covered this session (ids) — tell the model to skip them. */
  covered: string[];
  /** The thread currently being pulled on, if any. */
  currentThreadId: string | null;
  /** Threads the runner has already probed once (the one-probe rule is enforced in code too). */
  probedThreadIds: string[];
  /** True on the final turn so the model produces a graceful close. */
  closing: boolean;
}

function briefDigest(brief: SessionBrief): string {
  if (brief.cold_start) {
    return "COLD START — the brain is empty. There are no threads yet; open generically and let them talk.";
  }
  const lines: string[] = [];
  if (brief.persona_summary) lines.push(`Persona so far: ${brief.persona_summary}`);
  lines.push("Open threads (ranked; pull highest-priority uncovered first):");
  for (const t of brief.open_threads) {
    lines.push(
      `  [${t.id}] (priority ${t.priority}) goal: ${t.goal}` +
        (t.why ? ` — why now: ${t.why}` : "") +
        (t.suggested_opener ? `\n      suggested opener (reword freely): ${t.suggested_opener}` : "") +
        (t.followups && t.followups.length
          ? `\n      followups: ${t.followups.map((f) => `if ${f.if} → ${f.ask}`).join(" | ")}`
          : ""),
    );
  }
  return lines.join("\n");
}

/** Render the per-turn user message: the brief digest + the running transcript + control flags. */
export function buildUserPrompt(input: UserPromptInput): string {
  const { brief, transcript, covered, currentThreadId, probedThreadIds, closing } = input;
  const parts: string[] = [];
  parts.push("=== SESSION BRIEF ===");
  parts.push(briefDigest(brief));
  parts.push("");
  parts.push("=== TRANSCRIPT THIS SESSION ===");
  if (transcript.length === 0) {
    parts.push("(empty — this is the opening of the session)");
  } else {
    transcript.forEach((t, i) => {
      if (t.agent) parts.push(`Agent #${i + 1}: ${t.agent}`);
      parts.push(`Person #${i + 1}: ${t.person}`);
    });
  }
  parts.push("");
  parts.push("=== STATE ===");
  parts.push(`Current thread: ${currentThreadId ?? "none"}`);
  parts.push(`Already covered (skip): ${covered.length ? covered.join(", ") : "none"}`);
  parts.push(
    `Already probed once (do NOT probe again): ${probedThreadIds.length ? probedThreadIds.join(", ") : "none"}`,
  );
  if (closing) {
    parts.push("");
    parts.push("The session is ENDING now — produce a graceful close (action: close).");
  }
  parts.push("");
  parts.push("Return the JSON decision for your NEXT utterance.");
  return parts.join("\n");
}

/** A few cheap sanity checks; the provider already guarantees a parsed object. */
export function isLiveDecision(o: unknown): o is LiveDecision {
  if (typeof o !== "object" || o === null) return false;
  const d = o as Record<string, unknown>;
  return (
    typeof d.utterance === "string" &&
    typeof d.classification === "string" &&
    typeof d.action === "string" &&
    (typeof d.active_thread_id === "string" || d.active_thread_id === null) &&
    typeof d.thread_complete === "boolean"
  );
}
