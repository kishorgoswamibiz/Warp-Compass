"""The stage × role coverage matrix — "who should we invite next?" (P15b, plan §8.4).

A read-only operator report, derived **entirely from the graph**. It adds no question types and no
mechanism: for each lifecycle stage it lists the roles named in it and says which of those has an
*interviewed owner*, i.e. somebody whose own answers produced that role's activities.

Two things it makes visible that nothing else does:

* **A silent stage** — a phase someone named, with work happening inside it, that nobody has been
  interviewed about. That is the invite list.
* **A forked role** (risk R1) — a role with no owner shows up here as an owner-less row rather than
  hiding. If "the PM" ever escapes the alias table and mints a rival ``role.project-manager``, this
  is where it surfaces.

"Named in a stage" is deliberately broad: a role counts if it ``OWNS`` the stage, or ``PERFORMS`` an
activity that is ``PART_OF`` it, or is handed work by one (``HANDS_OFF_TO``). A role that only
receives work still belongs on the invite list — arguably most of all, since nobody has described
their side yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .completeness import load_snapshot
from .graphstore.base import GraphStore
from .models import EdgeType, NodeType
from .roles import REGISTRY_SAID_BY


@dataclass
class RoleCoverage:
    """One role's presence in one stage."""

    role_id: str
    role_name: str
    #: Personas whose interviews produced this role's activities — i.e. people who *are* the role.
    #: Empty means the role is named but nobody has been interviewed as it.
    interviewed_by: list[str] = field(default_factory=list)
    #: How the role turns up in this stage: "owns", "performs", "receives" (may be several).
    via: list[str] = field(default_factory=list)

    @property
    def has_interviewed_owner(self) -> bool:
        return bool(self.interviewed_by)


@dataclass
class StageCoverage:
    """One stage and every role named in it."""

    stage_id: str
    stage_name: str
    activity_count: int
    roles: list[RoleCoverage] = field(default_factory=list)

    @property
    def is_silent(self) -> bool:
        """Work happens here, but nobody who works here has been interviewed."""
        return not any(r.has_interviewed_owner for r in self.roles)

    @property
    def is_unowned(self) -> bool:
        """No role is *accountable* for the stage (no OWNS edge) — a §7.2 structural finding."""
        return not any("owns" in r.via for r in self.roles)


@dataclass
class CoverageReport:
    stages: list[StageCoverage] = field(default_factory=list)
    #: Roles named anywhere in the graph that nobody has been interviewed as, stage or no stage.
    #: The invite list when the lifecycle hasn't been mapped yet.
    roles_without_an_owner: list[RoleCoverage] = field(default_factory=list)
    #: Activities with no `PART_OF` stage — the work the lifecycle spine hasn't absorbed yet.
    activities_outside_any_stage: int = 0

    @property
    def silent_stages(self) -> list[StageCoverage]:
        return [s for s in self.stages if s.is_silent]


