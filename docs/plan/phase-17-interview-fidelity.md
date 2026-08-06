# Phase 17 — Interview fidelity: the brief must be true, varied, and remembered

> **Status:** **P17a + P17b LANDED (06 Aug 2026), graph rebuilt.** P17c is PLAN ONLY.
> ⚠ **A rebuild is owed:** WC-27 is fixed in the extractor prompt but the four Objectives it lost
> only return on the next `cli rebuild-graph` (§5.4).
>
> Written 06 Aug 2026 from the owner's report after two live second-sessions (Solution Architect and
> Business Analysis Specialist, both `s_next`, 06 Aug 2026 01:45–02:06). **Both testers ended their
> session early.** The owner's words: *"sometimes it's asking redundant questions… it sometimes feels
> like it's very targeted on keywords… it is re-asking the questions I have explained in the previous
> session… users may get a little agitated."*
>
> The owner's question was whether this needed a better LLM. **It did not.** Every complaint traces to
> the Session Brief the model was handed, and the transcripts are in `sample/` if you want to read the
> failure before the fix.
>
> Depends on: P16a (`declared_roles` reaching the brain), P16a-bis (role-inherited threads). Both
> shipped. Nothing here changes the two-plane split or adds a component.

---

## Context Card — read THIS, skip the source

- Data shapes (authoritative): `contracts/session-brief.schema.json`, `contracts/answer-log.schema.json`
- `Planner.plan(persona_id, *, session_id) -> SessionBrief` @ `brain/src/warp_compass_brain/planner.py#L249`
- `_cluster(threads, limit, *, per_node=_CLUSTER_MAX) -> list[OpenThread]` @ `planner.py#L105` — **P17a**, groups a brief by node
- `_CLUSTER_MAX = 3` @ `planner.py#L102` — threads about one node per brief
- `Planner._persona_summary(persona_id, subgraph_ids, snap, report, role_ids=None) -> str` @ `planner.py#L449`
- `Planner._role_threads(snap, report, subgraph_ids, role_ids) -> list[OpenThread]` @ `planner.py#L370`
- `CrossPersonaEngine._declared_owners(snap) -> dict[str, set[str]]` @ `crosspersona.py#L377` — `role_id -> personas who DECLARED it`
- `CrossPersonaEngine._role_owner_personas(role_id, snap) -> set[str]` @ `crosspersona.py#L393` — declarers **∪** contributors; **routing only**, never copy
- `_FIELD_IMPACT` @ `threads.py#L39` — `next_handoff` 0.65 is the top weight; this is why an unclustered brief is one question
- `SYSTEM_PROMPT` @ `pwa/src/runner/prompts.ts#L78`; `briefDigest()` @ `prompts.ts#L134`
- **P17b:** `Resolver.node_context(card) -> str` @ `resolve.py#L124` — `" [performed by X; in stage Y]"`, `""` when unplaced
- **P17b:** `Resolver.adjudicate(cand, retrieved, *, cand_context="")` @ `resolve.py#L172`
- **P17b:** `ingest._candidate_context(cand, extraction) -> str` @ `ingest.py#L29` — same line for the *proposed* node, from its own batch
- **P17b:** `lifecycle.all_answer_entries(bus) -> list[AnswerEntry]` @ `lifecycle.py#L200` — the complete input to a rebuild, live **and archived**, time-ordered
- Config knobs: `planner_max_threads=6`, `planner_role_max=4`, `planner_orphan_max=2`, **`similarity_ceiling=0.90`** (raised in P17b — read the comment before touching it)
- Run: `cd brain && uv run ruff check . && uv run pytest -q` · `cd pwa && npm run typecheck && npx vitest run`
- Inspect a real brief without writing anything: `cd brain && uv run python -m warp_compass_brain.cli plan --persona <id> --session s_verify`
- Re-measure before retuning the ceiling: `cd brain && uv run --extra vectors python ..\scripts\similarity_probe.py`
- Replay the graph after improving extraction: `cd brain && uv run python -m warp_compass_brain.cli rebuild-graph --dry-run` (then `--yes`)

