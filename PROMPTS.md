# PROMPTS — every piece of text the assistant says or is told

> **Why this file exists:** prompt wording is the thing you'll want to tune most often, and it's
> spread across two languages and two packages. This is the map. Links are `file#Lnn` — click them
> in VS Code and they open at the right line.
>
> Ordered by **how much each one changes the felt experience of the conversation**, most first.
> If the conversation "starts wrong" or "goes wrong", §1–§4 are the only places to look.

---

## Quick answer: "the conversation starts badly"

Three things compose the very first sentence the person hears, in this order:

```
greet()                +  opener
"Hi Ajay — you're the     "Let's map your day from the very beginning: what's the
 Delivery Specialist."     first piece of work that lands on your plate…"
   §1                          §2 (cold start)  or  §5 (warm, from the brief)
```

- **First-ever session** (nothing in the graph for them) → opener comes from
  `COLD_START_OPENERS` (§2).
- **Every later session** → opener comes from the **Session Brief**, i.e. the Planner's
  `suggested_opener` for the highest-priority thread (§5).

So: dislike the *first* session's start → edit §2. Dislike the *later* sessions' starts → edit §5.
Dislike the *tone/behaviour throughout* → edit §3.

---

## 1. The greeting prefix

| What | Where |
|---|---|
| `greet()` — prefixes the opener with the person's first name and role | [`pwa/src/runner/runner.ts#L111`](pwa/src/runner/runner.ts#L111) |

Current wording:

- Cold: `Hi {FirstName} — you're the {role_title}. {opener}`
- Warm: `Welcome back, {FirstName}. {opener}`

Falls through to a bare opener when there's no declared identity.

---

## 2. Cold-start openers (the first-session script) ⚠ duplicated

