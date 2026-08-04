# ISSUES — bugs, limitations, and open risks

> **What belongs here:** defects, known limitations, and risks that cut **across** phases — anything
> that could bite during operation or testing. One row per issue, newest first within each table.
>
> **What does NOT belong here:** build progress. `PROGRESS.md` is the phase board and the append-only
> handoff log; it stays the single source of truth for *what has been built*. This file is the single
> source of truth for *what is wrong or unfinished*. When they overlap, link — never restate.
>
> **How to use it:** every issue gets an id (`WC-nn`, never reused). When you fix one, move its row to
> **§2 Resolved** with the commit sha; do not delete it. The **"Affects testing?"** column exists so
> the owner can tell at a glance whether an open issue should change how they run a session.
>
> **Status:** `OPEN` · `INVESTIGATING` · `PLANNED` (a plan doc exists) · `OWNER-ACTION` (not a code
> fix) · `ACCEPTED` (known trade-off, no fix intended) · `RESOLVED`.
>
> Last updated: 04 Aug 2026.

---

## 1. Open

| id | Status | Sev | Affects testing? | Issue |
|---|---|---|---|---|
| **WC-01** | OWNER-ACTION | High | **Yes** | **The live Apps Script Web App is still the P11 build.** `Code.gs` changes from P13 *and* P15a were committed but never deployed, so a phone push writes `profile.json` with no `role_title` / `role_titles` and no per-folder `README.md`. Fix is 2 minutes: Apps Script editor → *Manage deployments* → edit → **New version** (same `/exec` URL, no Cloudflare secret change). ⚠ **`apps-script/` is the one component `git push` does NOT deploy** — this is exactly how P13's changes sat dormant for 6 days. See `PROGRESS.md` Blockers. |
| **WC-02** | INVESTIGATING | High | **Yes** | **Two participant folders exist for what looks like the same human:** `kishor-goswami-business-analysis-specia-8750` and `…-f25b`. Same name+role slug, different 4-hex suffix — the signature of re-onboarding after clearing site data or using a second device (P13 risk, `phase-13` §14). Consequence: one person reads as **two personas**, so corroboration can promote a fact to `confirmed` on one human's say-so, and two accounts from the same person can register as a *peer conflict*. Could not confirm whether both have answer logs — the Drive read hung (see WC-07). **Decide before the next round:** if one is stale, `cli retire-participant --id <the stale one>`. |
| **WC-03** | PLANNED | High | Only with **2+ participants** | **A role a multi-hat person *declared* has no owner, so handoffs to it loop forever.** `crosspersona._role_owner_personas` defines ownership as "contributed this role's activities" and ignores the onboarding declaration. So a colleague's "I hand it to the Technical Specialist" finds no owner → `route_discoverer` → the **colleague** is asked *"who would know?"* every round, and the real person is never asked. Same failure shape as plan-15 §4.3, via hat attribution instead of naming. **Fix is deterministic, no LLM: a declared role is owned.** → `docs/plan/phase-16-hat-fidelity.md` **P16a**. |
| **WC-04** | PLANNED | Medium | **Yes, mildly** | **The extractor doesn't know who is speaking, so it can't tell which hat did the work.** `Extractor.extract(answer)` gets one answer's text and nothing else; `role_titles` never reaches the brain's extraction path. So *"I write the BRD"* only gets a `PERFORMS` edge if the **answer itself** names a role. During testing this shows up as activities with no owning role, thin per-role SOP sections, and roles appearing on `cli coverage`'s invite list even though the person *is* that role. **Does not affect interview quality.** → P16b. |
| **WC-05** | PLANNED | Medium | No | **A dual-hat person's altitude is undefined** when their two hats sit at different `REPORTS_TO` depths. `alignment._persona_role` picks one role (plan-15 risk **R5**), which decides whether a divergence is a reported finding or a defect to reconcile. Needs an org chart *and* a divergence to matter, so it can't bite single-person testing. → P16c. |
| **WC-06** | PLANNED | Low | No | **SOP presentation for multi-hat people** — cosmetic; work done under two hats should appear under each, with a note so the reader isn't surprised to meet the same name twice. → P16d. |
| **WC-07** | ACCEPTED | Medium | **Yes** | **Reads against the Drive bus can hang for minutes** — `G:` is Google Drive for Desktop over Dokan; when its request pool is exhausted every operation blocks or fails with `WinError 1450`. `fsretry.py` covers the *raising* case, not the *blocking* one; only "Available offline" fixes hangs (done for the bus folder, per P14). **Hit twice in this session**, including on `cli docgen`, which reads the bus for persona display names (`persona_display_names(FolderBus(...))`). **Workaround:** `cli docgen --bus <local scratch path>` generates the deliverable without touching Drive (names render as raw persona ids). |
| **WC-08** | INVESTIGATING | Low | **Yes** | **`cli list-participants` produced exit 0 and no output** when run 04 Aug 2026. Expected both participants. Possibly a Drive stall (WC-07) swallowing the listing, possibly a real regression — **not yet diagnosed, do not assume either.** Re-run it; if it stays silent, check `BUS_ROOT` resolution in `cli.py` against `lifecycle.list_participants`. |
| **WC-09** | ACCEPTED | Medium | Rarely | **Nothing re-examines two accounts that already merged as "same".** `MISALIGNMENT` needs a node flagged `CONFLICTING`, which comes from the adjudicator at ingest (`resolve.adjudicate` — a real semantic judgement, so genuine divergence *is* catchable). But if two accounts merge as *same*, no later pass revisits them. This is the remainder of ADR #23: P15c added the **retention** (`Provenance.account`) that a batch semantic tier would need, so the tier is now *possible* — just not built. |
| **WC-10** | ACCEPTED | Low | No | **Readable participant ids are guessable.** P13 traded an unguessable UUID for `name-role-4hex`, so any app user could push into another's folder. Fine for trusted colleagues; needs a per-participant token before untrusted users. (`phase-13` §14.) |
| **WC-11** | OPEN | Low | No | **PWA icons are placeholders** — the manifest references `icon-192/512.png`, generated by a zero-dep script rather than designed. |
| **WC-12** | OPEN | Low | No | **STT field accuracy has never been measured.** ElevenLabs Scribe is verified working on *clean* audio only. Before trusting the permanent-truth transcript, run `node scripts/stt-eval.mjs <dir>` from `pwa/` over ~20 real messy recordings (Indian-accented English, noise, SKUs/jargon) and record the WER here. |