---

## 1. What the testers actually heard

Two transcripts, `sample/SA s_next.json` and `sample/Business Analyst s_next.json`, against the briefs
that produced them (`{bus}/participants/<id>/briefs/s_next.json`). Both people are real, both are the
owner's colleagues, and both disengaged.

**The Solution Architect**, opening question of his second session:

> *"Welcome back, Chandu. You wear both hats here — when you switch from your **Quality Assurance
> Head** hat to your **Technical Specialist** hat, what do you do with 'Assign Feedback to
> Developers'?"*

> *"No, no, I do not do quality assurance and all that… SA does not do anything in quality assurance
> and quality head."*

He declared exactly one role at onboarding: `"role_title": "Solution Architect"`.

Then five consecutive turns of the same question about five different activities. By the sixth:

> *"I mean, it's a continuous process. People parallelly take care of other things… it's a parallel
> thing till it goes to UAT and production."*

That is a person telling you the question does not fit. He was asked it three more times, then:

> *"Another **Account Management Specialist** described 'Send Proposal' — how does that part go when
> you're involved?"*
> *"I guess this is enough for today. We'll come back later."*

**The Business Analyst** was asked to reconcile 'Create Project Timeline', said *"the project timeline
is not my job, it is something that the project manager does"*, was asked again as the Delivery
Specialist, said *"No, no. I do not create the project timeline, so how am I in the delivery specialist
hat?"*, and four turns later was asked a third time:

> *"You also wear the Delivery Specialist hat — when you switch to it, what happens with handing
> documents to the project manager?"*
> *"I told you I do not act as a delivery specialist. **Why you're not trying to understand?**"*

He too ended the session early. He also said, twice, *"I had replied in my previous sessions"* and
*"Did I not tell you that I document the user stories?"*

---

## 2. What's broken — verified in code and in live data, 06 Aug 2026

Seven findings. **1, 2, 3 and 6 are P17a and are fixed.** 4, 5 and 7 are P17b/P17c.

### Finding 1 — the brief claims each person holds five or six roles they never declared ✅ FIXED

`persona_summary` leads `briefDigest()` and is therefore injected at the top of the live prompt on
**every turn**. What it said, verbatim, in the brief that ran the SA session:

> *"As **Business Analysis Specialist, Development Lead, Quality Assurance Head, Solution Architect,
> Technical Specialist**, you've described 11 activities…"*

and for the BA — note the third entry:

> *"As Account Management Specialist, Business Analysis Specialist, **Customer**, Delivery Specialist,
> Solution Architect, Technical Specialist…"*

`profile.json` for the two of them says `"Solution Architect"` and `"Business Analysis Specialist"`.
One role each.

The cause was one line:

```python
roles = sorted(c.canonical_name for c in cards if c.type is NodeType.ROLE) or declared
```

`cards` is every node the persona has provenance on. Say *"the QA team tests it"* once and you have
provenance on `role.quality-assurance-head` — so the brief said you **were** one. `declared`, already
computed correctly two lines above, was only the fallback.

**This is the WC-R5 over-reach**, in the single most damaging position available to it, and
`_persona_role_ids` had already refused to make the same inference in the very next method
(`planner.py#L352`, *"contribution is a guess"*). It just was never fixed here.

### Finding 2 — "you wear both hats" is inferred from mere mention ✅ FIXED

`dual_hat = persona in giver_personas`, where `giver_personas` came from `_role_owner_personas` —
*declarers* **∪** *contributors of the role's activities*. Describing what QA does earns you
provenance on QA's activities, so the graph concluded the SA wore the QA Head hat and the BA the
Delivery Specialist hat.

