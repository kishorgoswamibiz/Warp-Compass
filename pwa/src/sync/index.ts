/**
 * Public API of the phone-side sync layer (Phase 8): a stable participant identity and the manual
 * file hand-off to/from the shared-folder bus.
 */

export { getParticipant, setDisplayName } from "./participant";
export type { Participant, StorageLike } from "./participant";
export { answerLogFilename, downloadAnswerLog, parseBriefFile } from "./bus";
