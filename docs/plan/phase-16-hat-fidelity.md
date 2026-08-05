# Phase 16 — Hat fidelity: attributing work when one person wears several roles

> **Status:** **P16a + P16a-bis BUILDING (05 Aug 2026).** P16b–d remain PLAN ONLY.
> Originally written 04 Aug 2026 from the owner's question in session `opus-p15c`.
>
> **Revised 05 Aug 2026** after the owner asked for the engagement to be **role-scoped rather than
> person-scoped**, ahead of testing with several people. That request exposed a **fifth** problem
> this plan had explicitly ruled out of scope — see **§2 Finding 5**, which was **wrong**, and the
> new **P1-bis** in §3. The correction is the difference between a plan that works for one dual-hat
> person and one that works for three Business Analysts.
>
> **Read §3 before §4.** The question looks like one problem and is actually five separable ones with
> different best answers. Deciding them as a bundle is how this gets over-built.
>
> Depends on: P15a (multi-select `role_titles`), P15b (`Role.reports_to` scoring), P15c
> (`alignment.derive_altitudes`, `_persona_role`). All shipped.

---

## 1. The question, as the owner asked it

> *"If someone is a Business Analysis Specialist and they also work as a Technical Specialist — if
> some other person in the organization has talked about that Technical Specialist doing these
> things, or if that person who is a BA plus Technical Specialist says 'I do documentation' and later
> 'I do development', how is the brain going to understand which questions to ask the BA, which to
> ask the Technical Specialist, and which are more fit for someone who does both? Or will any question
> related to the Technical Specialist be asked to the person who has a dual role?"*

P15a made multi-role identity **declarable**. It did not make the resulting work **attributable**.
This phase is about the second half.

---

## 2. What's broken today — verified in code, 04 Aug 2026

### Finding 1 — the extractor has no idea who is speaking

