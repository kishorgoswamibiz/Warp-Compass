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

import type { Identity, LiveDecision, SessionBrief, TranscriptTurn } from "./types";

/**
 * Generic discovery openers for a first-ever session (empty brain). Mirrors the brain's
 * `COLD_START_OPENERS` in `planner.py` — the only scaffolding when there's nothing in the graph
 * yet. (Cross-language constant duplicated by design; both sides reference docs/02 §4.1.)
 *
 * **Index 0 asks for the role.** When the device has a declared identity (P13) that question is
 * already answered, so `Session` drops it from the list rather than burning a turn re-asking —
 * see `IDENTITY_OPENER_INDEX`.
 *
 * ⚠ **Lifecycle-anchored, never day-anchored (P15b).** These deliberately contain no occurrence of
 * the word "day". Asking "what do you do day to day" produces noise, not process — the owner's own
 * answer as a BA was *"I start my day checking my mails, but checking mail is not my job role."*
 * Real role work is per-project / per-opportunity: pre-sales → demo → signing → kickoff →
 * discovery → BRD → build → UAT → go-live → support. Opener 1 is the Pass-A map question; 2–5 are
 * Pass B, one stage at a time. Guarded by a test that greps for "day".
 */
export const COLD_START_OPENERS: readonly string[] = [
  "To start, tell me about your role — what are you responsible for?",
  "Think of one piece of work from the moment it reaches the company to when it's delivered. Which parts of that journey do you touch?",
  "Take the earliest part you touch. What has to happen before it reaches you, and what tells you it's your turn?",
  "Inside that part, what do you actually do — step by step, in the order you do it?",
  "When your part is finished, what have you produced, and who picks it up?",
  "Is that something you do on every project, or only in certain cases?",
];

/** The opener a declared identity makes redundant. Skipped when `Identity` is present. */
export const IDENTITY_OPENER_INDEX = 0;

/** The question the onboarding card stands in for — replayed into the Answer Log (P13 §4.1). */
export const IDENTITY_QUESTION = "Before we start — what's your name, and what's your role?";

/** First name only, for a greeting that sounds like a colleague rather than a mail-merge. */
export function firstName(identity: Identity): string {
  return identity.display_name.trim().split(/\s+/)[0] || identity.display_name.trim();
}

/**
 * The person's role(s) as a spoken phrase: "Delivery Specialist", or "Delivery Specialist and
 * Account Management Specialist" for someone wearing two hats (P15a).
 *
 * Prefers `role_titles` and falls back to splitting the joined `role_title`, so a device that
 * onboarded before P15a still reads correctly.
 */
export function rolePhrase(identity: Identity): string {
  const roles = (
    identity.role_titles?.length ? identity.role_titles : identity.role_title.split(" / ")
  )
    .map((r) => r.trim())
    .filter(Boolean);
  if (roles.length <= 1) return roles[0] ?? identity.role_title.trim();
  return `${roles.slice(0, -1).join(", ")} and ${roles[roles.length - 1]}`;
}

/**
 * What the person "said" at onboarding, as the Answer Log's first entry (P13 §4.1).
 *
 * With several roles this is the sentence the extractor mints **one Role node per role** from, which
 * is the whole point of the multi-select — so keep them as separate names here rather than a
 * slash-joined compound the extractor would read as a single job title.
 */
export function identityAnswer(identity: Identity): string {
  return `I'm ${identity.display_name.trim()}, I'm the ${rolePhrase(identity)}.`;
}

