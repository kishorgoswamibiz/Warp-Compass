/**
 * Avatar (Phase 12) — the face of the session. Pure inline SVG + CSS animations (no image assets,
 * no animation libraries) so it costs a few KB and stays PWA-light. All expression logic is CSS
 * keyed off `data-state`; the ONLY JS-driven part is the mouth, which the session screen drives by
 * setting the `--wc-mouth` custom property on the root <svg> from the live TTS audio level
 * (see voice/tts.ts `playAudioBlob(onLevel)`), so lips track the actual spoken audio.
 *
 * States:  idle — gentle bob, blinks, pupils wander
 *          listening — brows up, eyes a touch wider, curious head tilt + slow nods
 *          thinking — pupils drift up, one brow furrowed
 *          speaking — mouth follows --wc-mouth, brows lightly animated
 * `reaction` (short text like "Oh!") overrides with a pop-eyed micro-expression + a bubble.
 */

import { forwardRef } from "react";

export type AvatarState = "idle" | "listening" | "thinking" | "speaking";

export interface AvatarProps {
  state: AvatarState;
  /** Brief micro-reaction ("Oh!", "Mm-hm…") shown in a bubble; overrides `state` while set. */
  reaction?: string | null;
}

export const Avatar = forwardRef<SVGSVGElement, AvatarProps>(function Avatar(
  { state, reaction },
  ref,
) {
  return (
    <div className="wc-avatar-wrap" aria-hidden>
      <div className={`wc-avatar-bubble${reaction ? " wc-avatar-bubble-on" : ""}`}>
        {reaction ?? " "}
      </div>
      <svg
        ref={ref}
        className="wc-avatar"
        data-state={reaction ? "reacting" : state}
        viewBox="0 0 120 120"
        role="img"
      >
        <defs>
          <radialGradient id="wc-av-skin" cx="38%" cy="30%" r="80%">
            <stop offset="0%" stopColor="#3fe07f" />
            <stop offset="60%" stopColor="#15c95b" />
            <stop offset="100%" stopColor="#0fa549" />
          </radialGradient>
        </defs>

        <g className="wc-av-head">
          {/* soft drop glow keeps it feeling grounded on the grid background */}
          <ellipse cx="60" cy="112" rx="30" ry="5" fill="rgba(12,15,13,0.08)" />
          <circle cx="60" cy="58" r="46" fill="url(#wc-av-skin)" />

          {/* cheeks */}
          <circle className="wc-av-cheek" cx="36" cy="70" r="7" fill="rgba(255,255,255,0.28)" />
          <circle className="wc-av-cheek" cx="84" cy="70" r="7" fill="rgba(255,255,255,0.28)" />

          {/* brows — rotate/lift per state */}
          <path
            className="wc-av-brow wc-av-brow-l"
            d="M32 38 q10 -6 20 -2"
            fill="none"
            stroke="#0c0f0d"
            strokeWidth="3.4"
            strokeLinecap="round"
          />
          <path
            className="wc-av-brow wc-av-brow-r"
            d="M68 36 q10 -4 20 2"
            fill="none"
            stroke="#0c0f0d"
            strokeWidth="3.4"
            strokeLinecap="round"
          />

          {/* eyes — outer group blinks (scaleY), inner group pops (scale), pupils wander */}
          <g className="wc-av-eye wc-av-eye-l">
            <g className="wc-av-eyeball">
              <ellipse cx="42" cy="54" rx="9.5" ry="11" fill="#ffffff" />
              <circle className="wc-av-pupil" cx="43" cy="55" r="4.6" fill="#0c0f0d" />
              <circle cx="45" cy="52.5" r="1.5" fill="#ffffff" />
            </g>
          </g>
          <g className="wc-av-eye wc-av-eye-r">
            <g className="wc-av-eyeball">
              <ellipse cx="78" cy="54" rx="9.5" ry="11" fill="#ffffff" />
              <circle className="wc-av-pupil" cx="79" cy="55" r="4.6" fill="#0c0f0d" />
              <circle cx="81" cy="52.5" r="1.5" fill="#ffffff" />
            </g>
          </g>

          {/* mouth — scaleY follows --wc-mouth while speaking; a soft line otherwise */}
          <g className="wc-av-mouth">
            <ellipse className="wc-av-mouth-inner" cx="60" cy="82" rx="11" ry="9" fill="#0c0f0d" />
          </g>
        </g>
      </svg>
    </div>
  );
});
