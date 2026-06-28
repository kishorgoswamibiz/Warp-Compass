/**
 * A scripted `LLMProvider` for tests (mirrors the brain's `FakeLLM` in `tests/conftest.py`).
 *
 * Returns a queue of pre-baked JSON objects in order, so the turn loop is fully deterministic and
 * exercisable without a network call. Records the prompts it received for assertions.
 */

import type { LLMProvider } from "../types";

export interface RecordedCall {
  system: string;
  user: string;
}

export class FakeLLMProvider implements LLMProvider {
  readonly calls: RecordedCall[] = [];
  private i = 0;

  constructor(private readonly scripted: unknown[]) {}

  // eslint-disable-next-line @typescript-eslint/require-await
  async completeJSON(system: string, user: string): Promise<unknown> {
    this.calls.push({ system, user });
    if (this.i >= this.scripted.length) {
      throw new Error(
        `FakeLLMProvider exhausted: asked for response #${this.i + 1} but only ${this.scripted.length} were scripted`,
      );
    }
    return this.scripted[this.i++];
  }
}
