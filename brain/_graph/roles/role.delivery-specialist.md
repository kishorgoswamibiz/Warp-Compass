---
type: Role
id: role.delivery-specialist
title: Delivery Specialist
keywords:
- Project Manager
- PM
- DS
- Delivery Manager
- project manager
description: Delivery Specialist — a role in this organisation. Seeded from the engagement's role registry
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
  account: Person responsible for managing the project and providing effort estimations.
- said_by: rahul-delivery-delivery-specialist-2326
  session_id: s_20260805_2259
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T17:32:14.753Z'
  account: Compiles project timeline and efforts, hands off to account management, participates in discovery,
    and manages project timelines day-to-day.
- said_by: rahul-delivery-delivery-specialist-2326
  session_id: s_20260805_2259
  confidence: 0.7
  status: confirmed
  ts: '2026-08-05T17:34:12.819Z'
  account: Manages project efforts, timelines, stakeholders, coordinates with account management, and
    provides project status updates to the CEO.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_20260806_0618
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T00:50:57.659Z'
  account: Creates timelines and finalizes project plans.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_20260806_0618
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T00:54:14.576Z'
  account: Delivery management role responsible for project management.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_20260806_0618
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T00:56:20.222Z'
  account: Project manager who reviews documentation and manages the delivery process.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:47:05.130Z'
  account: Manages the project timeline and the overall handover process.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:49:13.457Z'
  account: Responsible for reviewing the project timeline.
- said_by: chandu-bhai-solution-architect-6dc3
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:54:15.502Z'
  account: Manages project timelines and milestones after solutions are defined.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:55:58.213Z'
  account: Oversees delivery of projects, including timeline management.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T01:57:56.896Z'
  account: The role responsible for coordinating validation and assignment of issues.
- said_by: kishor-goswami-business-analysis-specia-c3ab
  session_id: s_next
  confidence: 0.7
  status: confirmed
  ts: '2026-08-06T02:00:03.771Z'
  account: Responsible for managing the team and explaining the to-be process.
edges:
- type: OWNS
  to: stg.build-phase
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:47:05.130Z'
- type: OWNS
  to: stg.testing
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:47:05.130Z'
- type: PERFORMS
  to: act.bug-validation
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:57:56.896Z'
- type: PERFORMS
  to: act.client-needs-discovery-and-documentation
  provenance:
  - said_by: rahul-delivery-delivery-specialist-2326
    session_id: s_20260805_2259
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T17:32:14.753Z'
- type: PERFORMS
  to: act.compile-project-timeline-and-efforts
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:55:58.213Z'
- type: PERFORMS
  to: act.effort-estimation
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-fe69
    session_id: s_20260805_1515
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T09:52:21.873Z'
- type: PERFORMS
  to: act.explain-to-be-process-internally
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T02:00:03.771Z'
- type: PERFORMS
  to: act.project-management
  provenance:
  - said_by: rahul-delivery-delivery-specialist-2326
    session_id: s_20260805_2259
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T17:34:12.819Z'
- type: PERFORMS
  to: act.project-timeline-creation
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:54:15.502Z'
- type: PERFORMS
  to: act.review-project-timeline
  provenance:
  - said_by: chandu-bhai-solution-architect-6dc3
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T01:49:13.457Z'
- type: PERFORMS
  to: act.review-user-story-documents
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_20260806_0618
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T00:56:20.222Z'
- type: PERFORMS
  to: act.send-to-be-process-for-client-sign-off
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_next
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T02:00:03.771Z'
- type: PERFORMS
  to: act.submit-final-user-story-document
  provenance:
  - said_by: kishor-goswami-business-analysis-specia-c3ab
    session_id: s_20260806_0618
    confidence: 0.7
    status: unverified
    ts: '2026-08-06T00:56:20.222Z'
- type: REPORTS_TO
  to: role.chief-executive-officer
  provenance:
  - said_by: rahul-delivery-delivery-specialist-2326
    session_id: s_20260805_2259
    confidence: 0.7
    status: unverified
    ts: '2026-08-05T17:34:12.819Z'
timestamp: '2026-08-06T04:50:54.121984+00:00'
---

# Delivery Specialist

> **Role** `role.delivery-specialist` · status **confirmed** · keywords: Project Manager, PM, DS, Delivery Manager, project manager

Delivery Specialist — a role in this organisation. Seeded from the engagement's role registry so that every way people refer to it resolves onto one node; its responsibilities are filled in as people describe their work.

## Facts
- 2026-08-06 — registry (session seed.roles, confidence 1, confirmed)
- 2026-08-05 — kishor-goswami-business-analysis-specia-fe69 (session s_20260805_1515, confidence 0.7, confirmed)
- 2026-08-05 — rahul-delivery-delivery-specialist-2326 (session s_20260805_2259, confidence 0.7, confirmed)
- 2026-08-05 — rahul-delivery-delivery-specialist-2326 (session s_20260805_2259, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_20260806_0618, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_20260806_0618, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_20260806_0618, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — chandu-bhai-solution-architect-6dc3 (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)
- 2026-08-06 — kishor-goswami-business-analysis-specia-c3ab (session s_next, confidence 0.7, confirmed)

## Links
- OWNS → [[stg.build-phase]] — Build Phase
- OWNS → [[stg.testing]] — Testing
- PERFORMS → [[act.bug-validation]] — Bug Validation
- PERFORMS → [[act.client-needs-discovery-and-documentation]] — Client Needs Discovery and Documentation
- PERFORMS → [[act.compile-project-timeline-and-efforts]] — Compile Project Timeline and Efforts
- PERFORMS → [[act.effort-estimation]] — Effort Estimation
- PERFORMS → [[act.explain-to-be-process-internally]] — Explain To-Be Process Internally
- PERFORMS → [[act.project-management]] — Project Management
- PERFORMS → [[act.project-timeline-creation]] — Project Timeline Creation
- PERFORMS → [[act.review-project-timeline]] — Review Project Timeline
- PERFORMS → [[act.review-user-story-documents]] — Review User Story Documents
- PERFORMS → [[act.send-to-be-process-for-client-sign-off]] — Send To-Be Process for Client Sign-Off
- PERFORMS → [[act.submit-final-user-story-document]] — Submit Final User Story Document
- REPORTS_TO → [[role.chief-executive-officer]] — Chief Executive Officer

## Backlinks
- [[act.create-user-story-documents]] (Create User Story Documents) — HANDS_OFF_TO
- [[act.solutioning-and-estimation]] (Solutioning and Estimation) — HANDS_OFF_TO
- [[act.technical-solution-definition]] (Technical Solution Definition) — HANDS_OFF_TO

<!-- auto-generated by warp-compass-brain; edit via the pipeline, not by hand -->
