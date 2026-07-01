/**
 * Warp Compass — Drive-sync forwarder (Phase 11).
 *
 * The clean same-origin front door for the phone-side bus. The PWA can't write the owner's Drive and
 * can't cleanly follow Apps Script's cross-origin 302 redirect, so these handlers forward to the
 * Apps Script Web App (apps-script/Code.gs) server-side, injecting the shared secret (kept OFF the
 * client) and giving the browser trivial CORS — the same pattern as the key-proxy in `_shared.ts`.
 *
 * Two operations mirror the two bus ops (ADR #8):
 *   POST /sync/answer-log  { participant_id, profile?, answer_log }  -> write-once Answer Log to Drive
 *   GET  /sync/brief?participant_id=…                                 -> the participant's latest brief
 */

import { type Env, corsHeaders, jsonResponse } from "./_shared";

interface PushBody {
  participant_id?: string;
  persona_id?: string;
  display_name?: string;
  answer_log?: { session_id?: string };
}

const MAX_BODY_BYTES = 1_000_000; // ~1 MB — an Answer Log is text; guards the owner's Drive from abuse.

function misconfigured(env: Env): Response | null {
  if (!env.APPS_SCRIPT_URL || !env.SYNC_SHARED_SECRET) {
    return jsonResponse(
      { ok: false, error: "server_misconfigured", note: "APPS_SCRIPT_URL / SYNC_SHARED_SECRET not set." },
      500,
      env,
    );
  }
  return null;
}

/** POST /sync/answer-log — forward the Answer Log to Apps Script (which writes it write-once). */
export async function handleSyncPush(req: Request, env: Env): Promise<Response> {
  const bad = misconfigured(env);
  if (bad) return bad;

  const raw = await req.text();
  if (raw.length > MAX_BODY_BYTES) {
    return jsonResponse({ ok: false, error: "payload_too_large" }, 413, env);
  }
  let body: PushBody;
  try {
    body = JSON.parse(raw) as PushBody;
  } catch {
    return jsonResponse({ ok: false, error: "bad_request", note: "Body must be JSON." }, 400, env);
  }
  if (!body.participant_id || !body.answer_log?.session_id) {
    return jsonResponse(
      { ok: false, error: "bad_request", note: "need participant_id + answer_log.session_id" },
      400,
      env,
    );
  }

  const forward = {
    action: "push_answer_log",
    secret: env.SYNC_SHARED_SECRET,
    participant_id: body.participant_id,
    profile: { persona_id: body.persona_id, display_name: body.display_name },
    answer_log: body.answer_log,
  };

  let upstream: Response;
  try {
    // Apps Script /exec 302-redirects to googleusercontent.com; `follow` (default) returns the JSON.
    upstream = await fetch(env.APPS_SCRIPT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(forward),
      redirect: "follow",
    });
  } catch (e) {
    return jsonResponse({ ok: false, error: "upstream_unreachable", note: String(e) }, 502, env);
  }

  const text = await upstream.text();
  // Apps Script always 200s; a non-ok `ok` field (e.g. unauthorized) maps to a real status here.
  const status = upstream.ok && text.includes('"ok":true') ? 200 : 502;
  return new Response(text, {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(env) },
  });
}

/** GET /sync/brief?participant_id=… — forward to Apps Script and return the latest brief. */
export async function handleSyncPull(req: Request, env: Env): Promise<Response> {
  const bad = misconfigured(env);
  if (bad) return bad;

  const pid = new URL(req.url).searchParams.get("participant_id");
  if (!pid) {
    return jsonResponse({ ok: false, error: "bad_request", note: "need participant_id" }, 400, env);
  }

  const url = new URL(env.APPS_SCRIPT_URL);
  url.searchParams.set("action", "pull_brief");
  url.searchParams.set("secret", env.SYNC_SHARED_SECRET);
  url.searchParams.set("participant_id", pid);

  let upstream: Response;
  try {
    upstream = await fetch(url.toString(), { method: "GET", redirect: "follow" });
  } catch (e) {
    return jsonResponse({ ok: false, error: "upstream_unreachable", note: String(e) }, 502, env);
  }

  const text = await upstream.text();
  const status = upstream.ok && text.includes('"ok":true') ? 200 : 502;
  return new Response(text, {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(env) },
  });
}
