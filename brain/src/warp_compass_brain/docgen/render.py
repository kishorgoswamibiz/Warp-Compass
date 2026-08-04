"""Render the document models to Markdown + Mermaid (phase-10 brief, step 5).

Markdown/Mermaid first because both render natively in the PWA, GitHub, and most viewers with no
toolchain; Word/PDF export is additive behind the same models. The renderer is a pure function of
the models built by :mod:`traverse` — it adds no facts, only formatting, so traceability and the
confidence filter decided upstream are preserved verbatim.
"""

from __future__ import annotations

from ..alignment import Finding, FindingKind
from .traverse import (
    CategorySection,
    DiagramEdge,
    DiagramNode,
    DocNode,
    EndToEnd,
    GeneratedDocs,
    ProblemEntry,
    RoleSOP,
    SOPActivity,
    StageGroup,
)

_STATUS_MARKER = {
    "confirmed": "",
    "unverified": " _(unverified)_",
    "proposed": " _(proposed)_",
    "conflicting": " ⚠️ _(conflicting)_",
}


#: persona_id -> "Rahul Mehta (Business Analyst)". Supplied by the CLI from the bus profiles (P13);
#: an id with no entry renders as the raw id, so a retired, unknown, or pre-P13 persona still works.
PersonaNames = dict[str, str]


def render_markdown(docs: GeneratedDocs, names: PersonaNames | None = None) -> str:
    """The full deliverable: end-to-end process, per-role SOPs, and the problem register."""
    mode = "all knowledge" if docs.include_unverified else "confirmed knowledge only"
    names = names or {}
    parts = [
        "# Process Documentation",
        "",
        f"_Generated from the live knowledge graph — {mode}. Regenerate any time; this is a "
        "living view, not a one-off export._",
        "",
        _render_end_to_end(docs.end_to_end, names),
        _render_categories(docs.categories, names),
        _render_sops(docs.sops, names),
        _render_problems(docs.problems, docs.orphan_desires, names),
        _render_findings(docs, names),
    ]
    return "\n".join(p for p in parts if p).rstrip() + "\n"


# --- traceability + markers -------------------------------------------------------------------


def _marker(status: str) -> str:
    return _STATUS_MARKER.get(status, "")


def _who(said_by: str, names: PersonaNames) -> str:
    """A person's name where we know it; the raw persona id where we don't (never a blank)."""
    return names.get(said_by, said_by)


def _trace(node: DocNode, names: PersonaNames) -> str:
    if not node.sources:
        return "_(source: unknown)_"
    head = node.sources[0]
    extra = f" +{len(node.sources) - 1} more" if len(node.sources) > 1 else ""
    return f"_(source: {_who(head.said_by, names)} @ {head.ts[:10]}{extra})_"


def _node_line(node: DocNode, names: PersonaNames, *, prefix: str = "- ") -> str:
    return f"{prefix}**{node.name}**{_marker(node.status)} — {_trace(node, names)}"


# --- 1) end-to-end ----------------------------------------------------------------------------


def _render_end_to_end(e2e: EndToEnd, names: PersonaNames) -> str:
    lines = ["## 1. End-to-End Process", ""]
    if e2e.unbroken:
        lines.append("✅ The process forms one connected chain from a first trigger to a final "
                     "output.")
    else:
        lines.append("⚠️ The end-to-end chain is **not yet unbroken** — see _Gaps_ below; missing "
                     "links are shown, never bridged.")
    lines.append("")

    if e2e.stages:
        owned = [s for s in e2e.stages if s.owner_name]
        lines.append(
            f"The journey has **{len(e2e.stages)} "
            f"{'stage' if len(e2e.stages) == 1 else 'stages'}**: "
            + " → ".join(s.label for s in e2e.stages)
            + f". {len(owned)} of them {'has' if len(owned) == 1 else 'have'} a named owner."
        )
        lines.append("")

    if e2e.diagram_nodes:
        lines.append(_mermaid(e2e.diagram_nodes, e2e.diagram_edges, e2e.stages))
        lines.append("")

    if e2e.narrative:
        lines.append("### Walkthrough")
        lines.append("")
        for i, step in enumerate(e2e.narrative, start=1):
            lines.append(f"{i}. {step.line} {_trace(step.node, names)}")
        lines.append("")

    if e2e.gaps:
        lines.append("### Gaps (surfaced, not bridged)")
        lines.append("")
        for g in e2e.gaps:
            tag = "broken chain" if g.kind == "broken_chain" else "dangling handoff"
            lines.append(f"- **[{tag}]** {g.detail}")
        lines.append("")

    if e2e.hidden_count:
        lines.append(
            f"> {e2e.hidden_count} activit{'y' if e2e.hidden_count == 1 else 'ies'} hidden as "
            "not-yet-confirmed. Pass `--include-unverified` to show them (marked)."
        )
        lines.append("")
    return "\n".join(lines)


