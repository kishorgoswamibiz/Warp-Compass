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
from .roles import REGISTRY_SAID_BY, resolve_declared_roles


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
    #: Personas who **declared** this role at onboarding but whose answers have not produced any of
    #: its activities yet (P16a). Since P16a a declared role is *owned* for routing purposes, so
    #: these people are already receiving its handoffs and its inherited gaps — this list is what
    #: keeps that visible instead of silent (phase-16 R1).
    declared_by: list[str] = field(default_factory=list)

    @property
    def has_interviewed_owner(self) -> bool:
        return bool(self.interviewed_by)

    @property
    def is_declared_but_silent(self) -> bool:
        """Somebody says they hold this role, but has described none of its work yet.

        Materially different from "nobody owns this": that is an invite-list entry, this is a person
        already in the engagement who simply hasn't been asked the right questions yet — and after
        P16a-bis, one who is now being asked them. Before P16a the two were indistinguishable.
        """
        return bool(self.declared_by) and not self.interviewed_by


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
    #: Roles named anywhere in the graph that nobody has been interviewed as **and** nobody has
    #: declared. The invite list when the lifecycle hasn't been mapped yet.
    roles_without_an_owner: list[RoleCoverage] = field(default_factory=list)
    #: Roles somebody DECLARED at onboarding but whose work nobody has described yet (P16a). Not an
    #: invite-list entry — the person is already here and is already being asked (P16a-bis). Listed
    #: separately so a declared role that stays empty round after round is visible: either the
    #: questions aren't landing, or the chip was ticked in error (phase-16 R1/R8).
    roles_declared_but_silent: list[RoleCoverage] = field(default_factory=list)
    #: Activities with no `PART_OF` stage — the work the lifecycle spine hasn't absorbed yet.
    activities_outside_any_stage: int = 0

    @property
    def silent_stages(self) -> list[StageCoverage]:
        return [s for s in self.stages if s.is_silent]


def build_coverage(graph: GraphStore, declared_roles=None) -> CoverageReport:
    """Compute the stage × role matrix from a single snapshot. Read-only.

    ``declared_roles`` is ``persona_id -> declared role titles`` from the bus
    (``lifecycle.declared_roles``). Optional: without it the report is exactly the P15b one,
    which is what the tests over a bare graph rely on.
    """
    snap = load_snapshot(graph)

    stages = sorted(
        (c for c in snap.nodes.values() if c.type is NodeType.STAGE), key=lambda c: c.id
    )
    all_roles = sorted(
        (c for c in snap.nodes.values() if c.type is NodeType.ROLE), key=lambda c: c.id
    )

    declarers: dict[str, set[str]] = {}
    for persona_id, titles in (declared_roles or {}).items():
        for role_id in resolve_declared_roles(titles, all_roles):
            declarers.setdefault(role_id, set()).add(persona_id)

    def owners_of(role_id: str) -> list[str]:
        """Personas that own the role by having *described its work*.

        Deliberately narrower than ``crosspersona._role_owner_personas``, which since P16a also
        counts a declared role as owned. This report exists to show whether anyone has actually been
        **interviewed** as the role, so declaration is reported separately (``declared_by``) rather
        than folded in — merging them would hide precisely the case P16a introduced, a role with a
        routing target but no described work.

        The seeded registry is excluded: it is vocabulary, not a person who can be interviewed.
        """
        personas: set[str] = set()
        for act_id in snap.out(role_id, EdgeType.PERFORMS):
            card = snap.nodes.get(act_id)
            if card is not None:
                personas.update(p.said_by for p in card.provenance)
        return sorted(personas - {REGISTRY_SAID_BY})

    def declared_of(role_id: str, interviewed: list[str]) -> list[str]:
        return sorted(declarers.get(role_id, set()) - set(interviewed))

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
            interviewed = owners_of(role_id)
            roles.append(
                RoleCoverage(
                    role_id=role_id,
                    role_name=card.canonical_name,
                    interviewed_by=interviewed,
                    via=sorted(via_by_role[role_id]),
                    declared_by=declared_of(role_id, interviewed),
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
        # invite — listing all ten every time would drown the real signal (ADR #33). A role somebody
        # DECLARED is claimed, though, even if only the registry has spoken about it, so it belongs
        # in the report as declared-but-silent rather than being skipped.
        if all(p.said_by == REGISTRY_SAID_BY for p in card.provenance) and card.id not in declarers:
            continue
        interviewed = owners_of(card.id)
        if not interviewed:
            entry = RoleCoverage(
                role_id=card.id,
                role_name=card.canonical_name,
                declared_by=declared_of(card.id, interviewed),
            )
            if entry.is_declared_but_silent:
                report.roles_declared_but_silent.append(entry)
            else:
                report.roles_without_an_owner.append(entry)

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
            mark = "[x]" if r.has_interviewed_owner else ("[~]" if r.declared_by else "[ ]")
            if r.interviewed_by:
                who = ", ".join(r.interviewed_by)
            elif r.declared_by:
                who = "DECLARED, NOT YET DESCRIBED: " + ", ".join(r.declared_by)
            else:
                who = "NOT INTERVIEWED"
            lines.append(f"    {mark} {r.role_name:<38} {'+'.join(r.via):<22} {who}")

    if report.roles_declared_but_silent:
        lines.append("")
        lines.append("## Roles someone declared but hasn't described yet")
        lines.append(
            "    (already receiving this role's questions - NOT an invite-list entry. If one of"
        )
        lines.append("     these stays empty round after round, the chip may have been a mistake.)")
        for r in report.roles_declared_but_silent:
            lines.append(
                f"    [~] {r.role_name}  ({r.role_id})  declared by: " + ", ".join(r.declared_by)
            )

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
