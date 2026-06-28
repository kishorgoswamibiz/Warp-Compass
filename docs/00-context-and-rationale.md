# AI SOP & End-to-End Process Engine — Project Context & Rationale (read me first)

> **Purpose of this document.** This is the orientation brief for whoever (human or AI
> agent) is about to build the system. The other two documents tell you *what* to build
> (`01-functional-understanding`) and *how* (`02-technical-approach`). This one tells you
> the **vision, the requirements as the project owner expressed them, and the reasoning
> behind every major decision** — so you understand not just the design but *why* it is
> the way it is, and don't accidentally undo a deliberate choice. Read this first. The project name has to be "Warp Compass" tagline is "Direction to Operational Clarity". The referrence of the Ui theme is given in the folder named "WebApp Theme Referrence.png".

---

## 1. The problem we are solving

In a typical consulting/transformation engagement, a **Business Analyst (BA)** manually
interviews people at every level of a client organization — sales reps, managers,
inventory leads, delivery staff, executives — to understand the **complete Standard
Operating Procedure (SOP)** at each level: how each role *actually* works, every activity,
trigger, tool, handoff, rule, and exception. The BA then has to **connect all of it** and
distil **one coherent end-to-end process** that spans the whole organization, plus a
register of the problems and pain points each level lives with. This is slow, expensive,
inconsistent, and biased by the BA's own assumptions.

We are automating that whole job. The system conducts the interviews itself
(**discovery** is the *method*), builds a single connected model of the organization, and
produces the **complete SOP at every level + one connected end-to-end process + a problem
register** — living documentation that traces back to who said what.

> **Important framing:** this is **not** "just a discovery agent." Discovery (the
> conversation) is one capability. The goal is the **complete, connected SOP and a single
> end-to-end process** for the company. The architecture below already does exactly this —
> nothing in the design changes because of this framing; it only sharpens what the
> headline output is.

---

## 2. The project owner's vision & requirements (in their words, distilled)

These are the requirements as the owner articulated them across the design conversation.
Treat them as the source of intent:

0. **The real goal: the complete SOP + one end-to-end process.** Understand the full
   Standard Operating Procedure of the company at every level, connect it all, and define
   a single end-to-end process. Discovery conversations are the means; this connected SOP /
   end-to-end process is the end.
1. **Voice-first, daily, multi-level interviews.** The agent talks to employees at every
   level in short daily sessions (~45 min), like a BA would. People can answer questions
   *or* just narrate what they do and what's painful.
2. **One connected brain, not separate interviews.** Everything every persona says feeds
   a single shared model, so one level's answers shape what another level is asked.
3. **Smart memory, not crude RAG.** The owner explicitly does not want "dump text into a
   vector store and hope retrieval works." They want structured, connected memory that
   accumulates understanding and searches before it stores.
4. **Discovery, not a questionnaire.** A later, important refinement: *do not* hand the
   system a predefined set of questions or BA-defined personas. Start from open prompts
   ("tell me about yourself, what you do, how it works") and let the agent **discover**
   the people, their personas, and their workflows. Do not bind the system to the BA's
   prior knowledge — let it flow and identify reality on its own.
5. **Fast conversation, heavy thinking offline.** The live conversation must feel instant
   and human; the deep understanding should happen quietly between sessions, never while
   the person waits.
6. **A cheap, real prototype.** For testing, give the app to a handful of people. The
   number of users is **not fixed** — giving the app to one more person simply adds
   another user; the shared folder is the user registry and the brain onboards anyone new
   automatically (see §6). The owner explicitly does **not** want to stand up a cloud
   server (no GCP) or incur cost beyond the **DeepSeek** and **ElevenLabs** API bills. A
   mobile-friendly app people can use on the go is preferred.
7. **High-quality voice.** Free browser/OS speech was unsatisfying (it dropped words).
   The owner is willing to pay for a good speech API and chose **ElevenLabs** for both
   recognition and the spoken voice, on a **single API key / single bill**.
