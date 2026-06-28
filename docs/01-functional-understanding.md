# AI SOP & End-to-End Process Engine — Functional Understanding & Features (v3)

## 1. What we are building (in one paragraph)

An AI-powered system that does what a Business Analyst does manually today: it holds
natural, voice-first conversations with employees at **every level** of a client
organization, across several short daily sessions, to understand the **complete Standard
Operating Procedure (SOP)** of each role — every activity, trigger, tool, handoff, rule,
and exception — then **connects all of it into one shared model and synthesizes a single,
coherent end-to-end process** that spans the whole organization, together with a register
of the **problems and pain points** each level experiences. Discovery (the conversation)
is the *method*; the connected SOP and end-to-end process are the *goal* — this is not
merely a "discovery agent." Unlike a static questionnaire, it does not work from a fixed
list of questions at all: it **opens with generic discovery prompts and lets the structure
of the organization emerge**, discovering roles and workflows from what people actually say
rather than from what an analyst assumed in advance. It listens, stays on topic, challenges
contradictions, asks adaptive follow-ups, and keeps refining across sessions until the
end-to-end picture is complete and connected. Every persona feeds into **one shared
brain**, so what one level says shapes the questions asked of another. Crucially, the
system is split in two: a **fast live conversation** that feels human and responsive, and
a **deeper "thinking" layer** that does the heavy understanding quietly between sessions.

