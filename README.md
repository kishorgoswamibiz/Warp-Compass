# Warp Compass

**Direction to Operational Clarity.**

Warp Compass is an AI system that does what a Business Analyst does by hand today: it holds
natural, **voice-first** conversations with employees at **every level** of an organization,
discovers how each role actually works, and connects it all into the **complete SOP per level +
one connected end-to-end process + a problem register** — living, fully traceable documentation.

Discovery (the conversation) is the *method*; the **connected SOP / end-to-end process** is the
*goal*. There is no predefined questionnaire — the agent opens with generic prompts and lets the
structure of the org emerge from what people actually say.

## How it works — two speeds, one contract

- **Interaction plane** (`pwa/`) — a fast, installable voice app on each phone. It converses,
  stays on topic, follows up, and reconciles *within-session* contradictions. It holds **no
  graph**. It only **writes** an Answer Log.
- **Cognition plane** (`brain/`) — "the brain", a batch pipeline on a laptop. It extracts
  structured knowledge into an **OKF Markdown graph bundle** (search-before-store; one readable
  file per node, no database server), detects cross-session / cross-persona conflicts, scores
  completeness against a fixed **ontology**, and plans each persona's next focus. It only
  **reads** Answer Logs and **writes** Session Briefs.

They communicate through two artifacts only — **Answer Log** (up) and **Session Brief** (down) —
defined in `contracts/`. In the prototype, a free shared cloud folder (`worker/`-fronted PWA →
Drive/Dropbox → laptop) is the sync bus; the only paid services are **DeepSeek** and **ElevenLabs**.

See `docs/assets/architecture-prototype.png` for the full topology.

## Repository map

| Path | What |
|------|------|
| `docs/00..02-*.md` | **Canonical design** — context/rationale, functional spec, technical approach. |
| `docs/10-implementation-plan.md` | The master end-to-end build plan (10 phases). |
| `docs/plan/phase-*.md` | One self-contained build brief per phase. |
| `docs/{ARCHITECTURE,DATA-CONTRACTS,DECISIONS,THEME}.md` | Topology, the contract, decision log, UI spec. |
| `contracts/` | Language-neutral source of truth: `ontology.json` + JSON Schemas. |
| `brain/` | Python + uv cognition pipeline (**Phases 1–2 done**: ontology + GraphStore + ingest). |
| `pwa/` | React + Vite + TS voice PWA (scaffold). |
| `worker/` | Cloudflare Worker key proxy (scaffold). |
| `scripts/` | Operator scripts for the manual batch round (placeholder). |
| `PROGRESS.md` | **Living build board** — start here to contribute. |
| `AGENTS.md` | The contributor protocol. |

## Quickstart

Prerequisites: **Node 20+**, **Python 3.12+**, **[uv](https://docs.astral.sh/uv/)**.
No database — the graph is a folder of Markdown files (see `brain/README.md`).

```bash
# Brain
cd brain && uv sync && cp .env.example .env
uv run pytest                        # the whole suite; no services needed

# PWA (scaffold)
cd ../pwa && npm install && npm run dev    # http://localhost:5173

# Worker (scaffold)
cd ../worker && npm install && npx wrangler dev   # try /health
```

## Contributing

This is an agent-friendly build. **Read `PROGRESS.md`, then `AGENTS.md`**, claim a task, and
append a handoff entry when you're done. Nothing is lost between sessions.

## Status

**All phases complete (P0–P12) and deployed.** The PWA is live on Cloudflare Pages with
automatic Google Drive sync (P11), and the knowledge graph is an OKF Markdown bundle —
Neo4j was removed in P12 (`docs/plan/phase-12-okf-store.md`, ADR #28). Operating routine:
`OPERATOR-MANUAL.md`. Build history: `PROGRESS.md`.
