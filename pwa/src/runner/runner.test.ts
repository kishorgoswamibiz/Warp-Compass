/**
 * Phase 5 runner tests (the brief's "Test plan"):
 *  - cold start produces a generic opener and records the first answer;
 *  - a drifting answer triggers a redirect; a vague answer triggers EXACTLY one probe;
 *  - an in-session contradiction is surfaced and reconciled;
 *  - the emitted Answer Log validates against contracts/answer-log.schema.json.
 *
 * Driven by the scripted FakeLLMProvider so the turn loop is deterministic and network-free.
 */

import { describe, expect, it } from "vitest";
import { Runner } from "./runner";
import { FakeLLMProvider } from "./llm/fake";
import { COLD_START_OPENERS } from "./prompts";
import { validateAnswerLog } from "./validate";
import type { LiveDecision, SessionBrief } from "./types";
import type { RunnerClock } from "./runner";

const clock: RunnerClock = { now: () => "2026-06-28T12:00:00.000Z" };

function coldBrief(): SessionBrief {
  return {
    session_id: "s_cold",
    persona_id: "persona.A",
    schema_version: "1.0.0",
    cold_start: true,
    persona_summary: "",
    open_threads: [],
    reserve_threads: [],
  };
}

function seededBrief(): SessionBrief {
  return {
    session_id: "s_seed",
    persona_id: "persona.A",
    schema_version: "1.0.0",
    cold_start: false,
    persona_summary: "As Sales Rep, you've described 1 activity with open questions.",
    open_threads: [
      {
        id: "t1",
        goal: "Find out what triggers 'Take order'.",
        why: "The ontology counts 'trigger' as part of a complete picture.",
        priority: 1,
        suggested_opener: "Walk me through what kicks off 'Take order'.",
        followups: [{ if: "they name one trigger", ask: "Is that the only thing that starts it?" }],
      },
      {
        id: "t2",
        goal: "Confirm the handoff to Warehouse.",
        priority: 2,
        suggested_opener: "Once 'Take order' is done, who picks it up next?",
      },
    ],
    reserve_threads: [],
  };
}

const decision = (d: Partial<LiveDecision>): LiveDecision => ({
  classification: "clear",
  action: "opener",
  utterance: "…",
  active_thread_id: null,
  thread_complete: false,
  ...d,
});

describe("cold start", () => {
  it("opens with a generic opener and records the first answer", async () => {
    const llm = new FakeLLMProvider([
      decision({ classification: "clear", action: "opener", utterance: "Walk me through a normal day." }),
    ]);
    const runner = new Runner(coldBrief(), llm, clock);

    const opener = runner.start();
    expect(COLD_START_OPENERS).toContain(opener);
    expect(opener).toBe(COLD_START_OPENERS[0]);

    await runner.respond("I'm a sales rep — I take customer orders all day.");
    const log = runner.log.build();
    expect(log.entries).toHaveLength(1);
    expect(log.entries[0].raw_answer).toContain("sales rep");
    expect(log.entries[0].agent_utterance).toBe(opener);
    expect(log.entries[0].kind).toBe("guided"); // agent guided it, even with no thread
    expect(log.entries[0].thread_id).toBeNull();
  });
});

describe("seeded brief — opener leads with the top thread", () => {
  it("starts on the highest-priority thread's suggested opener", () => {
    const runner = new Runner(seededBrief(), new FakeLLMProvider([]), clock);
    expect(runner.start()).toBe("Walk me through what kicks off 'Take order'.");
    expect(runner.session.currentThreadId).toBe("t1");
  });
});

describe("redirect on drift", () => {
  it("a tangent answer yields a redirect and is logged as free narration", async () => {
    const llm = new FakeLLMProvider([
      decision({
        classification: "tangent",
        action: "redirect",
        utterance: "Sure — but back to 'Take order': what actually kicks it off?",
        active_thread_id: "t1",
      }),
    ]);
    const runner = new Runner(seededBrief(), llm, clock);
    runner.start();
    const { effectiveAction } = await runner.respond("Oh the canteen food here is terrible lately.");
    expect(effectiveAction).toBe("redirect");
    const entry = runner.log.build().entries[0];
    expect(entry.kind).toBe("free_narration");
    expect(entry.thread_id).toBeNull();
  });
});

describe("one-probe rule", () => {
  it("probes a vague answer exactly once, then advances to the next thread", async () => {
    const llm = new FakeLLMProvider([
      // 1st vague answer → the model probes
      decision({ classification: "vague", action: "probe", utterance: "Can you give a concrete example?", active_thread_id: "t1" }),
      // 2nd vague answer → the model WANTS to probe again, but the guard must stop it
      decision({ classification: "vague", action: "probe", utterance: "Still vague — try again?", active_thread_id: "t1" }),
    ]);
    const runner = new Runner(seededBrief(), llm, clock);
    runner.start();

    const first = await runner.respond("It depends, the usual stuff.");
    expect(first.effectiveAction).toBe("probe");
    expect(runner.session.hasProbed("t1")).toBe(true);

    const second = await runner.respond("Like I said, it just depends.");
    expect(second.effectiveAction).toBe("opener"); // advanced, not a 2nd probe
    expect(second.utterance).toBe("Once 'Take order' is done, who picks it up next?");
    expect(runner.session.isCovered("t1")).toBe(true);
    expect(runner.session.currentThreadId).toBe("t2");
  });
});

describe("within-session reconciliation", () => {
  it("surfaces a contradiction as a reconcile action", async () => {
    const llm = new FakeLLMProvider([
      decision({ classification: "clear", action: "opener", utterance: "Got it.", active_thread_id: "t1", thread_complete: true }),
      decision({
        classification: "clear",
        action: "reconcile",
        utterance: "Earlier you said orders come by email, now you said by phone — which is it usually?",
        active_thread_id: "t1",
      }),
    ]);
    const runner = new Runner(seededBrief(), llm, clock);
    runner.start();
    await runner.respond("Orders come in by email.");
    const { effectiveAction } = await runner.respond("Actually customers mostly phone them in.");
    expect(effectiveAction).toBe("reconcile");
  });
});

describe("answer log contract", () => {
  it("emits a log that validates against contracts/answer-log.schema.json", async () => {
    const llm = new FakeLLMProvider([
      decision({ classification: "clear", action: "opener", utterance: "Who picks it up next?", active_thread_id: "t2", thread_complete: true }),
      decision({ classification: "clear", action: "close", utterance: "Thanks!", active_thread_id: null, thread_complete: true }),
    ]);
    const runner = new Runner(seededBrief(), llm, clock);
    runner.start();
    await runner.respond("It's triggered when the order email lands in my inbox.");
    await runner.respond("Warehouse picks it up to pack and ship.");
    runner.close();

    const log = runner.log.build();
    expect(log.entries).toHaveLength(2);
    expect(log.session_id).toBe("s_seed");
    expect(log.participant_id).toBe("persona.A");
    const res = validateAnswerLog(log);
    expect(res.errors).toEqual([]);
    expect(res.valid).toBe(true);
  });
});
