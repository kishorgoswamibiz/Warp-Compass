# Phase 16 — Hat fidelity: attributing work when one person wears several roles

> **Status:** **PLAN ONLY — DO NOT BUILD YET.** Written 04 Aug 2026 from the owner's question in
> session `opus-p15c`. The owner has explicitly asked for this to be documented so they can think it
> through before any code is written. **Nothing in this document has been implemented.**
>
> **Read §3 before §4.** The question looks like one problem and is actually four separable ones with
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

### Finding 5 — what is *not* broken, and must not be "fixed"

**Questions route by persona, not by role, and that is correct.**
[`planner.py:170`](../../brain/src/warp_compass_brain/planner.py#L170) scopes gaps to nodes whose
provenance carries that `said_by`. A dual-hat person therefore receives the **union** of both hats'
questions in one brief.

So the direct answer to the owner's last question — *"will any Technical Specialist question be asked
of the dual-role person?"* — is **yes, and it should be.** It is one human, on one device, in one
conversation, who can answer for both hats. There is no "questions that fit both" category and this
phase should not invent one. Splitting a person's brief by hat would mean two sessions for one human
and a worse interview.

**The hat matters for the artefacts, not for the asking:** which SOP the work appears under, which
role owns a stage, and what altitude the person carries. That is the whole scope of this phase.

---

## 3. The question decomposes into four separable problems

Deciding these as one bundle is how this phase gets over-built. They have different best answers, and
**they can ship independently**.

| # | Problem | Who is affected | Blast radius if wrong |
|---|---|---|---|
| **P1** | **Routing.** Who owns `role.technical-specialist` so a colleague's handoff reaches them? | everyone downstream of a multi-hat person | **High** — a thread loops forever and a real person is never asked (§2 Finding 3) |
| **P2** | **Attribution.** Which hat performed this activity? | the deliverable's SOP sections | Medium — work lands under the wrong role heading |
| **P3** | **Altitude.** What level is a person with two hats at different depths? | misalignment classification | Medium–High — a finding is lost or invented |
| **P4** | **Presentation.** How does the SOP show work done under two hats? | readability of the deliverable | Low — cosmetic |

**Recommended order: P1 → P3 → P2 → P4.** P1 is the actual bug, is cheap, and needs no LLM judgement
at all. P2 is the one everybody reaches for first and is the *least* certain.

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
| **P16a** | `role_titles` into the brain + declared-role ownership (**P1-A**) | Fixes the live bug. Deterministic, no LLM, no field data needed to decide. |
| **P16b** | `SPEAKER` block in the extractor + multi-hat attribution fallback (**P2-A + P2-C**) | Reuses P16a's plumbing. Then **measure** on real data. |
| **P16c** | Per-hat altitude with min-depth fallback (**P3-B/A**) + the spanning-levels finding (**P3-C**) | Needs P16b's attribution to be worth doing. |
| **P16d** | SOP presentation for multi-hat people (**P4-A**) | Cosmetic; last. |

**P16a alone is a defensible stopping point.** It fixes the routing bug. Everything after it improves
fidelity, and the owner may reasonably want a round of real data before committing to any of it.

---

## 6. Files (anticipated)

**Changed**
- `brain/.../cycle.py` — read `role_titles` from the profile, pass to `ingest_answer`.
- `brain/.../ingest.py` — accept + forward `speaker_roles`.
- `brain/.../extractor.py` — the `SPEAKER` block (P16b).
- `brain/.../crosspersona.py` — `_role_owner_personas` accepts declared owners (P16a).
- `brain/.../lifecycle.py` — expose `role_titles`, not just the joined `role_title`.
- `brain/.../alignment.py` — per-hat altitude + the spanning-levels finding (P16c).
- `brain/.../docgen/traverse.py` — multi-hat SOP handling (P16d).
- `brain/.../coverage.py` — distinguish "declared owner, no activities yet" from "no owner".
- `PROMPTS.md` §6, `docs/DATA-CONTRACTS.md`, `docs/DECISIONS.md`, `PROGRESS.md`.

**Note:** `profile.json` already carries `role_titles` (P15a) — **no contract change is needed for
P16a.** ⚠ But it only gets there once the owner **redeploys the Apps Script Web App** (still the P11
build, see PROGRESS Blockers). Until then live profiles carry no `role_titles`, so P16a must fall back
to splitting the joined `role_title` on `" / "` — which P15a deliberately kept writable for exactly
this kind of reason.

---

## 7. Test plan

- **The forever-loop regression (the point of P16a).** A colleague hands work to the Technical
  Specialist; a dual-hat persona declared that role but has no `PERFORMS` edge under it. Assert the
  thread routes to **them** as `handoff_confirm`, **not** back to the colleague as `handoff_trace`.
- **Declaring is enough, mentioning still isn't.** A persona who merely *mentions* a role does not
  become its owner; a persona who *declared* it does.
- **Pre-redeploy fallback.** A profile with only the joined `role_title` still yields both roles.
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
2. `cli coverage` distinguishes **"declared owner, no work described yet"** from **"nobody owns
   this"** — today they look identical, and only the second is an invite-list entry.
3. An activity described by a dual-hat person is attributed to a hat, or honestly to both.
4. A dual-hat person's altitude is defined, documented, and degrades gracefully when unknown.
5. Suites green; `PROGRESS.md`, `PROMPTS.md`, `DECISIONS.md` updated.

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

---

## 11. Open for the owner

1. **P3 — what altitude does a dual-hat person carry?** Per-hat (most correct, depends on
   attribution), or their most senior hat (simple, one number)? This is a judgement about what
   authority means in the owner's org, not a technical call.
2. **Is P16a enough for now?** It fixes the bug. P16b–d improve fidelity and are cheaper to decide
   after one real round with multi-hat people in it.
3. **Would you rather spend interview turns on certainty?** P2-B ("was that as the BA or the TS?") is
   the accurate option and costs conversation. The owner's P15 ruling was that the interview must feel
   spoken, so my read is no — but it is the owner's trade to make.
4. **Should "this person spans two levels of the org" be a reported finding?** It is interesting for a
   consulting deliverable and trivial to compute once altitude is per-hat.
