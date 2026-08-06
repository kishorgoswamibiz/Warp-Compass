/**
 * Parity guard for the duplicated role registry (P15a).
 *
 * `roles.ts` is a hand-maintained mirror of `contracts/roles.json`. This test reads the contract off
 * disk and fails on ANY drift, so the duplication can never rot silently — the same discipline
 * PROMPTS.md §2 asks for around the two copies of `COLD_START_OPENERS`.
 */

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ROLE_NAMES, ROLE_REGISTRY, joinRoles } from "./roles";

interface Contract {
  roles: { slug: string; canonical_name: string; aliases: string[] }[];
}

const contract = JSON.parse(
  readFileSync(new URL("../../../contracts/roles.json", import.meta.url), "utf8"),
) as Contract;

describe("role registry parity with contracts/roles.json", () => {
  it("matches the contract exactly, including order", () => {
    expect(ROLE_REGISTRY.map((r) => ({ ...r, aliases: [...r.aliases] }))).toEqual(contract.roles);
  });

  it("exposes every contract title for the onboarding chips, in contract order", () => {
    expect(ROLE_NAMES).toEqual(contract.roles.map((r) => r.canonical_name));
    // Pinned so adding a chip stays a deliberate two-file change. 11 since "Solutions Lead"
    // (06 Aug 2026); the parity assertion above is what actually guards against drift.
    expect(ROLE_NAMES).toHaveLength(11);
  });

  it("carries the owner's decisions: Sales is an AMS alias, CEO and COO are roles", () => {
    const ams = ROLE_REGISTRY.find((r) => r.canonical_name === "Account Management Specialist");
    expect(ams?.aliases).toContain("Sales");
    expect(ROLE_NAMES).toContain("Chief Executive Officer");
    expect(ROLE_NAMES).toContain("Chief Operating Officer");
  });
});

describe("alias hygiene (a duplicate alias would MERGE two roles into one node)", () => {
  it("has no alias appearing under two roles, and no alias colliding with a canonical name", () => {
    const seen = new Map<string, string>();
    for (const role of ROLE_REGISTRY) {
      for (const name of [role.canonical_name, ...role.aliases]) {
        const key = name.toLowerCase();
        const owner = seen.get(key);
        expect(owner, `"${name}" is claimed by both ${owner} and ${role.canonical_name}`).toBe(
          undefined,
        );
        seen.set(key, role.canonical_name);
      }
    }
  });

  it("keeps QA and QA Head distinct — exact matching is what makes this safe", () => {
    const spec = ROLE_REGISTRY.find((r) => r.canonical_name === "Quality Assurance Specialist");
    const head = ROLE_REGISTRY.find((r) => r.canonical_name === "Quality Assurance Head");
    expect(spec?.aliases).toContain("QA");
    expect(head?.aliases).toContain("QA Head");
    expect(head?.aliases).not.toContain("QA");
  });
});

describe("joinRoles", () => {
  it("reads like a person for one, two and three hats", () => {
    expect(joinRoles(["Delivery Specialist"])).toBe("Delivery Specialist");
    expect(joinRoles(["Delivery Specialist", "Finance"])).toBe("Delivery Specialist and Finance");
    expect(joinRoles(["A", "B", "C"])).toBe("A, B and C");
  });

  it("ignores blanks rather than emitting a dangling 'and'", () => {
    expect(joinRoles(["Finance", "  ", ""])).toBe("Finance");
    expect(joinRoles([])).toBe("");
  });
});
