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
import type {
  ActionKind,
  Classification,
  Identity,
  LiveDecision,
  LLMProvider,
  SessionBrief,
} from "./types";

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

/**
 * The two classifications that mean "stop asking me this" (P17c / WC-25).
 *
 * `dont_know` scopes to the one thread, `not_mine` to the whole piece of work — a distinction the
 * brain acts on when it plans the next brief. In-session both do the same thing, because either way
 * the question just asked is spent.
 */
export function isRefusal(c: Classification): boolean {
  return c === "dont_know" || c === "not_mine";
}

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
  // Set once THREADS_DONE_UTTERANCE has fired, so a person who keeps talking after "we've covered
  // everything" doesn't hear the same wrap-up line repeated on every subsequent turn.
  private announcedDone = false;

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
   * The opening utterance.
   *
   * **Cold start stays deterministic** — `COLD_START_OPENERS` are already written for the ear, there
   * is no brief to be context-aware about, and skipping the call keeps a first-ever session instant.
   *
   * **A briefed session asks the model**, exactly like every other turn. Until P18 this printed the
   * brain's template verbatim, which made the one turn that sets the tone the one turn the model
   * never touched: the owner was opened with *"It sounds like Solution Architect hands 'Provide
   * Technical Solutions and Effort Estimates' over to you"* — a graph index label read aloud
   * mid-sentence. Worse than the wording, the template path never reads `WHO YOU'RE TALKING TO` or
   * `WHAT WE ALREADY KNOW`, so the opening question was structurally incapable of knowing what the
   * person had already told us (WC-26's block existed and could not reach turn one).
   *
   * With a declared identity (P13) the "tell me about your role" cold-start question is dropped
   * entirely — this is the turn P13 exists to save.
   */
  async start(): Promise<string> {
    const s = this.session;
    if (s.brief.cold_start || s.brief.open_threads.length === 0) {
      s.currentThreadId = null;
      s.lastAgentUtterance = this.greet(s.nextColdStartOpener(), true);
      return s.lastAgentUtterance;
    }
    const top = s.nextThread();
    // Pin the thread BEFORE the call, and keep it whatever the model reports (`opening` tells the
    // prompt it is already decided). The first answer is filed against `currentThreadId` — see
    // `respond` — so routing the opener through the model changes only the WORDS, never where the
    // answer lands. That makes turn one the one turn whose attribution is not the model's call,
    // where turns 2..n already trust `decision.active_thread_id`.
    s.currentThreadId = top ? top.id : null;
    const template = this.greet(
      top?.suggested_opener ?? top?.goal ?? s.nextColdStartOpener(),
      false,
    );
    s.lastAgentUtterance = await this.openingUtterance(template);
    return s.lastAgentUtterance;
  }

  /**
   * The model's opening words, falling back to the brain's template if the call fails.
   *
   * The fallback is load-bearing, not defensive padding: before P18 `start()` could not fail at all,
   * and this change introduces the first way for a session to die before its first question. A stiff
   * opening question is a small cost; a blank screen is the session.
   */
  private async openingUtterance(fallback: string): Promise<string> {
    try {
      const decision = await this.decide(false, true);
      return decision.utterance.trim() || fallback;
    } catch {
      return fallback;
    }
  }

  /**
   * Prefix an opener with a first-name greeting when we know who this is.
   *
   * Since P18 this runs on two paths only: a cold start, and the warm-session fallback. On a normal
   * warm session the model writes its own greeting, instructed by the prompt's opening block — so
   * keep the two readings close, or a failed call reads as a different app. (`PROMPTS.md` §1.)
   */
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
      // P17c / WC-25. The classification was already being computed every turn and thrown away;
      // persisting it is what lets a refusal outlive the session. It only bites paired with a
      // `thread_id`, which is why `tangent` — the one classification that nulls the thread — can
      // never suppress anything: drifting off a question is not refusing it.
      classification: decision.classification,
    });

    // ── guard layer ───────────────────────────────────────────────────────
    // The model reports whether the just-discussed thread is now covered.
    if (decision.thread_complete && threadAtQuestion) s.markCovered(threadAtQuestion);
    // A refusal closes the thread whatever the model reported (P17c / WC-25). `thread_complete`
    // asks "is this well covered?", and a model that has just been told *"that's not my job"*
    // reasonably answers no — which left the thread current and re-askable, the mechanic behind
    // *"I told you I do not act as a delivery specialist. Why you're not trying to understand?"*
    // A refused question is finished with; that is a rule, not a judgement call, so it lives here
    // rather than in the prompt. The cross-round half is the brain's (`lifecycle.declined_threads`).
    if (isRefusal(decision.classification) && threadAtQuestion) s.markCovered(threadAtQuestion);

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

    // The model is never told `closing: true` (see `decide`), and its own "close" action only
    // reaches here via the probe-exhaustion branch above — which requires the LAST remaining
    // thread specifically to be the one that got probed out, not just "no threads are left". A
    // thread that completes via "opener"/"acknowledge" (decision.thread_complete, no probing
    // involved) falls through both branches above with nothing checking whether that was the
    // final one. So check directly: on a briefed (non-cold-start) session, once every thread is
    // covered, force the close regardless of what the model chose for this turn — a briefed
    // session running dry is an objective fact the guard layer must not miss (WC-R11).
    if (
      effectiveAction !== "close" &&
      !this.announcedDone &&
      !s.brief.cold_start &&
      s.brief.open_threads.length > 0 &&
      s.allThreadsCovered()
    ) {
      effectiveAction = "close";
      utterance = THREADS_DONE_UTTERANCE;
      s.currentThreadId = null;
    }
    if (effectiveAction === "close") this.announcedDone = true;

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
  private async decide(closing: boolean, opening = false): Promise<LiveDecision> {
    const s = this.session;
    const user = buildUserPrompt({
      brief: s.brief,
      identity: this.identity,
      transcript: s.transcript,
      covered: s.coveredIds(),
      currentThreadId: s.currentThreadId,
      probedThreadIds: s.probedIds(),
      closing,
      opening,
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
