/**
 * OnboardingCard (Phase 13 · multi-role in P15a) — the one-time "who is using this device?" gate.
 *
 * Shown exactly once per device, before the first session. What the person enters here becomes
 * three things at once: their **display name** everywhere the operator looks, the **permanent
 * participant id** (and therefore the Drive folder name and the graph's provenance `said_by`), and
 * the **first entry of their first Answer Log** — which is what gives the graph its Role nodes from
 * turn zero (P13 §4.1).
 *
 * TYPED, NOT SPOKEN — deliberately. STT would mangle "Rahul" into "Raul", and that guess would
 * become a permanent folder name and provenance key that the immutability rule (ADR #29) forbids
 * us from correcting later. The warmth is recovered immediately afterwards by the bot's greeting.
 *
 * **Roles are a fixed multi-select** (P15a), not free text, for two reasons: one person commonly
 * holds several (a Delivery Specialist who also does sales), and free text forks the graph — "PM",
 * "Project Manager" and "Delivery Specialist" would become three Role nodes and question routing
 * would dead-end (phase-15 plan §4.3). Chips rather than `<select multiple>` because a native
 * multi-select is miserable on a phone.
 */

import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { ROLE_NAMES, createParticipant } from "../sync";
import type { Participant } from "../sync";

const MAX_LEN = 60;

export function OnboardingCard({ onDone }: { onDone: (p: Participant) => void }) {
  const [name, setName] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const firstChipRef = useRef<HTMLButtonElement>(null);

  const ready = name.trim().length > 0 && roles.length > 0;

  const toggleRole = (role: string) => {
    setRoles((current) =>
      current.includes(role) ? current.filter((r) => r !== role) : [...current, role],
    );
  };

  const submit = () => {
    if (!ready) return;
    // Registry order, not click order: the FIRST role mints the permanent id (ADR #29), so it must
    // not depend on which chip the person happened to tap first.
    const ordered = ROLE_NAMES.filter((r) => roles.includes(r));
    onDone(createParticipant({ name, roles: ordered }));
  };

  // Enter moves name → the role chips, so the card stays keyboard-only on a laptop.
  const onNameKey = (e: KeyboardEvent) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    firstChipRef.current?.focus();
  };

  return (
    <div className="wc-app">
      <header className="wc-header">
        <span className="wc-logo">
          WARP<span className="wc-logo-thin">COMPASS</span>
        </span>
      </header>

      <main className="wc-onboard">
        <div className="wc-onboard-card">
          <p className="wc-eyebrow">Before we start</p>
          <h1 className="wc-onboard-title">Who's using this device?</h1>
          <p className="wc-onboard-sub">
            We'll ask this once. Every session after this one picks up where you left off.
          </p>

          <label className="wc-field">
            <span className="wc-field-label">Your name</span>
            <input
              className="wc-input wc-field-input"
              type="text"
              autoFocus
              maxLength={MAX_LEN}
              placeholder="Rahul Mehta"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={onNameKey}
            />
          </label>

          <div className="wc-field">
            <span className="wc-field-label" id="wc-roles-label">
              Your role(s)
            </span>
            <p className="wc-field-hint">
              Pick every role you hold — more than one if you wear several hats.
            </p>
            <div className="wc-chips" role="group" aria-labelledby="wc-roles-label">
              {ROLE_NAMES.map((role, i) => {
                const selected = roles.includes(role);
                return (
                  <button
                    key={role}
                    ref={i === 0 ? firstChipRef : undefined}
                    type="button"
                    className={`wc-chip${selected ? " wc-chip-on" : ""}`}
                    aria-pressed={selected}
                    onClick={() => toggleRole(role)}
                  >
                    {role}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="wc-toolbar">
            <button className="wc-pill" onClick={submit} disabled={!ready}>
              Continue →
            </button>
          </div>

          <p className="wc-note wc-onboard-note">
            Your name labels your answers for the team. Your roles tell the assistant where to start,
            so it never has to ask again.
          </p>
        </div>
      </main>
    </div>
  );
}
