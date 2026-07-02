# Storage Decision Report: Google OKF vs. Neo4j for Warp Compass

**Date:** 2026-07-01
**Author:** Claude (Warp Compass build assistant)
**Question:** For the Warp Compass knowledge store, is Google's Open Knowledge Format (OKF) a better fit than the current Neo4j graph, given that our priorities are **readability, context management, and an efficient memory system** — and that graph *visualization* is explicitly **not** a priority.
**Audience:** This document is written to be self-contained so other agents/reviewers can analyze it without the codebase in front of them.

---

## 1. TL;DR — Verdict

**For Warp Compass's actual usage and stated priorities, an OKF-style git-backed Markdown store is the better fit than Neo4j — but with one real caveat you must design around (per-edge provenance).**

Two facts drive this conclusion:

1. **OKF is not a database — it is a file format.** Comparing "OKF vs Neo4j" is really comparing *"a queryable graph-database server"* vs *"a folder of linked Markdown files you load into memory yourself."* The real question is: **does Warp Compass need a database engine at all?**

2. **Warp Compass does not use Neo4j as a graph database.** The code performs only point lookups, one-hop neighbor reads, and full-graph bulk reads. **Every genuinely graph-shaped operation — chain validation, completeness scoring, cross-persona handoff verification, conflict routing — is done in Python over an in-memory snapshot, "DB-free."** Neo4j's real value (Cypher, ACID, path-finding, graph algorithms, scale) is almost entirely unused.

When a graph *database* is used only as a typed key-value store with edges, its cost (a running server, an operator "start Neo4j" step, opaque JSON-serialized properties) buys you very little — and a plain-files format wins on exactly the three things you said you care about.

**Recommendation:** Adopt an **OKF-conformant Markdown bundle** as the system of record, keep all traversal/scoring logic in Python (it already is), and keep the existing SQLite vector index. Treat Neo4j as optional/removable. Migrate in phases behind the existing `GraphStore` interface so it's low-risk and reversible. **This is a fit-and-ergonomics upgrade, not a correctness fix** — Neo4j is not broken; it is simply heavier than your usage justifies.

---

## 2. What OKF actually is (and isn't)

**Open Knowledge Format (OKF)** is an open specification from Google Cloud, **v0.1, published 2026-06-12** (authors Sam McVeety & Amir Hormati, Google Cloud Data team). It formalizes the "LLM-wiki" pattern into a portable, vendor-neutral format.

**Concretely, OKF is:**
- A **directory ("bundle") of Markdown files**, one file per *concept* (entity). **The file path is the concept's identity.**
- Each file has **YAML frontmatter** for structured, queryable fields.
- The **only required field is `type`.** Reserved standard fields: `type`, `title`, `description`, `resource`, `tags`, `timestamp`. Everything else is producer-defined.
- Concepts **link to each other with ordinary Markdown links** (`[customers](/tables/customers.md)`), which turns the directory into a graph "richer than the parent/child links implied by the file system."
- Reserved filenames: `index.md` (progressive disclosure as an agent navigates the hierarchy) and `log.md` (chronological change history).
- **No runtime, no SDK, no server, no proprietary account.** "Just markdown, just files, just YAML frontmatter." A ~15-line Python script can parse a bundle and build the link graph.

**What OKF explicitly is NOT (its non-goals):**
- **Not a query engine.** Per the official FAQ: *"OKF is implicitly a graph… but you can't run SPARQL on raw OKF."* You read the Markdown and follow links; anything richer needs your own tooling.
- **Not a system of record with transactions/locking.** It's "the portable snapshot you version in git, share across teams, or feed to an AI agent."
- **Not access control / security.** Explicitly out of scope.
- **Not RAG.** OKF stores *"curated, version-controlled concepts,"* not vector embeddings or semantic chunks. The community framing: *"OKF handles the 'known knowns.' RAG handles the 'I know it's somewhere.'"*

**Maturity caveat:** v0.1 is "a starting point, not a finished standard," Google-led, adoption unproven. Google shipped only proofs-of-concept (an enrichment agent, a static-HTML graph visualizer, three sample bundles). **However** — because the data is just Markdown + YAML in git, the lock-in risk is near zero: even if the spec stalls, your files remain trivially readable and re-parseable. This is the *opposite* of a proprietary DB's lock-in profile.

---

## 3. How Warp Compass *actually* uses Neo4j (the decisive evidence)

Warp Compass is an **AI-powered business-process-discovery system**: voice-first conversational discovery that builds per-role SOPs and one synthesized end-to-end process, plus a problem register.

