"""The alignment diagnostic (P15c, plan §7) — the half of the deliverable that isn't an SOP.

The engagement this system replaces is an EY/PwC-style one, and what a Big-4 report is actually made
of is not a process map: it is **findings**. This module produces two kinds, both computed
deterministically from the graph with no LLM call.

**1. Misalignment (§7.1).** When two people describe the same node differently, the system as built
erases the difference: ingest flags ``CONFLICTING``, completeness files an ``UNRESOLVED_CONFLICT``,
and the planner asks every contributor *"how does it actually work?"* until one version
survives. That is correct for data hygiene and exactly backwards for consulting. So the verdict
now branches on **derived altitude**:

* contributors at the **same** altitude — peers disagreeing about their own shared process — stay a
  data-quality problem and keep today's reconciliation routing;
* contributors at **different** altitudes — an exec and a doer — are a **finding**. Nobody is asked
  to reconcile it. Both accounts are preserved with who holds each, and it goes into the report.

The delta between what leadership believes happens and what actually happens *is the product*
(ADR #32).

**2. Structural findings (§7.2).** These need no disagreement and no conflict flag at all — they
fall straight out of the shape of the graph. An unowned stage, an expectation with nothing behind
it, an approval with no criteria, a stage nobody measures, a stage that rests on one person.

**Altitude is derived, never declared (§6.3, ADR #31).**::

    altitude(role) = REPORTS_TO hops from that role up to one with no outgoing REPORTS_TO

Roles at equal depth are peers. ``None`` means unknown, and an unknown altitude simply means a
divergence can't be classified yet — which is itself a reason to ask about reporting lines, and is
why P15b started scoring ``Role.reports_to``. A ``REPORTS_TO`` **cycle is a finding, not a crash**:
both roles are reported and treated as the same altitude.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .completeness import _Snapshot, load_snapshot
from .graphstore.base import GraphStore
from .models import ConfidenceStatus, EdgeType, NodeCard, NodeType
from .roles import REGISTRY_SAID_BY

# --- derived altitude -------------------------------------------------------------------------

#: Depth is capped so a pathological chain can't spin. Far above any real org.
_MAX_DEPTH = 64


@dataclass
class AltitudeMap:
    """Derived depth per role, plus the reporting cycles found on the way."""

    #: role_id -> hops up to the root. 0 is the top. ``None`` when it cannot be determined.
    depth: dict[str, int | None] = field(default_factory=dict)
    #: Roles caught in a `REPORTS_TO` cycle — a finding, reported rather than crashed on.
    cycles: list[list[str]] = field(default_factory=list)

    def of(self, role_id: str | None) -> int | None:
        return self.depth.get(role_id) if role_id else None

    def same_altitude(self, a: str | None, b: str | None) -> bool | None:
        """True/False, or ``None`` when either side's altitude is unknown."""
        da, db = self.of(a), self.of(b)
        if da is None or db is None:
            return None
        return da == db


def derive_altitudes(snap: _Snapshot) -> AltitudeMap:
    """Walk `REPORTS_TO` upward from every role. Pure graph query, nothing declared."""
    result = AltitudeMap()
    role_ids = [c.id for c in snap.nodes.values() if c.type is NodeType.ROLE]
    seen_cycles: set[frozenset[str]] = set()

    for rid in sorted(role_ids):
        path: list[str] = []
        on_path: set[str] = set()
        cur: str | None = rid
        depth: int | None = None
        while cur is not None:
            if cur in on_path:
                # A cycle: A reports to B reports to A. Report it and treat the members as peers,
                # which is what "same altitude" means for people who each think they report to the
                # other. Depth stays unknown — there is no root to count from.
                cycle = path[path.index(cur) :]
                key = frozenset(cycle)
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    result.cycles.append(cycle)
                depth = None
                break
            path.append(cur)
            on_path.add(cur)
            ups = [u for u in sorted(snap.out(cur, EdgeType.REPORTS_TO)) if u in snap.nodes]
            if not ups:
                depth = len(path) - 1  # `cur` is a root: no outgoing REPORTS_TO
                break
            if len(path) > _MAX_DEPTH:
                depth = None
                break
            cur = ups[0]  # first by id — a role reporting to two managers is a separate finding
        result.depth[rid] = depth
    return result


