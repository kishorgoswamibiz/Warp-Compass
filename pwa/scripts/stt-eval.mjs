/**
 * STT eval gate (Phase 7) — run ElevenLabs Scribe on real, messy recordings and measure accuracy
 * BEFORE we trust the speech leg. Vendor benchmarks use clean audio; our conditions (Indian-accented
 * English, background noise, SKUs/codes/CRM jargon) won't be. The transcript becomes the permanent
 * Answer Log truth (docs/02 §4), so this gate is mandatory before P7 is DONE.
 *
 * Usage (from pwa/):
 *   node scripts/stt-eval.mjs <dir>
 *
 * <dir> holds the recordings (.wav/.mp3/.m4a/.webm/.ogg/.flac). For each audio file, put a
 * same-named .txt next to it with the correct transcript to get a Word Error Rate (WER); files
 * without a reference are transcribed and printed only. The script reads ELEVENLABS_API_KEY from
 * worker/.dev.vars and the model from worker/wrangler.toml (ELEVENLABS_STT_MODEL, default scribe_v2).
 *
 * Aim for ~20 recordings that match field conditions. Record the aggregate WER in PROGRESS.md and
 * decide go/no-go on the speech leg from it.
 */

import { readFile, readdir } from "node:fs/promises";
import { basename, extname, join, resolve } from "node:path";

const AUDIO_EXT = new Set([".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac", ".mp4"]);
const MIME = {
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
  ".m4a": "audio/mp4",
  ".mp4": "audio/mp4",
  ".webm": "audio/webm",
  ".ogg": "audio/ogg",
  ".flac": "audio/flac",
};

async function readEnv(path, key) {
  try {
    const txt = await readFile(path, "utf8");
    for (const line of txt.split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
      if (m && m[1] === key) return m[2].replace(/^["']|["']$/g, "");
    }
  } catch {
    /* fall through */
  }
  return "";
}

/** Word-level error rate (Levenshtein over tokens). Normalizes case/punctuation/whitespace. */
function wer(ref, hyp) {
  const norm = (s) =>
    s
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  const r = norm(ref);
  const h = norm(hyp);
  if (r.length === 0) return h.length === 0 ? 0 : 1;
  const d = Array.from({ length: r.length + 1 }, (_, i) => [i, ...Array(h.length).fill(0)]);
  for (let j = 0; j <= h.length; j++) d[0][j] = j;
  for (let i = 1; i <= r.length; i++) {
    for (let j = 1; j <= h.length; j++) {
      const cost = r[i - 1] === h[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
    }
  }
  return d[r.length][h.length] / r.length;
}

async function transcribe(file, mime, apiKey, baseUrl, model) {
  const bytes = await readFile(file);
  const form = new FormData();
  form.append("model_id", model);
  form.append("file", new Blob([bytes], { type: mime }), basename(file));
  const resp = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/speech-to-text`, {
    method: "POST",
    headers: { "xi-api-key": apiKey },
    body: form,
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  const data = await resp.json();
  return (data.text ?? "").trim();
}

async function main() {
  const dir = process.argv[2];
  if (!dir) {
    console.error("Usage: node scripts/stt-eval.mjs <dir-of-recordings>");
    process.exit(1);
  }
  const apiKey = await readEnv(resolve("../worker/.dev.vars"), "ELEVENLABS_API_KEY");
  if (!apiKey) {
    console.error("ELEVENLABS_API_KEY not found in ../worker/.dev.vars");
    process.exit(1);
  }
  const baseUrl = (await readEnv(resolve("../worker/wrangler.toml"), "ELEVENLABS_BASE_URL")) || "https://api.elevenlabs.io";
  const model = (await readEnv(resolve("../worker/wrangler.toml"), "ELEVENLABS_STT_MODEL")) || "scribe_v2";

  const entries = (await readdir(resolve(dir))).filter((f) => AUDIO_EXT.has(extname(f).toLowerCase()));
  if (entries.length === 0) {
    console.error(`No audio files in ${dir}`);
    process.exit(1);
  }

  console.log(`Model: ${model} · ${entries.length} recordings\n`);
  const wers = [];
  for (const name of entries.sort()) {
    const file = join(resolve(dir), name);
    const ext = extname(name).toLowerCase();
    try {
      const hyp = await transcribe(file, MIME[ext] || "application/octet-stream", apiKey, baseUrl, model);
      let refTxt = "";
      try {
        refTxt = await readFile(join(resolve(dir), basename(name, ext) + ".txt"), "utf8");
      } catch {
        /* no reference */
      }
      if (refTxt.trim()) {
        const e = wer(refTxt, hyp);
        wers.push(e);
        console.log(`• ${name}  WER ${(e * 100).toFixed(1)}%`);
        console.log(`    ref: ${refTxt.trim()}`);
        console.log(`    hyp: ${hyp}\n`);
      } else {
        console.log(`• ${name}  (no reference)`);
        console.log(`    hyp: ${hyp}\n`);
      }
    } catch (err) {
      console.log(`• ${name}  ERROR: ${err.message}\n`);
    }
  }

  if (wers.length) {
    const avg = wers.reduce((a, b) => a + b, 0) / wers.length;
    console.log("────────────────────────────────────────");
    console.log(`Aggregate WER over ${wers.length} scored recordings: ${(avg * 100).toFixed(1)}%`);
    console.log(`(≈ ${(100 - avg * 100).toFixed(1)}% word accuracy)`);
  } else {
    console.log("No reference .txt files found — transcripts printed for manual review.");
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
