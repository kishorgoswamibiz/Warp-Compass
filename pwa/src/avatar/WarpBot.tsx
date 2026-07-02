/**
 * WarpBot (Phase 12v2) — the robot face of the session, styled after the "PWA Bot Sample"
 * reference: a white rounded head with a dark screen face, glowing green arc-eyes, ear pods,
 * levitating over a glowing base ring, with slow dotted orbit rings behind. Pure inline SVG +
 * CSS (bot.css) — no image assets, no animation libraries; everything animates transform/opacity
 * so it stays compositor-cheap on phones.
 *
 * Two input channels drive the performance:
 *  - `state`  — what the session is doing (idle / listening / thinking / speaking). Continuous.
 *  - `gesture` — a short one-shot act layered ON TOP by the director (director.ts): taking notes
 *    with a little arm, leaning in to listen, nodding, a curious peek, a pod-spin. Gestures are
 *    triggered by keywords in what the person says/types and by a random idle scheduler, so the
 *    bot never sits still like a template.
 *
 * The ONLY JS-driven part is the mouth waveform: the session screen writes the live TTS audio
 * level to `--wc-mouth` on the root <svg>, and the equalizer bars scale with it.
 */

import { forwardRef } from "react";

export type BotState = "idle" | "listening" | "thinking" | "speaking";
export type BotGesture = "note" | "nod" | "lean" | "peek" | "spin" | "happy" | "concern";

export interface WarpBotProps {
  state: BotState;
  /** One-shot act layered over `state`; cleared by the director when it finishes. */
  gesture?: BotGesture | null;
  /** Brief reaction line ("Oh!", "Noting that down…") shown in a bubble above the head. */
  reaction?: string | null;
}

