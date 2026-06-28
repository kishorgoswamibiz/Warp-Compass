/**
 * Warp Compass — canonical key-proxy logic (docs/02 §3.3).
 *
 * THE single source of truth for the key-injecting forwarder. It is imported by:
 *   • the Cloudflare **Pages Functions** in this folder (`llm.ts`, `stt.ts`, `tts.ts`, `health.ts`)
 *     — the PRODUCTION path (one Pages project hosts the PWA + these functions, same origin), and
 *   • the standalone `worker/src/index.ts` — kept for separate-origin / local `wrangler dev` use.
 *
 * Edit proxy behaviour HERE only; both deployments pick it up. The handlers use just the standard
 * `Request`/`Response`/`fetch`/`FormData`/`Blob` available in both the Workers and Pages runtimes,
 * so this file stays environment-neutral (no Pages/Worker-specific types).
 *
 * Keys NEVER reach the browser: the PWA POSTs text (and audio) here; we attach the secret keys and
 * forward to DeepSeek (live follow-ups) + ElevenLabs (STT/TTS). Turn-based → plain HTTP is enough.
 */

export interface Env {
  DEEPSEEK_API_KEY: string; // secret
  ELEVENLABS_API_KEY: string; // secret
  DEEPSEEK_BASE_URL: string; // var
  DEEPSEEK_MODEL_LIVE: string; // var (live tier, e.g. deepseek-v4-flash)
  ELEVENLABS_BASE_URL: string; // var (e.g. https://api.elevenlabs.io)
  ELEVENLABS_STT_MODEL: string; // var (e.g. scribe_v2)
  ELEVENLABS_TTS_MODEL: string; // var (e.g. eleven_flash_v2_5)
  ELEVENLABS_VOICE_ID: string; // var (a consistent voice for every user)
  ALLOWED_ORIGIN: string; // var
}

export function corsHeaders(env: Env): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin",
  };
}

export function jsonResponse(body: unknown, status: number, env: Env): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(env) },
  });
}

export function preflightResponse(env: Env): Response {
  return new Response(null, { status: 204, headers: corsHeaders(env) });
}

export function methodNotAllowed(env: Env): Response {
  return jsonResponse({ error: "method_not_allowed" }, 405, env);
}

export function healthResponse(env: Env): Response {
  return jsonResponse({ ok: true, service: "warp-compass", phase: "p10" }, 200, env);
}

interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}
interface LlmRequest {
  messages?: ChatMessage[];
  temperature?: number;
  response_format?: { type: string };
}

/**
 * Forward a chat-completion request to DeepSeek (OpenAI-compatible). The browser sends only the
 * messages (+ optional temperature / response_format); we inject the model + secret key. The
 * upstream OpenAI-shaped body is returned verbatim so the client reads `choices[0].message`.
 */
export async function handleLlm(req: Request, env: Env): Promise<Response> {
  if (!env.DEEPSEEK_API_KEY) {
    return jsonResponse(
      { error: "server_misconfigured", note: "DEEPSEEK_API_KEY not set." },
      500,
      env,
    );
  }
  let payload: LlmRequest;
  try {
    payload = (await req.json()) as LlmRequest;
  } catch {
    return jsonResponse({ error: "bad_request", note: "Body must be JSON." }, 400, env);
  }
  if (!Array.isArray(payload.messages) || payload.messages.length === 0) {
    return jsonResponse(
      { error: "bad_request", note: "`messages` (non-empty array) is required." },
      400,
      env,
    );
  }

  const base = (env.DEEPSEEK_BASE_URL || "https://api.deepseek.com").replace(/\/$/, "");
  let upstream: Response;
  try {
    upstream = await fetch(`${base}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${env.DEEPSEEK_API_KEY}`,
      },
      body: JSON.stringify({
        model: env.DEEPSEEK_MODEL_LIVE || "deepseek-v4-flash",
        messages: payload.messages,
        temperature: payload.temperature ?? 0.3,
        response_format: payload.response_format ?? { type: "json_object" },
      }),
    });
  } catch (e) {
    return jsonResponse({ error: "upstream_unreachable", note: String(e) }, 502, env);
  }

  // Pass the body + status straight through so the client sees real DeepSeek errors (rate limits…).
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json", ...corsHeaders(env) },
  });
}