The union is **correct for routing** and was put there deliberately by P16a/ADR #34: *"being asked is
cheap, never being asked is the bug."* It is wrong for **telling someone to their face which hats they
wear**, which is a claim about them, not a decision about whom to ask.

### Finding 3 — the brief is one question, repeated twelve times ✅ FIXED

The SA brief: **eleven of twelve threads were `next_handoff`.** Threads 2–6 were literally *"Once 'X'
is done, who picks it up next?"* for five different activities, consecutively; 7–10 the same question
in role-inherited wording; 11–12 the same again in orphan wording.

`_FIELD_IMPACT` ranks `next_handoff` top (0.65), `trigger` next (0.6), and `_priority` is impact plus a
small recency term. So `threads[: self._max]` took **one field across every activity** — a column-major
read of a table whose rows are the person's work. `reserve_threads` showed the banding plainly: four
`next_handoff`, then eleven `trigger`, then nine `output`, then seven `cadence`.

It also made the interviewer structurally unable to obey its own instructions. `SYSTEM_PROMPT` says
*"PASS B — one stage at a time… Finish a stage before moving to the next one."* No prefix of that
ranking can support it.

### Finding 4 — one real activity is four graph nodes, so it is asked four times ⏳ P17b

```
act.code-review · act.code-review-and-team-oversight
act.code-and-function-quality-review · act.review-checks
```

Brief threads 4 and 5 were consecutive: *"who picks up **Code Review and Team Oversight**?"* then
*"who picks up **Code Review**?"* Likewise discovery (`discovery-session`, `start-discovery`,
`conduct-discovery-and-demos`, `conduct-granular-discovery-sessions`) and documentation
(`documentation`, `functional-documentation`, `requirements-documentation`,
`create-user-story-documents`) — which is exactly why the BA said *"Did I not tell you that I document
the user stories?"*

**52 activity nodes from three people.** This is **WC-13 materialising** and it should no longer be
described as untested — it is confirmed and High.

Two distinct sub-causes, and they need different fixes:

- **Within one answer.** `act.code-and-function-quality-review` and `act.review-checks` were both
  minted from the *same* answer, same timestamp `2026-08-06T01:48:04.316Z`, and the second dragged in
  an invented `role.deployment-approver` to perform it. *"Prefer FEWER, well-formed nodes"*
  (`extractor.py#L35`) is not a strong enough instruction.
- **Across answers.** `similarity_ceiling = 0.86` is high for near-synonyms, and `_card_brief`
  (`resolve.py#L45`) shows the adjudicator only `name (aka aliases): description` — never the
  performing role or the node's edges, which is the signal that would actually separate *Review
  Checks* from *Code and Function Quality Review*.

