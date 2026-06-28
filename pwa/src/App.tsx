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
      </main>
    </div>
  );
}
