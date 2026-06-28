/**
 * Participant identity (Phase 8). The bus folder is keyed by `participant_id`, so the phone needs a
 * STABLE id across sessions (not a fresh UUID each time, as P6 did). We mint one on first launch and
 * persist it; the prototype maps **persona 1:1 to participant** (`persona_id = participant_id`), so
 * the brain's run-round can route each brief back to the right folder (ADR #17 — persona is the
 * provenance `said_by`, no `:Persona` node).
 *
 * Storage is injectable so the logic is testable off-browser (Node has no `localStorage`).
 */

export interface Participant {
  participant_id: string;
  persona_id: string;
  display_name?: string;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const KEY = "wc.participant";

function memoryStorage(): StorageLike {
  const m = new Map<string, string>();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v) };
}

function defaultStorage(): StorageLike {
  return typeof localStorage !== "undefined" ? localStorage : memoryStorage();
}

function mintId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return `p_${crypto.randomUUID()}`;
  return `p_${Math.random().toString(36).slice(2)}`;
}

/** The persisted participant, minting + storing one on first call. Idempotent thereafter. */
export function getParticipant(storage: StorageLike = defaultStorage()): Participant {
  const raw = storage.getItem(KEY);
  if (raw) {
    try {
      const p = JSON.parse(raw) as Participant;
      if (p.participant_id && p.persona_id) return p;
    } catch {
      /* fall through and re-mint */
    }
  }
  const id = mintId();
  const p: Participant = { participant_id: id, persona_id: id };
  storage.setItem(KEY, JSON.stringify(p));
  return p;
}

/** Set a human-friendly display name (optional; not required for the bus to work). */
export function setDisplayName(name: string, storage: StorageLike = defaultStorage()): Participant {
  const p = getParticipant(storage);
  p.display_name = name.trim();
  storage.setItem(KEY, JSON.stringify(p));
  return p;
}
