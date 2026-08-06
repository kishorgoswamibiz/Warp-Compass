---
type: Role
id: role.solution-architect
title: Solution Architect
keywords:
- SA
- Architect
description: Solution Architect — a role in this organisation. Seeded from the engagement's role registry
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
  ts: '2026-08-05T09:47:43.952Z'
  account: Responsible for conducting product demos and sending proposals during the pre-sales phase.
- said_by: kishor-goswami-business-analysis-specia-fe69
  session_id: s_20260805_1515
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T09:49:38.132Z'
  account: The SA estimates the effort required for a proposed solution during pre-sales.
- said_by: kishor-goswami-business-analysis-specia-fe69
  session_id: s_20260805_1515
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T09:50:56.463Z'
  account: Provides technical solutions and effort estimates for requirements.
- said_by: rahul-delivery-delivery-specialist-2326
  session_id: s_20260805_2259
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T17:32:14.753Z'
  account: Provides solutions and effort estimates during pre-sales.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_20260805_2309
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T17:45:37.737Z'
  account: Provides complete solution oversight for projects, conducts code reviews, and participates
    in pre-sales calls.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_20260806_0618
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T00:50:57.659Z'
  account: Designs solutions and estimates effort based on requirements.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_20260806_0618
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T00:54:14.576Z'
  account: Solution architecture role responsible for technical design and feasibility.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_20260806_0618
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T00:56:20.222Z'
  account: Provides technical solutions and effort estimates for user stories.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:45:42.276Z'
  account: The Solution Architect verifies development work on their projects to ensure code and functional
    quality before completion, distinct from formal quality assurance.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:54:15.502Z'
  account: Designs and documents the technical solutions during discovery.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:57:56.896Z'
  account: The role responsible for reviewing technical aspects and guiding bug fixes.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T02:01:07.569Z'
  account: Provides technical solutions and effort estimates for user stories.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T02:02:36.250Z'
  account: Collaborates on discovery sessions and feedback implementation.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T02:03:14.238Z'
  account: Responsible for providing the technical solution based on the requirements.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T02:04:07.590Z'
  account: Responsible for defining the technical solution and assumptions.
edges:
- type: PERFORMS
  to: act.bug-fixing
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:57:56.896Z'
- type: PERFORMS
  to: act.client-needs-discovery-and-documentation
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T02:02:36.250Z'
- type: PERFORMS
  to: act.conduct-code-reviews
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_20260805_2309
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T17:45:37.737Z'
- type: PERFORMS
  to: act.conduct-product-demo
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:47:43.952Z'
- type: PERFORMS
  to: act.design-solution-architecture
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_20260805_2309
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T17:45:37.737Z'
- type: PERFORMS
  to: act.effort-estimation
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:49:38.132Z'
- type: PERFORMS
  to: act.implement-uat-feedback
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T02:02:36.250Z'
- type: PERFORMS
  to: act.send-proposal
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:47:43.952Z'
- type: PERFORMS
  to: act.solutioning-and-estimation
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_20260806_0618
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T00:50:57.659Z'
- type: PERFORMS
  to: act.technical-solution-definition
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T02:04:07.590Z'
- type: PERFORMS
  to: act.verify-development-quality
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:45:42.276Z'
timestamp: '2026-08-06T04:50:54.121984+00:00'
---

# Solution Architect

> **Role** `role.solution-architect` · status **confirmed** · keywords: SA, Architect

Solution Architect — a role in this organisation. Seeded from the engagement's role registry so that every way people refer to it resolves onto one node; its responsibilities are filled in as people describe their work.

## Facts
- 2026-08-06 — registry (session seed.roles, confidence 1, confirmed)
- 2026-08-05 — kishor-goswami-business-analysis-specia-fe69 (session s_20260805_1515, confidence 0.7, confirmed)
- 2026-08-05 — kishor-goswami-business-analysis-specia-fe69 (session s_20260805_1515, confidence 0.7, confirmed)
- 2026-08-05 — kishor-goswami-business-analysis-specia-fe69 (session s_20260805_1515, confidence 0.7, confirmed)
- 2026-08-05 — rahul-delivery-delivery-specialist-2326 (session s_20260805_2259, confidence 0.7, confirmed)
- 2026-08-05 — chandu-bhai-solution-architect-6dc3 (session s_20260805_2309, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_20260806_0618, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_20260806_0618, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_20260806_0618, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)

## Links
- PERFORMS → [[act.bug-fixing]] — Bug Fixing
- PERFORMS → [[act.client-needs-discovery-and-documentation]] — Client Needs Discovery and Documentation
- PERFORMS → [[act.conduct-code-reviews]] — Conduct Code Reviews
- PERFORMS → [[act.conduct-product-demo]] — Conduct Product Demo
- PERFORMS → [[act.design-solution-architecture]] — Design Solution Architecture
- PERFORMS → [[act.effort-estimation]] — Effort Estimation
- PERFORMS → [[act.implement-uat-feedback]] — Implement UAT Feedback
- PERFORMS → [[act.send-proposal]] — Send Proposal
- PERFORMS → [[act.solutioning-and-estimation]] — Solutioning and Estimation
- PERFORMS → [[act.technical-solution-definition]] — Technical Solution Definition
- PERFORMS → [[act.verify-development-quality]] — Verify Development Quality

## Backlinks
- [[act.client-needs-discovery-and-documentation]] (Client Needs Discovery and Documentation) — HANDS_OFF_TO
- [[act.create-user-story-documents]] (Create User Story Documents) — HANDS_OFF_TO
- [[act.user-story-creation]] (User Story Creation) — HANDS_OFF_TO

<!-- auto-generated by warp-compass-brain; edit via the pipeline, not by hand -->
