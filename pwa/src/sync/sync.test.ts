/**
 * Phase 8 phone-side sync tests: a STABLE participant id (persisted, persona 1:1) and the bus
 * filename convention + brief-import validation. Storage is injected so this runs in Node.
 */

import { describe, expect, it } from "vitest";
import { getParticipant, setDisplayName } from "./participant";
import type { StorageLike } from "./participant";
import { answerLogFilename, parseBriefFile } from "./bus";

function fakeStorage(): StorageLike {
  const m = new Map<string, string>();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v) };
}

describe("participant identity", () => {
  it("mints once and returns the SAME id on subsequent calls (stable across sessions)", () => {
    const s = fakeStorage();
    const a = getParticipant(s);
    const b = getParticipant(s);
    expect(a.participant_id).toBe(b.participant_id);
    expect(a.persona_id).toBe(a.participant_id); // prototype 1:1
  });

  it("persists a display name without changing the id", () => {
    const s = fakeStorage();
    const a = getParticipant(s);
    const named = setDisplayName("Asha", s);
    expect(named.participant_id).toBe(a.participant_id);
    expect(named.display_name).toBe("Asha");
    expect(getParticipant(s).display_name).toBe("Asha");
  });
});

describe("bus helpers", () => {
  it("names an Answer Log by session id", () => {
    expect(answerLogFilename({ session_id: "s_2026_0630" })).toBe("s_2026_0630.json");
  });

  it("parses a valid Session Brief file", async () => {
    const brief = {
      session_id: "s_next",
      persona_id: "p_abc",
      cold_start: false,
      open_threads: [],
    };
    const file = new File([JSON.stringify(brief)], "s_next.json", { type: "application/json" });
    const parsed = await parseBriefFile(file);
    expect(parsed.persona_id).toBe("p_abc");
  });

  it("rejects a non-brief JSON file", async () => {
    const file = new File([JSON.stringify({ hello: "world" })], "x.json");
    await expect(parseBriefFile(file)).rejects.toThrow(/Session Brief/);
  });

  it("rejects invalid JSON", async () => {
    const file = new File(["{not json"], "x.json");
    await expect(parseBriefFile(file)).rejects.toThrow(/JSON/);
  });
});
