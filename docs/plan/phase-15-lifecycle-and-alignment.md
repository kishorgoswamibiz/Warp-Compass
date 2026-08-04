# Phase 15 — Lifecycle-anchored interviewing, declared multi-role identity, and the alignment diagnostic

> **Status:** ✅ **PHASE 15 COMPLETE — P15a + P15b + P15c all shipped 04 Aug 2026.** Written
> 03 Aug 2026 from the owner's design ruling in session `opus-p15`. Supersedes the P12 "map your day"
> interview framing.
>
> **Read §1 before anything else.** Several items in this plan were *rejected* by the owner during
> design and are recorded in §1.2 so a later agent doesn't helpfully re-add them.
>
> **Everything in §4–§9 is built.** The role registry, multi-select onboarding, `cli seed-roles` (run
> live — the §9 order-critical step is closed), the `KNOWN ROLES` block, the R3 corroboration
> exclusion, the §4.5 dual-hat copy branch; the full ontology diff, per-type completeness scoring for
> Stage/Role/Objective, the stage-aware chain verdict, both prompt rewrites, the new field openers, the
> probe budget, `cli coverage`; and the alignment diagnostic — derived altitude,
> `GapKind.MISALIGNMENT`, the `Provenance.account` snapshot, all eight §7.2 structural findings, and
> the docgen stage spine + Gaps & Recommendations section. ADRs #31, #32, #33 all logged and marked
> done. Verified: 204 brain tests, 68 pwa, plus an end-to-end smoke against the real `OkfGraphStore`.
>
> **Eight deliberate deviations from this plan, all recorded so nobody "corrects" them back:**
> 1. **§10's `lifecycle.py` change is unnecessary.** `role_title` is now a derived `" / "` mirror of
>    `role_titles`, so every P13-era reader works untouched. Fewer readers to keep in sync.
> 2. **§4.3 slightly overstates the unseeded failure.** Retrieval "returns nothing *relevant*" — but
>    not nothing: the lexical index still returns the single Role node as a weak neighbour, so the
>    outcome depends on the adjudicating model rather than being deterministic. `test_roles.py`
>    asserts the honest version — without aliases **no exact match protects the decision**.
> 3. **Registry-seeded roles are not scored for completeness at all** (not in the plan). Otherwise ten
>    roles nobody has mentioned file 20 permanent gaps and `satisfied` can never be true again.
> 4. **`Role.reports_to` gained an attribute escape hatch** (not in the plan), mirroring
>    `next_handoff`'s endpoint exemption. Without it the org root's gap is unclosable — asked forever.
> 5. **A lone stage does not count as "positioned"**, so it cannot launder the activities inside it
>    out of the broken-chain check. §6.2 didn't specify this; without it the noise just moves up a
>    level.
> 6. **Unknown altitude falls back to *reconciling*, not to claiming a misalignment.** §7.1's table
>    has no row for it. With no org chart we cannot assert a finding, and asking is how the chart gets
>    filled in — erring the other way manufactures findings out of missing data.
> 7. **"Single point of failure" requires ≥2 activities in the stage.** §7.2 says "a stage whose every
>    activity is performed by exactly one role", which fires on nearly every stage early in an
>    engagement and drowns the real findings.
> 8. **The §7.3 walkthrough is ordered by stage too, not just the diagram.** §7.3 only mentions the
>    diagram, but grouping the picture while leaving the prose ordered by artifact plumbing produces a
>    document whose two halves disagree — and the picture looks authoritative.

---

## 1. Goals (from the owner)

### 1.1 What we're building

1. **Stop interviewing by the clock; interview by the lifecycle.** "What do you do day to day"
   produces noise — the owner's own example: *"as a BA I start my day checking my mails, but
   checking mail is not my job role."* Real role work is **per-project / per-opportunity**, not
   daily: pre-sales → demo → signing → kickoff → discovery → BRD → build cycles → UAT → go-live →
   support. The interview must follow **one piece of work travelling through the company**, and each
   person is mapped by *which stages of that journey they touch and what they do inside each*.
2. **One universal interviewer for every altitude.** The CEO, the India head and a developer get the
   **same** question grammar. Differentiation emerges from the graph, never from per-level scripts.
3. **Declared multi-role identity at onboarding.** The role field becomes a **multi-select from a
   fixed list of 10 roles** (§4). Real people wear several hats — the owner's CEO confirmed some
   Delivery Specialists also do sales — so one person must be able to select e.g. *Delivery
   Specialist + Account Management Specialist*.
4. **The deliverable is one SOP _plus_ a gap-and-recommendation report.** The end goal is replacing
   an EY/PwC-style engagement, so a divergence between what an exec believes and what actually
   happens is a **billable finding**, not a data defect to reconcile away.
5. **Termination condition = the graph is fully connected.** "Enough" is when everything links up,
   not when a question list is exhausted.

### 1.2 Explicitly rejected during design — do NOT build these

