# WC-04 — the extractor cannot see who is speaking

> **Status: RESEARCH ONLY. Nothing here is built.** Written 07 Aug 2026 at the owner's request, to
> preserve a diagnosis rather than lose it between sessions. The owner has **not** decided to build
> this — the open question in §8 is genuinely open, and §7 argues this may not be the next thing.
>
> **Why this doc exists separately from `phase-16-hat-fidelity.md`.** That plan (04 Aug) already
> specifies the fix as **P16b** and its reasoning still holds. What it could not know is that **P17b
> (06 Aug) changed what WC-04 costs** — attribution stopped being a display concern and became an
> input to node resolution. §3 is the new evidence; the phase-16 plan should be read *through* it.
>
> Supersedes nothing. Read with: `phase-16-hat-fidelity.md` §2 Finding 1, §4 P2, §9 R2/R3;
> `phase-17-interview-fidelity.md` §5; `ISSUES.md` WC-04, WC-13, WC-24, WC-27.

---

## Context Card — read THIS, skip the source

- `Extractor.extract(answer) -> ExtractionResult` @ `brain/src/warp_compass_brain/extractor.py#L157` — **takes one string, nothing else. This is the bug.**
- `Extractor._SYSTEM` @ `extractor.py#L18` — the prompt. Note `#L79` "A DENIAL IS NOT A FACT ABOUT THE SPEAKER", which refers to *"their role"* the model is never told.
- `Ingestor.ingest_answer(answer, *, persona_id, session_id, ts)` @ `ingest.py#L94` — **has `persona_id` and does not pass it to extraction.**
- `_candidate_context(cand, extraction) -> str` @ `ingest.py#L31` — builds the candidate's `[performed by …; in stage …]` line **from the extractor's own proposed PERFORMS relations**. No attribution ⇒ no context line.
- `Resolver.node_context(card) -> str` @ `resolve.py#L105` — the same line for cards already in the graph.
- `Resolver._SYSTEM` @ `resolve.py#L43-52` — *"WEIGH IT HEAVILY … a different performing role -> almost certainly 'new'"*.
- `profile_role_titles(profile) -> tuple[str, ...]` @ `lifecycle.py#L141` — declared roles, with the pre-P15a joined-string fallback. **The value the extractor needs.**
- `declared_roles(bus) -> dict[persona_id, tuple[str, ...]]` @ `lifecycle.py#L163` — **live participants only.** See §5 for why that matters.
- `all_answer_entries(bus) -> list[AnswerEntry]` @ `lifecycle.py#L200` — the rebuild's input; reads `profile.json` per folder at `#L219`, **including archived**.
- `RoundRunner._process_participant` @ `cycle.py#L147` — reads `profile` at `#L149`, calls `_ingest_log` at `#L170`.
- `AlignmentEngine._duplicated_work(snap)` @ `alignment.py#L532` — the R3 blast radius, and a live bug in its own right (§6.4).
- `test_anti_splitting_rule_is_scoped_and_cannot_suppress_other_node_types` @ `brain/tests/test_extractor.py#L101` — the WC-27 guard; the template for how a prompt rule gets pinned here.

---

## 1. Problem statement

`Extractor.extract(answer)` receives **one answer's text and nothing else** — no persona id, no
declared roles, no session context. So *"I write the BRD"* can only produce a `PERFORMS` edge if the
answer **itself** names a role.

