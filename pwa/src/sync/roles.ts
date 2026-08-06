/**
 * The engagement's role registry — PWA mirror of `contracts/roles.json` (P15a).
 *
 * ⚠ **DUPLICATED BY DESIGN, like `COLD_START_OPENERS`.** The contract is the source of truth; this is
 * the browser-side copy so the onboarding chips need no fetch and no JSON in the bundle graph.
 * `roles.test.ts` reads the contract off disk and fails loudly on any drift — canonical names,
 * aliases, order, all of it. If you edit one, edit both.
 *
 * Why aliases live in a shared contract at all: they are what stops "the PM" and "Delivery
 * Specialist" forking into two Role nodes in the graph, which would silently break question routing
 * (docs/plan/phase-15-lifecycle-and-alignment.md §4.3). The PWA itself only needs `canonical_name`
 * for the chips — the aliases ride along so there is exactly one place to add a synonym.
 */

export interface RoleEntry {
  /** Stable node slug the brain seeds this role under. */
  slug: string;
  /** The formal title. What the chip shows, and what lands in the graph. */
  canonical_name: string;
  /** Conversational synonyms — abbreviations and the words people actually say. */
  aliases: readonly string[];
}

export const ROLE_REGISTRY: readonly RoleEntry[] = [
  {
    slug: "role.business-analysis-specialist",
    canonical_name: "Business Analysis Specialist",
    aliases: ["BA", "Business Analyst", "BAS"],
  },
  {
    slug: "role.technical-specialist",
    canonical_name: "Technical Specialist",
    aliases: ["Developer", "Dev", "TS", "Engineer"],
  },
  {
    slug: "role.solution-architect",
    canonical_name: "Solution Architect",
    aliases: ["SA", "Architect"],
  },
  {
    slug: "role.solutions-lead",
    canonical_name: "Solutions Lead",
    // Deliberately narrow (ADR #33): a bare "Lead" would swallow every "dev lead" / "team lead"
    // mention and silently merge two real roles, which is the one failure an alias table can cause
    // that is worse than a missing synonym.
    aliases: ["Solution Lead", "SL"],
  },
  {
    slug: "role.delivery-specialist",
    canonical_name: "Delivery Specialist",
    aliases: ["Project Manager", "PM", "DS", "Delivery Manager"],
  },
  {
    slug: "role.account-management-specialist",
    canonical_name: "Account Management Specialist",
    aliases: ["Account Manager", "AMS", "AM", "Sales"],
  },
  {
    slug: "role.quality-assurance-head",
    canonical_name: "Quality Assurance Head",
    aliases: ["QA Head", "QA Lead", "Head of QA"],
  },
  {
    slug: "role.quality-assurance-specialist",
    canonical_name: "Quality Assurance Specialist",
    aliases: ["QA", "Tester", "QA Engineer", "QAS"],
  },
  {
    slug: "role.finance",
    canonical_name: "Finance",
    aliases: ["Finance Team", "Accounts", "Finance Specialist"],
  },
  {
    slug: "role.chief-executive-officer",
    canonical_name: "Chief Executive Officer",
    aliases: ["CEO", "Chief Executive"],
  },
  {
    slug: "role.chief-operating-officer",
    canonical_name: "Chief Operating Officer",
    aliases: ["COO", "Chief Operating"],
  },
];

/** Just the titles, in registry order — the onboarding chip list. */
export const ROLE_NAMES: readonly string[] = ROLE_REGISTRY.map((r) => r.canonical_name);

/**
 * Join role titles the way a person would say them, for greetings and the identity sentence:
 * "Delivery Specialist", "Delivery Specialist and Finance", "A, B and C".
 */
export function joinRoles(roles: readonly string[]): string {
  const list = roles.map((r) => r.trim()).filter(Boolean);
  if (list.length === 0) return "";
  if (list.length === 1) return list[0];
  return `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
}