---

## 2. Resolved

| id | Sev | Fixed in | Issue |
|---|---|---|---|
| **WC-R6** | High | `9583841` | **`cli coverage` crashed on a `cp1252` console.** The matrix used a tick mark (`U+2713`), which does not exist in the codepage Python gets for stdout on Windows — `print()` raised `UnicodeEncodeError` and took the command down. **It passed the live smoke test only because the empty-graph message happens to be ASCII**, so the failure needed real data. Render is now pure ASCII (`[x]` / `[ ]`); the test does `text.encode("cp1252")` — the operation that was actually failing, not a proxy. *Lesson: anything this codebase `print()`s must be ASCII; graph files are UTF-8 and may contain em dashes, terminal output may not.* |
| **WC-R5** | High | `5a6b806` | **Role attribution silently deleted misalignment findings.** `alignment._persona_role` answered "which role IS this person?" by first match over roles performing any activity they'd contributed provenance to. An exec who merely *comments on* someone else's activity picks up provenance on it — so the CEO was identified **as** the Account Management Specialist, both contributors collapsed onto one altitude, and the finding vanished **with no error**. Attribution now scores roles: sole-contributor activities first, then shared, then id. |
| **WC-R4** | Medium | `5a6b806` | **The process diagram and the walkthrough disagreed.** The diagram was grouped into Mermaid subgraphs per stage, but the narrative was still ordered by `activity_flow`, which can only order what artifact/handoff links happen to connect — so it printed Discovery's work *before* Pre-Sales'. Half-done spine rendering is worse than none, because the picture looks authoritative. Stage order now wins; flow order decides within a stage; unstaged work last. |
| **WC-R3** | Medium | `d3351be` | **A planner opener asked the wrong person about the wrong role.** `reports_to` read *"Who do you report to?"* — but a Role gap fires for **any** role in the persona's subgraph, including one they merely *mentioned*, so a BA would be asked about their own reporting line while the thread pointed at the QA Head's node. Both `reports_to` and `performs` now name the role. A test asserts every opener names its node. |
| **WC-R2** | Medium | `cf983db` | **A test passed for the wrong reason.** The "without aliases, resolution forks" test was propped up by a stub LLM that agreed with whatever retrieval ranked first — but with one Role node in the graph the lexical index returns it as a neighbour *whatever* its similarity, so the outcome actually depended on model taste. Rewritten to assert the load-bearing, determinable fact: without the alias table **no exact match protects the decision**. |
| **WC-R1** | High | `cf983db` | **`PROGRESS.md` said P15 had "no code yet" while 25 files of P15a sat uncommitted on disk.** An interrupted session had written most of P15a and logged nothing. *Lesson: on picking up mid-phase, `git status` before trusting the board.* |

Earlier resolved issues (P0–P14) are recorded in the `PROGRESS.md` handoff log rather than restated
here. The notable ones: the P14 Drive `WinError 1450` failures (`fsretry.py`), tolerant reads
swallowing a busy-drive error and causing paid re-ingest, brief distribution recreating archived
participant folders, nodes going permanently silent when their only contributor retired,
`reset-engagement` deleting the real graph when pointed at a scratch bus, and the batch extractor
dying on an unparseable LLM 200.