def _mermaid(
    nodes: list[DiagramNode],
    edges: list[DiagramEdge],
    stages: list[StageGroup] | None = None,
) -> str:
    """The process map. With stages known, activities are grouped into Mermaid **subgraphs**.

    That grouping is what makes the diagram legible to a client (P15c §7.3): it reads as the journey
    of one piece of work, phase by phase, instead of a flat mesh. With no stages yet it falls back
    to the P10 flat diagram unchanged — the spine is additive, never required.
    """
    lines = ["```mermaid", "flowchart TD"]

    def declare(n: DiagramNode, indent: str = "    ") -> list[str]:
        nid = _safe(n.id)
        label = _esc(n.label)
        if n.kind == "event":
            shape = f"{nid}([{label}])"
        elif n.kind == "artifact":
            shape = f"{nid}[/{label}/]"
        elif n.kind == "gap_role":
            shape = f"{nid}({label})"
        else:  # activity
            shape = f"{nid}[{label}]"
        return [f"{indent}{shape}"]

    by_id = {n.id: n for n in nodes}
    staged: set[str] = set()
    for sg in stages or []:
        members = [aid for aid in sg.activity_ids if aid in by_id]
        if not members:
            continue
        staged.update(members)
        owner = f" — {sg.owner_name}" if sg.owner_name else ""
        lines.append(f'    subgraph {_safe(sg.id)}["{_esc(sg.label + owner)}"]')
        for aid in members:
            lines.extend(declare(by_id[aid], indent="        "))
        lines.append("    end")

    for n in nodes:
        if n.id in staged:
            continue
        lines.extend(declare(n))

    # Classes are emitted after every declaration: a `class` line inside a subgraph block is what
    # makes Mermaid attach the node to the wrong container.
    for n in nodes:
        cls = _node_class(n)
        if cls:
            lines.append(f"    class {_safe(n.id)} {cls};")

    for e in edges:
        arrow = "-.->" if e.dashed else "-->"
        lbl = f"|{_esc(e.label)}|" if e.label else ""
        lines.append(f"    {_safe(e.src)} {arrow}{lbl} {_safe(e.dst)}")
    lines.append("    classDef gap stroke-dasharray:4,stroke:#c0392b,color:#c0392b;")
    lines.append("    classDef conflict stroke:#e67e22,color:#e67e22;")
    lines.append("    classDef unverified stroke-dasharray:2,stroke:#888;")
    lines.append("```")
    return "\n".join(lines)


def _node_class(n: DiagramNode) -> str:
    if n.gap:
        return "gap"
    if n.status == "conflicting":
        return "conflict"
    if n.status in ("unverified", "proposed"):
        return "unverified"
    return ""


def _safe(node_id: str) -> str:
    """Mermaid node id: letters/digits/underscore only."""
    return "".join(c if c.isalnum() else "_" for c in node_id)


def _esc(text: str) -> str:
    return text.replace('"', "'").replace("[", "(").replace("]", ")").replace("\n", "<br/>")


# --- section numbering ------------------------------------------------------------------------


def _render_categories(sections: list[CategorySection], names: PersonaNames) -> str:
    if not sections:
        return ""
    lines = ["## 2. Process Map by Category", "",
             "_Sections follow the governed taxonomy codes (§11)._", ""]
    for s in sections:
        lines.append(f"### {s.code} {s.label}")
        lines.append("")
        for node in s.nodes:
            lines.append(_node_line(node, names))
        lines.append("")
    return "\n".join(lines)


# --- 3) SOPs ----------------------------------------------------------------------------------


def _render_sops(sops: list[RoleSOP], names: PersonaNames) -> str:
    if not sops:
        return ""
    lines = ["## 3. Standard Operating Procedures (by role)", ""]
    for sop in sops:
        lines.append(f"### {sop.role.name}{_marker(sop.role.status)}")
        lines.append("")
        lines.append(f"{_trace(sop.role, names)}")
        lines.append("")
        for act in sop.activities:
            lines.append(f"#### {act.node.name}{_marker(act.node.status)}")
            for label, vals in _sop_facets(act):
                if vals:
                    lines.append(f"- **{label}:** {', '.join(vals)}")
            lines.append(f"- {_trace(act.node, names)}")
            lines.append("")
    return "\n".join(lines)


def _sop_facets(act: SOPActivity) -> list[tuple[str, list[str]]]:
    return [
        ("Triggered by", act.triggers),
        ("Inputs", act.inputs),
        ("Systems", act.systems),
        ("Produces", act.produces),
        ("Hands off to", act.handoffs),
        ("Requires approval from", act.approvals),
        ("Governed by", act.rules),
        ("Exceptions", act.exceptions),
        ("Measured by", act.kpis),
    ]


# --- 3) problem register ----------------------------------------------------------------------


