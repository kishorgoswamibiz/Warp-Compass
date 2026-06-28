"""Render the document models to Markdown + Mermaid (phase-10 brief, step 5).

Markdown/Mermaid first because both render natively in the PWA, GitHub, and most viewers with no
toolchain; Word/PDF export is additive behind the same models. The renderer is a pure function of
the models built by :mod:`traverse` — it adds no facts, only formatting, so traceability and the
confidence filter decided upstream are preserved verbatim.
"""

from __future__ import annotations

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
)

_STATUS_MARKER = {
    "confirmed": "",
    "unverified": " _(unverified)_",
    "proposed": " _(proposed)_",
    "conflicting": " ⚠️ _(conflicting)_",
}


def render_markdown(docs: GeneratedDocs) -> str:
    """The full deliverable: end-to-end process, per-role SOPs, and the problem register."""
    mode = "all knowledge" if docs.include_unverified else "confirmed knowledge only"
    parts = [
        "# Process Documentation",
        "",
        f"_Generated from the live knowledge graph — {mode}. Regenerate any time; this is a "
        "living view, not a one-off export._",
        "",
        _render_end_to_end(docs.end_to_end),
        _render_categories(docs.categories),
        _render_sops(docs.sops),
        _render_problems(docs.problems, docs.orphan_desires),
    ]
    return "\n".join(p for p in parts if p).rstrip() + "\n"


# --- traceability + markers -------------------------------------------------------------------


def _marker(status: str) -> str:
    return _STATUS_MARKER.get(status, "")


def _trace(node: DocNode) -> str:
    if not node.sources:
        return "_(source: unknown)_"
    head = node.sources[0]
    extra = f" +{len(node.sources) - 1} more" if len(node.sources) > 1 else ""
    return f"_(source: {head.said_by} @ {head.ts[:10]}{extra})_"


def _node_line(node: DocNode, *, prefix: str = "- ") -> str:
    return f"{prefix}**{node.name}**{_marker(node.status)} — {_trace(node)}"


# --- 1) end-to-end ----------------------------------------------------------------------------


def _render_end_to_end(e2e: EndToEnd) -> str:
    lines = ["## 1. End-to-End Process", ""]
    if e2e.unbroken:
        lines.append("✅ The process forms one connected chain from a first trigger to a final "
                     "output.")
    else:
        lines.append("⚠️ The end-to-end chain is **not yet unbroken** — see _Gaps_ below; missing "
                     "links are shown, never bridged.")
    lines.append("")

    if e2e.diagram_nodes:
        lines.append(_mermaid(e2e.diagram_nodes, e2e.diagram_edges))
        lines.append("")

    if e2e.narrative:
        lines.append("### Walkthrough")
        lines.append("")
        for i, step in enumerate(e2e.narrative, start=1):
            lines.append(f"{i}. {step.line} {_trace(step.node)}")
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


def _mermaid(nodes: list[DiagramNode], edges: list[DiagramEdge]) -> str:
    lines = ["```mermaid", "flowchart TD"]
    for n in nodes:
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
        lines.append(f"    {shape}")
        cls = _node_class(n)
        if cls:
            lines.append(f"    class {nid} {cls};")
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


def _render_categories(sections: list[CategorySection]) -> str:
    if not sections:
        return ""
    lines = ["## 2. Process Map by Category", "",
             "_Sections follow the governed taxonomy codes (§11)._", ""]
    for s in sections:
        lines.append(f"### {s.code} {s.label}")
        lines.append("")
        for node in s.nodes:
            lines.append(_node_line(node))
        lines.append("")
    return "\n".join(lines)


# --- 3) SOPs ----------------------------------------------------------------------------------


def _render_sops(sops: list[RoleSOP]) -> str:
    if not sops:
        return ""
    lines = ["## 3. Standard Operating Procedures (by role)", ""]
    for sop in sops:
        lines.append(f"### {sop.role.name}{_marker(sop.role.status)}")
        lines.append("")
        lines.append(f"{_trace(sop.role)}")
        lines.append("")
        for act in sop.activities:
            lines.append(f"#### {act.node.name}{_marker(act.node.status)}")
            for label, vals in _sop_facets(act):
                if vals:
                    lines.append(f"- **{label}:** {', '.join(vals)}")
            lines.append(f"- {_trace(act.node)}")
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


def _render_problems(problems: list[ProblemEntry], orphan_desires: list[DocNode]) -> str:
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
        lines.append(f"- {_trace(p.node)}")
        lines.append("")
    if orphan_desires:
        lines.append("### Wished-for outcomes (unlinked)")
        lines.append("")
        for d in orphan_desires:
            lines.append(_node_line(d))
        lines.append("")
    return "\n".join(lines)
