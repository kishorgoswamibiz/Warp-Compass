/**
 * Warp Compass — standalone Cloudflare Worker key proxy (OPTIONAL).
 *
 * PRODUCTION now runs the same proxy as **Pages Functions** (`pwa/functions/`), so the PWA and its
 * proxy deploy as one git-connected Pages project (see DEPLOY.md). This standalone Worker is kept
 * for a separate-origin setup or for local `wrangler dev` on :8787 (the Vite dev proxy targets it).
 *
 * It contains NO proxy logic of its own — the handlers are the single source of truth in
 * `pwa/functions/_shared.ts`; this file only does path routing. Keys never reach the browser.
 */

import {
  type Env,
  handleLlm,
  handleStt,
  handleTts,
  healthResponse,
  jsonResponse,
  methodNotAllowed,
  preflightResponse,
} from "../../pwa/functions/_shared";

export type { Env };

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    if (req.method === "OPTIONS") {
      return preflightResponse(env);
    }

    const { pathname } = new URL(req.url);

    switch (pathname) {
      case "/health":
        return healthResponse(env);

      case "/llm": // DeepSeek live follow-ups
        return req.method === "POST" ? handleLlm(req, env) : methodNotAllowed(env);

      case "/stt": // ElevenLabs Scribe — speech -> text
        return req.method === "POST" ? handleStt(req, env) : methodNotAllowed(env);

      case "/tts": // ElevenLabs — text -> speech
        return req.method === "POST" ? handleTts(req, env) : methodNotAllowed(env);

      default:
        return jsonResponse({ error: "not_found", path: pathname }, 404, env);
    }
  },
};
