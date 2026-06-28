/**
 * Public API of the live runner (Phase 5). The P6 UI shell imports the runner from here.
 *
 * Browser-safe surface only: the Node-only `validate.ts` (ajv + node:fs) and `harness.ts`
 * (readline/fs) are intentionally NOT re-exported, so the browser bundle never pulls them in.
 * In the PWA, construct `new Runner(brief, new WorkerLLMProvider(), clock)` — keys live only in
 * the Worker (AGENTS.md).
 */

export { Runner, CLOSING_UTTERANCE } from "./runner";
export type { TurnResult, RunnerClock } from "./runner";
export { Session } from "./session";
export { AnswerLogBuilder, ANSWER_LOG_SCHEMA_VERSION } from "./answerlog";
export { COLD_START_OPENERS, SYSTEM_PROMPT, buildUserPrompt, isLiveDecision } from "./prompts";
export { WorkerLLMProvider } from "./llm/worker";
export { DirectDeepSeekProvider } from "./llm/deepseek";
export { FakeLLMProvider } from "./llm/fake";
export * from "./types";