> **What changed:** the system's purpose is framed as understanding the **complete SOP at
> every level and synthesizing one end-to-end process** — discovery is the method, not the
> whole product. (Also, as before: no predefined questionnaire; personas are *discovered*,
> not defined up front; the BA's input is optional background, not a constraint; and the
> doc reflects the concrete **prototype** — a phone web-app, a free cloud folder for sync,
> the brain run on the builder's laptop, no server, no cost beyond the two paid APIs.) The
> architecture is unchanged by the SOP framing.

---

## 2. Actors

| Actor | Role in the system |
|---|---|
| **Business Analyst (BA)** | Optionally primes the engagement with light background (company, domain, goal) and any hints they already hold — but this is **guidance, not a cage**: the system can start from a blank slate and will confirm or overturn any hint. Reviews and signs off the final output, and resolves anything flagged. |
| **Employee / Interviewee** | Talks to the agent in short daily sessions. Two modes: answers the agent's questions, or freely narrates what they do and the issues they hit. |
| **The Brain (system)** | Conducts conversations, discovers roles and workflows, builds the connected model, detects gaps and conflicts, and produces living documentation. |
| **Operator (prototype only)** | The person running the pilot: distributes the app link, collects each person's exported session, runs the brain on their laptop, and redistributes the per-persona memory. (In the networked version this is automatic.) |

---

## 3. Core concepts (shared vocabulary)

- **Persona** — a *role/level* in the org (e.g., Sales Rep, Inventory Lead, Manager).
  Personas are **discovered** from conversation, not defined in advance; many real
  employees can map to one persona. **Any number of users is supported, added at any
  time** — in the prototype each new user becomes their own persona (1:1); recognizing
  that several users share one role-persona is a later capability.
- **Ontology (the completeness compass)** — a fixed vocabulary of the *kinds* of things
  a process is made of (activities, triggers, tools, approvals, handoffs, rules,
  problems…). It is **not** a list of questions; it is the system's internal definition
  of "what a complete picture looks like," used only to notice gaps. Discovery is
  unbounded on *content*, structured on *completeness*.
- **Shared Organizational Brain** — one connected knowledge store that every persona
  contributes to and draws from. Not several separate brains; one brain.
- **Session** — one conversation sitting (~45 minutes), typically a couple a day per
  person over several days, always resuming where it left off.
- **Session Brief** — what the agent carries into a session: the persona's evolving
  understanding plus a ranked list of **open threads to pull on**. It is guidance the
  agent is free to deviate from, **not** a script. (On a first session there are no
  threads — only the generic discovery openers.)
- **SOP (per level)** — the structured map of how a role actually operates: its
  activities, triggers, tools, handoffs, approvals, rules, exceptions, and outputs. This
  is each level's Standard Operating Procedure, captured as-is.
- **End-to-End Process** — the **headline deliverable**: the single, connected process that
  results from stitching every level's SOP together along verified handoffs — from the
  first trigger to the final output, across the whole organization. This is the "one
  end-to-end process" the system exists to produce.
- **Problem Register** — every pain point with context (who, how often, impact, suspected
  cause, what they wish were different).
- **Satisfaction / Completeness** — the agent's sense of "I understand this well enough,"
  tracked per persona and across the whole org, measured against the ontology compass.
  Org-wide completeness explicitly includes **the end-to-end chain being unbroken** (every
  handoff verified from both sides, no dangling steps).

---

## 4. The rhythm of an engagement

Deliberately paced so the conversation stays light while understanding deepens:

1. Each employee does short sessions (~45 min) over several days.
2. A **first** session opens with **generic discovery** — "tell me about your role,"
   "walk me through a normal day," "where does your work come from and where does it go?"
   — and the agent follows the conversation rather than a script.
3. During any session the agent adapts live — redirecting, following up, and reconciling
   contradictions as they happen.
4. At the end it simply thanks the person and says it will process everything before next
   time — no awkward waiting while it "thinks."
5. **Between sessions**, the brain digests every answer (from this person and others),
   updates the connected model, and prepares a sharper set of **open threads** for each
   persona's next session.
6. Across sessions the focus visibly **evolves**: threads get sharper, chase the gaps that
   matter, and increasingly cross-reference what other levels have revealed.

---

## 5. Functional Features

### A. Setup (optional, light — by the BA)

1. **Optional context priming** — company, domain (e.g., sales/CRM), engagement goal.
   Helpful, not required; the system can start blank.
2. **Optional hints** — any reporting lines or handoffs the BA already knows, treated as
   *priors the system verifies*, never as fixed truth.
3. **Coverage emphasis (optional)** — areas to prioritize (approvals, day-to-day work,
   tools, exceptions). The ontology already defines completeness; this only nudges order.

> Note: there is **no** persona-definition step and **no** question authoring. Personas
> and questions both emerge from the conversations.

### B. The live conversation (what the employee experiences)

4. **Discovery-first openers** — the agent begins from open, human prompts and lets the
   person describe their world; it discovers the role and workflow rather than testing a
   checklist.
5. **Voice-first** — the agent speaks with a consistent, natural voice and listens with
   high-accuracy speech recognition, so answers are captured faithfully (not
   approximately) and it sounds the same to every employee regardless of their device.
   Powered by a dedicated speech service (ElevenLabs — Scribe v2 Realtime for recognition,
   Eleven v3/Flash for the voice). Typed fallback always available.
6. **Two modes** — *guided* (agent asks) and *free narration* (employee just talks about
   what they do and the problems they face); both are captured.
7. **Stays on topic** — if an answer drifts ("I asked about apples, you're describing a
   duck"), the agent gently steers back.
8. **Challenges contradictions in the moment** — if something said now clashes with
   something said earlier *in the same session*, it raises it and works it out.
9. **Natural, non-rigid flow** — it rewords, acknowledges, follows up, surfaces new
   threads of its own, and skips what's already covered, so it feels like talking to
   someone who's listening, not filling in a form.
10. **Low friction** — short sessions, pause/resume, graceful "let's continue next time,"
    and the ability to interject by voice at any point.

### C. How the understanding deepens (between sessions)

11. **Deep processing off the clock** — turning answers into structured, connected
    knowledge happens after the session, never while the person waits.
12. **Search-before-store** — before saving anything, the brain checks whether it already
    knows this (or something related). If so, it links/merges/updates; if not, it creates
    a new entry. No blind dumping, no duplicate clutter.
13. **Cross-session & cross-persona reconciliation** — contradictions against earlier
    sessions, or against what a *different* role said, are detected here and turned into
    open threads for a future session.
14. **Evolving threads** — each persona's next focus is generated from the current state
    of the whole brain, so it sharpens and cross-references other levels over time.
15. **Handoff corroboration** — when one level says "I pass this to my manager," the other
    side is asked to confirm it, so the end-to-end flow is verified from both directions.

### D. The connected brain (cross-persona intelligence)

16. **Single connected model → one end-to-end process** — the levels' SOPs are stitched
    along verified handoffs into a single end-to-end process, emerging from combining every
    level's perspective rather than from separate interviews. This synthesized end-to-end
    process is the system's primary output.
17. **Cross-pollinated focus** — what one level reveals shapes what adjacent levels are
    asked.
18. **Conflict register** — disagreements between levels are tracked and resolved rather
    than silently averaged away.

### E. Completeness & "satisfaction"

19. **Coverage tracking** — for each activity, the brain checks it knows the trigger,
    inputs, tool, output, next handoff, exceptions, and rules; gaps become threads.
20. **Per-persona and org-wide satisfaction** — separately tracked, so the BA can see both
    "is this role understood?" and "is the connected picture complete?"
21. **Re-opening topics** — completeness is never final; new information reopens the
    relevant area and sends the agent back to the right person.

### F. Documentation & output

22. **End-to-end process (headline output)** — the single connected process across all
    levels, from first trigger to final output, as a readable diagram plus narrative. This
    is the consolidated SOP and the primary deliverable.
23. **Per-level SOP** — each role's Standard Operating Procedure (its activities, triggers,
    tools, handoffs, approvals, rules, exceptions, outputs), as diagram + narrative.
24. **Problem statement register** — description, affected role, frequency, impact,
    suspected root cause, and desired outcome.
25. **Living documents** — output regenerates as the brain grows; never a one-time export.
26. **Full traceability** — every statement traces back to who said it and when.
27. **Export** — Word/PDF/Markdown and diagram files.

### G. Review, validation & governance

28. **BA-in-the-loop** — browse the brain, inspect open threads, resolve flagged conflicts,
    approve the final model.
29. **Confidence surfacing** — single-source or low-confidence facts are marked so the BA
    knows what to double-check; documentation shows confirmed knowledge by default.
30. **Improve without re-interviewing** — because every raw answer is kept, the BA can have
    the system *re-process* old answers with an improved understanding later, getting a
    better model without asking anyone to repeat themselves.
31. **Privacy & access** — employees see only their own persona; the consolidated view is
    BA-only; transcripts follow the client's data policy.

### H. How it runs in the prototype (operational)

32. **One app, every phone** — a single installable web app (PWA) the participants open
    via a link; works on Android and iOS.
33. **Add users anytime** — giving the app to one more person automatically adds them: the
    app creates their own folder in the shared drive on first use, and the brain notices
    the new user on its next run and starts building their understanding. No fixed number
    of users, no setup per user.
34. **Daily collect-and-redistribute** — each person exports their session; the operator
    runs the brain on their laptop to update the one shared brain; each person then
    imports a fresh, persona-scoped memory for next time. (This manual cycle is a
    stand-in for the automatic sync the networked version will have.)

---

## 6. A typical lifecycle

1. (Optional) BA primes light context; otherwise the system starts blank.
2. Employees do short daily sessions; the agent **discovers** roles and workflows
   adaptively and records every answer.
3. Between sessions the brain digests answers, updates the connected model, flags
   conflicts and gaps, and prepares sharper, cross-referencing threads per persona.
4. Over days, coverage rises; handoffs get verified from both sides; conflicts get
   reconciled; the per-level SOPs connect into one chain.
5. The BA reviews, resolves remaining flags, and signs off.
6. The system emits the **one end-to-end process** + per-level SOPs + problem register,
   fully traceable.

---

## 7. Scope

**In scope (prototype):**
- Discovery-first voice conversations for **any number of users** (added at any time),
  each on their own phone (PWA). New users are picked up automatically — the shared folder
  is the user registry.
- One shared brain on the operator's laptop; per-user memory exported/imported via a
  shared cloud folder.
- Output: one connected **end-to-end process** + per-level **SOPs** + problem register,
  with traceability.

**Out of scope (for now):**
- To-be / future-state design and recommendations (this version captures *as-is*).
- Automatic CRM build-out — the output *feeds* design, it doesn't implement it.
- Automatic networked sync between devices — the prototype uses manual export/import;
  the networked version comes later.
- Automatic persona-merging — recognizing that several users share one role-persona is a
  later capability (prototype is one persona per user).
- Browser extension / desktop toggle — planned later.
