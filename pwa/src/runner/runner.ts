/**
 * The live runner turn loop (Phase 5, `runner/runner.ts`).
 *
 * Consumes a Session Brief, converses over this-session context only, and writes an Answer Log.
 * It holds NO graph and performs NO extraction/resolution (docs/02 §4.1) — that is the batch
 * brain's job. Each turn: take the person's input → ask the live model to classify it and pick
 * the next utterance → apply a thin deterministic guard layer ("LLM proposes, rules dispose",
 * AGENTS.md) → append to the Answer Log → return the next utterance.
 *
 * The only guard with teeth is the **probe budget**: a vague thread gets a bounded number of
 * follow-ups, then the runner covers it and advances. That budget is 1 for most threads and 3 for a
 * lifecycle-**stage** thread (P15b §8.5) — walking a stage genuinely takes several turns, and the P5
 * "never twice" rule cut the deep dive off before it started. Cold-start openers and thread
 * advancement stay deterministic so the loop is testable without a live model; everything
 * conversational (redirect, reconcile, acknowledge, reword) is the model's call.
 */

import { AnswerLogBuilder } from "./answerlog";
import {
  buildUserPrompt,
  firstName,
  identityAnswer,
  IDENTITY_QUESTION,
  isLiveDecision,
  rolePhrase,
  SYSTEM_PROMPT,
} from "./prompts";
import { Session } from "./session";
import { LLMError } from "./types";
import type { ActionKind, Identity, LiveDecision, LLMProvider, SessionBrief } from "./types";

/** The final sign-off spoken once the person has already tapped "End & save". */
export const CLOSING_UTTERANCE =
  "That's really helpful — thank you. I'll take some time to make sense of all this before we next talk. Have a good one.";

/**
 * Spoken the moment the runner runs out of open threads on its own, BEFORE the person has tapped
 * "End & save". Unlike `CLOSING_UTTERANCE`, this names the button explicitly — the session isn't
 * actually saved until they tap it, and a purely conversational sign-off here is exactly what let a
 * tester believe they were done and walk away without saving.
 */
export const THREADS_DONE_UTTERANCE =
  'That\'s really helpful — I think we\'ve covered everything for today. Please tap "End & save" below now so your answers are saved before you go.';

export interface TurnResult {
  /** What the agent says next (after the guard layer). */
  utterance: string;
  /** The raw decision the live model returned. */
  decision: LiveDecision;
  /** The action actually taken, after the one-probe guard (may differ from `decision.action`). */
  effectiveAction: ActionKind;
}

export interface RunnerClock {
  /** ISO-8601 timestamp for the next logged entry. Injected so tests stay deterministic. */
  now(): string;
}

export interface RunnerOptions {
  participantId?: string;
  /** Declared at onboarding (P13): greets by name, and stops the model re-asking name/role. */
  identity?: Identity;
  /**
   * Seed the Answer Log's first entry with what the person declared at onboarding, so the brain
   * mints their Role node from turn zero (P13 §4.1). Set only on the FIRST session that reaches
   * the brain — otherwise every round re-ingests the same introduction.
   */
  seedIdentity?: boolean;
}

export class Runner {
  readonly session: Session;
  readonly log: AnswerLogBuilder;
  private readonly identity?: Identity;

  constructor(
    brief: SessionBrief,
    private readonly llm: LLMProvider,
    private readonly clock: RunnerClock,
    opts: RunnerOptions = {},
  ) {
    this.identity = opts.identity;
    this.session = new Session(brief, opts.identity);
    this.log = new AnswerLogBuilder(
      brief.session_id,
      brief.persona_id,
      opts.participantId ?? brief.persona_id, // prototype: participant maps 1:1 to persona
    );
    if (opts.seedIdentity && opts.identity) {
      // Free narration, because the person volunteered it rather than answering a brief thread.
      // The extractor abstracts the personal name away and keeps the ROLE (P12 §8), which is
      // exactly what we want in the graph.
      this.log.appendSeed({
        raw_answer: identityAnswer(opts.identity),
        ts: this.clock.now(),
        kind: "free_narration",
        thread_id: null,
        agent_utterance: IDENTITY_QUESTION,
      });
    }
  }

