/**
 * Avatar leg (Phase 12v2) — the lively robot face of the session, styled after the PWA Bot Sample
 * reference. Presentation only: nothing here touches the runner, the log, or the sync bus.
 * `WarpBot` renders the SVG robot; `director` decides what it acts out (keyword-driven gestures,
 * answer reactions, random idle antics, topic chips).
 */

import "./bot.css";

export { WarpBot } from "./WarpBot";
export type { BotState, BotGesture, WarpBotProps } from "./WarpBot";
export { reactToAnswer, glanceAt, chipsFor, useIdleAntics } from "./director";
export type { AnswerReaction } from "./director";