8. **Efficient, smart graph memory.** The owner is interested in modern "second brain"
   memory patterns (they referenced Andrej Karpathy's Obsidian-style *LLM Wiki* idea) and
   wants the memory to be genuinely smart and efficient.

---

## 3. What we are building (one screen)

A two-part system:

- **Interaction plane (fast, live, on the phone):** a PWA that runs a voice conversation.
  It opens with discovery prompts, listens, follows up, redirects when the person
  wanders, and catches contradictions *within the same session*. It does no deep
  understanding — it just converses and records.
- **Cognition plane (slow, batch, on the laptop):** "the brain." It takes the raw answers
  and extracts structured knowledge into a **graph**, merging or creating nodes via a
  search-before-store pipeline, detecting cross-session and cross-persona conflicts,
  scoring completeness against an **ontology**, and preparing each persona's next focus.

They communicate through two artifacts only: an **Answer Log** (up, from phone to brain)
and a **Session Brief** (down, from brain to phone). The **headline output is one
connected end-to-end process** (the consolidated SOP spanning every level), alongside the
per-level SOP and a problem register — all fully traceable. The end-to-end process is
literally the connected graph traversed from the first trigger to the final output across
all personas.

---

## 4. The load-bearing design principles (and why)

These are the ideas that, if removed, break the system. Do not undo them.

1. **Two-speed architecture.** *Why:* talking to a human must feel instant, but
   understanding a whole org is slow and needs the full graph. Coupling them would make
   the conversation laggy and the code tangled. Splitting them lets each be optimized
   independently, connected by one clean contract.
2. **"Fast" ≠ "dumb."** *Why:* an earlier draft made the live plane a rigid Q&A robot; the
   owner pushed back — people find that unengaging and stop sharing. So the live plane is
   genuinely smart *locally* (redirects, within-session contradiction-catching), while
   only *global* graph reasoning is deferred to batch.
3. **Discovery-first, with the ontology as a compass.** *Why:* a predefined questionnaire
   bakes in the BA's assumptions and misses reality. So the conversation is unscripted.
   **But** pure free-flow wanders and you lose any definition of "done" — so we keep a
   fixed **ontology** (the kinds of things a process is made of). It is *not* a list of
   questions; it is the internal yardstick the brain uses to notice gaps and decide what
   to pull on next. **Unbounded on content, structured on completeness.** (Discovery is the
   *method*; the **complete SOP + one end-to-end process** is the *goal*.)
4. **One connected end-to-end process is the point.** *Why:* the value is not five separate
   per-level write-ups — it is a single, coherent process stitched across every level, with
   handoffs verified from both sides and no broken links in the chain. The ontology's
   handoff/trigger edges exist precisely so the brain can traverse the graph end-to-end and
   emit that one process. "Completeness" includes the end-to-end chain being unbroken.
5. **Personas are discovered, not declared.** *Why:* same anti-assumption reason. The
   system infers a person's role from what they say. **Any number of users is supported,
   added at any time** — in the prototype each new user is their own persona (1:1); the
   operator just labels them. Auto-merging "these two users are the same role" into one
   shared persona is the only deferred part, and it never blocks adding users.
6. **LLM proposes, deterministic rules dispose.** *Why:* free LLM writing produces
   duplicates and hallucinations. So the LLM only ever *proposes* candidate nodes against
   a fixed vocabulary; deterministic code (a "create gate" with a similarity ceiling,
   vocabulary check, and completeness check) decides whether to merge, flag a conflict,
   create, or quarantine. This is the anti-hallucination spine.
7. **Graph-first memory, re-derivable from an immutable log.** *Why:* relationships are
   the whole point of "understanding a process," so a graph (not a vector blob) holds the
   meaning, with vectors only as a lookup helper. The **raw Answer Log is the immutable
   source of truth**; the graph is *re-derived* from it, so improving the extractor later
   rebuilds a better model with **no re-interviewing**, and the graph DB itself becomes
   low-stakes and swappable.
8. **Voice is asymmetric.** *Why:* the STT transcript becomes the permanent source of
   truth — a misheard word is corrupted forever — so **accuracy matters more than
   latency** there. TTS, by contrast, harms no data if it's plain; it only affects
   rapport. This asymmetry is why we spend on accurate STT and treat TTS as a UX nicety.
9. **Everything swappable behind thin interfaces.** *Why:* vendors and infra will change
   (and the prototype→networked move is coming). `STTProvider`, `TTSProvider`,
   `LLMProvider`, `GraphStore`, and the sync `Bus` are all one-line swaps.

---

## 5. Key decisions & the reasoning trail

| Decision | Why we landed here |
|---|---|
| **No predefined questionnaire** | Avoids BA bias; discovers the real org. The owner explicitly asked for this after initial ideation. |
| **Keep the ontology as a compass** | Without it, discovery wanders and "completeness" is undefinable. It guides the *brain*, never scripts the *conversation*. |
| **Personas discovered, not defined** | Same anti-assumption principle. Any number of users, added anytime; prototype maps each new user to their own persona (1:1), with role-clustering deferred. |
| **PWA (one web codebase), not native apps** | Native Android *and* iOS for a prototype is huge effort spent testing the app, not the intelligence. A PWA is one codebase, installs on both, and ships behind a link. |
| **Cloudflare Pages + Worker (free)** | A PWA needs HTTPS hosting (for mic + install). Pages is free with unlimited bandwidth. A Worker holds the API keys so they never sit in the browser — also free. |
| **Shared cloud folder as the sync bus** | Answers the owner's "how do the devices connect without a server" question. Phones export Answer Logs and import Session Briefs through Drive/Dropbox; the laptop brain reads/writes the same folder. Free; a manual stand-in for the networked v1. |
| **The brain runs on the laptop** | "No server" doesn't mean the heavy work vanishes — it has to run *somewhere*. For a 3-person prototype that somewhere is the owner's laptop (a Python batch job + local Neo4j), so there is genuinely no cloud server and no cost. |
| **DeepSeek for both planes** | Cheap fast calls live (via the proxy) and heavy calls in batch (from the laptop). |
| **ElevenLabs for both STT and TTS, one key** | Best transcription accuracy (the load-bearing leg), most natural voice, 90+ languages incl. Indian languages, one vendor/one bill. Free browser TTS is acceptable **only** in development. |
| **Neo4j Community for the graph** | Mature, free to self-host, Cypher (ideal for completeness/conflict queries), great visualization for the browsable org model. The "ideal" embedded option (Kùzu) was **archived in Oct 2025 after an Apple acqui-hire**; its forks are young, so we don't build the foundation on them — but `GraphStore` keeps that door open. |
| **Build the brain on typed text first** | Voice and sync are UI/transport layers. Getting the intelligence right on plain text de-risks everything; voice is bolted on after. |

---

## 6. Prototype scope, cost, and constraints

**Scope:** discovery-first voice conversations for **any number of users** (added at any
time), one shared brain, as-is flow + problem register output.

**How users are added (the registry mechanism).** The shared cloud folder *is* the user
database. On first launch the PWA mints a `participant_id` and creates that user's own
subfolder. On each batch run the brain **enumerates the folder**, registers any new user
it finds, ingests their logs, and begins producing their per-user Session Briefs. Adding
a user = send them the same app link — no config, no code change, no fixed count. (See
`02-technical-approach` §3.4.)

**Cost model:** the **only** paid services are **DeepSeek** and **ElevenLabs**. Cloudflare
Pages (host), the Cloudflare Worker (key proxy), the Drive/Dropbox sync folder, the local
Neo4j, and the laptop brain are all free. The only thing that grows with more users is API
spend (more sessions) — the architecture imposes no user cap.

**Constraints / deliberate prototype shortcuts (not bugs):**
- The sync is **manual** (export → collect → run brain → redistribute), sequenced **once
  per round**. A second same-day session won't see others' input until the next batch run.
  More users just means more logs in one batch run + more operator effort; the networked
  v1 removes the manual part.
- Each user is their **own persona** (1:1); auto-clustering users who share a role into one
  persona is deferred.
- The brain runs **on a laptop in batch**, not as an always-on service.
- The graph is a **working store**; the immutable Answer Log is the truth, and the graph
  can be rebuilt from it at any time.

---

## 7. Guidance to the builder (how to approach this)

- **Follow the build order** in `02-technical-approach` §16: ontology + GraphStore →
  extractor + create gate → completeness → planner → typed runner → PWA + host + proxy →
  voice → sync → cross-persona → docs.
- **Keep the phone thin.** All deep understanding belongs in the laptop brain. Resist
  putting graph logic on the device — that's the line that keeps the conversation fast.
- **Honor the contract.** The runner only writes the Answer Log; the brain only reads it
  and writes Session Briefs. Don't let the live plane read the graph.
- **Use the swap seams.** Wire every external dependency behind its interface from day one.
- **Lean on re-derivability.** Because the graph rebuilds from the raw log, you can iterate
  on the extractor/ontology freely — and you don't need to fear the graph DB choice.
- **Validate STT on real audio.** Before committing the speech leg, run the chosen model
  on ~20 real, messy recordings (Indian-accented English, background noise, SKUs/codes/CRM
  jargon). Vendor benchmarks use clean audio; your conditions won't be.
- **Never ship API keys in the browser.** All live calls route through the Worker proxy.

---

## 8. Deferred / open questions (explicitly not in the prototype)

- **Memory deep-dive.** The graph backbone is decided, but the owner wants to explore a
  smarter memory design — including an **Obsidian/Karpathy-style markdown-wiki
  *projection*** of the graph (human-browsable, file-portable, fits the export/import sync
  nicely). Treat this as a layer that can sit *on top of* the property graph, to be
  designed in a dedicated session — not a replacement for it.
- **Networked v1.** Replace the manual folder sync with a thin always-on sync endpoint and
  move the brain off the laptop. Architecture, contract, ontology, and pipeline are
  unchanged — only the transport.
- **Automatic persona discovery/merging** across many employees.
- **To-be / future-state design.** This system captures *as-is* only; it feeds design, it
  doesn't do it.

---

## 9. The three documents, and how they fit

1. **`00-context-and-rationale` (this file)** — vision, requirements, why. Read first.
2. **`01-functional-understanding`** — what the system does, feature by feature, for
   humans. The product view.
3. **`02-technical-approach`** — how it's built: the prototype topology, components, data
   contracts (Answer Log + Session Brief), graph ontology and node design, the
   resolve-or-create pipeline, conflict/completeness engines, prompts, tech stack, build
   order, and risks. The engineering view.

The accompanying **`architecture-prototype.png`** is the canonical picture of the
prototype topology described in `02 §3`.
