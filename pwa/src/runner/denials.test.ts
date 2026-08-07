/**
 * P17c runner tests — a refusal is recorded and acted on (WC-25), and memory reaches the prompt
 * (WC-26).
 *
 * The runner half of two complaints from the live sessions:
 *  - the model already classified *"the project timeline is not my job"* every single turn, and the
 *    runner dropped the classification on the floor, so the brain never learned;
 *  - the prompt carried what we still WANT and never what we already HAVE, so the interviewer could
 *    not say "you told me X — has that changed?"
 *
 * See `docs/plan/phase-17-interview-fidelity.md` §6. The brain half is
 * `brain/tests/test_memory_and_denials.py`.
 */

import { describe, expect, it } from "vitest";
import { isRefusal, Runner } from "./runner";
import { FakeLLMProvider } from "./llm/fake";
import { buildUserPrompt, SYSTEM_PROMPT } from "./prompts";
import { validateAnswerLog } from "./validate";
import type { LiveDecision, SessionBrief } from "./types";
import type { RunnerClock } from "./runner";

const clock: RunnerClock = { now: () => "2026-08-06T12:00:00.000Z" };

const decision = (d: Partial<LiveDecision>): LiveDecision => ({
  classification: "clear",
  action: "opener",
  utterance: "…",
  active_thread_id: null,
  thread_complete: false,
  ...d,
});

/** P18: every brief here has threads, so `start()` spends one scripted decision on the opener. */
const OPENING = decision({ action: "opener", utterance: "Welcome back — where shall we pick up?" });

function brief(extra: Partial<SessionBrief> = {}): SessionBrief {
  return {
    session_id: "s_p17c",
    persona_id: "persona.A",
    schema_version: "1.0.0",
    cold_start: false,
    persona_summary: "As Business Analysis Specialist, you've described 2 activities.",
    open_threads: [
      {
        id: "thread.missing_field.act.timeline.next_handoff",
        goal: "Find out who 'Project Timeline' hands off to next.",
        priority: 1,
        suggested_opener: "Once 'Project Timeline' is done, who picks it up next?",
      },
      {
        id: "thread.missing_field.act.brd.trigger",
        goal: "Find out what triggers 'Compile Final BRD'.",
        priority: 2,
        suggested_opener: "Walk me through what kicks off 'Compile Final BRD'.",
      },
    ],
    reserve_threads: [],
    ...extra,
  };
}

describe("WC-25 — a refusal reaches the Answer Log", () => {
  it("writes the classification onto the entry, paired with the thread it refuses", async () => {
    const llm = new FakeLLMProvider([
      OPENING,
      decision({
        classification: "not_mine",
        action: "opener",
        utterance: "Understood — let's talk about the BRD instead.",
        active_thread_id: "thread.missing_field.act.brd.trigger",
      }),
    ]);
    const runner = new Runner(brief(), llm, clock);
    await runner.start();

    await runner.respond("The project timeline is not my job.");

    const [entry] = runner.log.build().entries;
    expect(entry.classification).toBe("not_mine");
    // The pairing is the whole mechanism: a classification with no thread suppresses nothing.
    expect(entry.thread_id).toBe("thread.missing_field.act.timeline.next_handoff");
  });

  it("a log carrying a classification still validates against the contract", async () => {
    const llm = new FakeLLMProvider([
      OPENING,
      decision({ classification: "dont_know", action: "opener", utterance: "No problem." }),
      decision({ classification: "clear", action: "opener", utterance: "Got it." }),
    ]);
    const runner = new Runner(brief(), llm, clock, { participantId: "p_1" });
    await runner.start();
    await runner.respond("No idea, sorry.");
    await runner.respond("It starts when the client signs.");

    const result = validateAnswerLog(runner.log.build());
    expect(result.valid, JSON.stringify(result.errors)).toBe(true);
  });

  it("omits the field rather than writing null, so a pre-P17c entry stays contract-shaped", () => {
    const runner = new Runner(brief(), new FakeLLMProvider([]), clock, {
      participantId: "p_1",
      seedIdentity: true,
      identity: { display_name: "Kishor", role_title: "Business Analysis Specialist" },
    });

    const [seed] = runner.log.build().entries;
    expect("classification" in seed).toBe(false); // the app spoke for them; nothing was classified
    expect(validateAnswerLog(runner.log.build()).valid).toBe(true);
  });

  it("a tangent carries no thread, so drifting can never be read as refusing", async () => {
    const llm = new FakeLLMProvider([
      OPENING,
      decision({ classification: "tangent", action: "redirect", utterance: "Back to it —" }),
    ]);
    const runner = new Runner(brief(), llm, clock);
    await runner.start();

    await runner.respond("Anyway, the canteen food is terrible.");

    const [entry] = runner.log.build().entries;
    expect(entry.classification).toBe("tangent");
    expect(entry.thread_id).toBeNull();
  });
});