/**
 * Forward recorded audio to ElevenLabs Scribe (speech-to-text). The browser POSTs the raw audio
 * blob as the body (Content-Type = the recording's mime); we wrap it in the multipart form
 * ElevenLabs expects, inject the key + STT model, and return `{ text }`. Accuracy-first batch model
 * (docs/02 §4): the transcript becomes the permanent Answer Log truth.
 */
export async function handleStt(req: Request, env: Env): Promise<Response> {
  if (!env.ELEVENLABS_API_KEY) {
    return jsonResponse(
      { error: "server_misconfigured", note: "ELEVENLABS_API_KEY not set." },
      500,
      env,
    );
  }
  const audio = await req.arrayBuffer();
  if (audio.byteLength === 0) {
    return jsonResponse(
      { error: "bad_request", note: "Request body must be the recorded audio bytes." },
      400,
      env,
    );
  }

  const mime = req.headers.get("Content-Type") || "audio/webm";
  const form = new FormData();
  form.append("model_id", env.ELEVENLABS_STT_MODEL || "scribe_v2");
  form.append("file", new Blob([audio], { type: mime }), "turn.webm");

  const base = (env.ELEVENLABS_BASE_URL || "https://api.elevenlabs.io").replace(/\/$/, "");
  let upstream: Response;
  try {
    upstream = await fetch(`${base}/v1/speech-to-text`, {
      method: "POST",
      headers: { "xi-api-key": env.ELEVENLABS_API_KEY }, // no Content-Type: fetch sets the boundary
      body: form,
    });
  } catch (e) {
    return jsonResponse({ error: "upstream_unreachable", note: String(e) }, 502, env);
  }

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json", ...corsHeaders(env) },
  });
}

interface TtsRequest {
  text?: string;
}

/**
 * Forward text to ElevenLabs (text-to-speech). The browser POSTs `{ text }`; we inject the key, the
 * configured voice id (one consistent voice for every user, §13/§17), and the TTS model, then
 * stream the audio bytes back.
 */
export async function handleTts(req: Request, env: Env): Promise<Response> {
  if (!env.ELEVENLABS_API_KEY) {
    return jsonResponse(
      { error: "server_misconfigured", note: "ELEVENLABS_API_KEY not set." },
      500,
      env,
    );
  }
  let payload: TtsRequest;
  try {
    payload = (await req.json()) as TtsRequest;
  } catch {
    return jsonResponse({ error: "bad_request", note: "Body must be JSON." }, 400, env);
  }
  const text = (payload.text ?? "").trim();
  if (!text) {
    return jsonResponse({ error: "bad_request", note: "`text` (non-empty) is required." }, 400, env);
  }

  const voiceId = env.ELEVENLABS_VOICE_ID || "21m00Tcm4TlvDq8ikWAM"; // default public voice ("Rachel")
  const base = (env.ELEVENLABS_BASE_URL || "https://api.elevenlabs.io").replace(/\/$/, "");
  let upstream: Response;
  try {
    upstream = await fetch(`${base}/v1/text-to-speech/${voiceId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "audio/mpeg",
        "xi-api-key": env.ELEVENLABS_API_KEY,
      },
      body: JSON.stringify({
        text,
        model_id: env.ELEVENLABS_TTS_MODEL || "eleven_flash_v2_5",
      }),
    });
  } catch (e) {
    return jsonResponse({ error: "upstream_unreachable", note: String(e) }, 502, env);
  }

  if (!upstream.ok) {
    const errText = await upstream.text(); // surface the real ElevenLabs error
    return new Response(errText, {
      status: upstream.status,
      headers: { "Content-Type": "application/json", ...corsHeaders(env) },
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "audio/mpeg",
      ...corsHeaders(env),
    },
  });
}
