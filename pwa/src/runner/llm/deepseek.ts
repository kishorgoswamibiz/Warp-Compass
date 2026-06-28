/**
 * DirectDeepSeekProvider — calls DeepSeek's OpenAI-compatible chat API directly with `fetch`.
 *
 * ⚠️ VERIFICATION / DEV ONLY. This embeds the API key in the caller, so it is for the local typed
 * harness (Node, on the laptop) — NOT the shipped PWA. In the browser the runner must route
 * through the Cloudflare Worker (`WorkerLLMProvider`), because keys live ONLY in the Worker
 * (AGENTS.md, DECISION #8). This is the first exercise of the LIVE model `deepseek-v4-flash`.
 *
 * Mirrors brain/.../llm/deepseek.py: JSON mode, retry + exponential backoff honouring Retry-After.
 */

import { LLMError } from "../types";
import type { LLMProvider } from "../types";
import { loadsTolerant, sleep } from "./json";

export interface DeepSeekOptions {
  apiKey: string;
  baseUrl?: string; // default https://api.deepseek.com
  model?: string; // default deepseek-v4-flash (the LIVE tier)
  maxRetries?: number; // default 5
}

export class DirectDeepSeekProvider implements LLMProvider {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  readonly model: string;
  private readonly maxRetries: number;

  constructor(opts: DeepSeekOptions) {
    if (!opts.apiKey) {
      throw new LLMError("DEEPSEEK_API_KEY is empty. Set it in brain/.env (and save the file).");
    }
    this.apiKey = opts.apiKey;
    this.baseUrl = (opts.baseUrl ?? "https://api.deepseek.com").replace(/\/$/, "");
    this.model = opts.model ?? "deepseek-v4-flash";
    this.maxRetries = opts.maxRetries ?? 5;
  }

  async completeJSON(
    system: string,
    user: string,
    opts: { temperature?: number } = {},
  ): Promise<unknown> {
    const body = JSON.stringify({
      model: this.model,
      messages: [
        { role: "system", content: system },
        { role: "user", content: user },
      ],
      temperature: opts.temperature ?? 0.0,
      response_format: { type: "json_object" },
    });

    let lastErr: unknown;
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const resp = await fetch(`${this.baseUrl}/chat/completions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${this.apiKey}`,
          },
          body,
        });
        if (resp.status === 429 || resp.status >= 500) {
          lastErr = new LLMError(`DeepSeek HTTP ${resp.status}`);
          await this.backoff(attempt, resp.headers.get("retry-after"));
          continue;
        }
        if (!resp.ok) {
          throw new LLMError(`DeepSeek HTTP ${resp.status}: ${await resp.text()}`);
        }
        const data = (await resp.json()) as {
          choices?: { message?: { content?: string } }[];
        };
        const content = data.choices?.[0]?.message?.content ?? "";
        const parsed = loadsTolerant(content);
        if (typeof parsed !== "object" || parsed === null) {
          throw new LLMError("DeepSeek returned non-object JSON");
        }
        return parsed;
      } catch (e) {
        lastErr = e;
        if (e instanceof LLMError && /HTTP (4[0-8]\d|49\d)/.test(e.message)) throw e; // non-retryable 4xx
        await this.backoff(attempt, null);
      }
    }
    throw new LLMError(
      `DeepSeek call failed after ${this.maxRetries + 1} attempts: ${String(lastErr)}`,
    );
  }

  private async backoff(attempt: number, retryAfter: string | null): Promise<void> {
    if (attempt >= this.maxRetries) return;
    const headerMs = retryAfter ? Number(retryAfter) * 1000 : NaN;
    const ms = Number.isFinite(headerMs) ? headerMs : Math.min(1000 * 2 ** attempt, 16000);
    await sleep(ms);
  }
}