describe("WC-25 — a refusal closes the thread in-session too", () => {
  it("covers the refused thread even when the model says it isn't complete", async () => {
    // `thread_complete: false` is the realistic answer here — the question was not answered, it was
    // refused. Before P17c that left the thread current and re-askable.
    const llm = new FakeLLMProvider([
      OPENING,
      decision({
        classification: "not_mine",
        action: "opener",
        utterance: "Fair enough.",
        active_thread_id: "thread.missing_field.act.brd.trigger",
        thread_complete: false,
      }),
    ]);
    const runner = new Runner(brief(), llm, clock);
    await runner.start();

    await runner.respond("I told you, the timeline is not my job.");

    expect(runner.session.coveredIds()).toContain("thread.missing_field.act.timeline.next_handoff");
    expect(runner.session.nextThread()?.id).toBe("thread.missing_field.act.brd.trigger");
  });

  it("treats both refusals the same in-session; the scope difference is the brain's business", () => {
    expect(isRefusal("not_mine")).toBe(true);
    expect(isRefusal("dont_know")).toBe(true);
    expect(isRefusal("clear")).toBe(false);
    expect(isRefusal("vague")).toBe(false);
    expect(isRefusal("tangent")).toBe(false);
  });
});

describe("WC-25 — the model is told the distinction exists", () => {
  it("offers not_mine alongside dont_know, in the rules and in the response shape", () => {
    expect(SYSTEM_PROMPT).toContain('"not_mine"');
    expect(SYSTEM_PROMPT).toContain("clear|vague|tangent|dont_know|not_mine");
    // The denial rule has to name the classification, or the model follows it conversationally and
    // still writes nothing durable — which is exactly the pre-P17c behaviour.
    expect(SYSTEM_PROMPT).toMatch(/Classify that answer "not_mine"/);
  });
});

describe("WC-26 — what we already know reaches the prompt", () => {
  const known = [
    'You do "Compile Final BRD" (in Pre-sales Phase) — produces Final BRD; hands to Delivery Specialist',
    'You do "Detailed Project Discovery" (in Project Phase) — happens per project',
  ];

  const render = (b: SessionBrief) =>
    buildUserPrompt({
      brief: b,
      transcript: [],
      covered: [],
      currentThreadId: null,
      probedThreadIds: [],
      closing: false,
    });

  it("renders a WHAT WE ALREADY KNOW block above the brief", () => {
    const prompt = render(brief({ known_facts: known }));

    expect(prompt).toContain("=== WHAT WE ALREADY KNOW (from their earlier sessions) ===");
    for (const f of known) expect(prompt).toContain(f);
    // Above the brief on purpose: a model that reads the wants first starts composing questions
    // before it learns which ones are already answered.
    expect(prompt.indexOf("WHAT WE ALREADY KNOW")).toBeLessThan(prompt.indexOf("SESSION BRIEF"));
  });

  it("omits the block entirely when there is nothing to remember", () => {
    expect(render(brief())).not.toContain("WHAT WE ALREADY KNOW");
    expect(render(brief({ known_facts: [] }))).not.toContain("WHAT WE ALREADY KNOW");
  });

  it("forbids asking for it cold, and says what to do instead", () => {
    expect(SYSTEM_PROMPT).toContain("WHAT WE ALREADY KNOW");
    expect(SYSTEM_PROMPT).toMatch(/Never ask cold/);
    // "Don't ask" alone would make the model silently skip a topic it should be confirming.
    expect(SYSTEM_PROMPT).toMatch(/what has changed/);
  });
});
