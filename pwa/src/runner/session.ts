/**
 * Session state for the live runner (Phase 5, `runner/session.ts`).
 *
 * In-memory only: the brief + the growing transcript of THIS session (a few thousand tokens),
 * a thread cursor, and the covered/probed sets. No persistence, no graph — the Answer Log is the
 * only thing that leaves the session (docs/02 §4.1).
 */

import type { SessionBrief, TranscriptTurn } from "./types";
import { COLD_START_OPENERS } from "./prompts";

export class Session {
  readonly brief: SessionBrief;
  readonly transcript: TranscriptTurn[] = [];

  /** Thread the runner is currently pulling on (null = cold/generic/free). */
  currentThreadId: string | null = null;
  /** The exact utterance the agent last said (paired with the next person answer in the log). */
  lastAgentUtterance: string | null = null;

  private readonly covered = new Set<string>();
  private readonly probed = new Set<string>();
  /** Index into COLD_START_OPENERS for successive generic openers. */
  private coldStartCursor = 0;

  constructor(brief: SessionBrief) {
    this.brief = brief;
  }

  // ── transcript ──────────────────────────────────────────────────────────
  recordTurn(agent: string | null, person: string): void {
    this.transcript.push({ agent, person });
  }

  // ── thread bookkeeping ──────────────────────────────────────────────────
  markCovered(threadId: string): void {
    this.covered.add(threadId);
  }
  isCovered(threadId: string): boolean {
    return this.covered.has(threadId);
  }
  coveredIds(): string[] {
    return [...this.covered];
  }

  markProbed(threadId: string): void {
    this.probed.add(threadId);
  }
  hasProbed(threadId: string): boolean {
    return this.probed.has(threadId);
  }
  probedIds(): string[] {
    return [...this.probed];
  }

  /** The highest-priority thread not yet covered, or null when none remain. */
  nextThread() {
    const open = [...this.brief.open_threads].sort((a, b) => a.priority - b.priority);
    return open.find((t) => !this.covered.has(t.id)) ?? null;
  }

  /** True once every brief thread has been covered (drives a graceful close). */
  allThreadsCovered(): boolean {
    return this.brief.open_threads.every((t) => this.covered.has(t.id));
  }

  /** The next generic opener for a cold start, cycling through the canonical list. */
  nextColdStartOpener(): string {
    const opener = COLD_START_OPENERS[this.coldStartCursor % COLD_START_OPENERS.length];
    this.coldStartCursor += 1;
    return opener;
  }
}
