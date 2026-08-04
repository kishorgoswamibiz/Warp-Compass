/**
 * Public API of the phone-side sync layer: a stable participant identity, the AUTOMATIC network bus
 * (Phase 11 — push Answer Logs / pull Session Briefs), and the manual file hand-off kept as an
 * offline fallback (Phase 8).
 */

export {
  clearParticipant,
  createParticipant,
  getParticipant,
  isOnboarded,
  markIdentitySeeded,
  mintParticipantId,
  needsIdentitySeed,
  requireParticipant,
  slugPart,
  updateIdentity,
} from "./participant";
export type { Participant, StorageLike } from "./participant";
export { ROLE_NAMES, ROLE_REGISTRY, joinRoles } from "./roles";
export type { RoleEntry } from "./roles";
export { answerLogFilename, downloadAnswerLog, parseBriefFile } from "./bus";
export { pushAnswerLog, pullLatestBrief } from "./remote";
export type { PushResult } from "./remote";
