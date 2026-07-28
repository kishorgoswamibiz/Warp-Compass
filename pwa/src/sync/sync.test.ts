/**
 * Phone-side sync tests: the DECLARED participant identity (P13 — minted once, readable, immutable)
 * and the bus filename convention + brief-import validation. Storage is injected so this runs in
 * Node.
 */

import { describe, expect, it } from "vitest";
import {
  clearParticipant,
  createParticipant,
  getParticipant,
  isOnboarded,
  markIdentitySeeded,
  mintParticipantId,
  needsIdentitySeed,
  requireParticipant,
  slugPart,
  updateIdentity,
} from "./participant";
import type { StorageLike } from "./participant";
import { answerLogFilename, parseBriefFile } from "./bus";

function fakeStorage(): StorageLike {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
  };
}

const KEY = "wc.participant";

describe("id slugging", () => {
  it("lowercases, strips punctuation, and collapses separators", () => {
    expect(slugPart("Rahul  Mehta")).toBe("rahul-mehta");
    expect(slugPart("O'Brien-Smith, Jr.")).toBe("o-brien-smith-jr");
  });

  it("strips diacritics rather than dropping the letters", () => {
    expect(slugPart("José Ångström")).toBe("jose-angstrom");
  });

  it("caps a part and never leaves a trailing hyphen at the cut", () => {
    const long = slugPart("Senior Regional Operations Coordinator");
    expect(long.length).toBeLessThanOrEqual(24);
    expect(long.endsWith("-")).toBe(false);
  });

  it("yields an empty part for unslugabble input", () => {
    expect(slugPart("🙂🙂")).toBe("");
    expect(slugPart("   ")).toBe("");
  });

  it("mints a readable id that starts with an alphanumeric (never a reserved '_' name)", () => {
    const id = mintParticipantId("Rahul Mehta", "Business Analyst");
    expect(id).toMatch(/^rahul-mehta-business-analyst-[0-9a-f]{4}$/);
    expect(id.startsWith("_")).toBe(false);
  });

  it("falls back to user-<hex> so onboarding can never dead-end", () => {
    expect(mintParticipantId("🙂", "  ")).toMatch(/^user-[0-9a-f]{8}$/);
  });

  it("keeps two people with the same name and role apart", () => {
    const a = mintParticipantId("Rahul", "Analyst");
    const b = mintParticipantId("Rahul", "Analyst");
    expect(a).not.toBe(b);
  });
});

describe("participant identity", () => {
  it("is absent until onboarding completes", () => {
    const s = fakeStorage();
    expect(getParticipant(s)).toBeNull();
    expect(isOnboarded(s)).toBe(false);
    expect(() => requireParticipant(s)).toThrow(/onboarding/i);
  });

  it("persists the declared identity and returns the SAME id on later calls", () => {
    const s = fakeStorage();
    const created = createParticipant({ name: "Rahul Mehta", role: "Business Analyst" }, s);
    const again = getParticipant(s);
    expect(again?.participant_id).toBe(created.participant_id);
    expect(again?.persona_id).toBe(created.participant_id); // prototype 1:1 (ADR #17)
    expect(again?.display_name).toBe("Rahul Mehta");
    expect(again?.role_title).toBe("Business Analyst");
    expect(isOnboarded(s)).toBe(true);
  });

  it("trims what the person typed", () => {
    const s = fakeStorage();
    const p = createParticipant({ name: "  Asha  ", role: "  Sales Rep " }, s);
    expect(p.display_name).toBe("Asha");
    expect(p.role_title).toBe("Sales Rep");
  });

  it("corrects the name WITHOUT changing the id (ADR #29 immutability)", () => {
    const s = fakeStorage();
    const created = createParticipant({ name: "Rahul Mehtaa", role: "Business Analyst" }, s);
    const fixed = updateIdentity({ name: "Rahul Mehta" }, s);
    expect(fixed.participant_id).toBe(created.participant_id);
    expect(fixed.display_name).toBe("Rahul Mehta");
    expect(getParticipant(s)?.participant_id).toBe(created.participant_id);
  });

  it("treats a pre-P13 p_<uuid> record as NOT onboarded and records it as previous_id", () => {
    const s = fakeStorage();
    s.setItem(KEY, JSON.stringify({ participant_id: "p_legacy-uuid", persona_id: "p_legacy-uuid" }));
    expect(getParticipant(s)).toBeNull(); // no role_title → onboarding shows once

    const fresh = createParticipant({ name: "Rahul", role: "Analyst" }, s);
    expect(fresh.participant_id).not.toBe("p_legacy-uuid");
    expect(fresh.previous_id).toBe("p_legacy-uuid");
  });

  it("treats a corrupt record as absent rather than throwing", () => {
    const s = fakeStorage();
    s.setItem(KEY, "{not json");
    expect(getParticipant(s)).toBeNull();
  });

  it("switch user clears the device only", () => {
    const s = fakeStorage();
    createParticipant({ name: "Rahul", role: "Analyst" }, s);
    clearParticipant(s);
    expect(getParticipant(s)).toBeNull();
  });

  it("needs the identity seed until a log carrying it has left the device", () => {
    const s = fakeStorage();
    createParticipant({ name: "Rahul", role: "Analyst" }, s);
    expect(needsIdentitySeed(s)).toBe(true);

    markIdentitySeeded("2026-07-28T10:00:00.000Z", s);
    expect(needsIdentitySeed(s)).toBe(false);
    expect(getParticipant(s)?.identity_seeded_at).toBe("2026-07-28T10:00:00.000Z");

    // Idempotent: a second push must not move the stamp.
    markIdentitySeeded("2026-07-29T10:00:00.000Z", s);
    expect(getParticipant(s)?.identity_seeded_at).toBe("2026-07-28T10:00:00.000Z");
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