[`Extractor.extract(answer)`](../../brain/src/warp_compass_brain/extractor.py#L133) receives **one
answer's text and nothing else**: no persona id, no declared roles, no session context.
[`_user_prompt()`](../../brain/src/warp_compass_brain/extractor.py#L95) assembles allowed node/edge
types, category codes, the `KNOWN ROLES` registry block, and the answer. That is all.

Consequence: an answer like *"I write the BRD"* can only produce a `PERFORMS` edge if **the answer
itself names a role**. For a single-hat person the identity seed makes this recoverable in practice.
For a dual-hat person there is **no signal at all** telling the extractor which of their two hats did
the work — and the registry block actively offers it ten roles to choose from, none of them marked as
*this speaker's*.

### Finding 2 — `role_titles` never reaches the brain's extraction path

`role_titles` exists in the PWA (`participant.ts`), the sync Function (`_sync.ts`), Apps Script
(`Code.gs`) and `profile.json`. On the brain side, only
[`lifecycle.py:95`](../../brain/src/warp_compass_brain/lifecycle.py#L95) reads the joined
`role_title`, **for display only** (`list-participants`, `docgen` persona names). No code path feeds a
declared role into extraction.

The plumbing distance is short, which matters for costing this: `cycle.py` **already** reads the
profile at [`cycle.py:149`](../../brain/src/warp_compass_brain/cycle.py#L149) and calls
`ingest_answer` at [`cycle.py:197`](../../brain/src/warp_compass_brain/cycle.py#L197). The value is
sitting in a local variable two calls above the place it's needed.

### Finding 3 — ownership is inferred from activities, and a *declaration* is ignored

[`_role_owner_personas`](../../brain/src/warp_compass_brain/crosspersona.py#L349) defines "persona X
owns role R" as *X contributed the activities R performs*, with the docstring rationale: **"merely
mentioning a role is not owning it."** That rationale is correct for a role someone *mentions* — and
it silently discards the strongest possible evidence, which is a person **declaring at onboarding
that they hold the role**. P15a introduced that declaration and nothing consumes it.

**This is the finding that actually bites**, and it is the mechanism behind the owner's scenario:

1. A colleague says *"I hand the build over to the Technical Specialist."*
2. That resolves onto `role.technical-specialist` (P15a's aliases work — this part is fine).
3. Our dual-hat person genuinely **is** the Technical Specialist, but their dev work never got a
   `PERFORMS` edge under that hat (Finding 1), so the role has **no owner**.
4. `_handoff_state` returns `route_discoverer`
   ([`crosspersona.py`](../../brain/src/warp_compass_brain/crosspersona.py)), and the **colleague** is
   asked *"who would know how the Technical Specialist handles it?"* — **forever**.

That is precisely the failure P15a §4.3 traced and fixed for *naming*, reappearing through *hat
attribution*. The alias table is not enough on its own.

### Finding 4 — every "which role?" helper picks exactly one, and there are four of them

| Helper | Used for | Effect of picking wrong |
|---|---|---|
| [`completeness._owning_role`](../../brain/src/warp_compass_brain/completeness.py#L619) | which role a gap is reported against | cosmetic (display) |
| [`crosspersona._owning_role`](../../brain/src/warp_compass_brain/crosspersona.py#L341) | giver attribution on a handoff | wrong role named in the question |
| [`traverse._owning_role`](../../brain/src/warp_compass_brain/docgen/traverse.py#L302) | which SOP an activity appears under | **the deliverable is wrong** |
| [`alignment._persona_role`](../../brain/src/warp_compass_brain/alignment.py#L289) | the persona's altitude | **a misalignment is mis-classified or lost** |

This is plan-15 risk **R5**, and P15c raised its stakes: it now decides whether a divergence is a
billable finding or a defect to reconcile away. P15c hardened `_persona_role` (sole-contributor
weighting) but a genuinely dual-hat person still collapses to **one** role.

### Finding 5 — persona-scoped routing is right for one person and wrong for a role

> ⚠ **This finding was originally written as "what is *not* broken, and must not be fixed". That was
> wrong, and the error is worth keeping visible rather than quietly editing away.** The reasoning
> below is sound for the case it was tested against — **one** person wearing **two** hats — and it
> silently assumed that case was the general one. It is not. Revised 05 Aug 2026.

**What the original finding got right, and it still holds.**
[`planner.py:170`](../../brain/src/warp_compass_brain/planner.py#L170) scopes gaps to nodes whose
provenance carries that `said_by`. A dual-hat person therefore receives the **union** of both hats'
questions in one brief.

So the direct answer to the owner's original question — *"will any Technical Specialist question be
asked of the dual-role person?"* — is **yes, and it should be.** It is one human, on one device, in
one conversation, who can answer for both hats. There is no "questions that fit both" category and
this phase should not invent one. Splitting a person's brief by hat would mean two sessions for one
human and a worse interview.

**What it missed: the inverse direction.** Persona scoping answers *"which of MY nodes have gaps?"*
It has no answer to *"which of MY ROLE's nodes have gaps?"* — and with more than one holder of a
role, those are different questions:

1. BA#1 describes *"I write the user story document"* but never says how it gets reviewed → a
   `MISSING_FIELD` gap on that node.
2. BA#2 joins. Their brief is scoped to nodes **BA#2** has provenance on.
3. BA#2 is never asked about the user-story-document gap — **despite being the single best-placed
   person in the engagement to answer it.**

The owner's framing, which is the correct one: *if three BAs each describe a quarter of the role, the
remaining quarter is one gap on shared nodes, and it should fire at all three.* That works because
gaps are recomputed from the graph every round
([`CompletenessEngine.assess`](../../brain/src/warp_compass_brain/completeness.py)) — so the instant
**any** holder answers, it closes for **all** of them. No ledger, no dedup pass, no way for it to
loop. The mechanism is already there; only the scoping is missing.

**Why this is not a "role-keyed graph".** The owner's instinct was that the graph should be built on
roles rather than on users. Structurally **it already is**: `NodeType`
([`models.py:18`](../../brain/src/warp_compass_brain/models.py#L18)) has no `Person` member — Role is
a first-class node, activities hang off it, and `add_edge` merges on `(type, from, to)`
([`okf_store.py:179`](../../brain/src/warp_compass_brain/graphstore/okf_store.py#L179)) so several
roles may perform one activity and several people's answers converge on one node. The person survives
in exactly two places: `Provenance.said_by`, and planner scoping. **Only the second is wrong.**

`said_by` must stay person-keyed, and this is load-bearing, not conservatism:

| Depends on knowing *which human* | Breaks if provenance is keyed by role |
|---|---|
| Corroboration → `confirmed` (two distinct personas) | Two BAs agreeing becomes indistinguishable from one BA repeating themselves — facts promote on one say-so, WC-02 made permanent |
| Peer conflict (`resolve.adjudicate` → `CONFLICTING`) | Two BAs who genuinely work differently merge into one role's story; the divergence is deleted, not found |
| Cross-altitude misalignment (ADR #32, P15c) | Needs the speaker *and* their altitude |
| `Provenance.account` (P15c) | Retained precisely so two accounts stay comparable — pointless once both are "the BA" |
| Orphan threads (P13) | Retirement is per-person by definition |

**Conclusion.** Role is a **second** dimension beside the person, not a replacement for one. Person =
who testified; role = what the work belongs to and who else can speak for it. That is P1-bis.

**Everything else in this phase is unchanged: the hat matters for the artefacts, not for the
asking** — which SOP the work appears under, which role owns a stage, what altitude the person
carries.

---

## 3. The question decomposes into five separable problems

Deciding these as one bundle is how this phase gets over-built. They have different best answers, and
**they can ship independently**.

| # | Problem | Who is affected | Blast radius if wrong |
|---|---|---|---|
| **P1** | **Routing in.** Who owns `role.technical-specialist` so a colleague's handoff reaches them? | everyone downstream of a multi-hat person | **High** — a thread loops forever and a real person is never asked (§2 Finding 3) |
| **P1-bis** | **Routing out.** A role has an open gap. Which of its holders gets asked? | every role with **more than one holder** | **High** — the best-placed person is never asked, and a role's coverage stalls at whatever its first holder happened to say (§2 Finding 5) |
| **P2** | **Attribution.** Which hat performed this activity? | the deliverable's SOP sections | Medium — work lands under the wrong role heading |
| **P3** | **Altitude.** What level is a person with two hats at different depths? | misalignment classification | Medium–High — a finding is lost or invented |
| **P4** | **Presentation.** How does the SOP show work done under two hats? | readability of the deliverable | Low — cosmetic |

**Recommended order: P1 + P1-bis → P3 → P2 → P4.** P1 and P1-bis are the actual bugs, are cheap, and
need no LLM judgement at all — they also share all their plumbing, so shipping them apart would mean
building the same wire twice. P2 is the one everybody reaches for first and is the *least* certain.

**P1-bis is the one that gates multi-person testing.** P1 is invisible until a colleague hands work
to a multi-hat person; P1-bis bites the moment two people hold the same role, which is the *first*
thing that happens when the app goes to a team.

---

## 4. Options, per problem

### P1 — Routing: who owns a declared role

> **Recommendation: option A. High confidence.** This is the one part of the phase I would build
> without further field data.

| Option | How | Trade-off |
|---|---|---|
| **A. A declared role is owned, full stop** ⭐ | Plumb `role_titles` from `profile.json` → `cycle.py` → the cross-persona engine. `_role_owner_personas(R)` returns activity-contributors **∪** personas who *declared* R. | Deterministic, no LLM, no guessing. Kills the forever-loop outright. Cost: the brain must know declared roles — the same plumbing P2 needs anyway. **Risk:** someone who ticks a chip they don't really hold becomes the routing target for it. Mitigated by `cli coverage` making an owner-without-activities visible. |
| B. Fix attribution first and let ownership follow | Do P2, hope `PERFORMS` edges appear under both hats | Leaves the bug live until extraction is reliable, and it will never be 100%. Puts a deterministic problem behind a probabilistic one. |
| C. Fall back to `route_discoverer` but cap the retries | Stop asking after N rounds | Hides the symptom, still never reaches the right person. |

**Note on §2 Finding 3's rationale.** Option A does not contradict "mentioning a role is not owning
it" — it *sharpens* it. Mentioning stays insufficient; **declaring** becomes sufficient. Worth an ADR
because it changes a definition that three modules rely on.

### P1-bis — Routing out: which holder of a role gets the role's open gaps

> **Recommendation: A + C together. High confidence.** Same plumbing as P1-A, and the owner has
> already ruled on the behaviour: *"if it is not explained by any other same-role holder then it
> should be fired to everyone in that role."*

| Option | How | Trade-off |
|---|---|---|
| **A. Inherit the role's gaps** ⭐ | `planner.plan` adds gaps on nodes performed by a role the persona **declared**, on top of their own subgraph. Ranked *below* their own work, capped, with their own opener copy. | Delivers the owner's model exactly. Self-closing: gaps are recomputed each round, so one holder answering clears it for all. Reuses the P13 orphan-thread structural floor verbatim — a role gap can never outrank your own work. |
| B. Round-robin one holder at a time | Offer the gap to a single holder per round | Cleaner brief, but slower to reach `confirmed` and it throws away the corroboration that firing at all holders buys for free. Rejected by the owner. |
| **C. Plan for bus participants, not just contributors** ⭐ | `live_personas()` becomes graph contributors **∪** live participants on the bus | Without this, A does nothing for the person who needs it most. `plan_all` iterates `live_personas()`, derived from provenance `said_by` ([`planner.py:146`](../../brain/src/warp_compass_brain/planner.py#L146)) — so a **newly joined** BA who has said nothing yet is not in the list, gets no brief written, and cold-starts on generic openers while the role's open quarter sits unasked. |
| D. Inherit from roles *inferred* from contribution, not just declared | Union in roles whose activities they have provenance on | Rejected. That is exactly the over-reach WC-R5 fixed: an exec who merely *comments on* a BA activity picks up provenance on it and would start receiving the BA's question set. **Declaration is the key** — it is what the owner ticks on the first screen, and it is unambiguous. |

**Why "fire at all holders" is safe here and would not have been pre-P13.** Three properties, all
already true, make the naive worry (*"won't everyone get spammed with the same question forever?"*)
not apply:

1. gaps are derived fresh from the graph each round, so an answered gap is simply absent next round;
2. a second account on a node is **wanted** — two distinct personas is precisely what promotes a fact
   to `confirmed` (`ingest.py`), and if the two accounts disagree, `resolve.adjudicate` raises a
   `CONFLICTING` peer divergence, which is a finding rather than a defect;
3. the structural rank floor means a role gap never displaces the person's own work.

### P2 — Attribution: which hat did this work

> **Recommendation: A, then measure before considering B. Medium confidence — this is the part that
> needs the owner's field judgement.**

| Option | How | Trade-off |
|---|---|---|
| **A. A `SPEAKER` block in the extractor prompt** ⭐ | Inject the speaker's declared `role_titles` per answer, mirroring the runner's per-turn `WHO YOU'RE TALKING TO` block | Cheap, no interview cost, improves single-role attribution too. Turns an open guess over 10 registry roles into a **closed choice between their 2 hats**. **Right most of the time** ("BRD" → BA, "deploy" → TS) and occasionally wrong, silently. |
| B. Ask the person directly | *"Was that as the BA or as the Technical Specialist?"* | Accurate and unambiguous. Costs interview turns on bookkeeping, and the owner's whole design ruling was that the interview should feel like a conversation, not a form. Consider only if A measurably fails. |
| **C. Attribute to BOTH hats when genuinely ambiguous** | Emit two `PERFORMS` edges | **The ontology already allows this** — `add_edge` merges on `(type, from, to)`, so several roles can perform one activity. Honest about uncertainty rather than forcing a coin-flip. Cost: the activity appears in both SOPs, which may read as duplication. Pairs well with A as its fallback. |
| D. Infer from the lifecycle stage | Use the stage's `OWNS` role | Cute, and wrong often enough to be dangerous: a stage owner is accountable, not necessarily the performer. |

**Measure before escalating to B.** After one real round with A, sample ~20 attributed activities and
count how many landed under the wrong hat. That number is what decides whether spending interview
turns is justified — not intuition.

### P3 — Altitude for a person with two hats at different depths

> **Recommendation: B, with A as the fallback. Needs the owner's ruling** — it depends on what the
> owner believes a dual-hat person's authority actually is.

Concretely: if the BA hat reports to a Delivery Manager (depth 2) and the TS hat reports to a
Technical Lead (depth 3), what altitude does that person carry?

| Option | Behaviour | Trade-off |
|---|---|---|
| A. Highest authority (min depth) | The person is depth 2 | Simple, one number per person. Defensible: for detecting exec-vs-doer divergence what matters is the most senior position they speak from. Over-credits them on work done with the junior hat. |
| **B. Per-hat, chosen by the node** ⭐ | The hat that performs the activity supplies the altitude | Most correct: a divergence about the BRD is judged at BA level. Requires P2 to have attributed the activity — so **it degrades to A when attribution is unknown**, which is a clean fallback rather than a failure. |
| C. Report the spread as a finding | Emit a finding: "this person spans two levels" | Genuinely interesting for a consulting report, and orthogonal — worth doing **as well as** A or B, not instead. |

### P4 — Presentation in the deliverable

> **Recommendation: A. Low stakes, decide during implementation.**

| Option | Behaviour |
|---|---|
| **A. Work appears under each hat that performs it** ⭐ | Falls out of P2-C for free. Add a note when a person holds several roles, so the reader isn't surprised to meet the same name twice. |
| B. One combined SOP per person | Reads naturally for the individual, but the deliverable is a *role* SOP — a successor inheriting the BA hat only needs the BA half. |

---

## 5. Proposed sub-phases

| Sub-phase | Scope | Why this order |
|---|---|---|
| **P16a** | `role_titles` into the brain + declared-role ownership (**P1-A**) | Fixes the live routing-in bug. Deterministic, no LLM, no field data needed to decide. |
| **P16a-bis** | Role-scoped gap inheritance + plan for bus participants (**P1-bis A + C**) | **Ships with P16a**: it needs the identical `profile.json → brain` wire, and it is the half that makes the engagement role-scoped rather than person-scoped. Gates multi-person testing. |
| **P16b** | `SPEAKER` block in the extractor + multi-hat attribution fallback (**P2-A + P2-C**) | Reuses P16a's plumbing. Then **measure** on real data. |
| **P16c** | Per-hat altitude with min-depth fallback (**P3-B/A**) + the spanning-levels finding (**P3-C**) | Needs P16b's attribution to be worth doing. |
| **P16d** | SOP presentation for multi-hat people (**P4-A**) | Cosmetic; last. |

**P16a + P16a-bis together are a defensible stopping point.** They fix both routing bugs and make the
engagement role-scoped. Everything after them improves *fidelity*, and the owner may reasonably want a
round of real multi-person data before committing to any of it.

---

## 6. Files (anticipated)

**Changed — P16a + P16a-bis**
- `brain/.../roles.py` — `resolve_declared_roles(titles, role_cards)`: declared titles → Role **node
  ids**, matched on canonical name or alias. Resolves against the *graph*, not the registry slug,
  because `seed_roles` may have **adopted** an older node under a different id.
- `brain/.../lifecycle.py` — `profile_role_titles()` + `declared_roles(bus)`; expose `role_titles`,
  not just the joined `role_title`.
- `brain/.../crosspersona.py` — `_role_owner_personas` returns contributors **∪** declared holders.
- `brain/.../planner.py` — role-scoped gap inheritance; `live_personas()` covers bus participants.
- `brain/.../coverage.py` — distinguish "declared owner, no activities yet" from "no owner".
- `brain/.../config.py` — `planner_role_max`.
- `brain/.../cli.py` — wire `declared_roles(bus)` into `run-round`, `plan`, `coverage`, `conflicts`.

**Later sub-phases**
- `brain/.../cycle.py` + `ingest.py` + `extractor.py` — the `SPEAKER` block (P16b).
- `brain/.../alignment.py` — per-hat altitude + the spanning-levels finding (P16c).
- `brain/.../docgen/traverse.py` — multi-hat SOP handling (P16d).
- `PROMPTS.md` §6, `docs/DATA-CONTRACTS.md`, `docs/DECISIONS.md`, `PROGRESS.md`, `ISSUES.md`.

**Note:** `profile.json` already carries `role_titles` (P15a) — **no contract change is needed.**
⚠ Verified live on 04 Aug 2026: the deployed Apps Script is the **P13** build, not P11 as previously
recorded — `profile.json` *does* carry `role_title` with P15a's `" / "` join, and the per-folder
`README.md` *is* written (its `| **Role** |` header, singular, is what dates it to P13; P15a emits
`| **Role(s)** |`). So the array is missing but the joined string is not, and **P16a's split-on-`" / "`
fallback covers the live bus today** — which is exactly why P15a kept `role_title` writable. The
redeploy is still required before P16b wants the unjoined array.

---

## 7. Test plan

- **The forever-loop regression (the point of P16a).** A colleague hands work to the Technical
  Specialist; a dual-hat persona declared that role but has no `PERFORMS` edge under it. Assert the
  thread routes to **them** as `handoff_confirm`, **not** back to the colleague as `handoff_trace`.
- **Declaring is enough, mentioning still isn't.** A persona who merely *mentions* a role does not
  become its owner; a persona who *declared* it does.
- **Pre-redeploy fallback.** A profile with only the joined `role_title` still yields both roles.
- **The three-BAs case (the point of P16a-bis).** BA#1 leaves a `MISSING_FIELD` gap on an activity;
  BA#2 and BA#3 declared the same role and never touched that node. Assert the gap appears in **both**
  their briefs — and that once one of them answers, it is in **neither**.
- **A role gap never outranks your own work.** A persona with own gaps *and* inherited gaps gets
  their own first; a persona with only inherited gaps gets them from rank 1.
- **A newly joined holder gets a real brief, not a cold start.** A participant on the bus with zero
  provenance and a declared role receives the role's open gaps.
- **Declared, not inferred.** An exec with provenance on a BA activity (they commented on it) but who
  declared `Chief Executive Officer` does **not** inherit the BA's gaps — the WC-R5 over-reach must
  not come back through this door.
- **Adoption safety.** With a graph whose BA node is `role.business-analyst` (registry says
  `role.business-analysis-specialist`), a declaration of "Business Analysis Specialist" still resolves
  onto the adopted node.
- **Retired holders are not routed to.** A retired persona who declared a role receives nothing.
- **Speaker block (P16b).** The extractor prompt names the speaker's roles and no others; assert it
  still permits roles outside the registry (the ADR #33 open-vocabulary rule must survive).
- **Ambiguous attribution → both hats (P16b).** Two `PERFORMS` edges, and the activity appears in both
  SOPs exactly once each.
- **Per-hat altitude (P16c).** Two hats at depths 2 and 3; a divergence about BA-attributed work is
  judged at 2. With attribution unknown, it falls back to min depth without raising.
- **Spanning-levels finding (P16c).** Fires once per person, not once per hat pair.
- **Regression.** Full suites green (brain 204, pwa 68 at time of writing) + `docgen` re-run.

---

## 8. Done when

1. A colleague's handoff to a role that a multi-hat person **declared** reaches that person, and the
   colleague is never asked *"who would know?"* about it again.
2. **An open gap on a role reaches every live holder of that role, and closes for all of them the
   moment any one answers.** A holder who has contributed nothing yet still gets a real brief.
3. `cli coverage` distinguishes **"declared owner, no work described yet"** from **"nobody owns
   this"** — today they look identical, and only the second is an invite-list entry.
4. An activity described by a dual-hat person is attributed to a hat, or honestly to both. *(P16b)*
5. A dual-hat person's altitude is defined, documented, and degrades gracefully when unknown. *(P16c)*
6. Suites green; `PROGRESS.md`, `ISSUES.md`, `PROMPTS.md`, `DECISIONS.md` updated.

---

## 9. Risks

- **R1 — A declared role becomes a routing magnet.** Tick a chip you don't hold and questions about
  that role arrive at you. Mitigation: `cli coverage` surfaces a declared owner with no activities
  (which is also §8 item 2), so it is visible rather than silent.
- **R2 — The `SPEAKER` block could narrow the extractor too far.** If it reads as *"this person can
  only be these roles"*, we lose the ability to record work they do outside their declared hats. The
  wording must be a **preference**, exactly like `KNOWN ROLES` (ADR #33) — and that rule has already
  been softened once by accident, so it needs its own test.
- **R3 — Attributing to both hats inflates apparent duplication.** P15c's `DUPLICATED_WORK` finding
  looks for two roles doing the same thing. One person wearing two hats would trip it. **P16b must
  exclude same-persona role pairs from that finding**, or the report accuses a person of duplicating
  themselves.
- **R4 — Per-hat altitude multiplies the ways a misalignment can be mis-classified.** More precision
  is more failure modes. The fallback chain must be explicit and tested, not implicit.
- **R5 — This phase is small and easy to over-build.** P16a is ~a day; P16b–d are speculative until
  real multi-hat data exists. The honest sequencing is P16a, then a round, then re-read this document.
- **R6 — Inheritance makes a brief feel like someone else's homework.** A role with a lot of open work
  could hand a new holder a brief that is entirely inherited. That is *correct* for a new joiner —
  they should be asked about their role — but the copy has to say where the question came from, or it
  reads as the app inventing work they never mentioned. Mitigation: inherited threads get their own
  opener copy that names the role and asks for **their** version ("here is how a colleague in your
  role described it — is that how you do it?"), and are capped by `planner_role_max`.
- **R7 — Inheritance depends on dedup holding up at N people.** The three-BAs arithmetic only works if
  three people's quarters land on the **same** nodes. If "user story document" / "US doc" / "the story
  doc" fork into three nodes, each carries its own three-quarters-empty gap set and nothing ever
  closes. The machinery is in place (alias table + `fastembed` verified installed 04 Aug 2026 + LLM
  adjudicator) but has **never run at multi-person scale**. First multi-person round: check the
  activity node count against expectation before trusting anything else in this phase.
- **R8 — A declared role with no graph node inherits nothing, silently.** If someone declares a role
  that `seed_roles` never seeded and nobody has mentioned, there is no Role node to hang inheritance
  off. It is not an error — it is a role nobody has described yet — but it must not look like the
  feature is broken. `cli coverage` is where this has to be visible (§8 item 3).

---

## 10. ADRs to log when this lands

- **#34 — A declared role is owned; a mentioned role is not.** Onboarding's multi-select is treated as
  authoritative evidence of role ownership for routing, alongside activity contribution. *Why:* P15a
  made ownership declarable and nothing consumed it, so a multi-hat person's declared role had no
  owner and handoffs to it looped on the discoverer forever.
- **#35 — Ambiguous hat attribution records BOTH hats rather than guessing one.** *Why:* the ontology
  already permits several `PERFORMS` edges; a coin-flip that silently picks one hat puts work under
  the wrong role in a client-facing SOP, and "both" is the truthful answer when we don't know.
  Requires excluding same-persona pairs from `DUPLICATED_WORK`.
- **#36 — A gap belongs to a role, and is asked of every live holder of it; provenance stays keyed to
  the person.** Briefs inherit gaps on nodes performed by a role the persona *declared*, ranked below
  their own work. *Why:* persona scoping could only ever ask someone about nodes they had already
  spoken about, so a role's open questions never reached its other holders and coverage stalled at
  whatever its first holder happened to say. Firing at every holder is safe because gaps are
  recomputed from the graph each round (one answer closes it for all) and a second account is what
  promotes a fact to `confirmed`. The **person** remains the provenance key — re-keying it to the role
  would delete corroboration counting, peer-conflict detection, cross-altitude misalignment and the
  P15c `account` snapshot in one move (§2 Finding 5).

---

## 11. Open for the owner

1. **P3 — what altitude does a dual-hat person carry?** Per-hat (most correct, depends on
   attribution), or their most senior hat (simple, one number)? This is a judgement about what
   authority means in the owner's org, not a technical call.
2. ~~**Is P16a enough for now?**~~ **Answered 05 Aug 2026: P16a + P16a-bis, then a round.** The owner
   is testing with several people, which makes P1-bis the gating problem and P16b–d cheaper to decide
   once real multi-person data exists.
3. ~~**Fire at one holder or all of them?**~~ **Answered 05 Aug 2026: all holders of the role.**
   Owner's words: *"if it is not explained by any other same-role holder then it should be fired to
   everyone in that role."*
3. **Would you rather spend interview turns on certainty?** P2-B ("was that as the BA or the TS?") is
   the accurate option and costs conversation. The owner's P15 ruling was that the interview must feel
   spoken, so my read is no — but it is the owner's trade to make.
4. **Should "this person spans two levels of the org" be a reported finding?** It is interesting for a
   consulting deliverable and trivial to compute once altitude is per-hat.