export const WarpBot = forwardRef<SVGSVGElement, WarpBotProps>(function WarpBot(
  { state, gesture, reaction },
  ref,
) {
  return (
    <div className="wc-bot-wrap" aria-hidden>
      <div className={`wc-bot-bubble${reaction ? " wc-bot-bubble-on" : ""}`}>{reaction ?? " "}</div>
      <svg
        ref={ref}
        className="wc-bot"
        data-state={state}
        data-gesture={gesture ?? undefined}
        viewBox="0 0 200 230"
        role="img"
      >
        <defs>
          <linearGradient id="wc-bot-shell" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#e9f2ec" />
          </linearGradient>
          <radialGradient id="wc-bot-ring" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#7dffb2" />
            <stop offset="70%" stopColor="#17d266" />
            <stop offset="100%" stopColor="#17d266" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* dotted orbit rings, slowly counter-rotating */}
        <g className="wc-bot-orbits">
          <circle className="wc-bot-orbit wc-bot-orbit-1" cx="100" cy="98" r="76" />
          <circle className="wc-bot-orbit wc-bot-orbit-2" cx="100" cy="98" r="92" />
        </g>

        {/* floor shadow breathes with the levitation */}
        <ellipse className="wc-bot-shadow" cx="100" cy="216" rx="32" ry="5.5" fill="rgba(12,15,13,0.13)" />

        {/* base bowl with the glowing charge ring */}
        <g className="wc-bot-base">
          <ellipse cx="100" cy="198" rx="40" ry="17" fill="url(#wc-bot-shell)" stroke="#dbe7de" strokeWidth="1" />
          <ellipse className="wc-bot-ringglow" cx="100" cy="192" rx="26" ry="7.5" fill="url(#wc-bot-ring)" />
          <ellipse cx="100" cy="192" rx="18" ry="4.5" fill="#b9ffd6" opacity="0.9" />
        </g>

        {/* note-taking arm + pad: pops out for the "note" gesture. Drawn with absolute
            coordinates only — NO svg transform attributes, which the global
            `transform-box: fill-box` rule would re-anchor and fling out of place. */}
        <g className="wc-bot-arm">
          <path d="M136 194 q16 -2 22 -16" fill="none" stroke="#eef5f0" strokeWidth="9" strokeLinecap="round" />
          <g>
            <rect x="144" y="150" width="38" height="28" rx="5" fill="#ffffff" stroke="#d7e3da" strokeWidth="1.2" />
            <path className="wc-bot-scribble wc-bot-scribble-1" d="M150 158 h26" />
            <path className="wc-bot-scribble wc-bot-scribble-2" d="M150 164 h19" />
            <path className="wc-bot-scribble wc-bot-scribble-3" d="M150 170 h23" />
          </g>
          <g className="wc-bot-pen">
            <path d="M158 180 L166 163" stroke="#15c95b" strokeWidth="4.5" strokeLinecap="round" />
            <path d="M158 180 L160.5 174.8" stroke="#0c0f0d" strokeWidth="4.5" strokeLinecap="round" />
            <circle cx="156" cy="184" r="6.5" fill="#ffffff" stroke="#d7e3da" strokeWidth="1.2" />
          </g>
        </g>

        {/* levitating head */}
        <g className="wc-bot-head">
          {/* ear pods */}
          <g className="wc-bot-pod wc-bot-pod-l">
            <rect x="24" y="76" width="13" height="36" rx="6.5" fill="url(#wc-bot-shell)" stroke="#dbe7de" strokeWidth="1" />
            <rect className="wc-bot-podlight" x="27.5" y="83" width="6" height="22" rx="3" fill="#15c95b" />
          </g>
          <g className="wc-bot-pod wc-bot-pod-r">
            <rect x="163" y="76" width="13" height="36" rx="6.5" fill="url(#wc-bot-shell)" stroke="#dbe7de" strokeWidth="1" />
            <rect className="wc-bot-podlight" x="166.5" y="83" width="6" height="22" rx="3" fill="#15c95b" />
          </g>

          {/* shell + screen */}
          <rect x="38" y="44" width="124" height="104" rx="34" fill="url(#wc-bot-shell)" stroke="#dbe7de" strokeWidth="1.2" />
          <rect x="50" y="56" width="100" height="80" rx="24" fill="#111b15" />
          <rect x="50" y="56" width="100" height="80" rx="24" fill="none" stroke="rgba(46,232,120,0.18)" strokeWidth="1.5" />

          {/* the face lives on the screen; a group per feature, crossfaded by state */}
          <g className="wc-bot-face">
            {/* left / right eyes: happy arc ↔ round, swapped per state */}
            <g className="wc-bot-eye wc-bot-eye-l">
              <path className="wc-bot-eye-arc" d="M67 92 q11 -14 22 0" />
              <circle className="wc-bot-eye-round" cx="78" cy="88" r="8" />
            </g>
            <g className="wc-bot-eye wc-bot-eye-r">
              <path className="wc-bot-eye-arc" d="M111 92 q11 -14 22 0" />
              <circle className="wc-bot-eye-round" cx="122" cy="88" r="8" />
            </g>

            {/* mouth: smile ↔ "o" ↔ thinking dots ↔ speaking equalizer */}
            <g className="wc-bot-mouth">
              <path className="wc-bot-smile" d="M89 110 q11 10 22 0" />
              <circle className="wc-bot-o" cx="100" cy="113" r="6" />
              <g className="wc-bot-dots">
                <circle cx="90" cy="113" r="3" />
                <circle cx="100" cy="113" r="3" />
                <circle cx="110" cy="113" r="3" />
              </g>
              <g className="wc-bot-wave">
                <rect className="wc-bot-bar" x="82" y="104" width="4.5" height="18" rx="2.25" />
                <rect className="wc-bot-bar" x="90.5" y="104" width="4.5" height="18" rx="2.25" />
                <rect className="wc-bot-bar" x="99" y="104" width="4.5" height="18" rx="2.25" />
                <rect className="wc-bot-bar" x="107.5" y="104" width="4.5" height="18" rx="2.25" />
                <rect className="wc-bot-bar" x="116" y="104" width="4.5" height="18" rx="2.25" />
              </g>
            </g>
          </g>
        </g>
      </svg>
    </div>
  );
});
