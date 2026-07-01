/**
 * Warp Compass — Google Apps Script sync Web App (Phase 11).
 *
 * WHAT THIS IS: the free, serverless bridge that lets each user's PWA reach the one brain WITHOUT
 * any end user ever logging into Google. It is deployed to "Execute as: me (the owner)", so every
 * request runs under the OWNER's Drive — the phone just POSTs JSON. This is the "networked sync
 * endpoint" the design anticipated (docs/02 §2B, §13); the folder tree it maintains is byte-for-byte
 * the FolderBus layout (brain/src/warp_compass_brain/bus/), so the laptop brain reads/writes it
 * unchanged via Google Drive for Desktop.
 *
 * LAYOUT IT MAINTAINS (identical to FolderBus):
 *   {ROOT}/participants/{participant_id}/
 *       profile.json                     # registry entry (merged; NEVER clobbers the brain's ingested_logs)
 *       answer_logs/{session_id}.json     # runner -> brain  (WRITE-ONCE, immutable source of truth)
 *       briefs/*.json                     # brain -> runner  (we only ever read the latest)
 *
 * CONFIG (Project Settings -> Script properties — set these once, see apps-script/README.md):
 *   ROOT_FOLDER_ID  the Drive folder id of the engagement root (the SAME folder mirrored by Drive Desktop)
 *   SHARED_SECRET   must match SYNC_SHARED_SECRET in the Cloudflare Pages function (defense in depth)
 *
 * The Cloudflare Pages Function (pwa/functions/sync/*) is the only intended caller: it injects the
 * secret server-side and gives the PWA clean same-origin CORS. Apps Script always returns HTTP 200
 * (ContentService can't set status codes), so outcomes are carried in the JSON `ok` field; the Pages
 * Function maps them to real HTTP status.
 */

function doPost(e) {
  return handle_(e, "POST");
}

function doGet(e) {
  return handle_(e, "GET");
}

function handle_(e, method) {
  try {
    var body = {};
    if (e && e.postData && e.postData.contents) {
      body = JSON.parse(e.postData.contents);
    }
    var params = (e && e.parameter) || {};

    var secret = body.secret || params.secret || "";
    if (!prop_("SHARED_SECRET") || secret !== prop_("SHARED_SECRET")) {
      return json_({ ok: false, error: "unauthorized" });
    }

    var action = body.action || params.action || "";
    if (method === "POST" && action === "push_answer_log") return pushAnswerLog_(body);
    if (method === "GET" && action === "pull_brief") return pullBrief_(params);

    return json_({ ok: false, error: "bad_request", note: "unknown action: " + action });
  } catch (err) {
    return json_({ ok: false, error: "server_error", note: String(err) });
  }
}

/** POST: write one Answer Log (write-once) + upsert the participant profile. */
function pushAnswerLog_(body) {
  var pid = body.participant_id;
  var log = body.answer_log;
  if (!pid || !log || !log.session_id) {
    return json_({ ok: false, error: "bad_request", note: "need participant_id + answer_log.session_id" });
  }

  var pdir = participantDir_(pid);
  writeProfile_(pdir, pid, body.profile || {});

  var logs = childFolder_(pdir, "answer_logs");
  var name = String(log.session_id) + ".json";
  if (logs.getFilesByName(name).hasNext()) {
    // Immutable source of truth: never overwrite an existing Answer Log.
    return json_({ ok: true, written: false, reason: "exists", name: name });
  }
  logs.createFile(name, JSON.stringify(log, null, 2), "application/json");
  return json_({ ok: true, written: true, name: name });
}

/** GET: return the participant's latest Session Brief (by last-updated), or brief:null if none. */
function pullBrief_(params) {
  var pid = params.participant_id;
  if (!pid) return json_({ ok: false, error: "bad_request", note: "need participant_id" });

  var pdir = participantDir_(pid);
  var briefs = childFolder_(pdir, "briefs");
  var it = briefs.getFiles();
  var latest = null;
  while (it.hasNext()) {
    var f = it.next();
    if (f.getName().slice(-5).toLowerCase() !== ".json") continue;
    if (!latest || f.getLastUpdated().getTime() > latest.getLastUpdated().getTime()) latest = f;
  }
  if (!latest) return json_({ ok: true, brief: null });

  var brief = JSON.parse(latest.getBlob().getDataAsString());
  return json_({ ok: true, brief: brief, name: latest.getName() });
}

/**
 * Upsert profile.json by MERGING — critically, we preserve `ingested_logs` (the brain's resume key,
 * ADR #21c) and anything else the brain writes; we only set identity + display_name + last_seen.
 */
function writeProfile_(pdir, pid, incoming) {
  var files = pdir.getFilesByName("profile.json");
  var profile = {};
  var file = null;
  if (files.hasNext()) {
    file = files.next();
    try {
      profile = JSON.parse(file.getBlob().getDataAsString()) || {};
    } catch (e) {
      profile = {};
    }
  }
  if (!profile.participant_id) profile.participant_id = pid;
  if (!profile.persona_id) profile.persona_id = incoming.persona_id || pid; // prototype: 1:1 (ADR #17)
  if (!profile.created_at) profile.created_at = new Date().toISOString();
  if (incoming.display_name) profile.display_name = String(incoming.display_name);
  profile.last_seen = new Date().toISOString();

  var content = JSON.stringify(profile, null, 2);
  if (file) file.setContent(content);
  else pdir.createFile("profile.json", content, "application/json");
}

// ── Drive folder helpers ──────────────────────────────────────────────────────
function root_() {
  var id = prop_("ROOT_FOLDER_ID");
  if (!id) throw new Error("ROOT_FOLDER_ID script property is not set");
  return DriveApp.getFolderById(id);
}

function participantDir_(pid) {
  return childFolder_(childFolder_(root_(), "participants"), String(pid));
}

/** Find-or-create a direct child folder by name (idempotent). */
function childFolder_(parent, name) {
  var it = parent.getFoldersByName(name);
  if (it.hasNext()) return it.next();
  return parent.createFolder(name);
}

// ── small utils ───────────────────────────────────────────────────────────────
function prop_(k) {
  return PropertiesService.getScriptProperties().getProperty(k) || "";
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
