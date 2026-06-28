# AGENTS — how to work on Warp Compass

This is the operating protocol every contributor (human or AI) follows so work is picked up
cleanly mid-stream and **no context is lost**. It is short on purpose. Read it once, then live
by [`PROGRESS.md`](./PROGRESS.md).

## The loop (every work session)

1. **Read `PROGRESS.md` top-to-bottom.** It is the source of truth: status, task board,
   blockers, the append-only handoff log.
2. **Pick a task** from the board that is `TODO` and whose dependencies are `DONE` (see the
   dependency spine). Prefer the **Next up** queue.
3. **Claim it:** set the row to `IN-PROGRESS`, put your id in *Owner*, and add a line under
   *Active / claimed*. This prevents two agents colliding.
4. **Open the phase brief** in `docs/plan/phase-NN-*.md` — **read its `## Context Card` first**
   (verbatim signatures + pointers so you can skip most source reading), then the objective, steps,
   files, and definition of done. Don't re-derive the design; it's in `docs/02-technical-approach.md`.
   See **Context economy** below before you start fanning out searches.
5. **Do the work** in the right package (`brain/`, `pwa/`, `worker/`). Match existing patterns.
6. **Verify** against the phase's done-definition (tests pass, contract honored).
7. **Update the board:** set the row to `REVIEW` or `DONE`, refresh the status snapshot, remove
   your *Active/claimed* line, and **append a handoff-log entry** (Did / Next / Gotchas, newest
   on top). Never edit past handoff entries. **Also write/refresh the NEXT phase's `## Context
   Card`** (rule 1 under *Context economy*) — this is the cheapest moment to capture the exact
   signatures the next agent needs.
8. **Record any decision** you made (a tradeoff, a version pin, a deviation) in
   `docs/DECISIONS.md` as a new ADR row.

## Definition of done (applies to every task)

- The phase's own acceptance criteria are met.
- Code is typed and linted (`uv run ruff check .` for Python; `npm run typecheck` for TS).
- Tests for the new behavior pass (`uv run pytest`; add `-m "not neo4j"` for the no-DB subset).
- The relevant **contract** in `contracts/` is honored (and updated + version-bumped if the
  contract itself changed — flag contract changes loudly in the handoff log).
- `PROGRESS.md` is updated and a handoff entry is appended.

## Load-bearing rules (do not undo — see `docs/02 §4`)

- **Two planes, one contract.** The runner (phone) only **writes** the Answer Log; the brain
  only **reads** it. The phone **never** touches the graph. Keep all graph logic in `brain/`.
- **LLM proposes, deterministic rules dispose.** The LLM only proposes candidate nodes against
  the fixed ontology; the **create gate** (code) decides merge / conflict / create / quarantine.
- **Constrain to the ontology.** No inventing node/edge types or category codes; new ones go to
  a review queue, never straight into the graph.
- **Graph is re-derivable.** The raw Answer Log is immutable truth; never hand-edit the graph —
  improve the extractor and re-run instead.
- **Keys live only in the Worker.** Never embed API keys in the PWA.
- **Everything swappable.** New external deps go behind their interface (`GraphStore`,
  `VectorIndex`, and the upcoming `STTProvider`/`TTSProvider`/`LLMProvider`/`Bus`).

## Context economy (keep agent pickup cheap — read this)

A fresh agent (new terminal) starts with an empty context window. The expensive part of pickup is
**not** re-reading what happened — the handoff log tells you that cheaply — it's **re-deriving the
exact code shapes** (signatures, field names, ids) because prose can't be trusted to still match
code. Target **~30–50k tokens** to get build-ready. The rules below make that the default; follow
them so the *next* agent is cheap too.

1. **Every phase brief opens with a `## Context Card`** — the verbatim signatures, ids, and file
   pointers that phase depends on, so the agent reads one block instead of six files. **When you
   finish a phase, write/refresh the NEXT phase's Context Card** while that context is fresh in your
   head (you pay it cheaply; the next agent saves thousands of lines of source reading). Template:
   ```
   ## Context Card — read THIS, skip the source
   - Data shapes (authoritative): contracts/<x>.schema.json   ← read schemas, NOT the code mirrors
   - <Symbol/signature you depend on, verbatim>  @ <file:line>
   - <Constant / model-id / config key + its confirmed value>
   - Run: <the exact command(s), from which dir>
   ```
2. **Point at `contracts/` for any data shape**, never at the pydantic/TS mirrors. The JSON Schemas
   are small, stable, and authoritative; `planner.py`/`models.py` are large and re-derive them.
3. **Ration discovery.** Prefer `Read`ing the specific files the handoff/Card names over fanning out
   `Explore`/`general-purpose` agents — those return multi-thousand-token reports and were the single
   biggest pickup cost. Cap at **one** Explore agent, and only when scope is genuinely unknown.
4. **Search scope:** only `brain/src`, `pwa/src`, `worker/src`, `contracts/`, `docs/`, and the
   board/briefs. **Never** glob `node_modules`, `.venv`, `dist`, `_state`, or `_bus` — they're noise.
5. **Docs are pointers + signatures, not re-narrated code.** Duplicating how code works in prose
   makes it drift, and then the agent reads *both* doc and code to reconcile them — the opposite of
   the goal. Keep the **handoff log** as-is (Did/Next/Gotchas — high value per token; never trim it).

## Conventions

- **Agent id:** use a short stable handle, e.g. `agent:<model-or-name>-<short-purpose>`.
- **Commits (when git is initialized):** `<area>: <imperative summary>` where area ∈
  `brain|pwa|worker|contracts|docs` (e.g. `brain: add create gate`).
- **Where things live:** intelligence → `brain/`; UI/voice → `pwa/`; key proxy → `worker/`;
  cross-language schemas → `contracts/`; specs/plans → `docs/`.
- **Don't expand scope silently.** Out-of-scope ideas go to *Blockers & open questions* or a
  phase doc's "Out of scope", not into code.