⚠ **The cleanup is not surgery.** `answer-log.schema.json` says the log is *"Immutable, append-only,
the SOURCE OF TRUTH. The graph is re-derivable from these logs"* — and it genuinely is: all six logs
exist (five under `participants/`, plus the retired `fe69`'s under `_archive/`). So P17b is *fix the
extractor and resolver, then rebuild*, not a merge pass over 52 nodes. See §5.

### Finding 5 — nothing records what a person denied, so denials do not stick ⏳ P17c

*"SA does not do anything in quality assurance."* · *"No, I do not demo a solution to the client."* ·
*"the project timeline is not my job"* (three times).

None of it is written anywhere. Two layers:

- The extractor prompt has **no negation rule**, so *"I don't do X"* carries no positive assertion and
  is silently dropped. The wrong edge survives — `role.solution-architect PERFORMS act.give-demo` is
  still in the graph after he denied it, which is why that thread existed at all.
- The live runner **does** classify `dont_know` (`prompts.ts#L97`) and then throws it away.
  `answer-log.schema.json` has no field for it, so the brain never learns.

### Finding 6 — role-inherited threads name a role the person does not hold ✅ FIXED

The SA's last question before he quit was *"Another **Account Management Specialist** described 'Send
Proposal'…"*. `_role_threads` had scoped correctly to his declared role (`act.send-proposal` is
`PERFORMS`ed by `role.solution-architect` — itself an extraction error, Finding 4's territory), but the
copy used `t.role_name`, which is `Gap._attributed_role`: the *first* role performing the node. On a
node two roles perform, that is routinely the other one.

### Finding 7 — the model is never told what it already knows about this person ⏳ P17c

`briefDigest()` emits the persona summary and the open threads. There is **no** "already established"
block, so the interviewer cannot acknowledge prior knowledge, cannot notice that a question overlaps
something already recorded, and cannot say *"you told me X — has that changed?"* Hence *"I had replied
in my previous sessions"*.

### Not a finding — the live model

`deepseek-v4-flash` at `temperature: 0.3` behaved well in both transcripts: it acknowledged
corrections (*"Got it — QA is a separate team"*), apologised correctly (*"I apologize, Kishor — I
misunderstood"*), rephrased on request, and dropped the demo question the moment it was told the BA
owns demos. Everything it did wrong follows from the brief.

**One genuine model failure:** it asked the BA about the Delivery Specialist hat a third time, after
two denials — the brief's *"You hold both…"* assertion outweighed the transcript. P17a deletes that
thread at source and adds two prompt rules as the second line of defence (§4).

**If money is to be spent on a model, spend it on extraction, not the live turn.** Extraction is the
weak link (Findings 4 and 5), it already runs on the pro tier, and its real deficit is *context* —
`Extractor.extract(answer)` receives one answer's text and nothing else: not the question, not the
thread, not who is speaking. That is WC-04, whose *"Does not affect interview quality"* assessment is
now demonstrably wrong.

---

## 3. Why the fixes are staged

Not risk — **attribution**. Every P17a fix is verifiable by regenerating a brief and reading it; no
live session and no deploy is needed. P17c cannot be checked that way, because it changes what the
*runner* does with a session. Judging all seven at once from one interview would tell you only whether
the total is better.

| Stage | Findings | Surface | How you check it |
|---|---|---|---|
| **P17a** ✅ | 1, 2, 3, 6 | brain + 3 prompt strings | regenerate a brief, read it |
| **P17b** 📋 | 4 | brain prompts + config + graph rebuild | activity node count drops; the four code-review nodes become one |
| **P17c** 📋 | 5, 7 | **2 contracts + PWA deploy** | a live session |

---

## 4. P17a — as built (06 Aug 2026)

### 4.1 `_persona_summary` names declared roles only (ADR #37)

```python
declared = sorted(
    snap.nodes[rid].canonical_name for rid in (role_ids or ()) if rid in snap.nodes
) or sorted(self._declared.get(persona_id, ()))
...
roles = declared
```

Resolved graph names first so the phrasing matches the graph's vocabulary; raw declared titles as the
fallback for a person whose Role node does not exist yet.

**Nothing declared means the sentence drops its `As …,` prefix entirely** rather than guessing. That
case is a pre-P15a device or someone who skipped the chips; "we don't know your role" is honest and a
guess is actively harmful. `_persona_summary` capitalises the remainder so the sentence still reads.

### 4.2 The dual-hat branch requires a declaration on **both** sides (ADR #38)

```python
declared_owners = self._declared_owners(snap)
giver_personas = declared_owners.get(giver_role_id, set()) if giver_role_id else set()
recv_personas  = declared_owners.get(role_id, set())
...
dual_hat = persona in giver_personas and persona in recv_personas
```

**Routing is untouched** — the loop still iterates `_role_owner_personas(role_id, snap)`, so everyone
who would have received a thread still receives one. Only the *wording* narrows, and a non-declarer now
gets the standard `handoff_confirm` copy, which is answerable (*"do you receive it?"*) instead of
insulting. Half a declaration is not a declaration: declaring only the receiving role is not two hats.

### 4.3 Role-inherited threads name the role that made you inherit them (ADR #37)

`_role_threads` now records which declared role dragged each node in, and stamps it onto the thread,
overriding `Gap._attributed_role`:

```python
inheriting: dict[str, tuple[str, str | None]] = {}
for role_id in sorted(role_ids):
    ...
for t in threads:
    t.role_id, t.role_name = inheriting[t.node_id]
```

Both the opener and `_ROLE_WHY` read off `role_name`, so both become coherent at once.

### 4.4 Threads are clustered by node (ADR #39)

New `_cluster(threads, limit, per_node=_CLUSTER_MAX)`. Input must already be priority-sorted: that
order decides which node *opens* next, so the highest-priority thread still leads the brief and P9's
cross-persona threads still lead it overall. Applied to all three thread sources (own, role-inherited,
orphan) so the shape is uniform.

`_CLUSTER_MAX = 3` is small on purpose. It keeps a cluster a short walk through an activity rather than
an interrogation of one, **and it bounds the damage when the clustered node turns out not to be the
person's work at all** — the failure mode clustering introduces, and the reason §4.5's second prompt
rule exists.

`reserve_threads` is now computed by difference, because the carried set is no longer a prefix of the
ranked list. Getting that wrong would silently lose gaps from the operator's view of what is open, so
it has its own test.

### 4.5 Two prompt rules as the second line of defence

The brain-side fixes stop a bad thread being *written*. These handle a brief that is wrong anyway,
which eventually it always will be:

- **A denial is final** — *"accept it the first time, drop EVERY remaining question about that piece of
  work, and never raise it, or the role it implies, again this session. The brief can be wrong about
  what someone does; the person cannot."*
- **The identity block is the only authority on roles** — *"Never tell someone they hold a role it does
  not list, however strongly a thread implies it."*

`briefDigest()` also explains the new grouping, which is what turns the clustered ordering into a
conversation rather than a list the model machine-guns.

### 4.6 Tests

Three existing tests encoded the old behaviour and were **updated, not deleted**:

| Test | Was | Now |
|---|---|---|
| `test_self_handoff_is_routed_as_a_hat_switch_not_a_stranger` | dual hat from contribution | fixture declares both roles (`_DUAL_HAT_DECLARED`) |
| `test_self_handoff_copy_never_says_another_team` | same | same |
| `test_persona_summary_mentions_role_and_activity` | role read from subgraph | fixture declares the role |

`test_role_scoping.py::test_declaring_both_sides_of_a_handoff_makes_it_a_dual_hat_question` already
used a declaration and passed untouched — that is the case that *should* survive, and it did.

New: `test_contributing_to_both_roles_is_not_enough_to_claim_two_hats`,
`test_declaring_only_one_of_the_two_roles_is_still_not_two_hats`,
`test_persona_summary_never_claims_a_role_they_only_mentioned`,
`test_persona_summary_stays_silent_about_role_when_nothing_was_declared`,
`test_an_inherited_thread_names_the_role_that_made_you_inherit_it`, and four clustering tests
including `test_the_highest_priority_thread_still_leads_the_brief` (clustering must never demote a
conflict) and `test_threads_dropped_by_clustering_land_in_reserve`.

**244 brain tests, 75 PWA tests, ruff and tsc clean.**

### 4.7 Verified against the live graph

`cli plan` for both testers, before → after:

| | Before | After |
|---|---|---|
| SA summary | "As Business Analysis Specialist, Development Lead, Quality Assurance Head, Solution Architect, Technical Specialist…" | **"As Solution Architect…"** |
| BA summary | "As Account Management Specialist, …, Customer, Delivery Specialist, …" | **"As Business Analysis Specialist…"** |
| SA thread 1 | "You wear both hats here — when you switch from your Quality Assurance Head hat…" | **"It sounds like Quality Assurance Head hands 'Assign Feedback to Developers' over to you — do you receive it…"** |
| SA `next_handoff` threads | 11 of 12 | **2 of 12** |
| SA distinct fields | 1 | **4** (trigger, cadence, next_handoff, output) |
| SA role-thread copy | "Another **Account Management Specialist** described…" | **"Another Solution Architect described…"** |
| Shape | 12 activities × 1 field | **4 activities × 2–3 fields** |

---

## 5. P17b — dedup and rebuild

> ⚠ **The original plan for this section was wrong, and is kept below so the reasoning is visible.**
> It proposed lowering `similarity_ceiling` from 0.86 to ~0.78–0.80. Measuring the graph before
> touching it showed that would have **destroyed real process distinctions**. The measurement is
> §5.1; the corrected plan is §5.2.

### 5.1 The measurement that reversed the plan (06 Aug 2026)

Pairwise cosine over every Activity card in the live graph, using the real embedder
(`FastEmbedEmbedder`, `BAAI/bge-small-en-v1.5`, 384-dim — **not** the lexical fallback), on the same
text `ingest._card_text` stores:

| cosine | pair | verdict |
|---|---|---|
| **0.874** | `create-project-timeline` (**pre-sales**) ↔ `manage-project-timelines` (**project-delivery**) | **different work** |
| 0.862 | `code-review` ↔ `review-checks` | same habit, twice |
| 0.854 | `effort-estimation` ↔ `provide-effort-estimation` | same |
| 0.852 | `documentation` ↔ `functional-documentation` | same |
| **0.808** | `give-demo` (**discovery**) ↔ `give-uat-demos` (**uat**) | **different work** |
| 0.801 | `code-review` ↔ `code-review-and-team-oversight` | same |
| **0.785** | `provide-effort-estimation` (Delivery Specialist) ↔ `approve-effort-estimation` (**Customer**) | **different work** |
| 0.692–0.78 | the rest of the discovery / documentation families | same |

Controls — pairs that are obviously unrelated (`code-review` ↔ `perform-deployment`,
`send-proposal` ↔ `qa-testing`, …) — scored **0.558–0.687**.

**The conclusion is structural, not a tuning detail.** True duplicates occupy 0.69–0.87 and
genuinely-different work occupies 0.78–0.87. **They are the same band.** No threshold separates
them, and the highest-scoring pair in the entire graph is one that must *not* merge. A ceiling at
0.79 would have merged three distinct activities; the ceiling at **0.86 was already a latent wrong
merge** on the timeline pair, overriding a correct LLM verdict.

What *does* separate them is visible in the table: **the lifecycle stage and the performing role.**
Neither was ever shown to the adjudicator, whose entire view was
`- id=… type=… name="…" (aka …): description`.

### 5.2 As built

1. **The adjudicator now sees who performs it and which stage it is in** (ADR #40).
   `Resolver.node_context()` renders `[performed by X; in stage Y]` for every retrieved card, and
   `ingest._candidate_context()` does the same for the *proposed* node by reading its sibling refs
   out of the same extraction batch — the candidate has no edges in the graph yet, and giving the
   model context for every existing card but none for the thing it is judging is worse than
   symmetric ignorance, because "no stage" then reads as a difference. `_ADJ_SYSTEM` gained the rule
   that same-performer-same-stage means *same* and different-stage-or-role means *new*.
2. **`similarity_ceiling` 0.86 → 0.90** (ADR #41) — **raised, not lowered.** It reverts to what it
   should always have been: a backstop for near-identical restatements, not a mechanism that
   overrules considered judgement. Nothing in the current graph reaches 0.90.
3. **Extractor anti-splitting rule.** *"ONE ANSWER USUALLY DESCRIBES ONE ACTIVITY"*, with the
   explicit split test — different stage, different role, or separated in time — and the same rule
   for Roles, because the failing answer minted `act.review-checks` **and** a
   `role.deployment-approver` out of *"I just give them a go-ahead that fine, deploy it."*
4. **`cli rebuild-graph`** (new). Deletes the graph, vector index and review queues, re-seeds the
   role registry, then replays **every** answer — live and archived — in global timestamp order.
   - **`reset-engagement` is the wrong tool** and this is not it: that command deletes participant
     folders and `_retired.json`, i.e. the very logs a rebuild reads. `rebuild-graph` touches the
     graph and local derived state **only**; profiles, logs, briefs and archives are untouched.
     `ingested_logs` is deliberately left alone — after a full replay it is still true.
   - **Archived folders are included, and that is load-bearing.** Retirement archives rather than
     deletes precisely so the knowledge survives (ADR #30); a rebuild that walked only
     `participants/` would delete a departed colleague's whole contribution on its first run.
   - **Sorted by timestamp across everybody**, because merge order is not neutral — a merge appends
     provenance but keeps the *first* contributor's canonical name and description.
   - **Roles are seeded before replay**, the same ordering `seed-roles` documents for a first round:
     answers ingested first mint role nodes under whatever name the extractor picked, and the
     aliases then arrive too late to stop the fork (ADR #33).

### 5.3 What the rebuild actually produced (06 Aug 2026)

Replayed all 52 answers from 6 logs (5 live + 1 archived). ~40 minutes.

| type | before | after | |
|---|---|---|---|
| Activity | 62 | **49** | −21% |
| Role | 14 | **11** | the invented `deployment-approver` / `development-lead` are gone |
| Artifact | 16 | 13 | |
| Stage | 12 | 13 | |
| **Objective** | 4 | **0** | ⚠ **regression — see §5.4** |
| **ApprovalPoint** | 1 | **0** | ⚠ same cause |

**What worked.**
- Invented roles stopped being minted. The registry roles plus `Customer` are all that remain.
- **Every activity now has a performing role and a lifecycle stage** — the probe finds *zero*
  unplaced pairs, where the old graph was full of them. That is the input ADR #40 needs, so
  resolution gets better from here rather than staying where it is.
- The ceiling decision is now validated on fresh data, not just the old graph:

  | ceiling | merges duplicates | **wrongly merges** |
  |---|---|---|
  | **0.90** (shipped) | 0 | **0** |
  | 0.86 (previous) | 1 | **4** ← was already unsafe |
  | 0.78 (originally planned) | 8 | **38** |

**What only partly worked.** The four code-review nodes became three, not one; the user-story family
still carries `create-user-story-documents` vs `user-story-creation` and `submit-user-story-document`
vs `submit-final-user-story-document`. These are *cross-answer* forks — the adjudicator's job, not
the extractor's — so the remaining lever is retrieval quality, not the prompt. Residual count is a
handful, against dozens before.

### 5.4 Regression: the anti-splitting rule suppressed other node types

**Objectives went 4 → 0 and ApprovalPoints 1 → 0.** The lost content was real: *"Team Work Quality
Verified Before Project Completion"*, *"Understand Complete Process"*, *"Document Problem Statements
Well"*, *"Get Technical Understanding"*.

Cause: §5.2's rule was placed immediately after *"Prefer FEWER, well-formed nodes over many noisy
ones"* — two emphatic minimise-instructions back to back, near the top of the list — and it is long
and forceful. The model generalised it from "don't split one activity into three" to "emit less",
and the node types that lost out were the secondary ones.

This matters more than the duplicate count it was fixing: **ADR #32 makes Objectives the finding the
engagement sells**, and the extractor prompt is the single place that can silently delete them.

**Fixed** by scoping the rule explicitly — *"THIS RULE IS ABOUT NEAR-DUPLICATE ACTIVITIES AND ROLES,
NOTHING ELSE… a different node TYPE is not a duplicate"* — and pinned by
`test_anti_splitting_rule_is_scoped_and_cannot_suppress_other_node_types`.

⚠ **The fix is in the prompt, not in the data.** Those four Objectives stay missing until the next
rebuild, because the answers that carried them are already marked ingested.

*Lesson: a prompt rule is not a local edit. Adding an emphatic instruction changes the model's
behaviour on everything the prompt governs, not just the case that motivated it — so the acceptance
check has to count what you were **not** trying to change. The node-type table caught this; a check
that only looked at the activity count would have called it a clean win.*

## 6. P17c — memory and denials (PLAN ONLY)

Both items change a contract, so PWA and brain ship together, and a phone must be **fully reopened**
after deploy (cached service worker — `PROMPTS.md`).

**Denial capture (Finding 5).**
- `answer-log.schema.json`: add an optional `classification` property (`clear|vague|tangent|dont_know`).
  Optional and back-compatible, so a device on old cached JS still writes a valid log — the same
  discipline `role_titles` → `role_title` already uses.
- `runner.respond()` writes `decision.classification` into the entry (~2 lines).
- Brain: `dont_know` on a thread with a known node/field records a per-persona declined entry; the
  Planner filters those threads out for that persona. **Per persona, never global** — one BA not doing
  something is not evidence that no BA does.
- Extractor: a negation rule. *"When the answer denies doing something, do not emit PERFORMS for the
  speaker; if they name who does own it, emit that Role and the PERFORMS edge to them."*

**Known facts (Finding 7).**
- `session-brief.schema.json`: add `known_facts: string[]` (additive; the file is
  `additionalProperties: false`, so it must be declared).
- Planner generates 8–12 deterministic one-liners from the persona's subgraph — *"You create User Story
  Documents → hand to Solution Architect"*. Deterministic, not LLM-written: this is a memory, and a
  hallucinated memory is worse than none.
- `briefDigest()` renders a `=== WHAT WE ALREADY KNOW ===` block; `SYSTEM_PROMPT` gains a rule that
  nothing listed there may be asked cold — to confirm it, state what you have and ask what changed.

---

## 7. Out of scope, deliberately

- **Rewriting the ranking weights** (`_FIELD_IMPACT`). Clustering fixes the *shape* of the brief
  without touching the ranking contract; changing both at once would make the effect unattributable.
- **The probe budget** (`DEFAULT_PROBE_BUDGET = 1`, `isStageThread` matching only `.stg.`). It
  contributes to the machine-gun rhythm, but clustering now supplies depth *across* threads, so raising
  it would lengthen sessions for an effect we may already have. Re-measure after the next live session;
  this is the first knob to reach for if it still feels rushed.
- **`"0 fully covered, N with open questions"`** in `persona_summary`. With eight completeness fields
  per activity almost nothing is ever "fully covered", so this reads as a standing accusation. Cosmetic,
  real, and not P17a's business.
- **Brief length.** A brief can carry `max_threads` + `role_max` + `orphan_max` = 12 threads, and both
  testers quit before the end. That is a config question (`config.py`), not a code one — and it is the
  wrong knob to turn before P17b, since half the threads are currently about duplicate nodes.

---

## 8. Risks

| id | Risk | Mitigation |
|---|---|---|
| **R1** | Clustering amplifies a wrong node — three questions about an activity the person doesn't own, instead of one. | `_CLUSTER_MAX = 3` bounds it; §4.5's denial rule tells the model to drop the whole group on the first "not mine". **P17c is the real fix** — it makes the denial persist. |
| **R2** | A person who genuinely holds two roles but ticked only one now gets the stranger copy for their own handoff. | Strictly better than the inverse (asserting a role they deny). `cli coverage` already surfaces declared-but-silent roles; the fix is re-onboarding, which is cheap. |
| **R3** | `reserve_threads` is now a set difference, not a slice — a bug here silently hides open gaps from the operator. | `test_threads_dropped_by_clustering_land_in_reserve` asserts disjointness and that reserve is the larger set. |
| **R4** | P17b's rebuild re-runs extraction over settled text and could produce a *different* graph, not just a deduplicated one. | The logs are immutable and `_graph/` is in git — diff the before/after node counts per type and eyeball the activity list before committing. |
