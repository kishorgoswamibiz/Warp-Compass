/**
 * OnboardingCard (Phase 13) — the one-time "who is using this device?" gate.
 *
 * Shown exactly once per device, before the first session. What the person types here becomes
 * three things at once: their **display name** everywhere the operator looks, the **permanent
 * participant id** (and therefore the Drive folder name and the graph's provenance `said_by`), and
 * the **first entry of their first Answer Log** — which is what gives the graph a Role node from
 * turn zero (P13 §4.1).
 *
 * TYPED, NOT SPOKEN — deliberately. STT would mangle "Rahul" into "Raul", and that guess would
 * become a permanent folder name and provenance key that the immutability rule (ADR #29) forbids
 * us from correcting later. The warmth is recovered immediately afterwards by the bot's greeting.
 */

import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { createParticipant } from "../sync";
import type { Participant } from "../sync";

const MAX_LEN = 60;

export function OnboardingCard({ onDone }: { onDone: (p: Participant) => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const roleRef = useRef<HTMLInputElement>(null);

  const ready = name.trim().length > 0 && role.trim().length > 0;

  const submit = () => {
    if (!ready) return;
    onDone(createParticipant({ name, role }));
  };

  // Enter moves name → role → submit, so the card is keyboard-only on a laptop and "next"-able
  // on a phone keyboard.
  const onKey = (e: KeyboardEvent, next?: () => void) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    if (next) next();
    else submit();
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
              onKeyDown={(e) => onKey(e, () => roleRef.current?.focus())}
            />
          </label>

          <label className="wc-field">
            <span className="wc-field-label">Your role</span>
            <input
              ref={roleRef}
              className="wc-input wc-field-input"
              type="text"
              maxLength={MAX_LEN}
              placeholder="Business Analyst"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              onKeyDown={(e) => onKey(e)}
            />
          </label>

          <div className="wc-toolbar">
            <button className="wc-pill" onClick={submit} disabled={!ready}>
              Continue →
            </button>
          </div>

          <p className="wc-note wc-onboard-note">
            Your name labels your answers for the team. Your role tells the assistant where to
            start, so it never has to ask again.
          </p>
        </div>
      </main>
    </div>
  );
}