The speaker's declared identity exists on the bus (`profile.json`, `role_titles`, P15a) and reaches
the brain for routing (P16a, ADR #34) and for the brief's copy (P17a, ADR #37). **It has never
reached extraction.** The plumbing distance is short: `cycle.py` already holds the profile two calls
above the place it is needed.

---

## 2. What was measured on the live graph (07 Aug 2026)

A probe over all 21 activities in `brain/_graph/`, comparing provenance `said_by` against incoming
`PERFORMS`. **The result contradicts the issue text and is the reason this doc exists.**

| Measurement | Value |
|---|---|
| Activities | 21 |
| Roles | 12 |
| Activities with **no** performing role | **1** (`act.data-processing` — a junk node: no keywords, "general data processing task") |
| Activities with **more than one** performer | 3 |

**Attribution is mostly right today.** All eight of Rahul's own activities landed on Delivery
Specialist; Kishor's BRD and demo work landed on Business Analysis Specialist. Third-person
attribution works too — Kishor's *"the Delivery Specialist creates the pre-sales timeline"* correctly
put `act.create-pre-sales-timeline` under Delivery Specialist.

**Why that is not reassuring.** Both testers are single-hat, and the extractor is guessing from
*content stereotype* — "BRD" ⇒ BA, "deployment" ⇒ DS. It is right by coincidence of job-title cliché,
not by knowledge, and it is **silently** wrong whenever the cliché does not hold: a dual-hat person,
or anyone whose work does not match their title. There is no signal in the data that tells you which
attributions were knowledge and which were luck.

> **Re-run this probe before acting on this doc.** The numbers above are from a two-person graph and
> the whole point of §3 is that they move with headcount. The probe script is trivial: walk
> `_graph/roles/*.md` for `PERFORMS` edges, invert to `activity -> {roles}`, and join against each
> activity's provenance `said_by`.

---

## 3. The finding that changes the severity

WC-04 is filed **Medium — "the deliverable's SOP sections"**. That costing predates P17b and is now
wrong.

P17b gave the adjudicator a context line — `[performed by X; in stage Y]` — and told it to weigh it
heavily (`resolve.py#L43-52`):

> *"DIFFERENT stage, or a different performing role -> almost certainly 'new', even when the two names
> look nearly identical."*

Now consider two nodes that are in the graph **right now**:

| | `act.discovery-work` | `act.detailed-project-discovery` |
|---|---|---|
| description | "Conducting discovery to understand project requirements." | "Understanding the client's business process and project details in a very detailed fashion, capturing every minute thing…" |
| stage | `stg.project-phase` | `stg.project-phase` — **same** |
| performers | `{BA, SA}` | `{BA, DS, SA}` — **different** |
| said by | Rahul (`s_20260806_1411`) | Kishor (`s_20260806_1421`) |

Same work, same stage, two nodes. The **only** discriminating signal that differed was the performer
set — and the three-performer set came from a single Kishor answer.

**So the causal chain is now:**

```
WC-04 (extractor blind to speaker)
  -> imprecise / inconsistent PERFORMS attribution
  -> _candidate_context and node_context disagree
  -> adjudicator reads "different performing role" -> "new"
  -> the node forks
  -> the person is asked about the same work twice   [= WC-24 / WC-13]
```

WC-04 is no longer a cosmetic concern about SOP headings. **It is a contributing cause of the
High-severity issue that made a tester say _"Did I not tell you that I document the user stories?"_**
WC-24 already names the residue — `create-user-story-documents` vs `user-story-creation`,
`development-oversight` vs `monitor-progress` — and concludes *"the remaining lever is retrieval
quality, not the prompt."* That conclusion is incomplete: **attribution quality is the other lever**,
and it was invisible when WC-24 was written because P17b had only just started using it.

### 3.1 A second, independent P17b defect found on the way

The performer comparison is **asymmetric by construction**. A fresh candidate carries the performers
from *one answer*; an established card carries performers *accumulated over every answer so far*. So
`{BA, SA}` vs `{BA, DS, SA}` — two of three shared — will routinely arise for genuinely identical
work, and the adjudicator prompt gives **no rule for partial overlap**. It says "same performer" and
"a different performing role" and leaves set semantics to the model.

**This is worth fixing whether or not WC-04 is ever built.** The rule should key on *disjoint*
performer sets, not *unequal* ones. One prompt clause, pinned by a test.

---

## 4. Why the extractor prompt is a lower-risk place to change than WC-27 suggests

`phase-16` R2 warns the `SPEAKER` block *"could narrow the extractor too far"*, and WC-27's lesson is
sharper still: **a prompt rule is not a local edit** — P17b's anti-splitting rule was scoped at
activities and silently took Objectives 4 → 0.

Two reasons the risk here is different **in kind**, though not zero:

1. **It adds context, not a constraint.** WC-27's regression came from a *minimise* instruction
   generalising. "The speaker is X" has no minimise semantics; its failure mode is
   **over-attribution** (everything becomes the speaker's work), which is the opposite direction and
   is directly measurable as a rise in `PERFORMS` edges.
2. **It resolves a dangling pointer the prompt already has.** `extractor.py#L79` (the P17c denial
   rule) instructs: *"do NOT emit a PERFORMS edge from **their role** to it."* Nothing tells the model
   what their role is. The `SPEAKER` block makes an existing rule actionable rather than adding a new
   one.

**Neither reason removes the need for the WC-27 acceptance discipline: count what you were NOT trying
to change** (§6.5).

---

## 5. Approach — four layers

Layer 1 is shared plumbing. Layer 4 is independent. Layers 2 and 3 belong together.

### Layer 1 — plumb declared roles into extraction (deterministic, no LLM)

`profile_role_titles` → `ingest_answer` → `Extractor.extract`. Two call sites:

- **Round path:** `cycle.py#L149` already holds `profile`; thread it through `_ingest_log` (`#L170`).
- **Rebuild path:** `all_answer_entries` (`lifecycle.py#L200`) reads `profile.json` per folder at
  `#L219`. Add `role_titles` to `AnswerEntry` **there**.

> ⚠ **Do not source the rebuild's roles from `declared_roles(bus)`.** That function is
> live-participants-only by design (`lifecycle.py#L170`: retired people have no folder, which is what
> stops a departed person remaining a routing target). But `all_answer_entries` **deliberately
> includes `_archive/`** so a rebuild does not delete a departed colleague's contribution (ADR #30).
> Wire the rebuild through `declared_roles` and every retired person's answers lose attribution on
> every rebuild — a silent, compounding regression. Read the titles from the profile the loop has
> already opened.

### Layer 2 — the `SPEAKER` block (P2-A)

Mirror the runner's per-turn `WHO YOU'RE TALKING TO` block. Wording must be a **preference**, exactly
like `KNOWN ROLES` (ADR #33) — the open-vocabulary rule must survive, or the client role disappears
from the process map. Only the model can read "I" vs "the SA", which is why this layer cannot be
purely deterministic.

### Layer 3 — a deterministic floor

After extraction: if an Activity candidate has **no** incoming `PERFORMS` in its own batch, and the
speaker declared **exactly one** role, attach the edge.

Guard it hard or it becomes the WC-R5 / WC-28 over-reach in a new place:

- only when the extractor named **nobody** (never override a named role);
- only for a **single** declared role — two hats stays ambiguous;
- **never** when the answer's `classification` is `not_mine` (P17c already persists this).

Value beyond attribution: it feeds `_candidate_context`, so the adjudicator stops judging on wording
alone — the failure `ingest.py#L36` explicitly calls *"worse than symmetric ignorance"*.

### Layer 4 — the `DUPLICATED_WORK` guard (R3), independent of everything above

`alignment.py#L532` groups activities by consume/produce signature and fires at `len(roles) >= 2`.
**One activity with two performers already trips it today** — it would report *"Business Analysis
Specialist and Technical Specialist each do work that takes the same inputs and produces the same
outputs: 'Write the BRD'"* about a **single node**, which is co-performance, not duplication, and the
ontology explicitly allows it (`add_edge` merges on `(type, from, to)`).

The correct guard is **two distinct activities** (`len(acts) >= 2`), not the same-persona exclusion
phase-16 R3 proposes. Same-persona exclusion is then only needed for the genuine two-activity case.
**This is a live bug; it does not need P16b to be worth fixing.**

---

## 6. Risks

- **R-A — Over-attribution.** The speaker becomes the performer of work they merely described. This
  is the WC-R5 → WC-R15 → WC-R16 → WC-28 family, which has now recurred **four times**, each time
  through a different door. Layer 3's guards are aimed squarely at it. Measure: total `PERFORMS` edge
  count before/after.
- **R-B — Narrowing the open vocabulary (phase-16 R2).** If the block reads as *"this person can only
  be these roles"*, roles nobody declares (`End Client`, `Resource Manager`) stop being emitted.
  Needs its own test asserting a non-registry role still survives.
- **R-C — Silent suppression of other node types (WC-27, exactly).** Any edit to `_SYSTEM` can move
  Objectives, ApprovalPoints, Stages. Non-negotiable acceptance check in §6.5.
- **R-D — Attribution improves and forks stay anyway.** Honest limit: a tighter performer set feeds
  the adjudicator better evidence but is **not guaranteed** to merge the discovery pair in §3. The
  fork may also need retrieval-recall work (WC-24's conclusion). Do not promise a node-count drop.
- **R-E — Dual-hat is still undefined.** Layer 3 abstains for two hats, so the case WC-04 was
  originally filed about is the one it helps least. That is what §8 is for.

### 6.5 Acceptance check (mandatory, from WC-27's lesson)

After any `_SYSTEM` edit, count **every** node type, not just the ones you targeted:

- Activity — expected to fall or hold.
- **Objective, ApprovalPoint, Stage, Problem, System, Artifact, Event, Rule — must NOT fall.**

WC-27 is exactly this check not being run.

---

## 7. How to measure it — an A/B rebuild, not a sample

`phase-16` §4 P2 says *"sample ~20 attributed activities and count how many landed under the wrong
hat."* **You can do better now, because P17b built `cli rebuild-graph` and the Answer Logs are
immutable (ADR #4).**

Rebuild **twice from the same logs**, with and without the speaker block, and diff:

1. `PERFORMS` edge count and the per-activity performer sets;
2. Activity node count (the fork hypothesis);
3. every other node type (§6.5).

A controlled A/B on identical input beats a judgement call on a sample. Cost is one paid LLM call per
answer per run — the last rebuild ran at this scale in tens of minutes. `cli rebuild-graph` flushes
per-line precisely so an interrupted replay leaves a record (`cli.py#L634`).

**Also re-run the §2 probe on both graphs.** The interesting number is not how many activities have a
performer — it is already 20/21 — but whether the performer *sets agree across speakers* for work
that is genuinely the same.

---

## 8. Open for the owner — the one decision that blocks building this

**When a dual-hat person's work is genuinely ambiguous, do we record BOTH hats or NEITHER?**

| | Records both (P2-C) | Records neither |
|---|---|---|
| Deliverable | The activity appears under both SOP sections | Clean sections; the activity has no owning role |
| Adjudicator | Gets a performer set — better than nothing, possibly wrong | Gets no context line, judges on wording (today's behaviour) |
| Honesty | Truthful about uncertainty | Truthful by silence |
| Cost | Trips `DUPLICATED_WORK` until Layer 4 lands | Leaves the §3 fork mechanism live |

The ontology permits both edges; this is a judgement about what the client-facing deliverable should
read like, not a technical constraint. ADR **#35** is drafted for the "both" answer
(`phase-16-hat-fidelity.md` §10) and should not be logged until this is decided.

---

## 9. Sequencing recommendation

1. **Layer 4** and **§3.1** — independent live bugs, cheap, no rebuild needed to justify.
2. **Layer 1** — shared plumbing, deterministic, no behaviour change on its own.
3. **Layers 2 + 3 together**, A/B'd in one rebuild. Separating them means paying for two replays to
   learn less.

**This competes with interview-facing work and may lose.** A runner change is felt in the next
session; WC-04 is only visible after a rebuild *and* another round of interviews. It makes the
**third** session better than the second, not the next one. That trade is the owner's.

---

## 10. Changelog

| Date | What |
|---|---|
| 07 Aug 2026 | Written. Live-graph probe (§2), the P17b fork-causation finding (§3), the asymmetric-performer defect (§3.1), the archived-profile trap (§5 Layer 1), and the `DUPLICATED_WORK` single-node bug (§5 Layer 4) are new here and not in `phase-16-hat-fidelity.md`. |
