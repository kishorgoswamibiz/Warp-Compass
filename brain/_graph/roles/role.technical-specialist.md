---
type: Role
id: role.technical-specialist
title: Technical Specialist
keywords:
- Developer
- Dev
- TS
- Engineer
- developers
- developer team
- Development Team
- developer
- dev
- development team
- devs
description: Technical Specialist — a role in this organisation. Seeded from the engagement's role registry
  so that every way people refer to it resolves onto one node; its responsibilities are filled in as people
  describe their work.
status: confirmed
category_codes:
- '04'
key_attributes: {}
provenance:
- said_by: registry
  session_id: seed.roles
  confidence: 1.0
  status: confirmed
  ts: '2026-08-06T04:50:54.121984+00:00'
- said_by: kishor-goswami-business-analysis-specia-fe69
  session_id: s_20260805_1515
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T09:52:21.873Z'
  account: Person responsible for development, testing, and client demos during the project lifecycle.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_20260805_2309
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T17:47:12.443Z'
  account: Provides technical perspective during discovery and oversees development work.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_20260805_2309
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T17:49:03.342Z'
  account: Developers who receive task assignments based on testing feedback.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_20260806_0618
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T00:56:20.222Z'
  account: Developers who build the software based on requirements and seek clarifications.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:47:05.130Z'
  account: Develops the software and performs the handover notification to QA.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:48:04.316Z'
  account: Developers who write code and prepare change sets.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:49:53.446Z'
  account: Develops code and deploys it once approval is received.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:51:19.429Z'
  account: Developers who implement code changes.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:57:56.896Z'
  account: The role responsible for implementing code changes and fixing bugs.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:58:43.184Z'
  account: Developers who fix software bugs.
edges:
- type: PERFORMS
  to: act.bug-fixing
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:58:43.184Z'
- type: PERFORMS
  to: act.conduct-product-demo
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:52:21.873Z'
- type: PERFORMS
  to: act.develop-software
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:48:04.316Z'
- type: PERFORMS
  to: act.development-oversight
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_20260805_2309
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T17:47:12.443Z'
- type: PERFORMS
  to: act.document-uat-feedback
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:52:21.873Z'
- type: PERFORMS
  to: act.execute-go-live
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:49:53.446Z'
- type: PERFORMS
  to: act.implement-changes
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:51:19.429Z'
- type: PERFORMS
  to: act.implement-uat-feedback
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:52:21.873Z'
- type: PERFORMS
  to: act.monitor-progress
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:52:21.873Z'
- type: PERFORMS
  to: act.notify-qa
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:47:05.130Z'
- type: PERFORMS
  to: act.perform-testing
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:52:21.873Z'
- type: PERFORMS
  to: act.submit-user-story-document
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:52:21.873Z'
- type: PERFORMS
  to: act.technical-discovery
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_20260805_2309
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T17:47:12.443Z'
timestamp: '2026-08-06T04:50:54.121984+00:00'
---

# Technical Specialist

> **Role** `role.technical-specialist` · status **confirmed** · keywords: Developer, Dev, TS, Engineer, developers, developer team, Development Team, developer, dev, development team, devs

Technical Specialist — a role in this organisation. Seeded from the engagement's role registry so that every way people refer to it resolves onto one node; its responsibilities are filled in as people describe their work.

## Facts
- 2026-08-06 — registry (session seed.roles, confidence 1, confirmed)
- 2026-08-05 — kishor-goswami-business-analysis-specia-fe69 (session s_20260805_1515, confidence 0.7, confirmed)
- 2026-08-05 — chandu-bhai-solution-architect-6dc3 (session s_20260805_2309, confidence 0.7, confirmed)
- 2026-08-05 — chandu-bhai-solution-architect-6dc3 (session s_20260805_2309, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_20260806_0618, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)

## Links
- PERFORMS → [[act.bug-fixing]] — Bug Fixing
- PERFORMS → [[act.conduct-product-demo]] — Conduct Product Demo
- PERFORMS → [[act.develop-software]] — Develop Software
- PERFORMS → [[act.development-oversight]] — Development Oversight
- PERFORMS → [[act.document-uat-feedback]] — Document UAT Feedback
- PERFORMS → [[act.execute-go-live]] — Execute Go-Live
- PERFORMS → [[act.implement-changes]] — Implement Changes
- PERFORMS → [[act.implement-uat-feedback]] — Implement UAT Feedback
- PERFORMS → [[act.monitor-progress]] — Monitor Progress
- PERFORMS → [[act.notify-qa]] — Notify QA
- PERFORMS → [[act.perform-testing]] — Perform Testing
- PERFORMS → [[act.submit-user-story-document]] — Submit User Story Document
- PERFORMS → [[act.technical-discovery]] — Technical Discovery

## Backlinks
- [[act.code-and-change-set-review]] (Code and Change Set Review) — HANDS_OFF_TO
- [[act.development-oversight]] (Development Oversight) — HANDS_OFF_TO
- [[act.test-and-deployment-management]] (Test and Deployment Management) — HANDS_OFF_TO

<!-- auto-generated by warp-compass-brain; edit via the pipeline, not by hand -->