### 3.1 The data model
- **Nodes** carry a generic `:Node` label (for a uniqueness constraint on `id`) plus one **ontology type label** from a fixed set of **10 types** (`Role`, `Activity`, `System`, `Artifact`, `Event`, `Rule`, `Problem`, `KPI`, …).
- Node properties: `id` (unique, e.g. `act.check-stock`), `canonical_name`, `aliases[]`, `description`, `category_codes[]`, `key_attributes` (**JSON-serialized dict** — Neo4j can't store nested maps natively), `provenance[]` (**array of JSON-serialized records**: who/when/confidence/status), `status` (`proposed|unverified|confirmed|conflicting`).
- **12 directed edge types** (`PERFORMS`, `USES`, `PRODUCES`, `CONSUMES`, `TRIGGERS`, `REQUIRES_APPROVAL_FROM`, `HANDS_OFF_TO`, `ESCALATES_TO`, `REPORTS_TO`, `GOVERNED_BY`, `BLOCKS`, `MEASURED_BY`). **Each edge also carries `provenance[]`.**
- The ontology (types, required completeness fields, edge direction rules, taxonomy) lives in `contracts/ontology.json` and is **enforced in Python**, not by Neo4j.

### 3.2 Every query the code actually issues
From `brain/src/warp_compass_brain/graphstore/neo4j_store.py`:
- **Point lookup** by `id`.
- **Alias/candidate lookup:** case-insensitive scan over `canonical_name` + `aliases`.
- **One-hop neighbors:** `MATCH (n {id})-[:REL]->(m) RETURN m`.
- **Bulk reads:** all nodes of a type; all edges of a type (returning `from_id, to_id, type, provenance`).
- **Upserts:** `MERGE (n:Node {id}) SET n += $props` and `MERGE (a)-[r]->(b) SET r.provenance = …`.
- An unused generic `query(cypher)` **escape hatch**.

### 3.3 Where the real work happens — *not in the database*
- `completeness.py` (476 lines): loads the **entire graph snapshot**, checks per-activity completeness, detects one-sided handoffs, validates the end-to-end chain is unbroken.
- `crosspersona.py` (321 lines): bidirectional handoff verification and conflict routing — explicitly *"one-shot in-memory snapshot, pure, deterministic, DB-free in tests."*
- `docgen/traverse.py`: traversal to render SOPs and the end-to-end process.

**This is the crux.** No multi-hop Cypher, no `shortestPath`, no graph-data-science calls, no server-side pattern matching. Neo4j is a **typed key-value store with typed edges**, read wholesale into Python where the actual graph reasoning happens.

### 3.4 Scale & deployment
- **Single-user, local, prototype.** One shared "brain" graph on the builder's laptop. ~30–50 nodes/persona, thousands of nodes at most.
- Neo4j **Community Edition** via Neo4j Desktop; operator must **start Neo4j** before each batch round (a documented step in `OPERATOR-MANUAL.md`).
- Vectors are **not** in Neo4j: a separate **SQLite brute-force cosine index** (`brain/_state/vectors.sqlite`, `fastembed`/`BAAI/bge-small-en-v1.5`, 384-dim) handles semantic dedup, gated behind `--extra vectors`.

**Implication:** Neo4j's scale, concurrency, and query-engine strengths are irrelevant here, and even its vector capability is unused.

---

## 4. Scoring against *your* stated priorities

| Priority | Neo4j today | OKF-style Markdown bundle | Winner |
|---|---|---|---|
| **Readability** | Properties are **opaque**: `key_attributes` and `provenance[]` are JSON strings inside DB fields; you need Cypher or the browser to inspect anything. | Each node is a **human- and agent-readable Markdown file**; frontmatter holds typed fields, body holds the SOP prose. Diff-able on GitHub. | **OKF (decisively)** |
| **Context management** | Live phone runner already **cannot** use the graph (latency); a separate "Session Brief" is hand-assembled. Graph is a batch-only artifact. | Concept-per-file + `index.md` **progressive disclosure** is *designed* for exactly "assemble the right context slice for an agent." Session Brief becomes "read these N files." | **OKF** |
| **Efficient memory system** | Provenance/status tracked as serialized JSON; history/versioning is manual. | **git gives you free versioning, diffs, blame, and change history** (`log.md` convention). Provenance arrays are native YAML lists-of-maps — no JSON-string hack. | **OKF** |
| **Lightweight / seamless (your standing pref: no Docker, laptop-friendly)** | Requires a **running Neo4j server** + an operator "start the DB" step each round. | **No server, no daemon, no start step** — files live in the repo. Removes an entire operational dependency. | **OKF** |
| **Visualization** *(you said NOT a priority)* | Strong (Neo4j Browser/Bloom). | OKF ships a self-contained static-HTML graph visualizer if ever wanted. | Neo4j (but irrelevant) |
| **Query engine / multi-hop traversal** | Full Cypher available. | None — you traverse in code. | **Neo4j** — *but you don't use this* |
| **ACID / concurrent multi-user writes** | Yes. | No (git-level concurrency only). | **Neo4j** — *but single-user today* |
| **Schema enforcement** | One uniqueness constraint; ontology enforced in Python anyway. | Enforced in Python (unchanged); `type` guaranteed by spec. | Tie |
| **Vector search** | Unused (you use SQLite). | Unaffected (keep SQLite). | Tie |
| **Lock-in / portability** | Proprietary store; export needed to leave. | Plain files; zero lock-in even if OKF the spec dies. | **OKF** |

**On the four things you explicitly prioritized, OKF wins all four.** The columns Neo4j wins are precisely the capabilities Warp Compass does not currently use.

---

## 5. The one real gap you must design around: **per-edge provenance**

This is the single substantive modeling problem, and other agents should scrutinize it.

- Warp Compass edges are **first-class, typed, and carry `provenance[]` + effectively a status** (a handoff can be `proposed` / `confirmed` / `conflicting`). Cross-persona verification and conflict routing depend on this per-edge metadata.
- **Vanilla OKF links are just Markdown links** (`[x](y.md)`) — they cannot carry provenance, confidence, or status.

**Resolution (fully within OKF, since frontmatter beyond `type` is producer-defined):** model relationships as **structured frontmatter lists**, not (only) inline links. Example for an Activity concept:

```yaml
---
type: Activity
title: Check stock
status: confirmed
aliases: [check inventory, verify availability]
category_codes: ["05.1"]
provenance:
  - source: participant.sales-rep-01
    round: 3
    confidence: 0.9
    status: confirmed
key_attributes:
  trigger: order received
  system: CRM
edges:
  hands_off_to:
    - target: role.inventory-lead
      status: proposed        # not yet confirmed from the receiver's side
      provenance:
        - source: participant.sales-rep-01
          round: 3
          confidence: 0.7
  uses:
    - target: system.crm
      status: confirmed
      provenance: [...]
---
# Check stock
Prose SOP for humans and agents…
Hands off to [Inventory Lead](/roles/inventory-lead.md).
```

- Frontmatter `edges.*` carries the machine-readable, provenance-bearing graph your Python engines consume.
- The Markdown body keeps human-readable inline links for readability and the OKF static visualizer.
- Your loader builds the in-memory graph from `edges.*` — the *same* in-memory structure `completeness.py`/`crosspersona.py` already operate on.

This is technically a **"profile" of OKF** (a producer convention), not vanilla OKF. That's expected and endorsed by the spec's "minimally opinionated" philosophy — but flag it explicitly so reviewers know you are not getting drop-in interop with other OKF producers for edge metadata.

---

## 6. What migration actually requires (small, and behind an existing seam)

Warp Compass already abstracts storage behind a `GraphStore` interface (`neo4j_store.py` is one implementation). An `OkfGraphStore` sibling is the whole job:

1. **Loader** — walk the bundle, parse frontmatter (`pyyaml`) + body, build the in-memory node/edge graph. (~a few hundred lines; OKF's own reference parser is ~15 lines for the naive case.)
2. **Writer (upsert)** — "MERGE node" = write/patch `<type>/<id>.md`; "MERGE edge" = add/update an entry under `edges.*` in the source node's frontmatter. `id` → file path mapping replaces the uniqueness constraint.
3. **Integrity checks** — link/edge-target existence checker (replaces the DB's referential guarantees); id uniqueness = path uniqueness.
4. **Keep** the SQLite vector index and all Python scoring/traversal engines **unchanged** — they already operate on in-memory snapshots.
5. **Bulk read** becomes "load the folder" — for thousands of nodes this is milliseconds and removes the whole client/server round-trip.

**Phased, reversible plan:**
- **Phase A** — Implement `OkfGraphStore`; add a `docgen`-style exporter Neo4j → OKF bundle so you can generate and eyeball real output from current data.
- **Phase B** — Run both stores in parallel (dual-write) for one or two batch rounds; diff the in-memory graphs to prove equivalence.
- **Phase C** — Flip the default to OKF; keep Neo4j behind a flag as a fallback.
- **Phase D** — Once stable, drop the Neo4j dependency and the "start Neo4j" operator step.

---

## 7. When you should *keep* Neo4j instead

Be honest about the futures where the current engine is the right call. Reconsider (or keep Neo4j) if any of these become true:
- **You start issuing genuine multi-hop / variable-length graph queries** server-side (e.g., "find all paths from any customer-facing trigger to any finance approval across N personas") and don't want to hand-roll them in Python.
- **Warp Compass becomes multi-user SaaS with concurrent writers** needing ACID transactions and locking — git-file concurrency won't cut it.
- **Scale jumps by orders of magnitude** (hundreds of thousands+ of nodes) such that loading the whole bundle into memory per round stops being trivial.
- You want **server-side graph algorithms** (centrality, community detection) via Neo4j GDS.

None of these are true today, and the architecture (all logic in Python over snapshots) means you could even reintroduce a DB later without rewriting the reasoning engines. If you ever want a DB *and* the lightweight profile, an **embedded** graph DB (e.g. Kùzu — in-process, no server) would be a middle option — but it reintroduces opacity and buys nothing over files at your current scale.

---

## 8. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| OKF v0.1 spec churns / Google deprioritizes it | Low | Data is plain Markdown+YAML; you depend on the *pattern*, not Google's tooling. Zero lock-in. |
| Per-edge provenance isn't native OKF | Medium | Use the frontmatter `edges.*` profile (§5); document it as a Warp Compass convention. |
| Loss of DB-enforced referential integrity | Low–Med | Add a link/edge-target validator to the batch pipeline (fast, deterministic). |
| Large bundles slow to full-load | Low (today) | Only relevant at ≫10⁴ nodes; revisit per §7. `index.md` sharding mitigates for agents. |
| Manual/agent edits corrupt frontmatter | Low–Med | Schema-validate frontmatter against `contracts/ontology.json` on load (you already own this ontology). |
| Merge conflicts if multiple writers | Low today | Single-user batch pipeline; git handles it; revisit if multi-user. |

---

## 9. Bottom line for reviewers

- The framing "OKF vs Neo4j" conflates a **format** with an **engine**. The decision that matters is: *does Warp Compass need a graph-database engine?* The code says **no** — it uses Neo4j as a typed key-value+edge store and does all graph reasoning in Python.
- Given that, and given the stated priorities (**readability, context management, efficient memory** — visualization explicitly deprioritized), an **OKF-style git-backed Markdown bundle is the better fit**: it wins on all four priorities, deletes an operational dependency, and adds free versioning/provenance readability, at near-zero lock-in risk.
- The migration is small because it slots behind the existing `GraphStore` seam and reuses the existing in-memory engines and SQLite vector index.
- The one thing to get right is **per-edge provenance via a frontmatter `edges.*` profile** (§5). Everything else is mechanical.
- This is a **fit/ergonomics improvement, not a bug fix** — Neo4j works; it's just heavier than your usage warrants. Do it phased and reversible (§6).

---

## Sources

**OKF — primary & explanatory**
- [How the Open Knowledge Format can improve data sharing — Google Cloud Blog](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
- [Google Cloud Introduces Open Knowledge Format (OKF) — MarkTechPost](https://www.marktechpost.com/2026/06/16/google-cloud-introduces-open-knowledge-format-okf-a-vendor-neutral-markdown-spec-for-giving-ai-agents-curated-context/)
- [FAQ — Open Knowledge Format (okf.md)](https://okf.md/faq/)
- [Google Cloud Announces The Open Knowledge Format — Search Engine Journal](https://www.searchenginejournal.com/google-cloud-announces-the-open-knowledge-format/579253/)
- [Open Knowledge Format: AI Knowledge as Markdown Files — heise online](https://www.heise.de/en/news/Open-Knowledge-Format-AI-Knowledge-as-Markdown-Files-11332310.html)
- [What is OKF? Google's open knowledge format, explained — OWOX](https://www.owox.com/blog/articles/open-knowledge-format-okf)
- [Open Knowledge Format (OKF): Google AI Agent Standard — explainX](https://explainx.ai/blog/google-open-knowledge-format-okf-ai-agents-2026)

**OKF vs RAG / limitations**
- [Google's Open Knowledge Format (OKF) vs. RAG — AlphaMatch](https://www.alphamatch.ai/blog/google-open-knowledge-format-okf-vs-rag-2026)
- [Open Knowledge Format (OKF): The Markdown Standard Built for AI Agents — Agentic AI Decode](https://agenticaidecode.substack.com/p/open-knowledge-format-okf-the-markdown)

**Neo4j / graph memory for LLMs (when it's worth it vs overkill)**
- [How to Fix AI Agent Memory With a Neo4j Knowledge Graph — DecodingAI](https://www.decodingai.com/p/understanding-neo4j-graph-agent-memory-system)
- [Graphiti: Knowledge graph memory for an agentic world — Neo4j](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)
- [GraphRAG — Neo4j Labs](https://neo4j.com/labs/genai-ecosystem/graphrag/)

**Warp Compass codebase (primary evidence, this repo)**
- `brain/src/warp_compass_brain/graphstore/neo4j_store.py` — driver, schema, every query
- `brain/src/warp_compass_brain/completeness.py`, `crosspersona.py` — in-memory, DB-free graph reasoning
- `brain/src/warp_compass_brain/vectorindex/` — SQLite vector index (separate from Neo4j)
- `contracts/ontology.json` — 10 node types, 12 edge types, enforced in Python
- `OPERATOR-MANUAL.md`, `PROGRESS.md`, `02-technical-approach.md` — deployment & architecture
