/**
 * WorkerLLMProvider — the PRODUCTION seam for the shipped PWA.
 *
 * The browser never holds keys (AGENTS.md, DECISION #8): it POSTs the prompt to the Cloudflare
 * Worker key-proxy, which injects `DEEPSEEK_API_KEY` and forwards to DeepSeek's live tier. This
 * provider is wired and ready; the Worker `/llm` forwarder itself is implemented in Phase 6
 * (it currently returns 501 — see worker/src/index.ts), so this path is exercised end-to-end then.
 */

import { LLMError } from "../types";
import type { LLMProvider } from "../types";
import { loadsTolerant } from "./json";

export interface WorkerLLMOptions {
  /** Base URL of the Worker proxy, e.g. "" (same origin) or "http://localhost:8787". */
  baseUrl?: string;
  /** Endpoint path; defaults to "/llm". */
  path?: string;
}

export class WorkerLLMProvider implements LLMProvider {
  private readonly url: string;

  constructor(opts: WorkerLLMOptions = {}) {
    const base = (opts.baseUrl ?? "").replace(/\/$/, "");
    this.url = `${base}${opts.path ?? "/llm"}`;
  }

  async completeJSON(
    system: string,
    user: string,
    opts: { temperature?: number } = {},
  ): Promise<unknown> {
    let resp: Response;
    try {
      resp = await fetch(this.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [
            { role: "system", content: system },
            { role: "user", content: user },
          ],
          temperature: opts.temperature ?? 0.0,
          response_format: { type: "json_object" },
        }),
      });
    } catch (e) {
      throw new LLMError(`Worker /llm request failed: ${(e as Error).message}`);
    }
    if (!resp.ok) {
      throw new LLMError(`Worker /llm HTTP ${resp.status}: ${await resp.text()}`);
    }
    // The Worker forwards DeepSeek's OpenAI-shaped response; pull out the content.
    const data = (await resp.json()) as { choices?: { message?: { content?: string } }[] };
    const content = data.choices?.[0]?.message?.content ?? "";
    const parsed = loadsTolerant(content);
    if (typeof parsed !== "object" || parsed === null) {
      throw new LLMError("Worker /llm returned non-object JSON");
    }
    return parsed;
  }
}
