/** Tolerant JSON parsing shared by the live providers (mirrors brain's `_loads_tolerant`). */

import { LLMError } from "../types";

/** Parse JSON, tolerating a ```json … ``` fence if the model wraps its output. */
export function loadsTolerant(text: string): unknown {
  let s = (text ?? "").trim();
  if (s.startsWith("```")) {
    const nl = s.indexOf("\n");
    s = nl >= 0 ? s.slice(nl + 1) : s;
    if (s.startsWith("json")) s = s.slice(4).trim();
    if (s.endsWith("```")) s = s.slice(0, -3).trim();
  }
  try {
    return JSON.parse(s);
  } catch (e) {
    throw new LLMError(`model did not return valid JSON: ${(e as Error).message}`);
  }
}

/** Sleep that does not depend on Date (kept tiny so providers stay testable). */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
