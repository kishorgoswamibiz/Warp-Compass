/**
 * Participant identity (Phase 8 → **declared** in Phase 13).
 *
 * P8 minted an anonymous `p_<uuid>` on first launch: stable, but unreadable everywhere it landed —
 * the Drive folder name, the graph's provenance `said_by`, the deliverable's source lines. P13
 * replaces it with an identity the person **declares once**: a typed name + role, from which we mint
 * a readable, filesystem-safe id. P15a makes the role **multi-valued** (`role_titles`), because one
 * person commonly holds several — the id still comes from the first one and never moves.
 *
 *     Rahul Mehta · Business Analysis Specialist  →  rahul-mehta-business-analysis-s-3c1f
 *
 * The id is minted ONCE and is **immutable thereafter** — it is stamped permanently into graph
 * provenance, so a later correction to the person's name updates `display_name` only, never the id
 * (ADR #29). `updateIdentity` enforces that.
 *
 * The prototype still maps **persona 1:1 to participant** (`persona_id = participant_id`, ADR #17),
 * so `run-round` routes each brief back to the right folder.
 *
 * Storage is injectable so the logic is testable off-browser (Node has no `localStorage`).
 */

export interface Participant {
  participant_id: string;
  persona_id: string;
  /** How the person wrote their name. Display only — never part of the id after minting. */
  display_name: string;
  /**
   * Every role this person holds, chosen from `ROLE_REGISTRY` (P15a). **The canonical field.**
   * Always ≥1 entry. Multi-valued because real people wear several hats — a Delivery Specialist who
   * also does sales gets both, and the graph gets a Role node for each (P15 §4.5).
   */
  role_titles: string[];
  /**
   * `role_titles` joined with " / ", e.g. `"Delivery Specialist / Account Management Specialist"`.
   *
   * **Derived, never authored.** It exists so every P13-era consumer keeps working untouched — the
   * whoami line, the Drive `profile.json`, the per-folder README, `cli list-participants`. The
   * separator matches what the graph already contained before P15 ("Delivery Specialist / Project
   * Manager"), so nothing downstream has to learn a new shape.
   */
  role_title: string;
  /** ISO-8601 stamp of when onboarding completed. */
  onboarded_at: string;
  /**
   * Set once an Answer Log carrying the identity entry has left the device (P13 §4.1). Until then
   * every session re-seeds it, so an abandoned first session can't cost the graph its Role node;
   * after it, no session repeats the introduction.
   */
  identity_seeded_at?: string;
  /** A pre-P13 `p_<uuid>` this device carried before onboarding, kept for traceability. */
  previous_id?: string;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const KEY = "wc.participant";

/** How `role_titles` collapses into the legacy single-string `role_title`. */
const ROLE_JOIN = " / ";

/** Trim, drop blanks, drop duplicates — the shape `role_titles` is always stored in. */
function normalizeRoles(roles: readonly string[]): string[] {
  return [...new Set(roles.map((r) => r.trim()).filter(Boolean))];
}

/** Per-part slug budget. Keeps a full id under ~55 chars → Windows MAX_PATH headroom for
 *  `%BUS_ROOT%\participants\<id>\answer_logs\s_….json`. */
const MAX_PART = 24;

function memoryStorage(): StorageLike {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
  };
}

function defaultStorage(): StorageLike {
  return typeof localStorage !== "undefined" ? localStorage : memoryStorage();
}

// ── id minting ────────────────────────────────────────────────────────────────

/** `n` hex chars from the CSPRNG when available (Math.random is the non-secure fallback). */
function hex(n: number): string {
  const bytes = new Uint8Array(Math.ceil(n / 2));
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, n);
}

/**
 * One id part: lowercase, diacritics stripped, non-alphanumerics collapsed to `-`, trimmed, capped.
 * Guarantees the result starts with `[a-z0-9]` (or is empty) — so a minted id can never begin with
 * `_` and collide with the bus's reserved `_archive` / `_retired.json` entries.
 */
export function slugPart(text: string, max: number = MAX_PART): string {
  return text
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "") // strip combining accents left by NFKD
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, max)
    .replace(/-+$/g, ""); // a mid-word cut must not leave a trailing hyphen
}

/**
 * Mint the permanent participant id from a declared name + role. The 4-hex suffix keeps two people
 * with the same name and role apart. Unslugabble input (emoji-only, blank) falls back to
 * `user-<8 hex>` so onboarding can never dead-end.
 *
 * With several roles (P15a) only the **first** is used, deliberately: the id is immutable once minted
 * (ADR #29) because it is stamped into graph provenance, so it must not move when someone adds or
 * drops a hat. The id is a durable *label*; `role_titles` is the truth about what they do.
 */
export function mintParticipantId(name: string, role: string): string {
  const parts = [slugPart(name), slugPart(role)].filter(Boolean);
  if (parts.length === 0) return `user-${hex(8)}`;
  return `${parts.join("-")}-${hex(4)}`;
}

// ── read ──────────────────────────────────────────────────────────────────────

function readRaw(storage: StorageLike): Partial<Participant> | null {
  const raw = storage.getItem(KEY);
  if (!raw) return null;
  try {
    const p = JSON.parse(raw) as Partial<Participant>;
    return p && typeof p === "object" ? p : null;
  } catch {
    return null; // corrupt record → treat as absent; onboarding re-mints
  }
}

