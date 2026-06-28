# Warp Compass — Architecture (distilled)

The canonical, detailed version is `02-technical-approach.md` and the diagram
`assets/architecture-prototype.png`. This is the at-a-glance map for orientation.

## The one idea

Talking to a person must feel **instant**; understanding a whole org is **slow**. So we split
them into two planes joined by a single two-artifact contract.

```
  PHONE (interaction plane, live)                LAPTOP (cognition plane, batch)
  ┌──────────────────────────────┐              ┌────────────────────────────────────────┐
  │ PWA · voice I/O · live runner │              │ Extract → Resolve(create gate)          │
  │ holds NO graph                │              │   → Conflict & coverage → Planner       │
  │ writes Answer Log ───────────────► BUS ────────► reads logs, writes Session Briefs     │
  │ reads Session Brief ◄───────────── (shared    │ Neo4j (the one brain) · Vector index    │
  └──────────────┬───────────────┘    folder)    │ Raw Answer Log = immutable truth        │
                 │ live calls                     │ Ontology = completeness compass         │
                 ▼ (keys injected)                └────────────────────────────────────────┘
        Cloudflare Worker (proxy) ──► ElevenLabs (STT/TTS) · DeepSeek (LLM)
        Cloudflare Pages serves the PWA
```

## The contract (the only coupling)

- **Answer Log** (runner → brain): immutable, append-only, the **source of truth**.
  Schema: `contracts/answer-log.schema.json`.
- **Session Brief** (brain → runner): persona-scoped memory + ranked open threads; *guidance,
  not a script*. Schema: `contracts/session-brief.schema.json`.

The runner only **writes** the log; the brain only **reads** it. The graph is never exposed to
the phone. This decoupling lets each plane be optimized independently and makes the graph
re-derivable from the raw log.

## Memory (cognition plane)

| Store | Holds | Why |
|-------|-------|-----|
| **Neo4j graph** | Roles, activities, tools, approvals, handoffs, problems + relationships. | Relationships *are* the understanding. |
| **Vector index** | Embeddings of node cards/utterances. | A *helper* to find merge candidates — not the memory. |
| **Raw Answer Log** | Every raw answer + provenance. | Immutable truth; re-derive the graph anytime. |

The end-to-end process is literally a **graph traversal** across all personas:
`Event TRIGGERS → Role PERFORMS Activity → HANDS_OFF_TO Role → …`.

## Swap seams (thin interfaces — vendor/transport swaps stay one-line)

`GraphStore` (Neo4j) · `VectorIndex` (sqlite-vec) · `LLMProvider` (DeepSeek) ·
`STTProvider`/`TTSProvider` (ElevenLabs) · `Bus` (shared folder → sync endpoint in v1).

## Prototype vs networked v1

Same architecture; only the **transport between planes** differs. Prototype = manual
export/import via a shared folder + laptop brain. v1 = a thin always-on sync endpoint and the
brain moved off the laptop. The planes, contract, ontology, and pipeline are unchanged.
