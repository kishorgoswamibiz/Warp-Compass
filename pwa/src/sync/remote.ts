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

/**
 * How long the push may take before we call it dead. Nothing here (browser fetch → Pages Function →
 * Apps Script) has a deadline of its own, so without this a silent upstream leaves the promise
 * pending forever — and the closing screen, which now waits on it before letting the person leave,
 * would trap them on a dead screen with no way to reach the download fallback. Generous on purpose:
 * a cold Apps Script invocation is slow, and a false "failed" costs at most a duplicate log, which
 * the write-once bus discards.
 */
export const PUSH_TIMEOUT_MS = 45_000;

export interface PushResult {
  ok: boolean;
  written?: boolean; // false when the log already existed (write-once) — still a success
  reason?: string;
  error?: string;
}

/**
 * Push one Answer Log to the brain's Drive bus. Throws on network/HTTP failure, or when the upstream
 * stays silent past `PUSH_TIMEOUT_MS` — either way the caller falls back to the manual download.
 * Resolving one way or the other is a guarantee, not a nicety: the UI blocks the exit until it does.
 */
export async function pushAnswerLog(log: AnswerLog, participant: Participant): Promise<PushResult> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), PUSH_TIMEOUT_MS);
  try {
    const res = await fetch(PUSH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        participant_id: participant.participant_id,
        persona_id: participant.persona_id,
        // Declared at onboarding (P13). Apps Script merges these into profile.json and renders the
        // folder's README.md, which is what makes the Drive tree readable.
        display_name: participant.display_name,
        // Both shapes on purpose (P15a): `role_titles` is the truth, `role_title` is the joined string
        // every P13-era reader already understands — including an Apps Script deployment that has not
        // been updated yet, which is the situation today (PROGRESS Blockers).
        role_title: participant.role_title,
        role_titles: participant.role_titles,
        answer_log: log,
      }),
      signal: ctl.signal,
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
  } catch (e) {
    if (ctl.signal.aborted)
      throw new Error(`Sync timed out after ${Math.round(PUSH_TIMEOUT_MS / 1000)}s.`);
    throw e;
  } finally {
    clearTimeout(timer);
  }
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