def build_coverage(graph: GraphStore) -> CoverageReport:
    """Compute the stage × role matrix from a single snapshot. Read-only."""
    snap = load_snapshot(graph)

    stages = sorted(
        (c for c in snap.nodes.values() if c.type is NodeType.STAGE), key=lambda c: c.id
    )
    all_roles = sorted(
        (c for c in snap.nodes.values() if c.type is NodeType.ROLE), key=lambda c: c.id
    )

    def owners_of(role_id: str) -> list[str]:
        """Personas that own the role: those who contributed the activities it performs.

        Mirrors ``crosspersona._role_owner_personas`` — merely *mentioning* a role is not owning it.
        The seeded registry is excluded: it is vocabulary, not a person who can be interviewed.
        """
        personas: set[str] = set()
        for act_id in snap.out(role_id, EdgeType.PERFORMS):
            card = snap.nodes.get(act_id)
            if card is not None:
                personas.update(p.said_by for p in card.provenance)
        return sorted(personas - {REGISTRY_SAID_BY})

    report = CoverageReport()

    for stage in stages:
        act_ids = [a for a in snap.inc(stage.id, EdgeType.PART_OF) if a in snap.nodes]
        via_by_role: dict[str, set[str]] = {}
        for role_id in snap.inc(stage.id, EdgeType.OWNS):
            via_by_role.setdefault(role_id, set()).add("owns")
        for act_id in act_ids:
            for role_id in snap.inc(act_id, EdgeType.PERFORMS):
                via_by_role.setdefault(role_id, set()).add("performs")
            for role_id in snap.out(act_id, EdgeType.HANDS_OFF_TO):
                via_by_role.setdefault(role_id, set()).add("receives")

        roles = []
        for role_id in sorted(via_by_role):
            card = snap.nodes.get(role_id)
            if card is None:
                continue
            roles.append(
                RoleCoverage(
                    role_id=role_id,
                    role_name=card.canonical_name,
                    interviewed_by=owners_of(role_id),
                    via=sorted(via_by_role[role_id]),
                )
            )
        report.stages.append(
            StageCoverage(
                stage_id=stage.id,
                stage_name=stage.canonical_name,
                activity_count=len(act_ids),
                roles=roles,
            )
        )

    for card in all_roles:
        # A registry-only role is vocabulary nobody has claimed yet, not a person we failed to
        # invite — listing all ten every time would drown the real signal (ADR #33).
        if all(p.said_by == REGISTRY_SAID_BY for p in card.provenance):
            continue
        if not owners_of(card.id):
            report.roles_without_an_owner.append(
                RoleCoverage(role_id=card.id, role_name=card.canonical_name)
            )

    report.activities_outside_any_stage = sum(
        1
        for c in snap.nodes.values()
        if c.type is NodeType.ACTIVITY and not snap.out(c.id, EdgeType.PART_OF)
    )
    return report


def render_coverage(report: CoverageReport) -> str:
    """A terminal-readable matrix. The operator's "who to invite next" answer.

    **Pure ASCII, deliberately.** Python on Windows gives this process a ``cp1252`` stdout, and a
    tick mark (``U+2713``) is not in that codepage — printing one raises ``UnicodeEncodeError`` and
    takes the whole command down. The empty-graph path happens to be ASCII, so this only failed once
    a stage had an interviewed role, i.e. on real data rather than in a smoke test. Guarded by
    ``test_render_is_pure_ascii_so_it_cannot_crash_a_windows_console``.
    """
    lines: list[str] = []
    if not report.stages:
        lines.append("No lifecycle stages in the graph yet - nothing to map coverage against.")
        lines.append("(Stages are discovered from interviews; they are never predefined.)")
    for stage in report.stages:
        flags = []
        if stage.is_silent:
            flags.append("SILENT - nobody here has been interviewed")
        if stage.is_unowned:
            flags.append("UNOWNED - no role is accountable")
        suffix = f"   [{'; '.join(flags)}]" if flags else ""
        lines.append("")
        lines.append(f"## {stage.stage_name}  ({stage.activity_count} activities){suffix}")
        if not stage.roles:
            lines.append("    (no roles named in this stage yet)")
        for r in stage.roles:
            mark = "[x]" if r.has_interviewed_owner else "[ ]"
            who = ", ".join(r.interviewed_by) if r.interviewed_by else "NOT INTERVIEWED"
            lines.append(f"    {mark} {r.role_name:<38} {'+'.join(r.via):<22} {who}")

    if report.roles_without_an_owner:
        lines.append("")
        lines.append("## Roles named but never interviewed (the invite list)")
        for r in report.roles_without_an_owner:
            lines.append(f"    [ ] {r.role_name}  ({r.role_id})")

    if report.activities_outside_any_stage:
        lines.append("")
        lines.append(
            f"## {report.activities_outside_any_stage} activities are not in any stage yet "
            "- the lifecycle spine hasn't absorbed them."
        )
    return "\n".join(lines).lstrip("\n")