| Rejected | Why (owner's reasoning) |
|---|---|
| A special "that's not mine, X does it" routing mechanism | Already handled. Mentioning the role creates the Role node, and `crosspersona.py:306 _role_owner_personas()` routes the question into X's own brief once X is interviewed. Adding a mechanism would duplicate the graph's job. |
| Altitude-specific prompts / question sets (exec vs manager vs IC) | "No bifurcation between what question the CEO gets, what question the India head gets, or what question the developer gets." The whole point of graph-based memory is that nodes accumulate from whatever each person says. |
| A declared `level` / seniority field on the participant | Unnecessary — altitude is **derived** from `REPORTS_TO` depth once the org chart is captured (§6.3). Nothing predefined. |
| Multi-client / engagement separation | Not needed now. One graph = one client. Revisit when a second client starts. |
| A separate `Expectation` node type | An `Objective` attached to a Stage by a role that doesn't own that stage *is* an expectation (§5.2). One type, no redundancy. |

---

## 2. What's broken today (verified in code, 03 Aug 2026)

### Finding 1 — the day-framing is baked into four layers, not just the wording
- `COLD_START_OPENERS` — "day to day", "map your **day** from the very beginning"
  ([`prompts.ts:23`](../../pwa/src/runner/prompts.ts#L23) and the duplicated brain copy
  [`planner.py:58`](../../brain/src/warp_compass_brain/planner.py#L58)).
- `SYSTEM_PROMPT` END GOAL — "from the first trigger of their **day**"; METHOD — "the ordered chain
  of activities in a normal **day**/cycle" ([`prompts.ts:49`](../../pwa/src/runner/prompts.ts#L49)).
- **The graph itself has already absorbed it:** `brain/_graph/events/evt.start-of-day.md` exists as a
  real Event node. Rewording the prompts leaves that node behind (§9).

### Finding 2 — there is no lifecycle spine in the ontology, so the chain is guessed from plumbing
[`contracts/ontology.json`](../../contracts/ontology.json) has no `Stage` node and no
`PRECEDES`/`PART_OF` edges. "Pre-sales comes before kickoff" is unrepresentable. Consequently
`activity_flow()` ([`completeness.py:153`](../../brain/src/warp_compass_brain/completeness.py#L153))
infers order **only** from handoffs and produced→consumed artifacts — and interviews rarely yield
complete artifact plumbing. The damage is visible in the current
[`deliverable.md`](../../deliverable.md): 3 activities reported as `broken chain` and **21 hidden as
unconfirmed**, in a process the owner knows perfectly well is not broken.

### Finding 3 — half the ontology's completeness vocabulary is dead code
`Role.completeness_fields = ["reports_to", "performs"]` is declared in the contract, but
`CompletenessEngine.assess()` scores **Activities only**
([`completeness.py:200`](../../brain/src/warp_compass_brain/completeness.py#L200); `_persona_scores`
counts activities). `System`, `Artifact`, `Event`, `Role` completeness fields are never measured. So
`REPORTS_TO` exists as an edge type and **nothing in the system ever drives the org chart to
completion** — which also means altitude can't be derived (§6.3) until this is fixed.

### Finding 4 — the system is engineered to erase the signal we intend to sell
When two accounts of the same node differ, ingest flags `CONFLICTING`
([`ingest.py:173`](../../brain/src/warp_compass_brain/ingest.py#L173)), completeness files a
`UNRESOLVED_CONFLICT` defect ([`completeness.py:353`](../../brain/src/warp_compass_brain/completeness.py#L353)),
and the planner asks every contributor *"I've heard different accounts — how does it actually
work?"* ([`crosspersona.py:265`](../../brain/src/warp_compass_brain/crosspersona.py#L265)) until one
version survives. Correct for data hygiene, wrong for consulting: an exec-vs-doer divergence is the
finding.

### Finding 5 — no cadence anywhere
Nothing distinguishes "every day" from "once per opportunity" from "only when the client escalates."
This is Finding 1 expressed as schema: even with perfect stage questions, the graph cannot record
that pre-sales demos are per-opportunity.

### Finding 6 — a single declared role, and a role→node forking hazard (§4.3)
`Participant.role_title` is one string ([`participant.ts:27`](../../pwa/src/sync/participant.ts#L27))
and the onboarding card is a free-text input
([`OnboardingCard.tsx:73`](../../pwa/src/screens/OnboardingCard.tsx#L73)). Free text means "PM",
"Project Manager" and "Delivery Specialist" arrive as three different strings and — because
`find_by_alias` is **exact match** over `canonical_name` + `aliases`
([`okf_store.py:135`](../../brain/src/warp_compass_brain/graphstore/okf_store.py#L135)) — fork into
three Role nodes. See §4.3 for why that silently breaks the routing the owner is relying on.

---

## 3. Sub-phases (ship in this order)

| Sub-phase | Scope | Why this order |
|---|---|---|
| **P15a** | Role registry + multi-select onboarding + role seeding | Unblocks internal testing inside the owner's company immediately; independent of the interview rewrite. |
| **P15b** | Ontology diff (Stage, Objective, cadence) + completeness scoring for Stage/Role + prompt rewrite + graph migration | The interview change proper. Needs P15a's canonical roles to be worth interviewing against. |
| **P15c** | Alignment/diagnostic engine + gap-and-recommendation report in `docgen` | Needs P15b's stages and derived altitude to have anything to diagnose. |

---

## 4. P15a — the role registry and multi-select onboarding

### 4.1 `contracts/roles.json` — one source of truth for both planes

The 10 roles the owner supplied (8 + **CEO and COO**, added 04 Aug 2026), canonicalised, with the
conversational synonyms they also supplied. Consumed by **three** places (§4.4), so it lives in
`contracts/` next to `ontology.json` rather than being typed twice.

Pattern for every entry: **full title is canonical, the abbreviation people actually say is an
alias.** That way the deliverable reads formally and the conversation still matches.

```json
{
  "$schema_version": "1.0.0",
  "description": "The engagement's role registry. Canonical role names for the onboarding multi-select, plus the conversational synonyms people actually say. Aliases are load-bearing: they are what stops 'the PM' and 'Delivery Specialist' forking into two Role nodes (see docs/plan/phase-15 §4.3). Aliases must be unique across roles — find_by_alias is an exact, case-insensitive whole-string match.",
  "roles": [
    { "slug": "role.business-analysis-specialist", "canonical_name": "Business Analysis Specialist", "aliases": ["BA", "Business Analyst", "BAS"] },
    { "slug": "role.technical-specialist",         "canonical_name": "Technical Specialist",         "aliases": ["Developer", "Dev", "TS", "Engineer"] },
    { "slug": "role.solution-architect",           "canonical_name": "Solution Architect",           "aliases": ["SA", "Architect"] },
    { "slug": "role.delivery-specialist",          "canonical_name": "Delivery Specialist",          "aliases": ["Project Manager", "PM", "DS", "Delivery Manager"] },
    { "slug": "role.account-management-specialist","canonical_name": "Account Management Specialist", "aliases": ["Account Manager", "AMS", "AM", "Sales"] },
    { "slug": "role.quality-assurance-head",       "canonical_name": "Quality Assurance Head",       "aliases": ["QA Head", "QA Lead", "Head of QA"] },
    { "slug": "role.quality-assurance-specialist", "canonical_name": "Quality Assurance Specialist", "aliases": ["QA", "Tester", "QA Engineer", "QAS"] },
    { "slug": "role.finance",                      "canonical_name": "Finance",                      "aliases": ["Finance Team", "Accounts", "Finance Specialist"] },
    { "slug": "role.chief-executive-officer",      "canonical_name": "Chief Executive Officer",      "aliases": ["CEO", "Chief Executive"] },
    { "slug": "role.chief-operating-officer",      "canonical_name": "Chief Operating Officer",      "aliases": ["COO", "Chief Operating"] }
  ]
}
```

**Owner decisions, 04 Aug 2026 (both previously-open questions now closed):**
- **"Sales" is an alias of Account Management Specialist**, not a separate role. (If a distinct sales
  function ever appears in interviews, the extractor can still mint it — see §4.4 note 3.)
- **CEO and COO added** as roles 9 and 10. This also gives altitude derivation (§6.3) a natural root:
  the CEO is the role with no outgoing `REPORTS_TO`.
- Aliases kept deliberately narrow for the two exec roles. "Operations Head", "MD", "Founder" and
  similar are *not* included, because in a larger org they can be genuinely different people, and a
  wrong alias silently **merges two roles into one** — the one failure mode the alias table can cause
  (risk R1). Adding one later is a one-line change to this contract.

### 4.2 The multi-select onboarding card

`OnboardingCard.tsx` keeps the typed name field (STT would mangle a name into a permanent id — ADR
#29 still holds) and replaces the free-text role input with **checkable role chips**:

```
Who's using this device?

Your name            [ Rahul Mehta            ]

Your role(s)         Select every role you hold — pick more than one if you wear several hats.
                     [✓ Delivery Specialist] [✓ Account Management Specialist]
                     [ Business Analysis Specialist] [ Technical Specialist]
                     [ Solution Architect] [ Quality Assurance Head]
                     [ Quality Assurance Specialist] [ Finance]
                     [ Chief Executive Officer] [ Chief Operating Officer]

                                                             [ Continue → ]
```

- Chips, not a `<select multiple>`: 10 items are thumb-tappable on a phone and a native multi-select
  is miserable on mobile.
- `ready` = name non-empty **and** ≥1 role selected.
- Keyboard path preserved (Enter on name → first chip; Space toggles; Enter submits when ready).

### 4.3 Why the aliases are load-bearing (the owner asked whether they're needed — they are)

Trace what happens when the BA says *"the PM signs that off"*, **without** an alias table:

1. The extractor emits a `Role` candidate `canonical_name: "Project Manager"`.
2. `Resolver.retrieve()` ([`resolve.py:70`](../../brain/src/warp_compass_brain/resolve.py#L70)) tries
   exact alias match first — `find_by_alias("Project Manager", "Role")` misses, because the
   graph's node is `Delivery Specialist`.
3. It falls back to **vector** similarity. The default embedder is a deterministic **lexical hashing
   fallback** unless `--extra vectors` is installed (see PROGRESS Blockers), and `"PM"` /
   `"Project Manager"` share almost nothing lexically with `"Delivery Specialist"`. Retrieval
   returns nothing relevant, and `adjudicate()` short-circuits: *"new — no existing candidates of
   this type"* ([`resolve.py:97`](../../brain/src/warp_compass_brain/resolve.py#L97)).
4. The graph now holds **two** Role nodes for one person.
5. Now the consequence the owner cares about: `_role_owner_personas("role.project-manager")` finds no
   activities → no owner → `_handoff_state` returns `route_discoverer`
   ([`crosspersona.py:244`](../../brain/src/warp_compass_brain/crosspersona.py#L244)) → the BA is
   asked *"who would know how the Project Manager handles it?"* **forever**, and the actual Delivery
   Specialist is never asked, even though they are in the engagement answering questions.

So the alias table is not a nicety — it is the precondition for the graph-routing design in §1.2.
With `"Project Manager"` as an alias of `Delivery Specialist`, step 2 hits exactly, the mention lands
on the **same node**, the role has an owner, and the thread routes to the right person's brief at
priority 1.4.

*(Exact-match is also why aliases are safe: `"QA"` and `"QA Head"` are different whole strings, so
`Quality Assurance Specialist` and `Quality Assurance Head` cannot collide.)*

### 4.4 The three consumers of the registry

1. **PWA** — the chip list. Import a generated `pwa/src/sync/roles.ts` (a build step or a committed
   mirror with a test asserting it matches `contracts/roles.json`, the same discipline `PROMPTS.md`
   §2 uses for the duplicated openers).
2. **`cli seed-roles`** (new) — creates the 10 `Role` nodes up front with `aliases` pre-loaded, so
   `find_by_alias` hits from the very first answer instead of after someone happens to say the
   canonical name. Idempotent; provenance `said_by: "registry"`, status `unverified` (a seeded role is
   a vocabulary entry, not a claim about the business, and must not inflate corroboration counts —
   see §13 risk R3).
3. **Extractor** — inject the canonical role list into `_user_prompt()`
   ([`extractor.py:73`](../../brain/src/warp_compass_brain/extractor.py#L73)) as
   `KNOWN ROLES (use these exact canonical names when the answer refers to one)`. This fixes forking
   at the *source* rather than repairing it at resolve time.

   ⚠ **The registry is a closed vocabulary for the DROPDOWN ONLY, never for the extractor.** The
   phrasing must be "prefer these canonical names when the answer refers to one of them" — **not**
   "only these roles exist". Real interviews name roles nobody self-declares: the previous graph
   legitimately held `End Client`, `Resource Manager`, `Project Management Team` and
   `Development Team`. Closing the vocabulary here would delete the client from the process map.
   (Unlike `ontology.json`'s node/edge types, which *are* closed — that distinction matters.)

### 4.5 Multi-role plumbing

| Concern | Decision |
|---|---|
| `Participant.role_title: string` | Becomes `role_titles: string[]`. Readers accept both: `role_titles ?? [role_title]`. Keep writing a joined `role_title` for the P13-era readers in `Code.gs` and `lifecycle.py`. |
| Id minting (`mintParticipantId(name, role)`) | Mints from name + **first selected** role. The id is immutable (ADR #29), so a later hat change must not re-mint — document this: the id is a label, `role_titles` is the truth. |
| `identityAnswer()` | `"I'm Rahul Mehta, I'm the Delivery Specialist and Account Management Specialist."` → the extractor mints **both** Role nodes from turn zero, and the person legitimately owns two. |
| `apps-script/Code.gs` | Write `role_titles` into `profile.json` and render all roles in the per-folder `README.md`. **Prerequisite:** the live Web App is still the P11 build (PROGRESS Blockers) — it must be redeployed or the Drive leg silently drops this too. |
| Dual-hat self-handoff | A DS→AMS handoff by one person makes `_role_owner_personas(AMS)` return *that same persona*, so they get asked to confirm a handoff *to themselves* with copy that says "another team handed it to you". Add a copy branch in `planner._opener_and_followups`: when the receiving role's owners == `{this persona}`, ask *"When you switch from your Delivery Specialist hat to your Account Management hat, what do you do with it?"* — still worth asking, just not framed as a stranger. |
| `_owning_role()` returns the *first* role performing an activity | With multi-hat people this can misattribute a gap to the wrong hat. Acceptable for now (it only affects gap attribution, not routing); note it in the risk register. |

---

## 5. P15b — the ontology diff

### 5.1 New node types

| Type | Slug | Description | `completeness_fields` |
|---|---|---|---|
| `Stage` | `stg` | A phase in the lifecycle of one piece of work as it travels through the org (e.g. Pre-Sales, Kickoff, Discovery, Build, UAT, Go-Live, Support). Discovered per org — **never a predefined list**. | `position`, `activities`, `owner`, `exit_criteria` |
| `Objective` | `obj` | A stated intended outcome — what someone wants a stage, role or the org to achieve. Recorded **as stated by whoever stated it**. | `owner_role`, `objective_for`, `measured_by` |

`Objective` doubles as *expectation*: an Objective a role attaches to a stage **they don't own** is,
by construction, an expectation placed on someone else — which is exactly the fuel for §7.2. No
separate node type (§1.2).

### 5.2 New edge types

| Edge | From → To | Meaning |
|---|---|---|
| `PART_OF` | `Activity` → `Stage` | This activity happens inside this stage. **The spine.** |
| `PRECEDES` | `Stage` → `Stage` | Lifecycle order. |
| `OWNS` | `Role` → `Stage` | Accountability for a stage (distinct from performing an activity in it). |
| `PURSUES` | `Role` → `Objective` | Who stated/holds this objective. |
| `OBJECTIVE_FOR` | `Objective` → `Stage` | What the objective is about. |

The store's per-edge provenance means `PURSUES` records *who said it and when* for free — which is
all §7.2 needs.

### 5.3 `cadence` on Activity (Finding 5)

Add `"cadence"` to `Activity.completeness_fields` and register it in
`_ACTIVITY_ATTR_FIELDS` ([`completeness.py:52`](../../brain/src/warp_compass_brain/completeness.py#L52))
alongside `exceptions` — an attribute, not an edge. Expected values are free text distilled by the
extractor ("every project", "per opportunity", "monthly", "only on escalation"), because inventing an
enum here would just be the day-assumption again in a new costume.

### 5.4 Taxonomy codes

Add `00 Lifecycle & Stages` and `11 Objectives & Expectations` to the `taxonomy_registry` so the
generated document has sections for them (codes drive the deliverable's numbering, §11 of docs/02).

---

## 6. P15b — completeness engine changes

### 6.1 Score `Stage` and `Role`, not just `Activity` (Finding 3)

Generalise `assess()`: today it hardcodes an Activity loop. Add per-type field→graph maps:

```python
_ROLE_EDGE_FIELDS  = {"reports_to": (EdgeType.REPORTS_TO, "out"), "performs": (EdgeType.PERFORMS, "out")}
_STAGE_EDGE_FIELDS = {"position": (EdgeType.PRECEDES, "either"), "activities": (EdgeType.PART_OF, "in"),
                      "owner": (EdgeType.OWNS, "in")}
_STAGE_ATTR_FIELDS = frozenset({"exit_criteria"})
```

`"either"` is new (a stage at the start of the lifecycle has no predecessor, one at the end no
successor — either direction satisfies `position`). Keep the existing "field named in the ontology but
unmapped here → treat as unknowable, not missing" guard
([`completeness.py:280`](../../brain/src/warp_compass_brain/completeness.py#L280)) so adding
vocabulary can never mark the whole graph incomplete.

**Scoring `Role.reports_to` is what makes the org chart get asked about**, which is what makes §6.3
possible. It is the load-bearing line of this sub-phase.

### 6.2 Fix the false broken-chain noise (Finding 2)

Keep `activity_flow()` exactly as-is — it is shared with the doc generator and is the truth about
artifact/handoff flow. Change only the **verdict**:

- Add `stage_chain_connectivity` to `OrgScore`: the fraction of stages on a `PRECEDES` path from a
  first stage to a last one.
- Emit `BROKEN_CHAIN` for an activity only when it is off the activity-flow path **and** has no
  `PART_OF` stage. An activity that sits in a correctly-ordered stage is *located*; the missing
  artifact link is a lesser gap (`MISSING_FIELD` on `inputs`/`output`), which is what it actually is.

This is the surgical fix for "3 broken / 21 hidden" without weakening the check where it's real.

### 6.3 Derived altitude (replaces the rejected `level` field)

```
altitude(role) = number of REPORTS_TO hops from that role up to a role with no outgoing REPORTS_TO
```

A pure graph query, no declaration. Roles with equal depth are peers. Cycles (A reports to B reports
to A) are a **finding**, not a crash — report and treat both as the same altitude. Depth is `None`
while unknown, and an unknown altitude simply means §7.1 can't classify that divergence yet, which
is itself a reason to ask about reporting lines.

---

## 7. P15c — the alignment diagnostic

### 7.1 Divergence: preserve it, don't reconcile it (Finding 4)

Add `GapKind.MISALIGNMENT`. When a node carries conflicting accounts, branch on derived altitude:

| Contributors | Verdict | What happens |
|---|---|---|
| Same altitude (peers) | `UNRESOLVED_CONFLICT` (today's behaviour) | Route a reconciliation thread — two peers disagreeing about their own process is a data-quality problem. |
| Different altitudes | **`MISALIGNMENT`** | **Do not ask anyone to reconcile it.** Record both accounts with their altitude and reporting line, and emit it into the report as a finding. |

This requires retaining both accounts, which today's merge does not do — it keeps one canonical card
(the known limitation in PROGRESS Blockers, "semantic batch conflict detection deferred, ADR #23").
The minimal fix that unblocks it: **snapshot the candidate's `description` onto the `Provenance`
entry at ingest** ([`ingest.py:163`](../../brain/src/warp_compass_brain/ingest.py#L163)), so each
contributor's own words survive the merge. That is the smallest possible change with the largest
payoff in this phase, and it is exactly the retention step ADR #23 said would be needed.

### 7.2 Structural findings — computable with no conflict flag at all

These need no LLM and no disagreement; they fall straight out of the graph, and they are the kind of
thing a Big-4 report is actually made of:

| Finding | Query |
|---|---|
| **Expectation with no execution behind it** | An `Objective` `OBJECTIVE_FOR` a Stage, `PURSUES`d by a role that does **not** `OWN` that stage, where no activity `PART_OF` that stage produces anything related or is `MEASURED_BY` a KPI. *"Leadership expects X of this stage; nothing in the stage is aimed at X."* |
| **Unowned stage** | A `Stage` with no `OWNS` edge but ≥1 activity. Work happens, nobody is accountable. |
| **Approval with no criteria** | An `ApprovalPoint` whose `condition` attribute is empty. Decisions made on vibes. |
| **Unmeasured stage** | A stage whose activities have no `MEASURED_BY` KPI. |
| **Single point of failure** | A stage whose every activity is performed by exactly one role. |
| **Duplicated work** | Two roles performing activities that consume and produce the same artifacts. |
| **Silent stage** | A stage named by someone but with no interviewed owner — pairs with the operator's "who to invite next" list (§8.4). |

### 7.3 Report shape (`cli docgen`)

Extend the generated document, keeping the existing "surface gaps, never bridge them" discipline:

- **§1 End-to-end process** — now rendered on the **stage spine** (stages as mermaid subgraphs with
  activities inside), which is what makes the diagram legible to a client.
- **§N Gaps & recommendations** (new) — three ranked groups: *misalignments* (with both accounts and
  who holds each), *structural findings* (§7.2), and *knowledge gaps* (what we still haven't been
  told). Each finding carries its provenance, because a consulting finding without a source is an
  opinion.

---

## 8. P15b — the prompt rewrites

### 8.1 `COLD_START_OPENERS` (⚠ both copies — `prompts.ts` **and** `planner.py`)

```
0. "To start, tell me about your role — what are you responsible for?"          # dropped when identity declared
1. "Think of one piece of work from the moment it reaches the company to when it's delivered. Which parts of that journey do you touch?"
2. "Take the earliest part you touch. What has to happen before it reaches you, and what tells you it's your turn?"
3. "Inside that part, what do you actually do — step by step, in the order you do it?"
4. "When your part is finished, what have you produced, and who picks it up?"
5. "Is that something you do on every project, or only in certain cases?"
```

Index 0 must stay at index 0 (`IDENTITY_OPENER_INDEX`, P13's never-re-ask guarantee). Opener 1 is the
Pass-A map question; 2–5 are Pass B. No occurrence of the word "day" anywhere.

### 8.2 `SYSTEM_PROMPT` — the two changed blocks

**END GOAL** (replaces [`prompts.ts:49`](../../pwa/src/runner/prompts.ts#L49)):

> YOUR END GOAL is a complete Standard Operating Procedure of THIS person's role, mapped against the
> **lifecycle of work in their organisation** — the journey one piece of work takes from the moment
> it arrives to the moment it is delivered and supported. The unit of structure is the **STAGE** of
> that journey (for example: pre-sales, kickoff, discovery, build, testing, go-live, support — but
> **never assume these; discover theirs**). For every stage this person touches you ultimately need:
> what starts it, what they need in hand, which tool it happens in, what it produces, who picks it up
> next, **how often it happens** (every project? per client? only on escalation?), the exceptions, and
> the rules. **Do not organise anything around a calendar day** — most real work is per-project, not
> daily, and "what do you do each morning" produces noise, not process. You are NOT here to hunt for
> pain points.

**METHOD** (replaces [`prompts.ts:51`](../../pwa/src/runner/prompts.ts#L51)):

> METHOD — two passes, in this order:
> - **PASS A — the map (do this first, keep it brief).** Get the ordered list of lifecycle stages this
>   person personally touches. Ask them to think of one piece of work travelling end-to-end and name
>   which parts are theirs. Don't go deep yet.
> - **PASS B — one stage at a time.** Take the earliest stage they own and walk it: trigger → what
>   they need in hand → what they do, in order → which tool → what it produces → who picks it up →
>   how often it happens → what throws it off → what rules govern it. Finish a stage before moving to
>   the next one.
> - Anchor every question to what they already said, so it feels like one continuous walk through
>   their work, never a form.
> - **When they name another role as owning something, capture it warmly and move on.** Do NOT
>   interrogate them about someone else's work — that person will be asked directly.
> - **When they state what they expect of another stage, team or role, or an outcome they're aiming
>   for, record it as stated.** Do not challenge it or reconcile it against anything you were told
>   before.
> - NEVER open with (or steer toward) "what's the most difficult/frustrating part" questions. If they
>   volunteer a problem, capture it warmly, then return to mapping the flow.

Unchanged: the persona sentence, the brief-as-scaffolding contract, the classification/action sets,
the identity hard rule, one-question-per-turn, and the JSON shape. **One interviewer, one prompt** —
§1.2.

### 8.3 New planner openers

Add to `_FIELD_OPENERS` / `_FIELD_FOLLOWUPS`
([`planner.py:327`](../../brain/src/warp_compass_brain/planner.py#L327)):

| Field | Opener |
|---|---|
| `cadence` | `"How often does '{name}' happen — every project, or only in certain cases?"` |
| `position` (Stage) | `"Where does '{name}' sit in the journey — what comes just before it, and just after?"` |
| `owner` (Stage) | `"Who's accountable for '{name}' overall — not who does the tasks, who owns the outcome?"` |
| `activities` (Stage) | `"What actually happens during '{name}'? Walk me through it in order."` |
| `exit_criteria` (Stage) | `"How do you know '{name}' is done and it's safe to move on?"` |
| `reports_to` (Role) | `"Who do you report to, and who reports to you?"` |
| `objective_for` | `"What is '{name}' meant to achieve?"` |

### 8.4 One derived operator view (not a new question type)

`cli coverage` (new, read-only): the **stage × role matrix** — for each stage, which roles are named
in it and which of those have an interviewed owner. This is the "who to invite next" list, derived
entirely from the graph. It's an operator report; it adds no predefined questions and no mechanism
(§1.2).

### 8.5 The probe budget — DECIDED (owner, 04 Aug 2026)

Lifecycle interviewing needs to sit on one stage for many turns, but the runner currently refuses to
probe a thread twice ([`prompts.ts:68`](../../pwa/src/runner/prompts.ts#L68), enforced in
`runner.ts`).

**Ruling: 3 probes** for stage deep-dive threads, **1** for everything else; the 30-word /
one-question-per-turn cap is **kept** (it is what keeps the session feeling spoken rather than
written).

Implementation note: `Session.probed` is a `Set<string>`
([`session.ts:24`](../../pwa/src/runner/session.ts#L24)) and `hasProbed()` is a boolean check — it
becomes a `Map<string, number>` with a per-thread budget, and the guard in `runner.ts` compares a
count against the budget rather than testing membership. Keep `probedTheadIds` in the prompt's
`=== STATE ===` block (`probedThreadIds`) reporting only threads that have hit their budget, so the model still sees a
"do NOT probe again" list rather than a counter it has to reason about.

---

## 9. Migration — mostly moot, because the graph is empty (verified 04 Aug 2026)

**This section shrank dramatically after checking the live state.** The owner ran the
`OPERATOR-MANUAL.md` §1d clean slate (`cli reset-engagement`) between 03 and 04 Aug 2026:

- `GRAPH_ROOT` (`brain/_graph`) **does not exist** — all 52 node files are deleted from the working
  tree (still in git `HEAD`, uncommitted deletion, so recoverable if ever needed).
- `brain/_state/` is **empty** — which incidentally clears the long-standing mixed-dimension
  `vectors.sqlite` blocker in PROGRESS. **Pick one embedder mode now and stay on it.**
- The bus holds exactly **one** participant: `kishor-goswami-business-analysis-specia-f25b`.

Three consequences, all good:

1. **`evt.start-of-day` is already gone**, along with every other day-shaped node. Nothing to retire.
2. **No role-rename hazard.** This was going to be the ugly part: the old graph's role nodes were
   named with what are now *aliases* — `role.business-analyst`, `role.account-manager`,
   `role.quality-analyst`, `role.development-team` — and node ids are stamped into provenance and
   every edge, so they cannot be renamed in place (ADR #29's logic applies to node ids too). A rebuild
   from Answer Logs would have been the only clean route. **The reset removed the problem entirely.**
3. **This is the ideal moment to land P15a/P15b** — seed the registry into an empty graph, and every
   answer from the first round onward resolves against canonical roles.

**The only migration step that remains, and it is order-critical:**

> Run **`cli seed-roles` before the next `run-round`**. If a round ingests first, its answers mint
> role nodes with whatever names the extractor chose, and the aliases arrive too late to prevent the
> fork §4.3 describes.

The one existing participant declared their role as free text before the dropdown existed
(`…-business-analysis-specia-f25b` implies "Business Analysis Specialist", which matches the registry
canonical name exactly). Their `role_titles` should be verified after P15a ships — **but note** their
`profile.json` could not be read during planning: the Drive folder read hung (the P14 stream-only
symptom), so whether it carries `role_title` at all is **unverified**, and R6 (the un-redeployed Apps
Script) makes its absence likely.

---

## 10. Files

**New**
- `contracts/roles.json` — the role registry (§4.1).
- `pwa/src/sync/roles.ts` — generated/mirrored chip list + a test asserting parity with the contract.
- `brain/src/warp_compass_brain/alignment.py` — derived altitude, misalignment classification,
  structural findings (§7).
- `docs/plan/phase-15-lifecycle-and-alignment.md` — this file.

**Changed**
- `contracts/ontology.json` — `Stage`, `Objective`, 5 edges, `cadence`, 2 taxonomy codes.
- `pwa/src/screens/OnboardingCard.tsx` — multi-select chips.
- `pwa/src/sync/participant.ts` — `role_titles: string[]`, id minting note, back-compat reader.
- `pwa/src/runner/prompts.ts` — `COLD_START_OPENERS`, `SYSTEM_PROMPT`, `identityAnswer()`.
- `pwa/src/runner/{runner,session}.ts` — probe budget (§8.5).
- `brain/.../planner.py` — `COLD_START_OPENERS` (mirror), new field openers, dual-hat copy branch.
- `brain/.../completeness.py` — per-type scoring, `Stage`/`Role` fields, stage-aware chain verdict.
- `brain/.../crosspersona.py` — altitude branch: misalignment vs peer conflict.
- `brain/.../ingest.py` — snapshot each contributor's description onto `Provenance` (§7.1).
- `brain/.../extractor.py` — inject `KNOWN ROLES`.
- `brain/.../docgen/{traverse,render}.py` — stage-spine diagram + Gaps & Recommendations section.
- `brain/.../cli.py` — `seed-roles`, `coverage`.
- `brain/.../lifecycle.py` — read `role_titles` with `role_title` fallback.
- `apps-script/Code.gs` — `role_titles` in `profile.json` + README (**needs redeploy**).
- `PROMPTS.md`, `docs/DECISIONS.md` (ADRs #31–#33), `PROGRESS.md`, `docs/DATA-CONTRACTS.md`.

---

## 11. Test plan

- **Registry parity** — `roles.ts` matches `contracts/roles.json` (fails loudly on drift, the
  `PROMPTS.md` §2 discipline).
- **Alias resolution (the §4.3 regression test)** — seed roles, extract *"the PM approves it"*,
  assert it resolves to `role.delivery-specialist` and that **no** new Role node is created.
- **Routing through an alias, end to end** — BA says "hand it to the PM"; assert the resulting
  `handoff_confirm` thread lands in the *Delivery Specialist's* brief, not as a `handoff_trace` back
  on the BA.
- **Multi-role onboarding** — two roles selected → both Role nodes exist from the identity seed; id
  minted from the first role; `updateIdentity` adding a third role does **not** change the id.
- **Dual-hat self-handoff** — the copy branch fires and does not say "another team".
- **Stage scoring** — a stage with no owner / no position / no exit criteria yields exactly those
  three gaps; a first stage with no predecessor does **not** yield a `position` gap (`"either"`).
- **Chain verdict** — an activity inside a correctly-ordered stage but with no artifact link yields a
  `MISSING_FIELD`, **not** a `BROKEN_CHAIN` (asserts Finding 2 is fixed).
- **Derived altitude** — 3-level `REPORTS_TO` chain gives depths 0/1/2; a cycle is reported, not
  crashed; unknown depth degrades gracefully.
- **Misalignment vs conflict** — same-altitude divergence → `UNRESOLVED_CONFLICT` + reconciliation
  thread; cross-altitude divergence → `MISALIGNMENT`, **no** reconciliation thread, both accounts
  retained with their sources.
- **Structural findings** — one fixture per §7.2 row.
- **Prompt guards** — no cold-start opener or system-prompt line contains "day"; existing
  `runner.test.ts` / `test_planner.py` / `test_extractor.py` assertions updated deliberately, not
  silently.
- **Regression** — full suites green (brain 124, pwa 45 at time of writing) + `docgen` runs against
  the real graph and the deliverable is regenerated.

---

## 12. Done when

1. A person onboards with **two roles** selected from the fixed list, and both appear in the graph,
   the Drive profile, and `cli list-participants`.
2. Someone says *"the PM does that"* and the graph resolves it onto `Delivery Specialist` —
   verifiable in `cli coverage` (no orphan `role.project-manager` node).
3. A cold session opens with the **lifecycle** question, and a full session never mentions "day".
4. `cli completeness` reports **stage** and **role** gaps, and no longer reports false broken chains
   for activities that sit in ordered stages.
5. `cli docgen` emits the stage-spine process map **plus** a Gaps & Recommendations section
   containing at least one structural finding and, where the data supports it, one misalignment with
   both accounts and their altitudes.
6. `cli coverage` tells the operator which stage has no interviewed owner.
7. Suites green; `PROGRESS.md`, `PROMPTS.md`, `DECISIONS.md` updated.

---

## 13. Risks, and decisions to log

**ADRs to append when this lands**
- **#31 — One universal interviewer; altitude is derived, never declared.** Same question grammar for
  every level; `REPORTS_TO` depth supplies altitude. *Why:* owner's ruling — the graph, not a script,
  is what differentiates; per-level scripts bake in the bias the ontology exists to avoid.
- **#32 — Cross-altitude divergence is a finding, not a defect.** Preserved and reported; only
  same-altitude divergence is routed for reconciliation. Requires per-provenance description
  snapshots (partially retires ADR #23's deferral). *Why:* the delta between belief and practice is
  the product.
- **#33 — Roles are a governed registry with aliases; the lifecycle is not.** The 10 roles are a fixed
  contract *for self-declaration* because the engagement knows them (and aliases are load-bearing for
  routing, §4.3); the extractor may still mint roles that nobody self-declares (`End Client`); and
  **stages are discovered per org**, because assuming them is the day-assumption in a new costume.

**Risks**
- **R1 — The alias table is now a single point of failure for routing.** A missing synonym silently
  forks a role. Mitigation: the §11 regression test, and `cli coverage` makes a forked role visible
  as a role with no owner rather than letting it hide.
- **R2 — The fixed dropdown cannot express a role nobody anticipated.** Reduced but not gone: CEO and
  COO are now in the registry (§4.1), and roles nobody self-declares can still be minted from
  conversation (§4.4 note 3). What remains uncovered is a *new self-declaring* role — a Legal or HR
  hire would have nothing to select. Mitigation if it comes up: an "Other" chip revealing a free-text
  field that files the value to a review queue, mirroring how the ontology handles unknown types.
  Not built now — 10 roles cover the owner's company for this round of testing.
- **R3 — Seeded roles could inflate confidence.** Corroboration promotes a node once two distinct
  `said_by` values touch it ([`ingest.py:165`](../../brain/src/warp_compass_brain/ingest.py#L165));
  if `registry` counted as a voice, every role would look corroborated by one real person. Mitigation:
  exclude `said_by: "registry"` from the distinct-persona count. **Must be covered by a test.**
- **R4 — Stage discovery could drift into 30 micro-stages**, one per person's vocabulary. The alias +
  resolve machinery is the same defence used for every other node type; watch it in the first real
  round and tighten the extractor prompt if it sprawls.
- **R5 — `_owning_role()` picks the first role performing an activity**, so gaps for multi-hat people
  can be attributed to the wrong hat. Affects attribution only, not routing. Accepted for now.
- **R6 — The Apps Script Web App is still the P11 build.** P13's `role_title` work already never
  reached Drive; `role_titles` will meet the same fate unless the owner redeploys. This is now a
  **blocking prerequisite** for the Drive leg, not a nice-to-have.