The generic walk used when the graph has nothing on this person yet. **Lifecycle-anchored since
P15b:** opener 1 asks for the map (which parts of one piece of work's journey they touch), 2–5 walk
one stage, and 5 asks cadence.

| What | Where |
|---|---|
| `COLD_START_OPENERS` — **PWA copy**, what the person actually hears | [`pwa/src/runner/prompts.ts#L30`](pwa/src/runner/prompts.ts#L30) |
| `COLD_START_OPENERS` — **brain copy**, what the Planner emits on a cold brief | [`brain/src/warp_compass_brain/planner.py#L68`](brain/src/warp_compass_brain/planner.py#L68) |

> **⚠ Edit BOTH or they drift.** The constant is deliberately duplicated across the two languages
> (documented in the `prompts.ts` doc comment). Drift is now caught:
> `test_cold_start_openers_match_the_pwa_copy_verbatim` in `brain/tests/test_planner.py` parses
> `prompts.ts` and compares the lists character for character.
>
> Index `0` asks for the role and is **dropped automatically** when a declared identity exists — see
> `IDENTITY_OPENER_INDEX` ([`prompts.ts#L40`](pwa/src/runner/prompts.ts#L40)) and the filter in
> [`session.ts#L61`](pwa/src/runner/session.ts#L61). If you reorder the list, the role question must
> stay at index 0 or P13's "never ask the role again" guarantee breaks.
>
> **⚠ Never reintroduce the word "day."** "What do you do day to day" produces noise, not process —
> the owner's own answer as a BA was *"I start my day checking my mails, but checking mail is not my
> job role."* Real role work is per-project. Guarded by tests on **both** sides that grep the openers
> and the system prompt for `day` / `daily` / `morning`; the wording already drifted back once
> (P12 → P15), which is why the guard exists.

---

## 3. `SYSTEM_PROMPT` — the interviewer's personality, goal and method

**The single highest-leverage block in the whole system.** Sent on every live turn.

| What | Where |
|---|---|
| `SYSTEM_PROMPT` (~38 lines) | [`pwa/src/runner/prompts.ts#L78`](pwa/src/runner/prompts.ts#L78) |

What's in it, so you know which paragraph to edit:

| Section | Line | Controls |
|---|---|---|
| Persona | [#L78](pwa/src/runner/prompts.ts#L78) | "warm, sharp interviewer… like a curious colleague, never a form" |
| **END GOAL** | [#L80](pwa/src/runner/prompts.ts#L80) | the SOP mapped against the **lifecycle of work**; the unit of structure is the **STAGE**; cadence is required; "DO NOT organise anything around a calendar day"; explicitly *not* pain-point hunting |
| **METHOD** | [#L82](pwa/src/runner/prompts.ts#L82) | **two passes** — Pass A gets the stage map, Pass B walks one stage at a time; capture another role's work and move on; **record expectations as stated, never reconcile them**; never open with "what's most frustrating" |
| Brief contract | [#L90](pwa/src/runner/prompts.ts#L90) | brief is guidance, not a questionnaire; prefer threads that complete the chain |
| Classification set | [#L93](pwa/src/runner/prompts.ts#L93) | `clear` / `vague` / `tangent` / `dont_know` |
| Action set | [#L98](pwa/src/runner/prompts.ts#L98) | `opener` / `redirect` / `probe` / `reconcile` / `acknowledge` / `close` |
| Hard rules | [#L106](pwa/src/runner/prompts.ts#L106) | never re-ask name/role; no "let me look that up"; **one question per turn, under 30 words** |
| JSON output shape | [#L114](pwa/src/runner/prompts.ts#L114) | ⚠ must stay in sync with `isLiveDecision` ([#L194](pwa/src/runner/prompts.ts#L194)) and `LiveDecision` in [`types.ts`](pwa/src/runner/types.ts) |

> **Two lines here are load-bearing for the deliverable, not just the tone.** "NEVER assume these;
> discover theirs" is what keeps stages discovered per org rather than a predefined list (ADR #33),
> and "record it as stated. Do not challenge it or reconcile it" is what preserves the
> exec-vs-doer divergence that P15c reports as a finding (ADR #32). Softening either one quietly
> deletes the product.

**Tuning notes.** The "under 30 words" and "one question per turn" rules are what keep it feeling
spoken rather than written — loosen them and answers get long and the person disengages. The
anti-frustration rule at #L55 was added from your own field feedback (P12); removing it makes the
model drift back to interviewing for complaints instead of process.

---

## 4. `buildUserPrompt` — what the model is handed every single turn

| What | Where |
|---|---|
| `buildUserPrompt()` — assembles the per-turn user message | [`pwa/src/runner/prompts.ts#L120`](pwa/src/runner/prompts.ts#L120) |
| `briefDigest()` — how the Session Brief is flattened into text | [`pwa/src/runner/prompts.ts#L99`](pwa/src/runner/prompts.ts#L99) |

Blocks it emits, in order:

1. `=== WHO YOU'RE TALKING TO ===` — name + role + "do NOT ask for their name or role"
   ([#L125](pwa/src/runner/prompts.ts#L125)). Repeated **every turn** on purpose, so the rule
   survives the person circling back to introductions twenty turns in.
2. `=== SESSION BRIEF ===` — persona summary + ranked threads with goal / why / suggested opener /
   followups, or the cold-start line ([#L100](pwa/src/runner/prompts.ts#L100)).
3. `=== TRANSCRIPT THIS SESSION ===`
4. `=== STATE ===` — current thread, already-covered ids, already-probed ids, closing flag.

---

## 5. Planner openers + followups (the questions in every *later* session)

Deterministic scaffolding — the brain turns each detected gap into a thread with an opener the
runner may reword. **This is the text driving sessions 2..n**, so it matters as much as §2.

| What | Where |
|---|---|
| `_FIELD_OPENERS` — one opener per missing field | [`planner.py#L337`](brain/src/warp_compass_brain/planner.py#L337) |
| `_FIELD_FOLLOWUPS` — conditional second question per field | [`planner.py#L361`](brain/src/warp_compass_brain/planner.py#L361) |
| `_opener_and_followups()` — picks copy per gap kind: one-sided handoff, broken chain, unresolved conflict | [`planner.py#L388`](brain/src/warp_compass_brain/planner.py#L388) |
| P9 cross-persona routed threads: `handoff_confirm`, `handoff_trace`, `cross_conflict` | [`planner.py#L409`](brain/src/warp_compass_brain/planner.py#L409) onward |
| Persona summary sentence ("N activities; N systems; N problems raised") | [`planner.py#L260`](brain/src/warp_compass_brain/planner.py#L260) |

The fields with openers, grouped by what they're mapping:

| Node type | Fields |
|---|---|
| `Activity` | `trigger`, `inputs`, `system`, `output`, `next_handoff`, **`cadence`** (P15b), `exceptions`, `rules` |
| `Stage` (P15b) | `position`, `activities`, `owner`, `exit_criteria` |
| `Role` (P15b) | `reports_to`, `performs` |
| `Objective` (P15b) | `objective_for`, `owner_role` |

> **Adding a completeness field to `contracts/ontology.json` means adding an opener here too**, or
> the thread falls back to the raw `goal` string and reads like a form field.
> `test_every_scored_completeness_field_has_an_opener` fails if you forget.
>
> **`reports_to` and `performs` name the role rather than saying "you"** — deliberately. A Role gap
> fires for any role in the persona's subgraph, including one they merely *mentioned*, so
> "who do you report to?" would ask a BA about themselves while pointing at the QA Head's node.

### 5b. Orphan-thread copy (inherited from a retired teammate, P13)

Third-person phrasing + an explicit "I don't know" escape hatch, because the normal openers presume
ownership ("what do *you* need in hand") which would be wrong for someone else's process.

| What | Where |
|---|---|
| `_ORPHAN_WHY` | [`planner.py#L293`](brain/src/warp_compass_brain/planner.py#L293) |
| `_ORPHAN_DONT_KNOW` — "who would be the right person to ask?" | [`planner.py#L298`](brain/src/warp_compass_brain/planner.py#L298) |
| `_ORPHAN_FIELD_ASK` — per-field phrase fragments | [`planner.py#L303`](brain/src/warp_compass_brain/planner.py#L303) |
| `_orphan_opener_and_followups()` | [`planner.py#L314`](brain/src/warp_compass_brain/planner.py#L314) |

### 5c. Dual-hat self-handoff copy (P15a)

A multi-role person hands work from one of their own hats to another. The standard handoff copy says
a stranger passed it over, which reads as a bug and invites a "that's me" non-answer — so the thread
is reworded rather than suppressed (the switch is where dual-hat work most often leaks).

| What | Where |
|---|---|
| `KIND_HANDOFF_SELF` — the thread kind | [`crosspersona.py#L43`](brain/src/warp_compass_brain/crosspersona.py#L43) |
| Where the twin is minted (giver's owners ∩ receiver's owners) | [`crosspersona.py#L230`](brain/src/warp_compass_brain/crosspersona.py#L230) |
| The opener — *"when you switch from your X hat to your Y hat…"* | [`planner.py#L385`](brain/src/warp_compass_brain/planner.py#L385) |

> Guarded by `test_self_handoff_copy_never_says_another_team` — if you rewrite this copy, keep it
> free of "another team"/"another role", which is the entire point of the branch.

---

## 6. Extractor prompt (graph quality, not conversation)

Runs **after** the session, batch, on `deepseek-v4-pro`. Changing this changes what ends up in the
knowledge graph — not what the person hears.

| What | Where |
|---|---|
| `_SYSTEM` — the extraction contract | [`brain/src/warp_compass_brain/extractor.py#L18`](brain/src/warp_compass_brain/extractor.py#L18) |
| `_user_prompt()` — wraps the allowed types + the answer | [`extractor.py#L86`](brain/src/warp_compass_brain/extractor.py#L86) |
| `_known_roles_block()` — the `KNOWN ROLES` list injected every call (P15a) | [`extractor.py#L108`](brain/src/warp_compass_brain/extractor.py#L108) |

Rules worth knowing before you touch it:

- **"Be an ACTIVE EDITOR, never a transcriber"** ([#L35](brain/src/warp_compass_brain/extractor.py#L35)) — distil, don't copy conversational text.
- **`canonical_name` + `aliases` are the node's identifier** ([#L37](brain/src/warp_compass_brain/extractor.py#L37)) — these feed dedup/resolve, so loosening them causes duplicate nodes.
- **`description` = 1–3 factual sentences, what + why** ([#L40](brain/src/warp_compass_brain/extractor.py#L40)).
- **ABSTRACT PEOPLE INTO ROLES** ([#L43](brain/src/warp_compass_brain/extractor.py#L43)) — never emit "John"; emit "Discount Approver". People change, roles persist.
- **STAGES ARE THE SPINE** ([#L49](brain/src/warp_compass_brain/extractor.py#L49)) — emit a `Stage`
  and a `PART_OF` when the answer places work in a phase of the journey, and `PRECEDES` when it says
  one phase comes before another. ⚠ **"NEVER invent a stage the answer doesn't support, and never
  assume a standard set."** There is no `contracts/stages.json` and there must not be — a predefined
  stage list is the day-anchored assumption in a new costume (ADR #33). Keep names broad (a phase, not
  a task) and put each person's wording in `aliases` so two descriptions of the same phase merge.
- **CADENCE** ([#L56](brain/src/warp_compass_brain/extractor.py#L56)) — `key_attributes.cadence`, in
  the answer's own words. "Most real work is per-project, NOT daily — never write a daily cadence
  unless it was actually said."
- **EXPECTATIONS AND GOALS ARE DATA, NOT NOISE** ([#L59](brain/src/warp_compass_brain/extractor.py#L59))
  — emit an `Objective` and record it **as stated**, never reconciled against the graph. This is the
  raw material for the alignment findings (ADR #32); softening it here deletes the product.
- Node/edge types come from [`contracts/ontology.json`](contracts/ontology.json) — the prompt only
  *references* the allowed list, it doesn't define it. Add a type there, not here.
- **`KNOWN ROLES` is a PREFERENCE, not a limit** ([#L110](brain/src/warp_compass_brain/extractor.py#L110)).
  It lists the canonical names from [`contracts/roles.json`](contracts/roles.json) so "the PM" is
  emitted as "Delivery Specialist" — fixing role forking at the source rather than repairing it at
  resolve time. ⚠ **Never reword this to "only these roles exist".** Real interviews name roles
  nobody self-declares as (`End Client`, `Resource Manager`, `Development Team`), and closing the
  list would delete the client from the process map. This is the one place where the contract is
  *open* — unlike `ontology.json`'s node/edge types, which are closed.

---

## 7. Onboarding card copy (the very first screen, asked once)

| What | Where |
|---|---|
| Card copy — "Who's using this device?", field labels, the reassurance line | [`pwa/src/screens/OnboardingCard.tsx#L67`](pwa/src/screens/OnboardingCard.tsx#L67) |
| Role multi-select copy — "Your role(s)" + "Pick every role you hold…" (P15a) | [`OnboardingCard.tsx#L88`](pwa/src/screens/OnboardingCard.tsx#L88) |
| The 10 chip labels — **generated from the contract, not typed here** | [`contracts/roles.json`](contracts/roles.json) → [`pwa/src/sync/roles.ts#L24`](pwa/src/sync/roles.ts#L24) |
| `IDENTITY_QUESTION` — the question this card stands in for, replayed into the Answer Log | [`prompts.ts#L35`](pwa/src/runner/prompts.ts#L35) |
| `rolePhrase()` — `"Delivery Specialist and Account Management Specialist"` (P15a) | [`prompts.ts#L49`](pwa/src/runner/prompts.ts#L49) |
| `identityAnswer()` — `"I'm {name}, I'm the {roles}."`, seeded as the log's first entry | [`prompts.ts#L66`](pwa/src/runner/prompts.ts#L66) |
| `firstName()` — used by the greeting | [`prompts.ts#L38`](pwa/src/runner/prompts.ts#L38) |

> `identityAnswer()` is how the **graph** learns the person's role at turn zero — it's fed through
> the extractor like any other answer. Change its shape and you change what the extractor sees.
>
> ⚠ With several roles it must keep them as **separate names joined by "and"** (`rolePhrase`), not a
> `" / "`-joined compound: the extractor reads a slash-joined string as one job title and mints a
> single fused Role node, which defeats the whole multi-select. The `" / "` form is only the
> back-compat mirror stored in `Participant.role_title` for P13-era readers.
>
> **Editing the chip list is a contract change, not a copy change.** Add the role to
> `contracts/roles.json` (with its spoken synonyms) and mirror it into `pwa/src/sync/roles.ts` —
> `roles.test.ts` fails loudly if the two drift, the same discipline §2 uses for the duplicated
> openers. Then run `cli seed-roles` so the alias lands in the graph before the next round; aliases
> are what stop "the PM" forking away from "Delivery Specialist" (ADR #33).

---

## 8. Not prompts, but they shape the conversation

| What | Where | Effect |
|---|---|---|
| Guard layer — enforces the probe budget, thread advance, close | [`pwa/src/runner/runner.ts`](pwa/src/runner/runner.ts) | overrides the model when it misbehaves; a prompt change that fights the guards loses |
| **Probe budget** — 3 on a lifecycle-stage thread, 1 elsewhere (P15b) | [`session.ts` `probeBudget`](pwa/src/runner/session.ts) | how long the interviewer may stay on one stage. Raise it and sessions get deeper but longer; the 30-word cap is separate and should stay |
| `validate.ts` — decision schema check | [`pwa/src/runner/validate.ts`](pwa/src/runner/validate.ts) | rejects malformed model output |
| Live model + temperature | [`pwa/src/runner/llm.ts`](pwa/src/runner/llm.ts), [`pwa/wrangler.toml`](pwa/wrangler.toml) | `deepseek-v4-flash` on the hot path |
| Batch model | [`brain/.env`](brain/.env), [`brain/src/warp_compass_brain/config.py`](brain/src/warp_compass_brain/config.py) | `deepseek-v4-pro` for extraction |
| `complete_json()` — system+user call, `temperature=0.0` | [`brain/src/warp_compass_brain/llm/deepseek.py#L53`](brain/src/warp_compass_brain/llm/deepseek.py#L53) | determinism for extraction |

---

## After editing a prompt

```bash
# PWA-side prompts (§1–§4, §7)
cd pwa && npm run typecheck && npx vitest run && npm run build
# then: git push  → Cloudflare Pages auto-deploys

# brain-side prompts (§2 brain copy, §5, §6)
cd brain && uv run ruff check . && uv run pytest -q
```

Tests that assert on prompt text and **will fail loudly if you change wording they pin**:
[`pwa/src/runner/runner.test.ts`](pwa/src/runner/runner.test.ts),
[`brain/tests/test_planner.py`](brain/tests/test_planner.py),
[`brain/tests/test_extractor.py`](brain/tests/test_extractor.py).
That's a feature — read the failure, then decide whether the test or the prompt was wrong.

> A live session on a phone runs the **cached service worker**. After a prompt change deploys, fully
> reopen the installed PWA (not just background→foreground) or you'll test the old wording.

---

## Design rationale, if you want the "why" before rewriting

| Topic | Doc |
|---|---|
| Live-runner prompt design, brief-as-scaffolding | [`docs/02-architecture.md`](docs/02-architecture.md) §4.1, §12 |
| Interviewer refocus to end-to-end SOP (your field feedback) | [`docs/plan/phase-12-okf-store.md`](docs/plan/phase-12-okf-store.md) |
| Declared identity, never re-ask the role, orphan threads | [`docs/plan/phase-13-identity-and-lifecycle.md`](docs/plan/phase-13-identity-and-lifecycle.md) |
| All prompt-affecting decisions | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
