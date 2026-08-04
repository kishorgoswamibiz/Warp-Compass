# Warp Compass — Data Contracts

The machine-readable source of truth lives in `../contracts/` (JSON Schemas + `ontology.json`).
The Python brain mirrors these in `brain/src/warp_compass_brain/models.py`; the TS planes will
share them too. **If you change a contract, bump its version and flag it loudly in `PROGRESS.md`.**

## 1. The ontology (the completeness compass) — `contracts/ontology.json`

Not a list of questions — the internal definition of "what a complete picture looks like". The
LLM may only ever **choose from** these; anything new goes to a review queue.

**Node types (12):** **`Stage`**, `Role`, `Activity`, **`Objective`**, `System`, `Artifact`, `Event`,
`ApprovalPoint`, `Rule`, `Problem`, `Desire`, `KPI`.

**Edge types (17):** `PERFORMS` (Role→Activity), `USES` (Activity→System), `PRODUCES`,
`CONSUMES` (Activity↔Artifact), `TRIGGERS` (Event→Activity), `REQUIRES_APPROVAL_FROM`
(Activity→Role), `HANDS_OFF_TO` (Activity→Role), `ESCALATES_TO` (Role→Role), `GOVERNED_BY`
(Activity→Rule), `BLOCKS` (Problem→Activity), `MEASURED_BY` (Activity→KPI), `REPORTS_TO` (Role→Role),
and the P15b lifecycle spine: **`PART_OF`** (Activity→Stage), **`PRECEDES`** (Stage→Stage),
**`OWNS`** (Role→Stage), **`PURSUES`** (Role→Objective), **`OBJECTIVE_FOR`** (Objective→Stage).

### The lifecycle spine (P15b)

`Stage` is **the spine of the process map**: one phase in the journey a single piece of work takes
through the org (pre-sales → kickoff → discovery → build → UAT → go-live → support). Two rules:

