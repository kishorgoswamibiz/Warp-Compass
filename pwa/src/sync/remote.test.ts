/**
 * Phase 11 RemoteBus tests: the phone auto-pushes its Answer Log and auto-pulls its latest brief
 * over the same-origin sync endpoints. `fetch` is stubbed so this runs in Node with no network.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { pullLatestBrief, pushAnswerLog } from "./remote";
import type { AnswerLog } from "../runner";
import type { Participant } from "./participant";

const participant: Participant = { participant_id: "p_abc", persona_id: "p_abc", display_name: "Asha" };
const log = { session_id: "s_1", persona_id: "p_abc", entries: [] } as unknown as AnswerLog;

function stubFetch(status: number, body: unknown) {
  const f = vi.fn(
    async (_url: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", f);
  return f;
}

afterEach(() => vi.unstubAllGlobals());

describe("pushAnswerLog", () => {
  it("POSTs the log to /sync/answer-log and returns the result", async () => {
    const f = stubFetch(200, { ok: true, written: true, name: "s_1.json" });
    const res = await pushAnswerLog(log, participant);
    expect(res.written).toBe(true);
    const [url, init] = f.mock.calls[0];
    expect(url).toBe("/sync/answer-log");
    const sent = JSON.parse((init as RequestInit).body as string);
    expect(sent.participant_id).toBe("p_abc");
    expect(sent.answer_log.session_id).toBe("s_1");
  });

  it("treats an already-existing log (write-once) as success with written:false", async () => {
    stubFetch(200, { ok: true, written: false, reason: "exists" });
    const res = await pushAnswerLog(log, participant);
    expect(res.ok).toBe(true);
    expect(res.written).toBe(false);
  });

  it("throws on an error response so the caller can fall back to download", async () => {
    stubFetch(502, { ok: false, error: "upstream_unreachable" });
    await expect(pushAnswerLog(log, participant)).rejects.toThrow(/upstream_unreachable/);
  });
});

describe("pullLatestBrief", () => {
  it("returns the brief when one exists", async () => {
    const brief = { session_id: "s_next", persona_id: "p_abc", cold_start: false, open_threads: [] };
    const f = stubFetch(200, { ok: true, brief });
    const got = await pullLatestBrief("p_abc");
    expect(got?.persona_id).toBe("p_abc");
    expect(f.mock.calls[0][0]).toBe("/sync/brief?participant_id=p_abc");
  });

  it("returns null when there is no brief yet (before the first round)", async () => {
    stubFetch(200, { ok: true, brief: null });
    expect(await pullLatestBrief("p_abc")).toBeNull();
  });

  it("throws on failure so the caller cold-starts / offers manual import", async () => {
    stubFetch(500, { ok: false, error: "server_misconfigured" });
    await expect(pullLatestBrief("p_abc")).rejects.toThrow();
  });
});
