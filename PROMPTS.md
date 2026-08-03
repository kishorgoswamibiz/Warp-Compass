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

The generic chronological walk used when the graph has nothing on this person yet.

| What | Where |
|---|---|
| `COLD_START_OPENERS` — **PWA copy**, what the person actually hears | [`pwa/src/runner/prompts.ts#L23`](pwa/src/runner/prompts.ts#L23) |
| `COLD_START_OPENERS` — **brain copy**, what the Planner emits on a cold brief | [`brain/src/warp_compass_brain/planner.py#L58`](brain/src/warp_compass_brain/planner.py#L58) |

> **⚠ Edit BOTH or they drift.** The constant is deliberately duplicated across the two languages
> (documented in the `prompts.ts` doc comment). Index `0` asks for the role and is **dropped
> automatically** when a declared identity exists — see `IDENTITY_OPENER_INDEX`
> ([`prompts.ts#L32`](pwa/src/runner/prompts.ts#L32)) and the filter in
> [`session.ts#L38`](pwa/src/runner/session.ts#L38). If you reorder the list, the role question must
> stay at index 0 or P13's "never ask the role again" guarantee breaks.

---

## 3. `SYSTEM_PROMPT` — the interviewer's personality, goal and method

**The single highest-leverage block in the whole system.** Sent on every live turn.

| What | Where |
|---|---|
| `SYSTEM_PROMPT` (~35 lines) | [`pwa/src/runner/prompts.ts#L47`](pwa/src/runner/prompts.ts#L47) |

What's in it, so you know which paragraph to edit:

| Section | Line | Controls |
|---|---|---|
| Persona | [#L47](pwa/src/runner/prompts.ts#L47) | "warm, sharp interviewer… like a curious colleague, never a form" |
| **END GOAL** | [#L49](pwa/src/runner/prompts.ts#L49) | a complete 0→100 SOP; explicitly *not* pain-point hunting |
| **METHOD** | [#L51](pwa/src/runner/prompts.ts#L51) | skeleton first, then depth; "what happens next?"; anchor to what they said; **never open with "what's most frustrating"** |
| Brief contract | [#L57](pwa/src/runner/prompts.ts#L57) | brief is guidance, not a questionnaire; prefer threads that complete the chain |
| Classification set | [#L60](pwa/src/runner/prompts.ts#L60) | `clear` / `vague` / `tangent` / `dont_know` |
| Action set | [#L65](pwa/src/runner/prompts.ts#L65) | `opener` / `redirect` / `probe` / `reconcile` / `acknowledge` / `close` |
| Hard rules | [#L73](pwa/src/runner/prompts.ts#L73) | never re-ask name/role; no "let me look that up"; **one question per turn, under 30 words** |
| JSON output shape | [#L81](pwa/src/runner/prompts.ts#L81) | ⚠ must stay in sync with `isLiveDecision` ([#L161](pwa/src/runner/prompts.ts#L161)) and `LiveDecision` in [`types.ts`](pwa/src/runner/types.ts) |

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
| `_FIELD_OPENERS` — one opener per missing field (trigger / inputs / system / output / next_handoff / exceptions / rules) | [`planner.py#L327`](brain/src/warp_compass_brain/planner.py#L327) |
| `_FIELD_FOLLOWUPS` — conditional second question per field | [`planner.py#L337`](brain/src/warp_compass_brain/planner.py#L337) |
| `_opener_and_followups()` — picks copy per gap kind: one-sided handoff, broken chain, unresolved conflict | [`planner.py#L350`](brain/src/warp_compass_brain/planner.py#L350) |
| P9 cross-persona routed threads: `handoff_confirm`, `handoff_trace`, `cross_conflict` | [`planner.py#L371`](brain/src/warp_compass_brain/planner.py#L371) onward |
| Persona summary sentence ("N activities; N systems; N problems raised") | [`planner.py#L260`](brain/src/warp_compass_brain/planner.py#L260) |

### 5b. Orphan-thread copy (inherited from a retired teammate, P13)

Third-person phrasing + an explicit "I don't know" escape hatch, because the normal openers presume
ownership ("what do *you* need in hand") which would be wrong for someone else's process.

| What | Where |
|---|---|
| `_ORPHAN_WHY` | [`planner.py#L283`](brain/src/warp_compass_brain/planner.py#L283) |
| `_ORPHAN_DONT_KNOW` — "who would be the right person to ask?" | [`planner.py#L288`](brain/src/warp_compass_brain/planner.py#L288) |
| `_ORPHAN_FIELD_ASK` — per-field phrase fragments | [`planner.py#L293`](brain/src/warp_compass_brain/planner.py#L293) |
| `_orphan_opener_and_followups()` | [`planner.py#L304`](brain/src/warp_compass_brain/planner.py#L304) |

---

## 6. Extractor prompt (graph quality, not conversation)

Runs **after** the session, batch, on `deepseek-v4-pro`. Changing this changes what ends up in the
knowledge graph — not what the person hears.

| What | Where |
|---|---|
| `_SYSTEM` — the extraction contract | [`brain/src/warp_compass_brain/extractor.py#L17`](brain/src/warp_compass_brain/extractor.py#L17) |
| `_user_prompt()` — wraps the allowed types + the answer | [`extractor.py#L73`](brain/src/warp_compass_brain/extractor.py#L73) |

Rules worth knowing before you touch it:

- **"Be an ACTIVE EDITOR, never a transcriber"** ([#L35](brain/src/warp_compass_brain/extractor.py#L35)) — distil, don't copy conversational text.
- **`canonical_name` + `aliases` are the node's identifier** ([#L37](brain/src/warp_compass_brain/extractor.py#L37)) — these feed dedup/resolve, so loosening them causes duplicate nodes.
- **`description` = 1–3 factual sentences, what + why** ([#L40](brain/src/warp_compass_brain/extractor.py#L40)).
- **ABSTRACT PEOPLE INTO ROLES** ([#L42](brain/src/warp_compass_brain/extractor.py#L42)) — never emit "John"; emit "Discount Approver". People change, roles persist.
- Node/edge types come from [`contracts/ontology.json`](contracts/ontology.json) — the prompt only
  *references* the allowed list, it doesn't define it. Add a type there, not here.

---

## 7. Onboarding card copy (the very first screen, asked once)

| What | Where |
|---|---|
| Card copy — "Who's using this device?", field labels, the reassurance line | [`pwa/src/screens/OnboardingCard.tsx#L53`](pwa/src/screens/OnboardingCard.tsx#L53) |
| `IDENTITY_QUESTION` — the question this card stands in for, replayed into the Answer Log | [`prompts.ts#L35`](pwa/src/runner/prompts.ts#L35) |
| `identityAnswer()` — `"I'm {name}, I'm the {role}."`, seeded as the log's first entry | [`prompts.ts#L43`](pwa/src/runner/prompts.ts#L43) |
| `firstName()` — used by the greeting | [`prompts.ts#L38`](pwa/src/runner/prompts.ts#L38) |

> `identityAnswer()` is how the **graph** learns the person's role at turn zero — it's fed through
> the extractor like any other answer. Change its shape and you change what the extractor sees.

---

## 8. Not prompts, but they shape the conversation

| What | Where | Effect |
|---|---|---|
| Guard layer — enforces one-probe-per-thread, thread advance, close | [`pwa/src/runner/runner.ts`](pwa/src/runner/runner.ts) | overrides the model when it misbehaves; a prompt change that fights the guards loses |
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