def _render_problems(
    problems: list[ProblemEntry], orphan_desires: list[DocNode], names: PersonaNames
) -> str:
    if not problems and not orphan_desires:
        return ""
    lines = ["## 4. Problem Register", ""]
    if not problems:
        lines.append("_No problems recorded yet._")
        lines.append("")
    for p in problems:
        lines.append(f"### {p.node.name}{_marker(p.node.status)}")
        if p.node.description:
            lines.append(f"- {p.node.description}")
        if p.affected_activities:
            lines.append(f"- **Affects:** {', '.join(p.affected_activities)}")
        if p.frequency:
            lines.append(f"- **Frequency:** {p.frequency}")
        if p.impact:
            lines.append(f"- **Impact:** {p.impact}")
        if p.suspected_cause:
            lines.append(f"- **Suspected cause:** {p.suspected_cause}")
        if p.desires:
            lines.append(f"- **Wished-for:** {', '.join(d.name for d in p.desires)}")
        lines.append(f"- {_trace(p.node, names)}")
        lines.append("")
    if orphan_desires:
        lines.append("### Wished-for outcomes (unlinked)")
        lines.append("")
        for d in orphan_desires:
            lines.append(_node_line(d, names))
        lines.append("")
    return "\n".join(lines)


# --- N) gaps & recommendations (P15c §7.3) ----------------------------------------------------
#
# The consulting half of the deliverable. Three ranked groups, in this order on purpose:
#
#   1. misalignments   — what people disagree about ACROSS levels. Both accounts quoted, neither
#                        reconciled away (ADR #32). This is what a client argues with, and what
#                        justifies the engagement.
#   2. structural      — what the shape of the graph shows, with no disagreement needed at all.
#   3. knowledge gaps  — what we still haven't been told. Last, because it's our homework.
#
# Every entry carries its source or the roles it concerns: a consulting finding without a source is
# an opinion.

_FINDING_LABEL = {
    FindingKind.MISALIGNMENT: "Misalignment across levels",
    FindingKind.UNOWNED_STAGE: "Unowned stage",
    FindingKind.EXPECTATION_WITHOUT_EXECUTION: "Expectation with nothing behind it",
    FindingKind.APPROVAL_WITHOUT_CRITERIA: "Approval with no criteria",
    FindingKind.UNMEASURED_STAGE: "Unmeasured stage",
    FindingKind.SINGLE_POINT_OF_FAILURE: "Single point of failure",
    FindingKind.DUPLICATED_WORK: "Duplicated work",
    FindingKind.SILENT_STAGE: "Silent stage (nobody interviewed)",
    FindingKind.REPORTING_CYCLE: "Reporting line forms a loop",
}


def _render_findings(docs: GeneratedDocs, names: PersonaNames) -> str:
    total = len(docs.misalignments) + len(docs.structural_findings) + len(docs.knowledge_gaps)
    if not total:
        return ""

    lines = ["## Gaps & Recommendations", ""]
    lines.append(
        f"_{len(docs.misalignments)} misalignment(s), {len(docs.structural_findings)} structural "
        f"finding(s), {len(docs.knowledge_gaps)} open question(s). Every item is derived from the "
        "graph and carries its source._"
    )
    lines.append("")

    if docs.misalignments:
        lines.append("### Misalignments — recorded, not reconciled")
        lines.append("")
        lines.append(
            "> Where an account differs **across levels of the organisation**, both versions are "
            "kept as given. The difference *is* the finding: nobody has been asked to talk the "
            "other out of their version."
        )
        lines.append("")
        for f in docs.misalignments:
            lines.extend(_render_misalignment(f, names))

    if docs.structural_findings:
        lines.append("### Structural findings")
        lines.append("")
        for f in docs.structural_findings:
            lines.extend(_render_structural(f))
        lines.append("")  # a heading straight after a list item doesn't render as a heading

    if docs.knowledge_gaps:
        lines.append("### Still to be told")
        lines.append("")
        lines.append(
            "_Open questions, not defects in the business. These close as more people are "
            "interviewed._"
        )
        lines.append("")
        for g in docs.knowledge_gaps:
            who = f" _(ask: {g.role_name})_" if g.role_name else ""
            lines.append(f"- {g.detail}{who}")
        lines.append("")

    return "\n".join(lines)


def _render_misalignment(f: Finding, names: PersonaNames) -> list[str]:
    lines = [f"#### {f.node_name or 'Unnamed'}", "", f.detail, ""]
    for a in f.accounts:
        level = f", level {a.altitude}" if a.altitude is not None else ", level unknown"
        role = a.role_name or "role not yet known"
        said = a.account.strip() or "_(their wording predates account capture)_"
        lines.append(f"- **{role}**{level} — {_who(a.said_by, names)}: {said}")
    lines.append("")
    if f.recommendation:
        lines.append(f"**Recommendation.** {f.recommendation}")
        lines.append("")
    return lines


def _render_structural(f: Finding) -> list[str]:
    label = _FINDING_LABEL.get(f.kind, f.kind.value.replace("_", " "))
    lines = [f"- **[{label}]** {f.detail}"]
    if f.role_names:
        lines.append(f"  - Concerns: {', '.join(f.role_names)}")
    if f.recommendation:
        lines.append(f"  - _Recommendation:_ {f.recommendation}")
    return lines
