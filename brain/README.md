# Warp Compass — Brain (cognition plane)

The laptop batch pipeline: **extract → resolve (create gate) → conflict/coverage → planner**
over a Neo4j graph. Python + [uv](https://docs.astral.sh/uv/).

> **Status:** Phase 1 complete — ontology + `GraphStore`. Phases 2–10 are in
> `../docs/plan/`. Track progress in `../PROGRESS.md`.

## Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Neo4j Desktop** (free, no Docker) — see *Neo4j setup* below. (Docker is an optional alternative.)

## Setup
```bash
cd brain
uv sync                       # resolve deps into .venv
cp .env.example .env          # then set NEO4J_PASSWORD to the one you chose in Neo4j Desktop
```
Start your Neo4j database (see below), then run the tests.

## Neo4j setup (Neo4j Desktop — runs only on this laptop, one time)

The graph DB lives **only on your laptop**. End users never install it — they only open the PWA.
Your data **persists across restarts**; closing the laptop never wipes it. After a reboot you just
press **Start** on the database again (the data is already on disk). And because the raw Answer Log
is the immutable source of truth, the graph is always re-derivable — you can't lose understanding.

1. Download & install **Neo4j Desktop** from <https://neo4j.com/download/> (free).
2. Create a **new local DBMS / instance** (Neo4j 5.x). Set a password and remember it.
3. **Start** the instance. It listens on the default Bolt port `bolt://localhost:7687`
   (browser UI at `http://localhost:7474`). Username is `neo4j`.
4. Put that password in `brain/.env` as `NEO4J_PASSWORD` (leave `NEO4J_URI`/`NEO4J_USER` as-is).
5. Each working session: open Neo4j Desktop → **Start** the instance → run a batch round. Done.

> Alternative (only if you ever want it): `docker compose up -d` uses the bundled
> `docker-compose.yml` to run Neo4j Community instead. Not needed with Neo4j Desktop.

> **Always run uv/Python commands from this `brain/` directory.** `uv run` discovers the project
> via `pyproject.toml` here; running from elsewhere gives `No module named 'warp_compass_brain'`.

## Phase 2 — ingest pipeline (works today)
```bash
# confirm which DeepSeek models your key can access
uv run python -m warp_compass_brain.cli check-models
# turn one answer into graph nodes (Neo4j must be started). Add --extra vectors for embeddings.
uv run --extra vectors python -m warp_compass_brain.cli ingest \
  "An order comes in, I check stock, then escalate big ones to the manager." --persona persona.A
```

## Run the tests
```bash
uv run pytest -m "not neo4j"  # fast: ontology + model tests, no DB needed
uv run pytest                 # full: also runs the GraphStore round-trip (needs Neo4j started)
uv run ruff check .           # lint
```
The `neo4j`-marked tests **skip cleanly** if no database is reachable, so the fast suite always
works even before you set up Neo4j.

## Layout
```
src/warp_compass_brain/
  models.py        # NodeCard, Edge, Provenance, enums (mirror contracts/)
  ontology.py      # loads + validates against contracts/ontology.json (the compass)
  config.py        # env-driven settings
  graphstore/      # GraphStore ABC (swap seam) + Neo4jGraphStore
  vectorindex/     # VectorIndex ABC (Phase-2 helper; interface only for now)
tests/
docker-compose.yml # Neo4j Community
```

The graph is **re-derivable** from the raw Answer Log (the immutable source of truth), so the
DB is a low-stakes working store. See `../docs/02-technical-approach.md`.
