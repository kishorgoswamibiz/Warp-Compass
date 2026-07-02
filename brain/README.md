# Warp Compass — Brain (cognition plane)

The laptop batch pipeline: **extract → resolve (create gate) → conflict/coverage → planner**
over an **OKF Markdown graph bundle** (no database server — P12). Python + [uv](https://docs.astral.sh/uv/).

> **Status:** all phases done (P0–P12). Operating routine: `../OPERATOR-MANUAL.md`. Track
> progress in `../PROGRESS.md`.

## Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

That's it — **no Neo4j, no Docker, no database**. The knowledge graph is a folder of Markdown
files (one per node) that the pipeline reads/writes directly.

## Setup
```bash
cd brain
uv sync                       # resolve deps into .venv
cp .env.example .env          # then set DEEPSEEK_API_KEY (+ BUS_ROOT for the Drive folder)
```

## Where the graph lives (P12 — OKF bundle)

The graph is a directory of Markdown files with YAML frontmatter, defaulting to
**`{BUS_ROOT}/graph`** — inside the same Google-Drive-synced engagement folder the Answer Logs
and briefs use, so the knowledge base backs up and syncs for free. Override with `GRAPH_ROOT`
in `brain/.env`. Layout:

```
graph/
  index.md            # generated overview (counts + links per type)
  roles/role.sales-manager.md
  activities/act.check-stock.md
  systems/ · artifacts/ · events/ · rules/ · problems/ · ...
```

Each node file: frontmatter = machine truth (`type`, `title`, `keywords` (aliases),
`description`, `status`, `provenance`, outgoing `edges` with per-edge provenance); body =
generated human/LLM view with timestamped Facts and two-way `[[wiki-links]]` (Links on the
giver, Backlinks on the receiver). Read them freely; **don't hand-edit** — the pipeline owns
them, and everything is re-derivable from the immutable Answer Logs anyway.

> **Always run uv/Python commands from this `brain/` directory.** `uv run` discovers the project
> via `pyproject.toml` here; running from elsewhere gives `No module named 'warp_compass_brain'`.

## Ingest pipeline (works today)
```bash
# confirm which DeepSeek models your key can access
uv run python -m warp_compass_brain.cli check-models
# turn one answer into graph nodes. Add --extra vectors for semantic dedup embeddings.
uv run --extra vectors python -m warp_compass_brain.cli ingest \
  "An order comes in, I check stock, then escalate big ones to the manager." --persona persona.A
```

## Run the tests
```bash
uv run pytest                 # the whole suite — no database or network needed (72 tests)
uv run ruff check .           # lint
```

## Layout
```
src/warp_compass_brain/
  models.py        # NodeCard, Edge, Provenance, enums (mirror contracts/)
  ontology.py      # loads + validates against contracts/ontology.json (the compass)
  config.py        # env-driven settings (GRAPH_ROOT, BUS_ROOT, keys)
  graphstore/      # GraphStore ABC (swap seam) + OkfGraphStore (Markdown bundle)
  vectorindex/     # local embeddings + sqlite cosine index (semantic dedup)
tests/
```

Migrating pre-P12 Neo4j data (one-off): `uv run --with neo4j python ..\scripts\migrate_neo4j_to_okf.py`
— or just rebuild from the Answer Logs (clear `ingested_logs` in each `profile.json`, re-run a round).

The graph is **re-derivable** from the raw Answer Log (the immutable source of truth), so the
store is a low-stakes working copy. See `../docs/plan/phase-12-okf-store.md` and
`../docs/02-technical-approach.md`.
