/**
 * Answer Log writer (Phase 5, `runner/answerlog.ts`).
 *
 * Accumulates the immutable, append-only entries that the runner emits — the SOURCE OF TRUTH the
 * brain re-derives the graph from (docs/02 §5, AGENTS.md "Two planes, one contract"). The runner
 * only ever WRITES this; it never reads the graph. Entries are valid-by-construction here; the
 * Node-only `validate.ts` checks a built log against `contracts/answer-log.schema.json`.
 */

import type { AnswerKind, AnswerLog, AnswerLogEntry } from "./types";

export const ANSWER_LOG_SCHEMA_VERSION = "1.0.0";

export class AnswerLogBuilder {
  private readonly entries: AnswerLogEntry[] = [];

  constructor(
    private readonly session_id: string,
    private readonly persona_id: string,
    private readonly participant_id: string,
  ) {}

  /**
   * Append one entry. `kind` follows the contract: an answer addressing a thread is `guided`
   * (with `thread_id` set); volunteered narration is `free_narration` (with `thread_id` null).
   */
  append(e: {
    raw_answer: string;
    ts: string;
    kind: AnswerKind;
    thread_id: string | null;
    agent_utterance: string | null;
    audio_ptr?: string | null;
  }): void {
    this.entries.push({
      thread_id: e.thread_id,
      kind: e.kind,
      agent_utterance: e.agent_utterance,
      raw_answer: e.raw_answer,
      audio_ptr: e.audio_ptr ?? null,
      ts: e.ts,
    });
  }

  count(): number {
    return this.entries.length;
  }

  /** The finished, contract-shaped Answer Log. */
  build(): AnswerLog {
    return {
      session_id: this.session_id,
      persona_id: this.persona_id,
      participant_id: this.participant_id,
      schema_version: ANSWER_LOG_SCHEMA_VERSION,
      entries: [...this.entries],
    };
  }

  toJSON(indent = 2): string {
    return JSON.stringify(this.build(), null, indent);
  }
}