# --- findings ---------------------------------------------------------------------------------


class FindingKind(StrEnum):
    """The shape of an alignment finding. Distinct from `GapKind`: a gap is something we haven't
    been told, a finding is something we HAVE been told that is worth reporting."""

    MISALIGNMENT = "misalignment"                      # cross-altitude divergence (§7.1)
    UNOWNED_STAGE = "unowned_stage"                    # work happens, nobody accountable
    EXPECTATION_WITHOUT_EXECUTION = "expectation_without_execution"
    APPROVAL_WITHOUT_CRITERIA = "approval_without_criteria"
    UNMEASURED_STAGE = "unmeasured_stage"
    SINGLE_POINT_OF_FAILURE = "single_point_of_failure"
    DUPLICATED_WORK = "duplicated_work"
    SILENT_STAGE = "silent_stage"                      # named by someone, no interviewed owner
    REPORTING_CYCLE = "reporting_cycle"


#: Report order. Misalignments lead — they are the ones a client argues with, and the ones that
#: justify the engagement. Knowledge gaps are NOT here; they stay in `CompletenessReport`.
_SEVERITY: dict[FindingKind, int] = {
    FindingKind.MISALIGNMENT: 0,
    FindingKind.UNOWNED_STAGE: 1,
    FindingKind.EXPECTATION_WITHOUT_EXECUTION: 2,
    FindingKind.SINGLE_POINT_OF_FAILURE: 3,
    FindingKind.APPROVAL_WITHOUT_CRITERIA: 4,
    FindingKind.REPORTING_CYCLE: 5,
    FindingKind.UNMEASURED_STAGE: 6,
    FindingKind.DUPLICATED_WORK: 7,
    FindingKind.SILENT_STAGE: 8,
}


@dataclass(frozen=True)
class Account:
    """One person's own version of a node, recovered from provenance (§7.1)."""

    said_by: str
    #: Their own words, from `Provenance.account`. Empty for pre-P15c entries.
    account: str
    role_id: str | None = None
    role_name: str | None = None
    altitude: int | None = None
    ts: str = ""


@dataclass(frozen=True)
class Finding:
    """One reportable alignment finding, always traceable to its source."""

    kind: FindingKind
    #: One sentence a client can read.
    detail: str
    node_id: str | None = None
    node_name: str | None = None
    #: For a MISALIGNMENT: every contributor's own account, highest in the org first.
    accounts: tuple[Account, ...] = ()
    #: Roles the finding is about (a stage's owner, the roles duplicating work, the cycle members).
    role_ids: tuple[str, ...] = ()
    role_names: tuple[str, ...] = ()
    #: What to do about it. Deliberately plain and non-prescriptive — we surface, never invent.
    recommendation: str = ""

    @property
    def severity(self) -> int:
        return _SEVERITY.get(self.kind, 99)


@dataclass
class AlignmentReport:
    findings: list[Finding] = field(default_factory=list)
    altitudes: AltitudeMap = field(default_factory=AltitudeMap)

    def ranked(self) -> list[Finding]:
        """Most severe first; stable and deterministic within a severity band."""
        return sorted(self.findings, key=lambda f: (f.severity, f.node_id or "", f.detail))

    def of_kind(self, kind: FindingKind) -> list[Finding]:
        return [f for f in self.findings if f.kind is kind]

    @property
    def misalignments(self) -> list[Finding]:
        return self.of_kind(FindingKind.MISALIGNMENT)

    @property
    def structural(self) -> list[Finding]:
        return [f for f in self.ranked() if f.kind is not FindingKind.MISALIGNMENT]


