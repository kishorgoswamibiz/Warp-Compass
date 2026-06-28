# Phase 5 — Live runner (typed, text-only)

> **Status: ✅ DONE (2026-06-28, `agent:opus-p5`).** Implemented in `pwa/src/runner/`
> (`types.ts`, `prompts.ts`, `session.ts`, `runner.ts`, `answerlog.ts`, `llm/{fake,deepseek,worker,json}.ts`,
> `validate.ts`, `harness.ts`, `index.ts`). **First exercise of the LIVE model `deepseek-v4-flash`**
> — confirmed via `cli check-models` and a live typed session (cold-start opener, vague→one-probe,
> tangent→redirect, graceful close) that emitted a **schema-valid Answer Log**. Loop closed with
> P2–P4: new brain CLI `ingest-log <path>` re-derived graph nodes/edges from the runner's log
> (2 created, 5 merged into the existing graph, 6 edges). 6 vitest tests + `npm run typecheck`
> clean. See ADR #18 and the PROGRESS handoff log. The shipped PWA wires `WorkerLLMProvider`
> (keys only in the Worker); the Node harness uses `DirectDeepSeekProvider` for local verification.

**Goal:** The fast interaction plane as **text first** — consume a Session Brief, converse, and
write an Answer Log. Prove the intelligence before adding voice. It holds **no graph** (`02 §4.1`).

**Depends on:** P4 (a brief to consume). **Package:** `pwa` (logic; UI shell in P6).

## Behaviors (live, over session context only)
- **Open & discover.** Cold start → generic openers ("walk me through a normal day…"); otherwise
  lead with the brief's top threads. Never read from a fixed question list.
- **Redirect on drift.** Check each answer against the current thread's intent; steer back in its
  own words if the person wandered.
- **Reconcile within-session contradictions.** With the whole session in context, spot that
  answer #11 clashes with #3 and resolve on the spot.
- **Follow up & reword.** One probe on vague answers; skip what's covered.
- **Capture free narration.** When the person just talks, record cleanly, acknowledge, optional
  one clarifier.
- **Graceful close.** Thank, say it'll process before next time — no "thinking" wait.

## Steps
1. **`LLMProvider` (live, `v4-flash`)**: a lightweight prompt (`02 §12`) that classifies each
   answer (clear/vague/tangent/don't-know) and produces the next utterance. **Must not** reference
   or query the graph.
2. **Session state** (`runner/session.ts`): in-memory brief + growing transcript (a few thousand
   tokens). Thread cursor, covered-set.
3. **Turn loop** (`runner/runner.ts`): take input → classify → choose action (opener/redirect/
   probe/reconcile/acknowledge) → emit utterance → append to transcript.
4. **Answer Log writer** (`runner/answerlog.ts`): append entries valid against
   `contracts/answer-log.schema.json`; mark `kind`, `thread_id` (or null), timestamps.
5. **Typed UI harness** (temporary): a console/textarea loop to drive it without voice.

## Files
`pwa/src/runner/{runner.ts,session.ts,answerlog.ts,prompts.ts}` (+ a shared TS types module
generated/derived from `contracts/`).

## Test plan
- Cold start produces a generic opener and records the first answer.
- A drifting answer triggers a redirect; a vague answer triggers exactly one probe.
- An in-session contradiction is surfaced and reconciled.
- The emitted Answer Log validates against the schema.

## Done when
A full typed session runs end-to-end and produces a schema-valid Answer Log the brain can ingest
(close the loop with P2–P4 on the same machine).