- **Stages are discovered per organisation — never a predefined list** (ADR #33). Unlike the role
  registry, there is no `contracts/stages.json` and there must not be: assuming a stage set is the
  day-anchored assumption in a new costume. The extractor is told to discover theirs.
- **`PART_OF` is what makes the process map orderable.** Before it, `activity_flow()` could infer
  order *only* from handoffs and produced→consumed artifacts, and real interviews rarely yield
  complete artifact plumbing — so activities the business knows are fine were reported as
  `broken chain`. An activity in a correctly-positioned stage is now *located*; only the artifact
  link is missing, which is a `MISSING_FIELD`, not a break.

`Objective` is a stated intended outcome, recorded **as stated**. It doubles as an *expectation*: an
Objective a role attaches to a stage they don't `OWN` is, by construction, an expectation placed on
someone else — which is why there is no separate `Expectation` type (ADR #32 uses this for the
alignment findings).

**Completeness fields** (per node type) drive the gap detector — e.g. an `Activity` is "complete"
when its trigger, inputs, system, output, next handoff, **cadence**, exceptions and rules are known;
a `Stage` when its position, activities, owner and exit criteria are; a `Role` when its reporting
line and the work it performs are. **Until P15b only Activities were ever scored**, so `Role`'s
fields were declared and never measured — which is why nothing had ever driven the org chart to
completion. Two escape hatches keep otherwise-unclosable gaps from being asked forever:
`Activity.next_handoff` is satisfied by producing a final output nobody consumes (the work leaves the
org), and `Role.reports_to` by a truthy `key_attributes["reports_to"]` (the role at the top of the
org genuinely reports to nobody — which is also what makes it a usable root for derived altitude).
A node whose only provenance is `said_by: "registry"` is **not scored at all**: it is vocabulary, not
a claim about the business.

**`cadence`** is free text in `key_attributes`, in the answer's own terms ("every project", "per
opportunity", "only on escalation") — deliberately **not an enum**. Without it the graph could not
record that pre-sales demos are per-opportunity rather than daily.

**Taxonomy registry:** governed hierarchical **category codes** (e.g. `05`, `05.1`) used as a
many-to-many tag — these become the **section numbering of the final document** (Phase 10). P15b adds
`00 Lifecycle & Stages` (which sorts first, so the process spine leads the document) and
`11 Objectives & Expectations`.

## 2. Identity vs Type vs Category — three different jobs (§6.3)

A graph is not a tree, so one hierarchical code can't do all three. We separate:

- **Identity** — a stable, never-reused slug: `role.sales-manager`, `appr.discount-over-10pct`.
- **Type** — a fixed enum from the ontology.
- **Category code** — a governed, many-to-many tag from the taxonomy registry.

This keeps a Role a *single reusable node* that many approvals/escalations point to via edges —
no duplicate-role sprawl.

## 3. Node card — `contracts/node-card.schema.json`

The compact canonical record every node carries; what gets embedded and what the adjudicator
LLM reads when deciding "same or new". Key fields: `id`, `type`, `canonical_name`, **`aliases`**
(the dedup superpower), `description`, `category_codes`, `key_attributes`, `provenance[]`.

## 4. Confidence lifecycle (§6.5)

Status only rises with evidence:
`proposed → unverified (one source) → confirmed (corroborated by another persona/BA) → conflicting`.
The doc generator renders **`confirmed` only** by default — truth rises, noise stagnates.

## 5. Answer Log (runner → brain) — `contracts/answer-log.schema.json`

Immutable, append-only, **source of truth**. One file per session, one persona per session (no
diarization). Each entry: `thread_id` (or null for free narration), `kind` (`guided` |
`free_narration`), `agent_utterance`, **`raw_answer`** (verbatim — permanent), optional
`audio_ptr`, `ts`. The runner only ever writes this.

## 6. Session Brief (brain → runner) — `contracts/session-brief.schema.json`

The persona-scoped memory view + **ranked open threads**. **Guidance, not a script** — the runner
may reword and deviate. Each thread: `goal`, `why`, `priority`, `suggested_opener`, conditional
`followups`. On `cold_start: true` (empty brain) there are **no threads** — only generic openers.

## 7. Role registry — `contracts/roles.json` (P15a)

The engagement's **10 canonical roles** plus the conversational synonyms people actually say. Pattern
for every entry: **the full title is canonical, the abbreviation people say is an alias** — so the
deliverable reads formally and the conversation still matches.

```json
{ "slug": "role.delivery-specialist", "canonical_name": "Delivery Specialist",
  "aliases": ["Project Manager", "PM", "DS", "Delivery Manager"] }
```

**Three consumers, one source:**

| Consumer | How it reads the registry | Closed or open? |
|---|---|---|
| PWA onboarding chips | `pwa/src/sync/roles.ts` (committed mirror; `roles.test.ts` fails on drift) | **Closed** — you may only pick from the list |
| `cli seed-roles` | `brain/.../roles.py` → 10 `Role` nodes with `aliases` pre-loaded | — |
| Extractor prompt | a `KNOWN ROLES` block injected per call | **Open** — a preference, never a limit |

**Why the aliases are load-bearing.** `find_by_alias` is an **exact, case-insensitive whole-string
match** and the default embedder is a lexical hashing fallback. Without the alias table *"the PM
signs that off"* mints a rival `Project Manager` node with no owner, so the handoff routes back to
whoever mentioned them as *"who would know?"* forever, and the real Delivery Specialist is never
asked. See ADR #33 and `brain/tests/test_roles.py`.

**Two hard rules this contract carries:**

1. **Aliases must be unique across roles**, and must not collide with another role's canonical name.
   A duplicate alias silently **merges two real roles into one node** — the only failure mode the
   table itself can cause. Enforced by tests on both planes. (`"QA"` and `"QA Head"` are safe
   precisely because matching is whole-string.)
2. **`seed-roles` must run BEFORE the first `run-round`.** Answers ingested first mint role nodes
   under whatever name the extractor chose, and the aliases arrive too late to prevent the fork.

**Multi-role identity.** `Participant.role_titles: string[]` is the truth; `role_title` is the
**derived** `" / "`-joined mirror kept so every P13-era reader (the Drive `profile.json`, the
per-folder `README.md`, `lifecycle.py`, `cli list-participants`) works untouched. The participant id
is minted from the **first** role only and never moves when a hat is added or dropped (ADR #29) — the
id is a durable label, `role_titles` is the truth about what someone does.

**Stages are deliberately NOT a contract.** Roles are governed because the engagement knows them;
lifecycle stages are **discovered per organisation**, because a predefined stage list is the
day-anchored assumption in a new costume (ADR #33).

## Versioning

Each schema carries a `schema_version` (start `1.0.0`). Backward-incompatible changes bump major;
because the graph is re-derivable, an extractor/ontology improvement just means re-running the
pipeline over stored Answer Logs — no re-interviewing.