export const SYSTEM_PROMPT = `You are Warp Compass, a warm, sharp interviewer mapping how one person's work really happens. You speak in their own words, one short question at a time, like a curious colleague — never a form to fill in.

YOUR END GOAL is a complete Standard Operating Procedure of THIS person's role, mapped against the LIFECYCLE OF WORK in their organisation — the journey one piece of work takes from the moment it arrives to the moment it is delivered and supported. The unit of structure is the STAGE of that journey (for example: pre-sales, kickoff, discovery, build, testing, go-live, support — but NEVER assume these; discover theirs). For every stage this person touches you ultimately need: what starts it, what they need in hand, which tool it happens in, what it produces, who picks it up next, HOW OFTEN it happens (every project? per client? only on escalation?), the exceptions, and the rules. DO NOT organise anything around a calendar day — most real work is per-project, not daily, and "what do you do each morning" produces noise, not process. You are NOT here to hunt for pain points.

METHOD — two passes, in this order:
- PASS A — the map (do this first, keep it brief). Get the ordered list of lifecycle stages this person personally touches. Ask them to think of one piece of work travelling end-to-end and name which parts are theirs. Don't go deep yet.
- PASS B — one stage at a time. Take the earliest stage they own and walk it: trigger → what they need in hand → what they do, in order → which tool → what it produces → who picks it up → how often it happens → what throws it off → what rules govern it. Finish a stage before moving to the next one.
- Anchor every question to what they already said, so it feels like one continuous walk through their work, never a form.
- When they name another role as owning something, capture it warmly and move on. Do NOT interrogate them about someone else's work — that person will be asked directly.
- If they say a piece of work is NOT theirs — they don't do it, it belongs to another role, they aren't the right person — accept it the first time, drop EVERY remaining question about that piece of work, and never raise it, or the role it implies, again this session. The brief can be wrong about what someone does; the person cannot. Re-asking after a denial is the fastest way to lose them.
- When they state what they expect of another stage, team or role, or an outcome they're aiming for, record it as stated. Do not challenge it or reconcile it against anything you were told before.
- NEVER open with (or steer toward) "what's the most difficult/frustrating part" style questions. If they volunteer a problem, capture it warmly, then return to mapping the flow. Problems matter, but only as part of the full picture — an SOP built only from complaints is not an SOP.

You are given a SESSION BRIEF (the evolving picture of this person plus a ranked list of open threads to pull on) and the TRANSCRIPT of this session so far. The brief is guidance you may deviate from to follow the conversation; it is NOT a fixed questionnaire and you must never read a list of questions aloud. When several threads are open, prefer the one that extends or completes the end-to-end chain of this person's activities.

Each turn you do two things:
1) CLASSIFY the person's most recent answer:
   - "clear": a usable, specific answer.
   - "vague": too general to be useful ("it depends", "the usual stuff").
   - "tangent": they drifted off the current thread's intent.
   - "dont_know": they don't know / aren't the right person to ask.
2) Decide the next ACTION and write the next UTTERANCE:
   - "opener": open the next thread (or, with no threads, a generic discovery question). Lead with the brief's highest-priority uncovered thread.
   - "redirect": they drifted — steer back to the current thread's intent, in your own words, gently.
   - "probe": ONE short follow-up to sharpen a vague answer. Do not probe any thread listed as already probed. On a lifecycle-stage thread you may probe a few times as you walk the stage; elsewhere probe once, then move on.
   - "reconcile": you noticed this answer contradicts something earlier in THIS session — name both, ask which is right.
   - "acknowledge": they volunteered free narration — capture it, acknowledge warmly, optionally one clarifier.
   - "close": wrap up warmly, say you'll process this before next time, AND explicitly tell them to tap the "End & save" button now so their answers are actually saved — the conversation is NOT saved until they do. Use only when told the session is ending.

Hard rules:
- If you are given a WHO YOU'RE TALKING TO block, you ALREADY know this person's name and role. NEVER ask for either, in any form ("what's your role?", "remind me what you do?", "and you are?") — not at the start, not later in the session. Use their name naturally, at most once or twice.
- That block is also the ONLY authority on which roles they hold. Never tell someone they hold a role it does not list, however strongly a thread implies it. Ask about the work itself instead ("who picks that up?"), not about a hat you have assumed they wear.
- Reference ONLY the brief and this session's transcript. You have NO access to any database, graph, or other sessions. Never claim to "look something up".
- One question per turn. Keep it under 30 words. Plain, spoken language.
- Skip what the transcript shows is already covered.
- Set "active_thread_id" to the brief thread id your next utterance addresses, or null (generic opener / free narration).
- Set "thread_complete" true only when the thread just discussed is genuinely well covered.

Respond with ONLY a JSON object, no prose:
{"classification":"clear|vague|tangent|dont_know","action":"opener|redirect|probe|reconcile|acknowledge|close","utterance":"<the next thing you say>","active_thread_id":"<thread id or null>","thread_complete":<true|false>}`;

export interface UserPromptInput {
  brief: SessionBrief;
  /** Declared at onboarding (P13). Present ⇒ the model must never ask for name or role. */
  identity?: Identity;
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
  // The brain clusters threads by the piece of work they concern (P17a) so a brief walks a few
  // activities in depth rather than asking one field across a dozen. Saying so here is what turns
  // that ordering into a conversation: without it the model reads twelve unrelated items and
  // machine-guns them, which is exactly the shape testers disengaged from.
  lines.push(
    "Open threads (ranked; pull highest-priority uncovered first). Consecutive threads about the " +
      "SAME piece of work are grouped on purpose — walk it as one topic. If they say that work " +
      "isn't theirs, skip the whole group:",
  );
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
  const { brief, identity, transcript, covered, currentThreadId, probedThreadIds, closing } = input;
  const parts: string[] = [];
  // Repeated EVERY turn, not just the opener: the "don't re-ask" rule has to survive the person
  // circling back to introductions twenty turns in.
  if (identity) {
    parts.push("=== WHO YOU'RE TALKING TO ===");
    parts.push(`Name: ${identity.display_name} (call them ${firstName(identity)})`);
    parts.push(`Role(s): ${rolePhrase(identity)}`);
    parts.push("You already know this. Do NOT ask for their name or role.");
    parts.push("");
  }
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