  /**
   * The opening utterance. Deterministic: a generic opener on a cold start, otherwise the
   * top-priority thread's suggested opener (scaffolding the runner may reword — not rails).
   *
   * With a declared identity (P13) the opener is prefixed with a greeting and the "tell me about
   * your role" cold-start question is dropped entirely — this is the turn P13 exists to save.
   */
  start(): string {
    const s = this.session;
    if (s.brief.cold_start || s.brief.open_threads.length === 0) {
      s.currentThreadId = null;
      s.lastAgentUtterance = this.greet(s.nextColdStartOpener(), true);
      return s.lastAgentUtterance;
    }
    const top = s.nextThread();
    s.currentThreadId = top ? top.id : null;
    const opener = top?.suggested_opener ?? top?.goal ?? s.nextColdStartOpener();
    s.lastAgentUtterance = this.greet(opener, false);
    return s.lastAgentUtterance;
  }

  /** Prefix an opener with a first-name greeting when we know who this is. */
  private greet(opener: string, cold: boolean): string {
    if (!this.identity) return opener;
    const who = firstName(this.identity);
    return cold
      ? `Hi ${who} — you're the ${rolePhrase(this.identity)}. ${opener}`
      : `Welcome back, ${who}. ${opener}`;
  }

  /**
   * Feed one person answer. Logs it (paired with the question it answered), asks the model for
   * the next move, applies the guard layer, and returns the next utterance.
   */
  async respond(personAnswer: string): Promise<TurnResult> {
    const s = this.session;
    const agentUtterance = s.lastAgentUtterance; // the question this answer responds to
    const threadAtQuestion = s.currentThreadId;

    s.recordTurn(agentUtterance, personAnswer);

    const decision = await this.decide(false);

    // Record the answer. thread_id follows the thread the question addressed unless the person
    // drifted (tangent → free narration); kind follows whether the agent guided the turn.
    const drifted = decision.classification === "tangent";
    const thread_id = drifted ? null : threadAtQuestion;
    const kind = agentUtterance && !drifted ? "guided" : "free_narration";
    this.log.append({
      raw_answer: personAnswer,
      ts: this.clock.now(),
      kind,
      thread_id,
      agent_utterance: agentUtterance,
    });

    // ── guard layer ───────────────────────────────────────────────────────
    // The model reports whether the just-discussed thread is now covered.
    if (decision.thread_complete && threadAtQuestion) s.markCovered(threadAtQuestion);

    let effectiveAction: ActionKind = decision.action;
    let utterance = decision.utterance;

    if (decision.action === "probe") {
      const tid = threadAtQuestion ?? decision.active_thread_id;
      if (tid && s.probeBudgetExhausted(tid)) {
        // Probe budget spent (1 normally, 3 on a lifecycle-stage deep dive — P15b §8.5):
        // cover the thread and advance rather than circling it.
        s.markCovered(tid);
        const adv = this.advance();
        effectiveAction = adv.action;
        utterance = adv.utterance;
      } else if (tid) {
        s.markProbed(tid);
        s.currentThreadId = tid; // stay on this thread while it still has budget
      } else {
        s.currentThreadId = decision.active_thread_id;
      }
    } else {
      // Trust the model's choice of which thread the next utterance addresses.
      s.currentThreadId = decision.active_thread_id;
    }

    s.lastAgentUtterance = utterance;
    return { utterance, decision, effectiveAction };
  }

  /** Graceful close. Logs nothing further; returns a warm sign-off (no "thinking" wait). */
  close(): string {
    this.session.lastAgentUtterance = CLOSING_UTTERANCE;
    return CLOSING_UTTERANCE;
  }

  // ── internals ─────────────────────────────────────────────────────────────

  /** Deterministically move to the next uncovered thread, or signal a close. */
  private advance(): { utterance: string; action: ActionKind } {
    const next = this.session.nextThread();
    if (next) {
      this.session.currentThreadId = next.id;
      return {
        utterance: next.suggested_opener ?? `Let's talk about ${next.goal}`,
        action: "opener",
      };
    }
    this.session.currentThreadId = null;
    return { utterance: THREADS_DONE_UTTERANCE, action: "close" };
  }

  /** One live model call → a validated `LiveDecision`. */
  private async decide(closing: boolean): Promise<LiveDecision> {
    const s = this.session;
    const user = buildUserPrompt({
      brief: s.brief,
      identity: this.identity,
      transcript: s.transcript,
      covered: s.coveredIds(),
      currentThreadId: s.currentThreadId,
      probedThreadIds: s.probedIds(),
      closing,
    });
    const raw = await this.llm.completeJSON(SYSTEM_PROMPT, user, { temperature: 0.3 });
    if (!isLiveDecision(raw)) {
      throw new LLMError(
        `live model returned an unexpected shape: ${JSON.stringify(raw).slice(0, 300)}`,
      );
    }
    return raw;
  }
}
