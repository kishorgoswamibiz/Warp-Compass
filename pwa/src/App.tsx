// Phase 8 shell: a landing screen → the live runner (SessionScreen). Holds NO graph; all live calls
// route through the Worker key-proxy (keys never in the browser). The phone has a STABLE participant
// id (the bus folder is keyed by it) and can import its latest Session Brief from the bus to
// cross-pollinate the next session; a fresh start cold-starts.
import { useRef, useState } from "react";
import { SessionScreen } from "./screens/SessionScreen";
import { getParticipant, parseBriefFile } from "./sync";
import type { SessionBrief } from "./runner";

export function App() {
  const [started, setStarted] = useState(false);
  const [brief, setBrief] = useState<SessionBrief | undefined>(undefined);
  const [importError, setImportError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const participant = getParticipant();
  const shortId = participant.participant_id.replace(/^p_/, "").slice(0, 8);

  if (started) {
    return (
      <div className="wc-app">
        <SessionScreen brief={brief} onExit={() => setStarted(false)} />
      </div>
    );
  }

  const onPickBrief = async (file: File | undefined) => {
    if (!file) return;
    setImportError(null);
    try {
      setBrief(await parseBriefFile(file));
      setStarted(true);
    } catch (e) {
      setImportError((e as Error).message);
    }
  };

  return (
    <div className="wc-app">
      <header className="wc-header">
        <span className="wc-logo">
          WARP<span className="wc-logo-thin">COMPASS</span>
        </span>
      </header>

      <main className="wc-hero">
        <h1 className="wc-title">
          Direction to <span className="wc-accent">Operational Clarity</span>.
        </h1>
        <p className="wc-sub">
          A short daily conversation. Tell us how your work really happens — we listen,
          and we build the picture.
        </p>

        <div className="wc-toolbar wc-hero-actions">
          <button
            className="wc-pill"
            onClick={() => {
              setBrief(undefined);
              setStarted(true);
            }}
          >
            Start a session →
          </button>
          <button className="wc-ghost" onClick={() => fileRef.current?.click()}>
            Import today's brief
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(e) => void onPickBrief(e.target.files?.[0] ?? undefined)}
          />
        </div>
        {importError && <p className="wc-note wc-import-error">Couldn't import: {importError}</p>}
        <p className="wc-note">
          Voice or text. Your answers are saved as an Answer Log — drop it into your folder on the
          shared bus; the daily round sends back an updated brief to import here.
        </p>
        <p className="wc-note">
          You are <code>{shortId}</code> on this device.
        </p>

        <div className="wc-stats">
          <div>
            <div className="wc-stat-num">10</div>
            <div className="wc-stat-label">Build phases</div>
          </div>
          <div>
            <div className="wc-stat-num">2</div>
            <div className="wc-stat-label">Speed planes</div>
          </div>
          <div>
            <div className="wc-stat-num">1</div>
            <div className="wc-stat-label">Connected brain</div>
          </div>
        </div>

        <a className="wc-scrollcue" href="#how">
          See how it works <span aria-hidden>↓</span>
        </a>
      </main>

      {/* ── What it does (the objective) ─────────────────────────────────── */}
      <section className="wc-explain" id="what">
        <p className="wc-eyebrow">What it does</p>
        <h2 className="wc-h2">
          It does the consultant's discovery — at every level, then connects it into one
          picture.
        </h2>
        <p className="wc-lead">
          Instead of a consultant manually interviewing every role, the system interviews
          them itself and weaves every answer into a single connected model of how the
          company really runs.
        </p>

        <div className="wc-flow">
          <div className="wc-chips">
            {["Sales reps", "Managers", "Inventory", "Delivery", "Executives"].map((r) => (
              <span className="wc-chip" key={r}>
                {r}
              </span>
            ))}
          </div>

          <div className="wc-flow-arrow" aria-hidden>
            ↓
          </div>

          <div className="wc-flow-node">
            <strong>One connected brain</strong>
            <span>Every answer feeds a single shared model — one level shapes the next.</span>
          </div>

          <div className="wc-flow-arrow" aria-hidden>
            ↓
          </div>

          <div className="wc-flow-out">
            <div className="wc-out-card">
              <strong>One end-to-end process</strong>
              <span>The complete SOP, stitched across every level — fully traceable.</span>
            </div>
            <div className="wc-out-card">
              <strong>Problem register</strong>
              <span>The pain points each role lives with, captured as they're said.</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── How it works (two-speed architecture) ────────────────────────── */}
      <section className="wc-explain" id="how">
        <p className="wc-eyebrow">How it works</p>
        <h2 className="wc-h2">Two speeds: instant to talk to, deep to understand.</h2>
        <p className="wc-lead">
          The conversation stays fast and human on your phone; the heavy thinking happens
          quietly between sessions — so you never wait on the machine.
        </p>

        <div className="wc-planes">
          <article className="wc-plane">
            <div className="wc-plane-icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <rect x="6.5" y="2.5" width="11" height="19" rx="2.5" />
                <line x1="11" y1="18.5" x2="13" y2="18.5" />
              </svg>
            </div>
            <h3>Talk — on your phone</h3>
            <p>
              A fast, human conversation. Voice or text. It listens, follows up, and catches
              contradictions on the spot. No deep thinking here — just listen and record.
            </p>
          </article>

          <div className="wc-plane-link" aria-hidden>
            <span className="wc-wire">Answer Log ↑</span>
            <span className="wc-wire">Session Brief ↓</span>
          </div>

          <article className="wc-plane">
            <div className="wc-plane-icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="6" cy="7" r="2" />
                <circle cx="18" cy="6" r="2" />
                <circle cx="16" cy="17" r="2" />
                <circle cx="7" cy="16" r="2" />
                <line x1="8" y1="7.5" x2="16" y2="6.5" />
                <line x1="7" y1="9" x2="7" y2="14" />
                <line x1="17.2" y1="7.8" x2="16.3" y2="15.1" />
                <line x1="8.8" y1="15.4" x2="14.4" y2="16.6" />
              </svg>
            </div>
            <h3>Think — the brain</h3>
            <p>
              Between sessions, transcripts become a connected graph — merging facts, flagging
              conflicts, and scoring what's still missing to ask next.
            </p>
          </article>
        </div>

        <div className="wc-principles">
          <div className="wc-principle">
            <strong>Discovery-first</strong>
            <span>No fixed questionnaire — it discovers the real org, not assumptions.</span>
          </div>
          <div className="wc-principle">
            <strong>Graph memory</strong>
            <span>Relationships, not a text blob — and rebuildable from the raw logs.</span>
          </div>
          <div className="wc-principle">
            <strong>Voice-first</strong>
            <span>Accurate transcripts are the permanent source of truth.</span>
          </div>
        </div>
      </section>
    </div>
  );
}
