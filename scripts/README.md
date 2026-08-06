# Operator scripts (prototype)

The prototype sync is **manual and sequenced once per round** (§3.2, §14). One round =
collect every participant's Answer Logs → run the brain → distribute each persona's Session
Brief. A second same-day session won't see others' input until the next round.

> **Status:** LIVE (Phase 8). `run-round` enumerates the bus, auto-onboards new participants,
> ingests new Answer Logs into the single graph, re-plans, and distributes briefs. The cross-persona
> *conflict* pass (step 3) lands in Phase 9; today the round does register → ingest → plan → distribute.

## The daily cycle
1. **Talk** — each participant runs a session in the PWA.
2. **Export** — each phone downloads its Answer Log; the operator drops it into that participant's
   `answer_logs/` on the shared bus (manual stand-in for networked sync, DECISION #8).
3. **Ingest + process** — `run-round` reads *all* new logs and runs the pipeline over the single
   OKF graph bundle (skipping logs already ingested — see each `profile.json`).
4. **Distribute** — the planner writes one Session Brief per persona into its `briefs/`.
5. **Resume** — each phone imports its latest brief; the next session is cross-pollinated.

## Run it
```
# Mac/Linux/Git-Bash:
scripts/run-round.sh --session s_2026_0630
# Windows PowerShell:
.\scripts\run-round.ps1 --session s_2026_0630
# Or directly (from brain/):
uv run python -m warp_compass_brain.cli run-round --session s_2026_0630 [--bus <path>]
```
Prereqs: `brain/.env` has the DeepSeek key (no database to start — P12). The bus defaults to
`settings.bus_root` (`brain/_bus`); pass `--bus` to point at the shared folder. The graph bundle
lives at `{bus_root}/graph` unless `GRAPH_ROOT` overrides it.

## Shared-folder (bus) layout — the user registry
```
<bus_root>/participants/{participant_id}/
    profile.json                # registry entry: participant_id, persona_id, ingested_logs[]
    answer_logs/                # phone writes here  (export)
    briefs/                     # brain writes here  (import)
```
Adding a user = sending them the same app link; the brain picks up the new subfolder on its
next run. No config, no fixed count. **The folder is the registry** — `profile.json` is created
automatically on first sight and records which logs are already ingested (the resume key).

## Files
- `run-round.sh` / `run-round.ps1` — one collect→register→ingest→plan→distribute round (Phase 8).
- `migrate_neo4j_to_okf.py` — one-off copy of a pre-P12 Neo4j graph into the OKF bundle
  (`uv run --with neo4j python ..\scripts\migrate_neo4j_to_okf.py` from `brain/`).
- `similarity_probe.py` — **run this before changing `similarity_ceiling`** (P17b). Reports every
  close node pair split by whether the two share a stage and a performer, then shows what each
  candidate ceiling would merge and what it would merge *wrongly*. Phase 17 planned to lower the
  ceiling and this probe is what showed that would delete real process distinctions — duplicates and
  genuinely-different work sit in the same cosine band (ADR #41).
  `uv run --extra vectors python ..\scripts\similarity_probe.py` from `brain/`.

> **Rebuilding the graph is a CLI command, not a script:** `cli rebuild-graph --yes` (P17b) replays
> every Answer Log, live and archived, after you improve the extractor or resolver. It never touches
> the bus. See `OPERATOR-MANUAL.md` §4. Do not confuse it with `reset-engagement`, which deletes the
> participant folders — i.e. the logs a rebuild reads.
