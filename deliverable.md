# Process Documentation
_Generated from the live knowledge graph — confirmed knowledge only. Regenerate any time; this is a living view, not a one-off export._
## 1. End-to-End Process

⚠️ The end-to-end chain is **not yet unbroken** — see _Gaps_ below; missing links are shown, never bridged.

```mermaid
flowchart TD
    act_develop_project_plan_and_effort_estimation[Develop Project Plan and Effort Estimation<br/>(Delivery Specialist)]
    class act_develop_project_plan_and_effort_estimation gap;
    act_submit_proposal_to_client[Submit Proposal to Client<br/>(Account Manager)]
    class act_submit_proposal_to_client gap;
    act_add_cost_estimation[Add Cost Estimation<br/>(Account Manager)]
    class act_add_cost_estimation gap;
    gap_role_end_client(End Client<br/>(not described))
    class gap_role_end_client gap;
    act_add_cost_estimation -->|Cost Estimation| act_submit_proposal_to_client
    act_develop_project_plan_and_effort_estimation -->|Effort and Time Estimates| act_add_cost_estimation
    act_develop_project_plan_and_effort_estimation -->|Effort and Time Estimates| act_submit_proposal_to_client
    act_submit_proposal_to_client -.->|handoff?| gap_role_end_client
    classDef gap stroke-dasharray:4,stroke:#c0392b,color:#c0392b;
    classDef conflict stroke:#e67e22,color:#e67e22;
    classDef unverified stroke-dasharray:2,stroke:#888;
```

### Walkthrough

1. **Develop Project Plan and Effort Estimation** — performed by Delivery Specialist; continues to Add Cost Estimation (Effort and Time Estimates), Submit Proposal to Client (Effort and Time Estimates). _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
2. **Add Cost Estimation** — performed by Account Manager; continues to Submit Proposal to Client (Cost Estimation). _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
3. **Submit Proposal to Client** — performed by Account Manager. _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_

### Gaps (surfaced, not bridged)

- **[dangling handoff]** Handoff from 'Submit Proposal to Client' to 'End Client' is one-sided: the receiving role performs no activity we know of.
- **[broken chain]** Activity 'Add Cost Estimation' is not on any path from a first trigger to a final output — the end-to-end chain is broken here.
- **[broken chain]** Activity 'Develop Project Plan and Effort Estimation' is not on any path from a first trigger to a final output — the end-to-end chain is broken here.
- **[broken chain]** Activity 'Submit Proposal to Client' is not on any path from a first trigger to a final output — the end-to-end chain is broken here.

> 21 activities hidden as not-yet-confirmed. Pass `--include-unverified` to show them (marked).

## 2. Process Map by Category

_Sections follow the governed taxonomy codes (§11)._

### 02 Core Activities

- **Add Cost Estimation** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Develop Project Plan and Effort Estimation** ⚠️ _(conflicting)_ — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Submit Proposal to Client** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_

### 04 Handoffs & Escalation

- **Account Manager** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Business Analyst** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Delivery Specialist** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Project Management Team** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Solution Architect** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_

### 07 Outputs & Artifacts

- **Approved Proposal** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Cost Estimation** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Detailed Requirements** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
- **Solution Design** — _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_

## 3. Standard Operating Procedures (by role)

### Account Manager

_(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_

#### Add Cost Estimation
- **Inputs:** Effort and Time Estimates, Project Plan
- **Produces:** Cost Estimation
- _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_

#### Submit Proposal to Client
- **Inputs:** Approved Proposal, Cost Estimation, Effort and Time Estimates, Solution Design
- **Hands off to:** End Client
- _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_

### Delivery Specialist

_(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_

#### Develop Project Plan and Effort Estimation ⚠️ _(conflicting)_
- **Inputs:** Solution Design
- **Produces:** Effort and Time Estimates, Project Plan
- _(source: Ajay Delivery (Delivery Specialist / Project Manager) @ 2026-07-28 +1 more)_