class AlignmentEngine:
    """Computes derived altitude and every §7 finding. Read-only, no LLM, no network."""

    def __init__(self, graph: GraphStore) -> None:
        self._g = graph

    def assess(self) -> AlignmentReport:
        snap = load_snapshot(self._g)
        alt = derive_altitudes(snap)
        report = AlignmentReport(altitudes=alt)

        report.findings.extend(self._misalignments(snap, alt))
        report.findings.extend(self._reporting_cycles(snap, alt))
        report.findings.extend(self._stage_findings(snap))
        report.findings.extend(self._expectations_without_execution(snap))
        report.findings.extend(self._approvals_without_criteria(snap))
        report.findings.extend(self._duplicated_work(snap))
        return report

    # --- §7.1 misalignment ---

    def is_misalignment(self, card: NodeCard, snap: _Snapshot, alt: AltitudeMap) -> bool:
        """True when a divergence on this node spans altitudes, so it must NOT be reconciled.

        `crosspersona` calls this to decide whether to route a reconciliation thread. Unknown
        altitude falls back to **reconcile** deliberately: with no org chart we cannot claim a
        finding, and asking is how the org chart gets filled in.
        """
        if not _is_conflicting(card):
            return False
        accounts = self._accounts(card, snap, alt)
        depths = {a.altitude for a in accounts if a.altitude is not None}
        return len(depths) > 1

    def _misalignments(self, snap: _Snapshot, alt: AltitudeMap) -> list[Finding]:
        out: list[Finding] = []
        for card in sorted(snap.nodes.values(), key=lambda c: c.id):
            if not self.is_misalignment(card, snap, alt):
                continue
            accounts = self._accounts(card, snap, alt)
            top = accounts[0]
            bottom = accounts[-1]
            out.append(
                Finding(
                    kind=FindingKind.MISALIGNMENT,
                    detail=(
                        f"Accounts of {card.type.value.lower()} '{card.canonical_name}' differ "
                        f"across levels of the organisation: "
                        f"{_who(top)} and {_who(bottom)} describe it differently."
                    ),
                    node_id=card.id,
                    node_name=card.canonical_name,
                    accounts=accounts,
                    role_ids=tuple(a.role_id for a in accounts if a.role_id),
                    role_names=tuple(a.role_name for a in accounts if a.role_name),
                    recommendation=(
                        "Both accounts are recorded as given. Treat the difference as the finding: "
                        "confirm which one the business intends to run on, and align the other."
                    ),
                )
            )
        return out

    def _accounts(self, card: NodeCard, snap: _Snapshot, alt: AltitudeMap) -> tuple[Account, ...]:
        """Every contributor's own version, ordered highest in the org first (unknown last)."""
        seen: dict[str, Account] = {}
        for p in card.provenance:
            if p.said_by == REGISTRY_SAID_BY:
                continue  # vocabulary, not testimony — it has no account and no altitude
            role_id, role_name = self._persona_role(p.said_by, snap)
            candidate = Account(
                said_by=p.said_by,
                account=p.account,
                role_id=role_id,
                role_name=role_name,
                altitude=alt.of(role_id),
                ts=p.ts,
            )
            # One entry per person: their latest account wins, and an entry that actually carries
            # words beats an empty pre-P15c one.
            prev = seen.get(p.said_by)
            if prev is None or (not prev.account and candidate.account) or candidate.ts >= prev.ts:
                if prev is not None and prev.account and not candidate.account:
                    continue
                seen[p.said_by] = candidate
        return tuple(
            sorted(
                seen.values(),
                key=lambda a: (a.altitude if a.altitude is not None else _MAX_DEPTH, a.said_by),
            )
        )

    def _persona_role(self, persona_id: str, snap: _Snapshot) -> tuple[str | None, str | None]:
        """Which role a persona *is* — the role whose work their own interview produced.

        Same idea as `crosspersona._role_owner_personas`, in reverse: mentioning a role is not being
        it. But "contributed provenance to an activity this role performs" is too weak on its own,
        and getting it wrong here is expensive — it decides whether a divergence reads as a
        cross-altitude **finding** or a peer conflict to reconcile away.

        The failure it has to avoid: an exec who merely *comments on* someone else's activity picks
        up provenance on it, and a naive first-match then identifies the exec AS that role. Both
        contributors collapse onto one altitude and the misalignment silently disappears — the exact
        signal ADR #32 exists to preserve.

        So roles are scored, strongest evidence first:

        1. activities where this persona is the **sole** contributor (they described work nobody
           else did — near-conclusive evidence they perform it);
        2. failing that, activities they contributed to at all;
        3. ties break on role id, deterministically.

        A genuinely multi-hat person still resolves to one role (plan risk R5). That affects which
        hat a finding is attributed to, never whether the finding is raised.
        """
        role_ids = sorted(c.id for c in snap.nodes.values() if c.type is NodeType.ROLE)
        best: tuple[int, int, str] | None = None
        for role_id in role_ids:
            sole = shared = 0
            for act_id in snap.out(role_id, EdgeType.PERFORMS):
                act = snap.nodes.get(act_id)
                if act is None:
                    continue
                voices = {p.said_by for p in act.provenance} - {REGISTRY_SAID_BY}
                if persona_id not in voices:
                    continue
                if voices == {persona_id}:
                    sole += 1
                else:
                    shared += 1
            if sole or shared:
                # negate the id so `max` still breaks ties toward the lowest id
                candidate = (sole, shared, role_id)
                if best is None or (candidate[0], candidate[1]) > (best[0], best[1]):
                    best = candidate
        if best is None:
            return None, None
        role = snap.nodes.get(best[2])
        return best[2], role.canonical_name if role else None

    def _reporting_cycles(self, snap: _Snapshot, alt: AltitudeMap) -> list[Finding]:
        out: list[Finding] = []
        for cycle in alt.cycles:
            names = [
                (snap.nodes[r].canonical_name if r in snap.nodes else r) for r in cycle
            ]
            out.append(
                Finding(
                    kind=FindingKind.REPORTING_CYCLE,
                    detail=(
                        "Reporting lines form a loop: "
                        + " reports to ".join(names)
                        + f" reports to {names[0]}."
                    ),
                    role_ids=tuple(cycle),
                    role_names=tuple(names),
                    recommendation=(
                        "Confirm the actual reporting line. Until it is resolved these roles are "
                        "treated as peers, so divergences between them read as data-quality "
                        "issues rather than misalignments."
                    ),
                )
            )
        return out

    # --- §7.2 structural findings ---

    def _stage_findings(self, snap: _Snapshot) -> list[Finding]:
        out: list[Finding] = []
        for stage in sorted(
            (c for c in snap.nodes.values() if c.type is NodeType.STAGE), key=lambda c: c.id
        ):
            acts = [a for a in snap.inc(stage.id, EdgeType.PART_OF) if a in snap.nodes]
            owners = [r for r in snap.inc(stage.id, EdgeType.OWNS) if r in snap.nodes]

            if acts and not owners:
                out.append(
                    Finding(
                        kind=FindingKind.UNOWNED_STAGE,
                        detail=(
                            f"Stage '{stage.canonical_name}' has {len(acts)} "
                            f"{'activity' if len(acts) == 1 else 'activities'} but nobody is "
                            "accountable for it."
                        ),
                        node_id=stage.id,
                        node_name=stage.canonical_name,
                        recommendation=(
                            "Name a single owner for the stage's outcome — distinct from the "
                            "people performing the tasks inside it."
                        ),
                    )
                )

            if acts and not any(snap.out(a, EdgeType.MEASURED_BY) for a in acts):
                n = len(acts)
                out.append(
                    Finding(
                        kind=FindingKind.UNMEASURED_STAGE,
                        detail=(
                            f"Nothing in stage '{stage.canonical_name}' is measured — "
                            + (
                                "its one activity has no KPI."
                                if n == 1
                                else f"none of its {n} activities has a KPI."
                            )
                        ),
                        node_id=stage.id,
                        node_name=stage.canonical_name,
                        recommendation=(
                            "Agree one measure for the stage's outcome, so its performance is "
                            "visible rather than inferred."
                        ),
                    )
                )

            performers = {
                r
                for a in acts
                for r in snap.inc(a, EdgeType.PERFORMS)
                if r in snap.nodes
            }
            # ≥2 activities required, deliberately. A stage with a single known activity done by a
            # single role is the *normal* early state of every interview, so firing here would put a
            # SPOF row against nearly every stage and drown the findings that mean something. Two or
            # more activities all resting on one role is a real concentration of risk.
            if len(acts) >= 2 and len(performers) == 1:
                only = next(iter(performers))
                name = snap.nodes[only].canonical_name
                out.append(
                    Finding(
                        kind=FindingKind.SINGLE_POINT_OF_FAILURE,
                        detail=(
                            f"All {len(acts)} activities in stage '{stage.canonical_name}' are "
                            f"performed by one role: {name}. The stage stops if they are "
                            "unavailable."
                        ),
                        node_id=stage.id,
                        node_name=stage.canonical_name,
                        role_ids=(only,),
                        role_names=(name,),
                        recommendation=(
                            "Identify a second person who can run this stage, or document it well "
                            "enough that someone else could."
                        ),
                    )
                )

            # A stage named by someone with no interviewed owner — pairs with `cli coverage`.
            if not _has_interviewed_performer(acts, snap):
                out.append(
                    Finding(
                        kind=FindingKind.SILENT_STAGE,
                        detail=(
                            f"Stage '{stage.canonical_name}' was described by others, but nobody "
                            "who works in it has been interviewed."
                        ),
                        node_id=stage.id,
                        node_name=stage.canonical_name,
                        recommendation=(
                            "Interview someone who works in this stage — everything recorded about "
                            "it so far is second-hand."
                        ),
                    )
                )
        return out

    def _expectations_without_execution(self, snap: _Snapshot) -> list[Finding]:
        """An Objective on a stage its holder does not OWN, with nothing in the stage aimed at it.

        This is the §7.2 row that turns an ``Objective`` into an *expectation*: leadership wants
        X of a stage, and nothing inside the stage is measured or pointed at X.
        """
        out: list[Finding] = []
        for obj in sorted(
            (c for c in snap.nodes.values() if c.type is NodeType.OBJECTIVE), key=lambda c: c.id
        ):
            holders = [r for r in snap.inc(obj.id, EdgeType.PURSUES) if r in snap.nodes]
            for stage_id in sorted(snap.out(obj.id, EdgeType.OBJECTIVE_FOR)):
                stage = snap.nodes.get(stage_id)
                if stage is None:
                    continue
                owners = set(snap.inc(stage_id, EdgeType.OWNS))
                # Only an expectation when the holder doesn't own the stage they're aiming at.
                outsiders = [r for r in holders if r not in owners]
                if not outsiders:
                    continue
                acts = [a for a in snap.inc(stage_id, EdgeType.PART_OF) if a in snap.nodes]
                if any(snap.out(a, EdgeType.MEASURED_BY) for a in acts):
                    continue  # something in the stage is measured — not obviously unaddressed
                names = [snap.nodes[r].canonical_name for r in outsiders]
                out.append(
                    Finding(
                        kind=FindingKind.EXPECTATION_WITHOUT_EXECUTION,
                        detail=(
                            f"{', '.join(names)} expects '{obj.canonical_name}' of stage "
                            f"'{stage.canonical_name}', but nothing in that stage is aimed "
                            "at it or measured against it."
                        ),
                        node_id=obj.id,
                        node_name=obj.canonical_name,
                        role_ids=tuple(outsiders),
                        role_names=tuple(names),
                        recommendation=(
                            "Either make the expectation explicit to the people running the stage "
                            "and measure it, or retire it."
                        ),
                    )
                )
        return out

    def _approvals_without_criteria(self, snap: _Snapshot) -> list[Finding]:
        out: list[Finding] = []
        for appr in sorted(
            (c for c in snap.nodes.values() if c.type is NodeType.APPROVAL_POINT),
            key=lambda c: c.id,
        ):
            if str(appr.key_attributes.get("condition") or "").strip():
                continue
            out.append(
                Finding(
                    kind=FindingKind.APPROVAL_WITHOUT_CRITERIA,
                    detail=(
                        f"Approval '{appr.canonical_name}' has no stated condition — there is no "
                        "recorded rule for when it is granted or refused."
                    ),
                    node_id=appr.id,
                    node_name=appr.canonical_name,
                    recommendation=(
                        "Write down the threshold or test the approver actually applies, so the "
                        "decision is repeatable by someone else."
                    ),
                )
            )
        return out

    def _duplicated_work(self, snap: _Snapshot) -> list[Finding]:
        """Two roles performing activities that consume AND produce the same artifacts."""
        out: list[Finding] = []
        by_signature: dict[tuple[frozenset[str], frozenset[str]], list[tuple[str, str]]] = {}
        for act in sorted(
            (c for c in snap.nodes.values() if c.type is NodeType.ACTIVITY), key=lambda c: c.id
        ):
            consumes = frozenset(snap.out(act.id, EdgeType.CONSUMES))
            produces = frozenset(snap.out(act.id, EdgeType.PRODUCES))
            if not consumes or not produces:
                continue  # too little plumbing to claim duplication
            for role_id in sorted(snap.inc(act.id, EdgeType.PERFORMS)):
                if role_id in snap.nodes:
                    by_signature.setdefault((consumes, produces), []).append((role_id, act.id))

        for (_c, _p), pairs in sorted(by_signature.items(), key=lambda kv: kv[1][0][1]):
            roles = sorted({r for r, _ in pairs})
            if len(roles) < 2:
                continue
            names = [snap.nodes[r].canonical_name for r in roles]
            acts = sorted({a for _, a in pairs})
            out.append(
                Finding(
                    kind=FindingKind.DUPLICATED_WORK,
                    detail=(
                        f"{' and '.join(names)} each do work that takes the same inputs and "
                        "produces the same outputs: "
                        + ", ".join(f"'{snap.nodes[a].canonical_name}'" for a in acts)
                        + "."
                    ),
                    node_id=acts[0],
                    node_name=snap.nodes[acts[0]].canonical_name,
                    role_ids=tuple(roles),
                    role_names=tuple(names),
                    recommendation=(
                        "Confirm whether this is genuine duplication or a deliberate check. If "
                        "duplication, decide which role owns it."
                    ),
                )
            )
        return out


# --- helpers ----------------------------------------------------------------------------------


def _is_conflicting(card: NodeCard) -> bool:
    return any(p.status is ConfidenceStatus.CONFLICTING for p in card.provenance)


def _has_interviewed_performer(act_ids: list[str], snap: _Snapshot) -> bool:
    """Whether anybody who performs work in these activities has actually been interviewed."""
    for act_id in act_ids:
        act = snap.nodes.get(act_id)
        if act is None:
            continue
        if not snap.inc(act_id, EdgeType.PERFORMS):
            continue
        if any(p.said_by != REGISTRY_SAID_BY for p in act.provenance):
            return True
    return False


def _who(a: Account) -> str:
    """How a contributor is named in a finding sentence."""
    if a.role_name and a.altitude is not None:
        return f"{a.role_name} (level {a.altitude})"
    if a.role_name:
        return a.role_name
    return a.said_by
