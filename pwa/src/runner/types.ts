/**
 * Shared TypeScript types for the live runner (Phase 5).
 *
 * The contract types (`SessionBrief`, `AnswerLog`, …) are the TS mirror of the language-neutral
 * JSON Schemas in `contracts/` — the same contract the Python brain mirrors as pydantic models.
 * Keep these in lock-step with `contracts/session-brief.schema.json` and
 * `contracts/answer-log.schema.json`; the answer-log writer validates against the schema at
 * runtime, so a drift here is caught by the tests.
 *
 * The runner holds NO graph (docs/02 §4.1): everything here is about consuming a brief and
 * emitting an Answer Log over this-session context only.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Contract: Brain → Runner (session-brief.schema.json)
// ─────────────────────────────────────────────────────────────────────────────

/** A conditional follow-up the runner *may* reword — scaffolding, not rails. */
export interface BriefFollowup {
  if: string;
  ask: string;
}

/** One ranked thread to pull on. `priority` is an integer RANK (1 = pull first). */
export interface BriefThread {
  id: string;
  goal: string;
  why?: string;
  priority: number;
  suggested_opener?: string;
  followups?: BriefFollowup[];
}

/**
 * Who the runner is talking to (Phase 13). Declared ONCE at onboarding and carried into every
 * session, so the interviewer never spends a turn asking for a name or a role it already has.
 * Runner-internal: it reaches the brain as the Answer Log's first entry, not as a log field.
 */
export interface Identity {
  display_name: string;
  /** Every declared role, joined with " / ". Always present — the P13-era shape. */
  role_title: string;
  /**
   * The declared roles as chosen (P15a). Optional so a pre-P15 caller still type-checks; prompts
   * prefer it when present because "the Delivery Specialist and Finance" reads better than a
   * slash-joined string, and the extractor gets two clean Role names instead of one compound.
   */
  role_titles?: string[];
}

/** The persona-scoped memory view + ranked open threads. Guidance, not a script. */
export interface SessionBrief {
  session_id: string;
  persona_id: string;
  schema_version?: string;
  /** True on a first-ever session (empty brain): no threads, only generic openers. */
  cold_start: boolean;
  persona_summary?: string;
  open_threads: BriefThread[];
  reserve_threads?: string[];
  /**
   * What this person has already told us, as flat one-line statements (P17c / WC-26).
   *
   * The brief has always carried what we still WANT (`open_threads`) and never what we already
   * HAVE, so the interviewer could not acknowledge a previous session — hence *"I had replied in my
   * previous sessions"* and *"Did I not tell you…?"*. Written deterministically by the brain from
   * the graph, never by a model: this is a memory, and a hallucinated memory is worse than none.
   */
  known_facts?: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Contract: Runner → Brain (answer-log.schema.json)
// ─────────────────────────────────────────────────────────────────────────────

/** One line of this session's transcript, as held in memory and fed to the model. */
export interface TranscriptTurn {
  agent: string | null;
  person: string;
}

export type AnswerKind = "guided" | "free_narration";

/** One immutable entry: the agent's utterance paired with the person's verbatim answer. */
export interface AnswerLogEntry {
  /** Open-thread this entry addresses, or null for free narration. */
  thread_id: string | null;
  kind: AnswerKind;
  /** What the agent said (null for free narration). */
  agent_utterance: string | null;
  /** Verbatim transcript — the permanent truth. */
  raw_answer: string;
  /** Optional pointer to recorded audio (voice arrives in P7). */
  audio_ptr?: string | null;
  /**
   * How the live model read this answer (P17c / WC-25). Optional so a device on old cached JS
   * still writes a valid log. Its reason for existing is the two refusals: a `dont_know` or
   * `not_mine` paired with a `thread_id` is what lets the brain stop asking. Before this field the
   * model classified the refusal and the runner threw it away, so *"the project timeline is not my
   * job"* — said three times in one session — never reached the graph and came back next round.
   */
  classification?: Classification;
  /** ISO-8601 timestamp. */
  ts: string;
}

/** Immutable, append-only — the SOURCE OF TRUTH the brain re-derives the graph from. */
export interface AnswerLog {
  session_id: string;
  persona_id: string;
  /** The real person/device. Prototype maps persona 1:1 from participant. */
  participant_id: string;
  schema_version?: string;
  entries: AnswerLogEntry[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Runner-internal: the live LLM turn contract (docs/02 §12 "Live runner")
// ─────────────────────────────────────────────────────────────────────────────

/**
 * How the live model read the person's most recent answer.
 *
 * **`dont_know` and `not_mine` are deliberately separate (P17c / WC-25).** They look alike in a
 * transcript and mean very different things to the brain: *"I don't know what triggers that"* closes
 * one question, *"the project timeline is not my job"* closes every question about the project
 * timeline. Collapsing them forces a choice between two wrong behaviours — a brief that re-asks the
 * other three clustered threads about work the person just disowned, or one that goes silent on an
 * activity they genuinely perform because they were hazy on a single detail. The model already has
 * to draw this line to obey the denial rule in `SYSTEM_PROMPT`; this makes the answer durable.
 */
export type Classification = "clear" | "vague" | "tangent" | "dont_know" | "not_mine";

/** What the next utterance is doing. */
export type ActionKind =
  | "opener" // first pull on a thread (or a generic discovery opener)
  | "redirect" // person drifted; steer back to the current thread's intent
  | "probe" // one follow-up on a vague answer
  | "reconcile" // surface a within-session contradiction and resolve it
  | "acknowledge" // capture free narration, acknowledge, maybe one clarifier
  | "close"; // graceful close

/**
 * The single JSON object the live model returns each turn: it (a) classifies the previous
 * answer and (b) produces the next utterance — using ONLY the brief + this session's transcript.
 * It must never reference or query the graph.
 */
export interface LiveDecision {
  classification: Classification;
  action: ActionKind;
  /** The next thing the agent says. */
  utterance: string;
  /** The thread the *next* utterance addresses, or null (cold start / generic / free narration). */
  active_thread_id: string | null;
  /** True when the thread just discussed is sufficiently covered → advance the cursor. */
  thread_complete: boolean;
}

/**
 * A minimal, swappable provider seam (mirrors the brain's `LLMProvider`). One strict-JSON call
 * is all the live runner needs. Implementations handle retry/backoff and JSON parsing internally
 * and throw `LLMError` on failure. In the shipped PWA the implementation routes through the
 * Cloudflare Worker (keys never reach the browser, AGENTS.md); tests use a scripted fake.
 */
export interface LLMProvider {
  completeJSON(system: string, user: string, opts?: { temperature?: number }): Promise<unknown>;
}

export class LLMError extends Error {}
