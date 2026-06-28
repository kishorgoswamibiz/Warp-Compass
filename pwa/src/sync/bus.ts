/**
 * Bus client helpers (Phase 8). A browser PWA can't write to the shared folder directly, so the
 * "bus" on the phone side is a **manual** file hand-off (DECISION #8): export = download the Answer
 * Log (the operator drops it into `participants/{id}/answer_logs/`), import = pick the latest brief
 * file the operator copied out of `participants/{id}/briefs/`. A networked endpoint swaps in later
 * behind the same two operations.
 */

import type { AnswerLog, SessionBrief } from "../runner";

/** The bus filename convention for an Answer Log: keyed by session, unique per session. */
export function answerLogFilename(log: { session_id: string }): string {
  return `${log.session_id}.json`;
}

/** Trigger a browser download of the Answer Log under the bus filename convention. */
export function downloadAnswerLog(log: AnswerLog): void {
  const blob = new Blob([JSON.stringify(log, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = answerLogFilename(log);
  a.click();
  URL.revokeObjectURL(url);
}

/** Parse + minimally validate a Session Brief file the operator imported from the bus. */
export async function parseBriefFile(file: File): Promise<SessionBrief> {
  let data: unknown;
  try {
    data = JSON.parse(await file.text());
  } catch {
    throw new Error("That file isn't valid JSON.");
  }
  const b = data as Partial<SessionBrief>;
  if (
    !b ||
    typeof b.session_id !== "string" ||
    typeof b.persona_id !== "string" ||
    typeof b.cold_start !== "boolean" ||
    !Array.isArray(b.open_threads)
  ) {
    throw new Error("That file isn't a Session Brief.");
  }
  return b as SessionBrief;
}