/**
 * The onboarded participant, or `null` when this device hasn't been onboarded yet.
 *
 * A pre-P13 record (a `p_<uuid>` with no role at all) counts as **not** onboarded: the card shows
 * once and a new readable id is minted. The old UUID folder is abandoned rather than migrated —
 * migrating would mean rewriting provenance, which the immutability rule forbids.
 *
 * A **P13-era record** (single `role_title`, no `role_titles`) is a different case and IS onboarded:
 * it is read forward by splitting the joined string, so shipping P15a never re-onboards a device that
 * already has an identity — that would mint a second id for the same person and orphan their facts.
 */
export function getParticipant(storage: StorageLike = defaultStorage()): Participant | null {
  const p = readRaw(storage);
  if (!p?.participant_id || !p.persona_id) return null;
  const roles = normalizeRoles(
    p.role_titles?.length ? p.role_titles : (p.role_title ?? "").split(ROLE_JOIN),
  );
  if (roles.length === 0) return null; // legacy P8 record — no role was ever declared
  return {
    participant_id: p.participant_id,
    persona_id: p.persona_id,
    display_name: p.display_name ?? "",
    role_titles: roles,
    role_title: roles.join(ROLE_JOIN),
    onboarded_at: p.onboarded_at ?? "",
    ...(p.identity_seeded_at ? { identity_seeded_at: p.identity_seeded_at } : {}),
    ...(p.previous_id ? { previous_id: p.previous_id } : {}),
  };
}

/** True once name + role have been declared on this device. */
export function isOnboarded(storage: StorageLike = defaultStorage()): boolean {
  return getParticipant(storage) !== null;
}

/**
 * The onboarded participant, for call sites downstream of the onboarding gate (the session screen,
 * the sync push) where its absence is a programming error rather than a state to handle.
 */
export function requireParticipant(storage: StorageLike = defaultStorage()): Participant {
  const p = getParticipant(storage);
  if (!p) throw new Error("No participant on this device — onboarding has not completed.");
  return p;
}

// ── write ─────────────────────────────────────────────────────────────────────

/**
 * Complete onboarding: mint the permanent id and persist the identity. Overwrites any legacy record.
 *
 * `roles` is the multi-select from the onboarding card (P15a); `role` remains accepted as a
 * single-value shorthand so existing call sites and tests keep compiling.
 */
export function createParticipant(
  input: { name: string; role?: string; roles?: readonly string[]; now?: string },
  storage: StorageLike = defaultStorage(),
): Participant {
  const display_name = input.name.trim();
  const role_titles = normalizeRoles(input.roles ?? (input.role ? [input.role] : []));
  const previous = readRaw(storage)?.participant_id;
  const id = mintParticipantId(display_name, role_titles[0] ?? "");
  const p: Participant = {
    participant_id: id,
    persona_id: id, // prototype: persona 1:1 with participant (ADR #17)
    display_name,
    role_titles,
    role_title: role_titles.join(ROLE_JOIN),
    onboarded_at: input.now ?? new Date().toISOString(),
    ...(previous ? { previous_id: previous } : {}),
  };
  storage.setItem(KEY, JSON.stringify(p));
  return p;
}

/**
 * Correct the display name and/or roles after onboarding — including picking up a second hat.
 * **Never touches the id** — it is already stamped into graph provenance and Drive folder names
 * (ADR #29), so adding a role changes what we know about the person, not who they are.
 */
export function updateIdentity(
  changes: { name?: string; role?: string; roles?: readonly string[] },
  storage: StorageLike = defaultStorage(),
): Participant {
  const p = requireParticipant(storage);
  const incoming = normalizeRoles(changes.roles ?? (changes.role ? [changes.role] : []));
  const role_titles = incoming.length ? incoming : p.role_titles;
  const next: Participant = {
    ...p,
    display_name: changes.name?.trim() || p.display_name,
    role_titles,
    role_title: role_titles.join(ROLE_JOIN),
  };
  storage.setItem(KEY, JSON.stringify(next));
  return next;
}

/**
 * True while the identity entry still needs to be seeded into an Answer Log (P13 §4.1) — i.e. no
 * log carrying it has reached the brain yet.
 */
export function needsIdentitySeed(storage: StorageLike = defaultStorage()): boolean {
  const p = getParticipant(storage);
  return p !== null && !p.identity_seeded_at;
}

/** Record that a log carrying the identity entry has left the device. Idempotent. */
export function markIdentitySeeded(
  now: string = new Date().toISOString(),
  storage: StorageLike = defaultStorage(),
): void {
  const p = getParticipant(storage);
  if (!p || p.identity_seeded_at) return;
  storage.setItem(KEY, JSON.stringify({ ...p, identity_seeded_at: now }));
}

/**
 * Forget the identity on THIS DEVICE so the next launch shows onboarding ("Switch user").
 *
 * Device-local only: answers already pushed stay in the engagement's records. Removing a person
 * from the brain is a separate, operator-only step (`retire-participant`, P13 §6).
 */
export function clearParticipant(storage: StorageLike = defaultStorage()): void {
  storage.removeItem(KEY);
}
