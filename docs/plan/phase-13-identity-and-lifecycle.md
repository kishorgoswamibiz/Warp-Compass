# Phase 13 — Declared identity + participant lifecycle

> **Decision context (owner, 28 Jul 2026):** field testing is moving from one person (the owner)
> to a broader team. Three problems surfaced: (1) the bot asks *"tell me about your role"* on
> every cold session because nobody is ever asked who they are; (2) Drive folders and graph
> provenance are named `p_<uuid>`, so no artifact is attributable by looking at it; (3) there is
> no way to remove a user when a seat changes hands mid-test.
>
> The owner's explicit ruling on (3): **removing a user must never mutate the knowledge graph.**
> A rebuild costs LLM spend and re-extraction risk, and the graph is deliberately entangled —
> one node can carry facts from a Business Analyst and a Project Manager at once. We retire the
> *person*, keep the *knowledge*, and let the questions they left behind be answered by whoever
> is still in the engagement. ADRs #29 and #30 record this.

---

## 1. Goals (from the owner)

1. **Ask name + role exactly once per device**, then never again — not on session two, not on a
   cold start, not ever.
2. **Every artifact is attributable at a glance** — a Drive folder, a graph Facts line, and the
   deliverable should name a person, not a UUID.
3. **Removing a user is simple and cheap** — delete the person, keep the brain. No graph surgery,
   no LLM calls, low hallucination surface, small enough to trust.
4. **The retired person's open questions survive** and get asked to whoever remains. If someone
   left a process half-described, a teammate should be able to finish the story.
5. **A clean-slate procedure** the owner can run before handing the app to the broader team.
   Manual steps are acceptable; a script is a bonus.

Explicitly **not** a goal: per-persona graph deletion. See §8.

---

## 2. What's broken today (verified in code)

| # | Symptom | Root cause |
|---|---|---|
| A | Bot re-asks the role every cold session | `COLD_START_OPENERS[0]` (`pwa/src/runner/prompts.ts:20`, mirrored `planner.py:50`) fires whenever no brief exists — including *every* session before the operator's first `run-round` |
| B | Nobody is ever asked their name | `getParticipant()` (`pwa/src/sync/participant.ts:39`) mints `p_<uuid>` silently. `setDisplayName()` exists and is unit-tested, but **no UI calls it** — `display_name` is permanently `undefined`, and `remote.ts:32` pushes that `undefined` to Drive |
| C | Drive folders unreadable | `participantDir_()` (`apps-script/Code.gs:134`) keys the folder on `participant_id`, i.e. the UUID |
| D | Graph provenance unreadable | `cycle.py:130` uses `persona_id` (= the same UUID) as `said_by`, stamped on every node and edge |
| E | No delete path exists | Nothing in the PWA, Apps Script, or CLI removes a participant. `GraphStore` has no `delete_node`/`delete_edge`; `VectorIndex` has no `remove` |

Two further defects, found while designing the fix, are what actually make this phase non-trivial:

### Finding 1 — archiving a folder doesn't stick; the next round recreates it

`Planner.personas()` (`planner.py:123`) enumerates personas from **graph provenance**, not from
the bus. So a retired persona is still planned for. `cycle.py:104` then does:

```python
participant_id = persona_to_participant.get(brief.persona_id, brief.persona_id)
```

The fallback resolves to the persona id, and `FolderBus.write_brief` (`bus/folder.py:66-69`)
calls `d.mkdir(parents=True, exist_ok=True)` — **recreating the folder the operator just
archived**, with a fresh brief inside it. Without fixing this, "just delete the folder" silently
does not hold.

### Finding 2 — a retired person's open questions go permanently silent

`Planner.plan()` (`planner.py:143`) restricts each persona's gaps to `subgraph_ids` — the nodes
*that persona* contributed to. When Rahul retires, nodes only he ever touched belong to nobody's
subgraph, so their gaps are never surfaced to anyone again. Goal 4 is therefore **not** a
property we get for free by leaving the graph alone; it needs a redistribution mechanism.

---

## 3. The identity model

### 3.1 The id

Minted **once**, at onboarding, from the declared name and role:

```
rahul-ba-3c1f          ← <name-slug>-<role-slug>-<4 hex>
kishor-g-sales-lead-7f3a
```

- **Slugging:** lowercase, strip diacritics, non-alphanumeric → `-`, collapse repeats, trim.
  Each part capped at 24 chars, so the full id stays under ~55 — leaving Windows `MAX_PATH`
  headroom for `%BUS_ROOT%\participants\<id>\answer_logs\s_….json`.
- **4-hex suffix** (`crypto.getRandomValues`) keeps two people named Rahul apart.
- **Empty or unslugabble input** falls back to `user-<8 hex>`.
- **Reserved:** an id may not begin with `_` (protects `_archive`, `_retired.json`).
- `persona_id` remains `== participant_id` (ADR #17, 1:1, unchanged).

> **The id is immutable after minting.** It is stamped permanently into graph provenance, so a
> later correction to the person's name updates `display_name` only — **never** the id. This
> rule is load-bearing; breaking it orphans every Facts line that person contributed.

### 3.2 The stored record

`localStorage["wc.participant"]` grows from two fields to five:

```json
{
  "participant_id": "rahul-ba-3c1f",
  "persona_id":     "rahul-ba-3c1f",
  "display_name":   "Rahul Mehta",
  "role_title":     "Business Analyst",
  "onboarded_at":   "2026-07-28T09:12:00Z"
}
```

`getParticipant()` changes signature from *"mint on demand"* to `Participant | null`, plus a
`createParticipant({name, role})` and a `requireParticipant()` for the session path where
onboarding is already guaranteed. `App.tsx` gates the landing screen on it.

**Legacy `p_<uuid>` devices** (a record with no `role_title`) are treated as not-onboarded: the
card shows once, a new readable id is minted, and `previous_id` is recorded on the new record for
traceability. The old UUID folder is abandoned, not migrated — it is test data, and migrating it
would mean rewriting provenance, which §3.1 forbids.

### 3.3 The onboarding card

A typed form, shown once, before the first session:

```
┌──────────────────────────────┐
│  Before we start             │
│  Your name  [ Rahul Mehta ]  │
│  Your role  [ Business An… ] │
│         [ Continue → ]       │
│  Asked once on this device.  │
└──────────────────────────────┘
```

Typed, not spoken — deliberately. STT would mangle "Rahul" into "Raul" or "Rahool", and that
guess would become a **permanent** folder name and provenance key (§3.1). Identity is a system
key; it must not ride on a transcription guess. The warmth is recovered immediately afterwards
by the bot's greeting (§4).

---

## 4. Never asking twice

Three coordinated changes, none of which cost an LLM call:

1. **`runner.start()`** (`pwa/src/runner/runner.ts:63`) — when identity is known and the brief is
   a cold start, skip `COLD_START_OPENERS[0]` and open with a greeting built from the identity:

   > *"Hi Rahul — you're the Business Analyst. Let's map your day from the very beginning: what's
   > the first piece of work that lands on your plate, and what kicks it off?"*

   Deterministic string assembly, so it stays testable without a live model.

2. **`buildUserPrompt()`** (`prompts.ts:97`) — prepend a `=== WHO YOU'RE TALKING TO ===` block
   carrying name and role. This is what stops the model re-asking on turn nine when the person
   circles back, which a start-only fix would miss.

3. **`Runner` constructor** — `opts` gains `identity?: { display_name, role_title }`, passed from
   `SessionScreen.tsx:121`. It already accepts `participantId`, so this is an additive change.

### 4.1 Seeding the role into the graph

The onboarding answer is written as the Answer Log's **first entry**:

```json
{
  "kind": "free_narration",
  "thread_id": null,
  "agent_utterance": "Before we start — what's your name, and what's your role?",
  "raw_answer": "I'm Rahul Mehta, I'm the Business Analyst.",
  "ts": "2026-07-28T09:12:00Z"
}
```

The extractor then mints `roles/role.business-analyst.md` from turn zero, instead of waiting for
the person to mention their role in conversation.

Two things to be honest about:

- **`raw_answer` is assembled from form fields, not transcribed.** The schema calls this field
  "verbatim transcript". This is a deliberate, documented deviation (ADR #29): the person *did*
  answer that exact question, just by typing two fields instead of speaking a sentence. The
  alternative — an `identity` block in the log header — would require editing
  `contracts/answer-log.schema.json`, which is `additionalProperties: false`, and would break the
  one contract both planes depend on. The entry route needs no schema change.
- **The person's name does not reach the graph.** P12's extractor rule abstracts personal names
  into organizational roles, so "I'm Rahul Mehta, I'm the Business Analyst" yields
  `role.business-analyst` and drops "Rahul". That is correct and intended — the name lives in
  `profile.json`, the role lives in the graph. People change; roles persist.

---

## 5. Readable Drive and readable graph

Most of this falls out of §3.1 for free, because `said_by` *is* the participant id:

```
participants/rahul-ba-3c1f/          ← was participants/p_3f9a1c8e-…/
  README.md                          ← new
  profile.json                       ← now carries display_name + role_title
  answer_logs/ · briefs/

graph/activities/act.check-stock.md
  ## Facts
  - 2026-07-28 — rahul-ba-3c1f (session s_20260728_0912, confidence 0.7, unverified)
```

Two additions the owner asked for:

- **`README.md` per participant folder** — display name, role, first seen, session count.
  Written by `writeProfile_()` in `apps-script/Code.gs` alongside `profile.json`, on every push,
  so it stays current without the brain being involved.
- **Named personas in the deliverable** — `docgen/render.py` resolves `persona_id` →
  `"Rahul Mehta (Business Analyst)"` from the bus profiles, falling back to the raw id for
  retired or unknown personas. Roughly 15 lines plus a lookup passed in from the CLI.

Session filenames stay as `s_<stamp>.json`. They are the resume key in
`profile.json["ingested_logs"]`, the folder already names the person, and renaming them buys
readability we already have while risking the resume logic.

---

## 6. Retiring a user

### 6.1 The model

> **Retire the person. Keep the knowledge. Redistribute the questions.**

Retiring is a **bus-level** operation. `graph/` is never opened, never written, never read.
Zero LLM calls, byte-identical graph before and after — asserted in tests (§10).

### 6.2 `retire-participant`

```powershell
uv run python -m warp_compass_brain.cli retire-participant --id rahul-ba-3c1f [--dry-run] [--hard-delete]
```

1. Verify `participants/<id>/` exists (else exit 1 with the live list).
2. Move it to `_archive/<id>__2026-07-28/`. Archive by default; `--hard-delete` skips the copy.
   *(Archive directory names keep a sortable `YYYY-MM-DD` stamp so the folder listing orders
   chronologically; every human-facing date in output and docs uses `dd MMM yyyy`.)*
3. Append to `{BUS_ROOT}/_retired.json`:
   `{ id, display_name, role_title, retired_at, archived_to }`.
4. Print exactly what moved. **Never touches `graph/`.**

Google Drive's 30-day trash is the second backstop behind `_archive/`.

A companion `list-participants` prints live and retired participants with display names and
session counts — the operator's "who is in this engagement?" view.

### 6.3 Fixing Finding 1 — brief distribution respects the bus

`cycle.py:104`'s fallback is removed. A brief is written **only** to a participant that currently
exists in the bus. The two failure modes are then deliberately distinguished:

| Persona's folder | In `_retired.json` | Behaviour |
|---|---|---|
| missing | yes | skip silently; count as `retired_skipped` |
| missing | **no** | skip **and warn loudly** — almost certainly Drive hasn't synced down, and silently swallowing this would look identical to a retirement |

That distinction is the whole reason `_retired.json` exists rather than just inferring retirement
from an absent folder.

### 6.4 Fixing Finding 2 — the orphan thread pool

A node is **orphaned** when every `said_by` in its provenance is retired. Gaps on orphaned nodes
become threads that are appended to **every live persona's** brief, with:

- **A priority floor** — always ranked below all of that persona's own-subgraph threads, so they
  can never crowd out a person's own work.
- **A cap** — `orphan_max`, default 2 per brief.
- **Third-person framing** — the current person didn't say this, so the opener must not pretend
  they did. `why` reads *"raised by a teammate no longer in the engagement"*, and the opener is
  prefixed: *"A colleague described a step called 'Check stock' — do you know how that part
  works?"*

Offering the same orphan thread to several people is intentional, not waste: two independent
answers to the same question is exactly what `ingest.py:165` promotes to `confirmed`.

### 6.5 "Switch user" in the PWA

A quiet link on the landing screen clears `wc.participant` and reloads into onboarding. Copy must
be unambiguous that this is **device-local**:

> *Switching user only resets this device. Answers already sent stay with the team's records —
> ask your facilitator to retire the old user.*

Deletion stays operator-only. Exposing `retire-participant` through the PWA would let any end
user — or anyone who guesses an id — remove data.

### 6.6 One accepted consequence

If a replacement holds the same seat, their nodes merge with their predecessor's, and
`ingest.py:165` will see two distinct `said_by` values and promote the node to `confirmed` —
when it is really one chair, corroborated once. Confidence is mildly overstated.

Accepted for now; harmless at testing volume. If it ever matters, a `replaces: <old_id>` field on
the successor's profile plus a check in `CrossPersonaEngine` would collapse the lineage into one
voice. Not built in this phase.

---

## 7. Clean slate before the broader rollout

Five places hold state. All can be done by hand; steps 1–2 are what the script automates.

1. **Drive** — delete `%BUS_ROOT%\participants\*` and `%BUS_ROOT%\graph\`.
2. **Local brain state** — delete `brain\_state\vectors.sqlite` (20 KB of Jun 2026 test vectors),
   plus `quarantine.jsonl` and `pending_taxonomy.jsonl` if present.
3. **`deliverable.md` is committed with test data in it** — it currently names `persona.demo` and
   `p_alice`. Regenerate or blank it; a new team member will otherwise read it as a sample output.
4. **The owner's own test phones** — each holds `wc.participant`. After this phase, "Switch user"
   handles it; before it, clear site data. New team members are clean by definition.
5. **`PROGRESS.md`** — add the P13 row and a handoff entry.

Optional command:

```powershell
uv run python -m warp_compass_brain.cli reset-engagement --dry-run
uv run python -m warp_compass_brain.cli reset-engagement --yes
```

Refuses to run without `--yes`; `--dry-run` prints counts and touches nothing; `--keep-archive`
preserves `_archive/`. Worth building because this is a command the owner will run *repeatedly*
during testing, and a half-completed manual checklist (graph cleared, vectors kept) produces
confusing dimension-mismatch errors rather than an obvious failure.

**Verify clean:** `run-round` reports zero participants, and `graph/index.md` shows zero across
every type.

Two rollout items unrelated to data cleanliness, worth confirming before the team installs:
the Cloudflare Pages **Production** secrets (`APPS_SCRIPT_URL`, `SYNC_SHARED_SECRET`) are set,
and testers fully close and reopen the PWA once so the service worker takes the new build instead
of serving a cached one.

---

## 8. What this phase deliberately does NOT build

**Per-persona graph deletion**, in either form:

- *Full rebuild* (wipe `graph/`, re-ingest remaining logs) — exact, but costs LLM spend on every
  removal, growing linearly with the engagement, and re-runs extraction over text that was
  already extracted once, reintroducing variance into knowledge that had settled.
- *Surgical prune* (strip that persona's provenance, delete orphaned nodes, recompute confidence)
  — free and fast, but needs new `GraphStore.delete_node`/`delete_edge` and `VectorIndex.remove`
  seams, ~250 lines of ripple-effect logic, and still leaves residue: aliases and descriptions
  that person contributed to a *surviving* node were folded in by `ingest.py:158-161` and cannot
  be unwound.

The owner's reasoning, recorded verbatim in ADR #30: context is shared, so deletion machinery is
risk with no upside during a discovery engagement. Questions left behind by a departed teammate
are not garbage to be collected — they are open questions about the business, and the business
still exists. §6.4 asks them to someone else instead.

---

## 9. Files

**PWA**
- `pwa/src/sync/participant.ts` — identity record, slug minting, `createParticipant`,
  `requireParticipant`, `clearParticipant`, legacy-uuid detection
- `pwa/src/screens/OnboardingCard.tsx` — **new**
- `pwa/src/App.tsx` — gate on onboarding; identity line replaces the `shortId` line; "Switch user"
- `pwa/src/screens/SessionScreen.tsx` — pass identity into `Runner`; seed the first log entry
- `pwa/src/runner/{runner,session,prompts}.ts` — greeting, identity prompt block, opener skip
- `pwa/src/sync/remote.ts` — push `role_title` alongside `display_name`

**Sync**
- `pwa/functions/_sync.ts` — forward `role_title`
- `apps-script/Code.gs` — persist `role_title`; write `README.md`

**Brain**
- `brain/src/warp_compass_brain/bus/{base,folder}.py` — `list_retired`, `retire`, `archive_dir`
- `brain/src/warp_compass_brain/cycle.py` — Finding 1; `retired_skipped` + warning in the summary
- `brain/src/warp_compass_brain/planner.py` — orphan thread pool; accept `retired_personas`
- `brain/src/warp_compass_brain/lifecycle.py` — **new**: retire + reset primitives
- `brain/src/warp_compass_brain/docgen/render.py` — persona display names
- `brain/src/warp_compass_brain/cli.py` — `retire-participant`, `list-participants`,
  `reset-engagement`
- `brain/src/warp_compass_brain/config.py` — `planner_orphan_max` (default 2)

**Docs**
- `OPERATOR-MANUAL.md` — §7 "Retiring a user", §8 "Starting a clean engagement"
- `PROGRESS.md` — P13 row + handoff entry · `docs/DECISIONS.md` — ADR #29, #30

---

## 10. Test plan

**PWA (`vitest`)**
- Slug minting: diacritics, punctuation, over-long names, empty input → `user-<hex>`, `_` prefix
  rejected, two identical names → distinct ids
- `getParticipant()` returns `null` before onboarding; stable across calls after
- Legacy `p_<uuid>` record → detected as not-onboarded; new id minted; `previous_id` recorded
- Identity known → opener is **not** `COLD_START_OPENERS[0]` and contains the first name
- Identity absent → behaviour byte-identical to today (protects the offline fallback path)
- The built Answer Log's first entry is the identity entry, and validates against
  `contracts/answer-log.schema.json`

**Brain (`pytest`)**
- `test_cycle.py`: persona with no participant folder → **no brief written and the folder is not
  recreated** (assert the path still does not exist — this is Finding 1's regression test);
  retired → silent; missing-but-not-retired → warns
- `test_planner.py`: orphan gaps appear in every live persona's brief, below own threads, capped
  at `orphan_max`; a node with one live contributor is **not** orphaned; own-subgraph threads
  unaffected
- `test_lifecycle.py` (**new**): retire moves the folder, writes `_retired.json`, and leaves
  `graph/` **byte-identical** — hash the tree before and after; `--dry-run` mutates nothing;
  `reset-engagement` without `--yes` refuses
- `test_docgen.py`: display names render; unknown/retired persona falls back to the raw id

Full suite must stay green with **no services running** (the P12 property).

---

## 11. Done when

Status as of **28 Jul 2026** — built, unit-verified, and CLI smoke-tested. The last box needs the
owner's localhost run.

- [x] A fresh device shows the onboarding card once, and never asks name or role again — including
      across two sessions **before** any `run-round`, which is the case the old cold-start path got
      wrong (`runner.test.ts`: greeting, opener skip, and the per-turn prompt block)
- [x] Drive shows `participants/rahul-ba-3c1f/` with a readable `README.md` (`Code.gs`)
- [x] `graph/**/*.md` Facts lines name people (provenance *is* the id); `deliverable.md` reads
      "Rahul Mehta (Business Analyst)" (`test_docgen.py`)
- [x] `role.business-analyst` reaches the graph from turn zero via the seeded first entry, which
      still validates against `answer-log.schema.json`
- [x] `retire-participant --id X` archives the folder, and the **next `run-round` does not recreate
      it** (`test_cycle.py::test_retired_persona_gets_no_brief_and_its_folder_is_NOT_recreated`)
- [x] `graph/` is byte-identical across a retirement
      (`test_lifecycle.py::test_retiring_leaves_the_graph_byte_identical` — tree hash before/after)
- [x] X's unanswered questions appear in a live teammate's next brief, framed third-person, capped,
      and ranked below their own work (`test_planner.py`)
- [x] `reset-engagement --yes` clears participants + graph + roster + state; refuses without
      `--yes`; `--dry-run` changes nothing
- [x] Full `pytest` (**100 passed**) + `vitest` (**45 passed**) green, `ruff` clean, PWA
      `npm run build` and worker `typecheck` green
- [ ] Live round exercised end-to-end on a real device (owner's localhost run)

---

## 13. As built — where the implementation went beyond this plan

Five things the plan didn't anticipate. All are in the code and covered by tests.

1. **`identity_seeded_at` on the participant record.** §4.1 said "seed the first entry" without
   saying *when to stop*. Seeding on every session would re-ingest the same introduction every
   round. Seeding once at onboarding would lose the Role node if that first session were abandoned.
   So the stamp is written when a log carrying the entry actually **leaves the device** (push or
   download) — self-healing, and exactly-once in the normal path.

2. **`AnswerLogBuilder.answerCount()`.** The seeded entry is a real log entry but not something the
   person said, so the end-of-session "N answers captured" would have been off by one. `count()`
   is what goes to the brain; `answerCount()` is what the UI reports.

3. **A warm-start greeting too.** The plan only specified the cold-start greeting. A returning
   person now gets *"Welcome back, Rahul."* before the top thread's opener — the same one-line
   change, and it would have felt strange to be greeted by name only on day one.

4. **The planner skips retired personas outright** (`live_personas()`), rather than relying on
   `cycle.py` to drop their briefs at distribution. Building a brief costs a full completeness
   pass, and nobody would read it. The `cycle.py` guard stays as defence-in-depth, since a planner
   that doesn't know about retirement (a test double, a future implementation) must still not
   recreate folders.

5. **`reset-engagement` path scoping — a footgun caught in smoke testing.** The command resolved
   the graph root and `_state/` paths from *settings*, not from the bus it was pointed at. So
   `--bus <scratch> --yes` deleted the configured engagement's vector state (it wiped a stale
   `vectors.sqlite` during testing — gitignored and self-rebuilding, so no loss, but the next run
   on real data would not have been so lucky). Now the graph resolves against the given bus, and
   `_state/` is cleared **only** when resetting the configured bus, with the skip printed
   explicitly. Regression test:
   `test_lifecycle.py::test_reset_only_touches_the_state_files_it_is_handed`.

Two further defects surfaced on review after the first implementation pass, both fixed:

6. **The download fallback marked the identity as seeded.** If a push failed and the person
   downloaded their log instead, `identity_seeded_at` was stamped — so if the operator never
   dropped that file into `answer_logs/`, the Role node was lost and **no later session would
   re-seed it**. Silent, permanent. Now only a *successful push* marks it. Being wrong the other
   way costs one duplicate introduction that merges into the same node, which is the right side to
   err on.

7. **A restored participant would silently receive no briefs.** Retire someone, later drag their
   folder back out of `_archive/` without clearing `_retired.json`, and they'd be on the bus *and*
   marked retired: `cycle` maps their folder happily while the Planner excludes them from
   `live_personas()`. No brief, no warning. `lifecycle.effective_retired()` now defines retired as
   *marked **and** absent from the bus* — the folder is the registry, so the folder wins.

---

## 14. Risk register (as built)

What could still bite, honestly rated. Nothing here blocks the localhost run; items 1–2 are worth
a decision before the engagement carries real client data.

| # | Risk | Likelihood · Impact | Where it stands |
|---|---|---|---|
| 1 | **Readable ids are guessable.** Any legitimate app user can edit `localStorage` and push logs into someone else's folder. The shared secret keeps *outsiders* out, but P13 traded an unguessable `p_<uuid>` for a slug whose only unguessable part is 4 hex (65 536 options). | Low · Medium | **Accepted for now.** Threat model is trusted colleagues inside one engagement. If it ever matters: mint a per-participant token at onboarding and require it on push. Worth revisiting before any client-facing deployment. |
| 2 | **One human, two personas.** Clearing site data, switching browser, or a new install re-onboards → new id → their knowledge splits in two. Worse, cross-persona corroboration reads the two halves as two independent voices and can promote a fact to `confirmed` on one person's say-so. | Medium · Medium | **Not mitigated.** Same root as the successor-seat consequence (§6.6). Operator fix: retire the stale id. A `replaces:` lineage field would solve both at once. |
| 3 | **Orphan threads can repeat forever.** The same top-2 orphans surface every round until answered. If genuinely nobody knows, live personas get asked the same inherited question round after round. | Medium · Low | **Bounded, not solved.** Capped at `planner_orphan_max` (default 2) and ranked last; set it to `0` in `brain/.env` to switch the pool off entirely. Same shape as an unanswered own-thread, just likelier to persist. |
| 4 | **`reset-engagement` doesn't invalidate devices.** A test phone still holding a pre-reset identity will recreate its participant folder on its next push — so a "clean" bus quietly repopulates with an old id. | High during testing · Low | **Documented, manual.** `OPERATOR-MANUAL.md` §1d step 1: clear each test device with **Switch user**. Unavoidable without server-side identity. |
| 5 | **Legacy `p_<uuid>` folders linger.** After the update, old devices re-onboard and their old folders stay behind — still on the bus, still receiving briefs nobody reads. | High once · Very low | Retire them (`retire-participant`) or let `reset-engagement` clear them. Cosmetic clutter only. |
| 6 | **Id collision.** Two people with the same name *and* role collide at 1-in-65 536 — they'd share a folder and merge into one persona, undetected. | Very low · High | **Accepted.** Detectable by eye in `list-participants` (two entries can't share an id, so it shows as one person with unexpected sessions). |
| 7 | **README write costs a Drive listing per push.** `writeReadme_` enumerates `answer_logs/` to count sessions on every push. | Certain · Negligible | Fine at prototype scale (tens of files). Revisit only if Apps Script quotas start biting. |

---

## 12. Risks & decisions

| Risk | Mitigation |
|---|---|
| A typo'd name becomes a permanent id | `display_name` is editable and used for all display; the id is internal and appears only in folder names and Facts lines. Documented as immutable (§3.1) |
| Two devices, one person → two personas | Accepted at prototype scale. The graph treats them as two voices, which mildly inflates corroboration. Same shape as §6.6 |
| Orphan threads annoy people with irrelevant questions | Priority floor + `orphan_max` cap + third-person framing. Tunable in one config value |
| Operator retires the wrong person | `--dry-run`, archive-by-default, Drive's 30-day trash, and `graph/` untouched — so the knowledge survives even a mistaken retirement. Only the folder needs restoring |
| `raw_answer` isn't literally verbatim for the identity entry | Documented deviation, ADR #29. The alternative breaks a frozen contract shared by both planes |

**New ADRs to record:**

- **#29 — Identity is declared once per device and becomes the participant/persona id.** A typed
  onboarding card collects name + role; the id is a readable slug minted once and immutable
  thereafter; the onboarding answer is seeded as the Answer Log's first entry (a documented
  deviation from strict verbatim, chosen over editing the frozen answer-log contract).
- **#30 — Retiring a participant never mutates the graph.** Removal is a bus-level archive plus a
  `_retired.json` marker. Per-persona graph deletion (rebuild or prune) is explicitly rejected:
  context is shared between roles, deletion machinery carries risk with no discovery upside, and
  a departed teammate's open questions are redistributed to live personas (§6.4) rather than
  deleted.

**Unchanged:** ADR #17 (persona 1:1 with participant), ADR #4 (graph re-derivable from immutable
Answer Logs — still true, and still the escape hatch if a rebuild is ever genuinely wanted).
