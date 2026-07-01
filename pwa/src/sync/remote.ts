/**
 * RemoteBus (Phase 11) — the AUTOMATIC phone-side bus, replacing the manual file hand-off (P8).
 *
 * The PWA pushes its Answer Log and pulls its latest Session Brief over the network via the
 * same-origin Cloudflare Pages Functions (`/sync/answer-log`, `/sync/brief`), which forward to the
 * Google Apps Script Web App running as the owner (apps-script/Code.gs). No end-user Google login;
 * the phone only ever sees relative URLs. Both calls are best-effort with clear failure signalling so
 * the UI can fall back to the manual download/import when offline or misconfigured.
 */

import type { AnswerLog, SessionBrief } from "../runner";
import type { Participant } from "./participant";

const PUSH_URL = "/sync/answer-log";
const BRIEF_URL = "/sync/brief";

export interface PushResult {
  ok: boolean;
  written?: boolean; // false when the log already existed (write-once) — still a success
  reason?: string;
  error?: string;
}

/** Push one Answer Log to the brain's Drive bus. Throws on network/HTTP failure (caller falls back). */
export async function pushAnswerLog(log: AnswerLog, participant: Participant): Promise<PushResult> {
  const res = await fetch(PUSH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      participant_id: participant.participant_id,
      persona_id: participant.persona_id,
      display_name: participant.display_name,
      answer_log: log,
    }),
  });
  let data: PushResult;
  try {
    data = (await res.json()) as PushResult;
  } catch {
    throw new Error(`Sync failed (HTTP ${res.status}).`);
  }
  if (!res.ok || !data.ok) {
    throw new Error(data.error ? `Sync failed: ${data.error}` : `Sync failed (HTTP ${res.status}).`);
  }
  return data;
}

/**
 * Pull the participant's latest Session Brief from the bus. Returns `null` when there is none yet
 * (e.g. before the first batch round). Throws on network/HTTP failure so the caller can offer the
 * manual import fallback.
 */
export async function pullLatestBrief(participantId: string): Promise<SessionBrief | null> {
  const res = await fetch(`${BRIEF_URL}?participant_id=${encodeURIComponent(participantId)}`);
  let data: { ok?: boolean; brief?: SessionBrief | null; error?: string };
  try {
    data = await res.json();
  } catch {
    throw new Error(`Couldn't reach the brief service (HTTP ${res.status}).`);
  }
  if (!res.ok || !data.ok) {
    throw new Error(data.error ? `Brief fetch failed: ${data.error}` : `Brief fetch failed (HTTP ${res.status}).`);
  }
  return data.brief ?? null;
}
