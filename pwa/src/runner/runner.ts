/**
 * The live runner turn loop (Phase 5, `runner/runner.ts`).
 *
 * Consumes a Session Brief, converses over this-session context only, and writes an Answer Log.
 * It holds NO graph and performs NO extraction/resolution (docs/02 §4.1) — that is the batch
 * brain's job. Each turn: take the person's input → ask the live model to classify it and pick
 * the next utterance → apply a thin deterministic guard layer ("LLM proposes, rules dispose",
 * AGENTS.md) → append to the Answer Log → return the next utterance.
 *
 * The only guard with teeth is the **one-probe rule**: a vague thread is probed at most once, then
 * the runner advances. Cold-start openers and thread advancement are deterministic so the loop is
 * testable without a live model; everything conversational (redirect, reconcile, acknowledge,
 * reword) is the model's call.
 */

import { AnswerLogBuilder } from "./answerlog";
import { buildUserPrompt, isLiveDecision, SYSTEM_PROMPT } from "./prompts";
import { Session } from "./session";
import { LLMError } from "./types";
import type { ActionKind, LiveDecision, LLMProvider, SessionBrief } from "./types";

export const CLOSING_UTTERANCE =
  "That's really helpful — thank you. I'll take some time to make sense of all this before we next talk. Have a good one.";

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

export class Runner {
  readonly session: Session;
  readonly log: AnswerLogBuilder;

  constructor(
    brief: SessionBrief,
    private readonly llm: LLMProvider,
    private readonly clock: RunnerClock,
    opts: { participantId?: string } = {},
  ) {
    this.session = new Session(brief);
    this.log = new AnswerLogBuilder(
      brief.session_id,
      brief.persona_id,
      opts.participantId ?? brief.persona_id, // prototype: participant maps 1:1 to persona
    );
  }

  /**
   * The opening utterance. Deterministic: a generic opener on a cold start, otherwise the
   * top-priority thread's suggested opener (scaffolding the runner may reword — not rails).
   */
  start(): string {
    const s = this.session;
    if (s.brief.cold_start || s.brief.open_threads.length === 0) {
      s.currentThreadId = null;
      s.lastAgentUtterance = s.nextColdStartOpener();
      return s.lastAgentUtterance;
    }
    const top = s.nextThread();
    s.currentThreadId = top ? top.id : null;
    s.lastAgentUtterance =
      top?.suggested_opener ?? top?.goal ?? s.nextColdStartOpener();
    return s.lastAgentUtterance;
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
      if (tid && s.hasProbed(tid)) {
        // One-probe rule: never probe the same thread twice — cover it and advance.
        s.markCovered(tid);
        const adv = this.advance();
        effectiveAction = adv.action;
        utterance = adv.utterance;
      } else if (tid) {
        s.markProbed(tid);
        s.currentThreadId = tid; // stay on this thread for the single probe
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
    return { utterance: CLOSING_UTTERANCE, action: "close" };
  }

  /** One live model call → a validated `LiveDecision`. */
  private async decide(closing: boolean): Promise<LiveDecision> {
    const s = this.session;
    const user = buildUserPrompt({
      brief: s.brief,
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
