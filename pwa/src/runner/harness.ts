/**
 * Typed console harness for the live runner (Phase 5, temporary — UI shell arrives in P6).
 *
 * Drives the runner without voice so the intelligence can be proven end-to-end. Runs in Node on
 * the laptop and (for verification only) calls the LIVE model `deepseek-v4-flash` DIRECTLY via
 * `DirectDeepSeekProvider`, reading the key from `brain/.env`. The shipped PWA will instead inject
 * `WorkerLLMProvider` (keys live only in the Worker — AGENTS.md). It writes a schema-valid Answer
 * Log the brain can ingest (close the loop with: `cli ingest-log <path>`).
 *
 * Usage (run from pwa/):
 *   npm run session                              # cold-start, interactive
 *   npm run session -- --brief brief.json        # consume a `cli plan` brief
 *   npm run session -- --script answers.txt      # non-interactive (one answer per line)
 *   npm run session -- --persona persona.demo --session s_demo --out ../brain/_bus/log.json
 */

import { createInterface } from "node:readline/promises";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { stdin, stdout, argv, env } from "node:process";
import { Runner } from "./runner";
import { DirectDeepSeekProvider } from "./llm/deepseek";
import { validateAnswerLog } from "./validate";
import type { RunnerClock } from "./runner";
import type { SessionBrief } from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..", "..", ".."); // pwa/src/runner → repo root
const BRAIN_ENV = resolve(REPO_ROOT, "brain", ".env");

function parseArgs(args: string[]): Record<string, string | boolean> {
  const out: Record<string, string | boolean> = {};
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith("--")) {
        out[key] = next;
        i++;
      } else {
        out[key] = true;
      }
    }
  }
  return out;
}

/** Read DEEPSEEK_API_KEY (+ optional model override) from process env or brain/.env. */
function loadDeepSeekKey(): { apiKey: string; model?: string; baseUrl?: string } {
  let apiKey = env.DEEPSEEK_API_KEY ?? "";
  let model = env.DEEPSEEK_MODEL_LIVE;
  let baseUrl = env.DEEPSEEK_BASE_URL;
  try {
    const txt = readFileSync(BRAIN_ENV, "utf-8");
    for (const line of txt.split(/\r?\n/)) {
      const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
      if (!m) continue;
      const [, k, vRaw] = m;
      const v = vRaw.replace(/^["']|["']$/g, "");
      if (k === "DEEPSEEK_API_KEY" && !apiKey) apiKey = v;
      if (k === "DEEPSEEK_MODEL_LIVE" && !model) model = v;
      if (k === "DEEPSEEK_BASE_URL" && !baseUrl) baseUrl = v;
    }
  } catch {
    /* no brain/.env — rely on process env */
  }
  return { apiKey, model, baseUrl };
}

function loadBrief(args: Record<string, string | boolean>): SessionBrief {
  const persona = (args.persona as string) ?? "persona.demo";
  const session = (args.session as string) ?? "s_live";
  if (typeof args.brief === "string") {
    const raw = JSON.parse(readFileSync(resolve(process.cwd(), args.brief), "utf-8"));
    const brief: SessionBrief = Array.isArray(raw)
      ? raw.find((b: SessionBrief) => b.persona_id === persona) ?? raw[0]
      : raw;
    return brief;
  }
  // default: a cold-start brief (empty brain) — only generic openers.
  return {
    session_id: session,
    persona_id: persona,
    schema_version: "1.0.0",
    cold_start: true,
    persona_summary: "",
    open_threads: [],
    reserve_threads: [],
  };
}

const clock: RunnerClock = { now: () => new Date().toISOString() };

async function main(): Promise<void> {
  const args = parseArgs(argv.slice(2));
  const { apiKey, model, baseUrl } = loadDeepSeekKey();
  if (!apiKey) {
    stdout.write("DEEPSEEK_API_KEY not found (checked env + brain/.env). Aborting.\n");
    process.exitCode = 1;
    return;
  }

  const brief = loadBrief(args);
  const llm = new DirectDeepSeekProvider({ apiKey, model, baseUrl });
  const runner = new Runner(brief, llm, clock);

  stdout.write(`\n— Warp Compass live runner (model: ${llm.model}) —\n`);
  stdout.write(brief.cold_start ? "[cold start: empty brain]\n\n" : `[${brief.open_threads.length} open threads]\n\n`);

  const opener = runner.start();
  stdout.write(`AGENT: ${opener}\n`);

  // Non-interactive: feed scripted answers (one per line). Otherwise read from stdin.
  let answers: string[] | null = null;
  if (typeof args.script === "string") {
    answers = readFileSync(resolve(process.cwd(), args.script), "utf-8")
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
  }

  if (answers) {
    for (const a of answers) {
      stdout.write(`PERSON: ${a}\n`);
      const { utterance, decision, effectiveAction } = await runner.respond(a);
      stdout.write(`  [${decision.classification} → ${effectiveAction}]\n`);
      stdout.write(`AGENT: ${utterance}\n`);
    }
    stdout.write(`AGENT: ${runner.close()}\n`);
  } else {
    const rl = createInterface({ input: stdin, output: stdout });
    stdout.write("\n(type your answer; an empty line ends the session)\n");
    for (;;) {
      const a = (await rl.question("PERSON: ")).trim();
      if (!a) break;
      const { utterance, decision, effectiveAction } = await runner.respond(a);
      stdout.write(`  [${decision.classification} → ${effectiveAction}]\n`);
      stdout.write(`AGENT: ${utterance}\n`);
    }
    stdout.write(`AGENT: ${runner.close()}\n`);
    rl.close();
  }

  // Write + validate the Answer Log.
  const log = runner.log.build();
  const validation = validateAnswerLog(log);
  const outPath =
    typeof args.out === "string"
      ? resolve(process.cwd(), args.out)
      : resolve(REPO_ROOT, "brain", "_bus", brief.persona_id, `${brief.session_id}.json`);
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, JSON.stringify(log, null, 2), "utf-8");

  stdout.write(`\nAnswer Log: ${log.entries.length} entries → ${outPath}\n`);
  stdout.write(
    validation.valid
      ? "Schema: VALID against contracts/answer-log.schema.json ✓\n"
      : `Schema: INVALID ✗\n  ${validation.errors.join("\n  ")}\n`,
  );
  stdout.write(
    `\nClose the loop:  cd brain && uv run python -m warp_compass_brain.cli ingest-log "${outPath}"\n`,
  );
}

main().catch((e) => {
  stdout.write(`\nharness error: ${e instanceof Error ? e.stack ?? e.message : String(e)}\n`);
  process.exitCode = 1;
});
