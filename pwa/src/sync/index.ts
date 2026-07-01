/**
 * Public API of the phone-side sync layer: a stable participant identity, the AUTOMATIC network bus
 * (Phase 11 — push Answer Logs / pull Session Briefs), and the manual file hand-off kept as an
 * offline fallback (Phase 8).
 */

export { getParticipant, setDisplayName } from "./participant";
export type { Participant, StorageLike } from "./participant";
export { answerLogFilename, downloadAnswerLog, parseBriefFile } from "./bus";
export { pushAnswerLog, pullLatestBrief } from "./remote";
export type { PushResult } from "./remote";
