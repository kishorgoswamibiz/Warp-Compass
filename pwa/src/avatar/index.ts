/**
 * Avatar leg (Phase 12) — the lively face of the session. Presentation only: nothing here touches
 * the runner, the log, or the sync bus. `Avatar` renders the SVG face; `pickReaction` chooses the
 * subtle acknowledgement the avatar makes right after the person answers.
 */

export { Avatar } from "./Avatar";
export type { AvatarState, AvatarProps } from "./Avatar";
export { pickReaction } from "./reactions";
