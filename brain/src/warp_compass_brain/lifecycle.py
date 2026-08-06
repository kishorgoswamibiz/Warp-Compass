"""Participant lifecycle (Phase 13) — retiring one person, and resetting a whole engagement.

**The governing rule: retiring a participant NEVER touches the graph (ADR #30).** Removal is a
bus-level move plus a marker in ``_retired.json``. No node is edited, no provenance is stripped, no
LLM is called — so the operation is instant, free, and impossible to get subtly wrong.

That is a deliberate rejection of per-persona graph deletion. Context in a discovery engagement is
*shared*: one activity commonly carries facts from a Business Analyst and a Project Manager at
once, and the aliases and descriptions a person contributed were folded irreversibly into
surviving nodes at merge time (``ingest.py``). A rebuild would cost LLM spend on every removal and
re-run extraction over text that had already settled; a surgical prune would need delete seams
through the whole store and still leave residue. Neither buys anything a discovery project wants.

What happens to their unanswered questions is handled in ``planner.py``: nodes whose contributors
are all retired become *orphan threads*, offered to whoever is still here. The questions outlive
the person, because the business they describe does too.

``reset_engagement`` is the other end of the same story: wipe everything and start clean, which is
what an operator wants before handing the app to a wider team.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .bus import FolderBus


@dataclass
class RetireResult:
    participant_id: str
    display_name: str = ""
    role_title: str = ""
    answer_logs: int = 0
    briefs: int = 0
    archived_to: str | None = None
    hard_deleted: bool = False
    dry_run: bool = False

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)


@dataclass
class ResetResult:
    participants_removed: list[str] = field(default_factory=list)
    graph_removed: bool = False
    retired_removed: bool = False
    archive_removed: bool = False
    state_files_removed: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)


class LifecycleError(RuntimeError):
    """An operator mistake worth stopping for (unknown id, missing folder, missing confirmation)."""


# --- retire one participant ---------------------------------------------------------------------


def retire_participant(
    bus: FolderBus,
    participant_id: str,
    *,
    now: str,
    hard_delete: bool = False,
    dry_run: bool = False,
) -> RetireResult:
    """Move one participant out of the engagement. The graph is not opened, let alone written.

    Archives to ``_archive/<id>__<YYYY-MM-DD>/`` by default (Google Drive's 30-day trash is the
    second backstop); ``hard_delete`` skips the copy. The archive folder name keeps a sortable
    ISO date so a listing orders chronologically.
    """
    pdir = bus.participant_dir(participant_id)
    if not pdir.is_dir():
        live = ", ".join(bus.list_participants()) or "(none)"
        raise LifecycleError(
            f"no participant folder {participant_id!r} on the bus. Live participants: {live}"
        )

    profile = bus.read_profile(participant_id)
    result = RetireResult(
        participant_id=participant_id,
        display_name=str(profile.get("display_name", "")),
        role_title=str(profile.get("role_title", "")),
        answer_logs=len(bus.list_answer_logs(participant_id)),
        briefs=_count_json(pdir / "briefs"),
        dry_run=dry_run,
    )

    archive_name = f"{participant_id}__{now[:10]}"
    if dry_run:
        result.archived_to = None if hard_delete else str(bus.archive_dir / archive_name)
        result.hard_deleted = hard_delete
        return result

    if hard_delete:
        shutil.rmtree(pdir)
        result.hard_deleted = True
    else:
        result.archived_to = str(bus.move_to_archive(participant_id, archive_name))

    # The marker is what stops the next round recreating the folder (P13 Finding 1) and what makes
    # their leftover questions orphan threads instead of silence (Finding 2).
    bus.mark_retired(
        {
            "id": participant_id,
            "display_name": result.display_name,
            "role_title": result.role_title,
            "retired_at": now,
            "archived_to": result.archived_to,
        }
    )
    return result


def _count_json(d: Path) -> int:
    if not d.is_dir():
        return 0
    return sum(1 for p in d.iterdir() if p.is_file() and p.suffix == ".json")


# --- declared identity (P16a) ---------------------------------------------------------------------

#: How the PWA joins several declared roles into the legacy single-string `role_title`
#: (`pwa/src/sync/participant.ts` ROLE_JOIN). Kept writable by P15a precisely so the brain can
#: recover the list from a bus written by an older Apps Script deployment.
ROLE_JOIN = " / "


def profile_role_titles(profile: dict) -> tuple[str, ...]:
    """The roles a person **declared at onboarding**, from their ``profile.json``.

    ``role_titles`` (P15a) is the truth. The ``role_title`` fallback is not defensive
    padding — it is the live case: verified 04 Aug 2026, the deployed Apps Script is the P13
    build, which writes the joined string and drops the array. Splitting it back on ``" / "``
    is lossless for every role in ``contracts/roles.json`` (none contains the separator) and
    is what lets declared-role ownership work **before** the Web App is redeployed.
    """
    raw = profile.get("role_titles")
    if isinstance(raw, (list, tuple)):
        titles = [str(t).strip() for t in raw]
    else:
        titles = [t.strip() for t in str(profile.get("role_title") or "").split(ROLE_JOIN)]

    seen: list[str] = []
    for t in titles:
        if t and t.lower() not in {s.lower() for s in seen}:
            seen.append(t)
    return tuple(seen)


def declared_roles(bus: FolderBus) -> dict[str, tuple[str, ...]]:
    """``persona_id -> the role titles they declared``, for every **live** participant.

    Keyed by ``persona_id`` (not participant id) because that is what provenance is stamped with and
    what the Planner and cross-persona engine route on — the same choice ``persona_display_names``
    makes, for the same reason.

    Retired people are absent by construction: they have no folder, so ``list_participants``
    does not return them. That is what keeps a departed person from remaining a routing target
    for the role they used to hold.

    **Someone who declared nothing still gets a key, mapped to ``()``.** The map doubles as the
    Planner's roster of live participants (``Planner.live_personas``), and dropping the
    role-less would put a real person who simply skipped the chips back into the hole this phase
    exists to close: no brief, no questions, no explanation.
    """
    out: dict[str, tuple[str, ...]] = {}
    for pid in bus.list_participants():
        profile = bus.read_profile(pid)
        out[str(profile.get("persona_id") or pid)] = profile_role_titles(profile)
    return out


# --- roster -------------------------------------------------------------------------------------


@dataclass
class AnswerEntry:
    """One answer ready to re-ingest: what ``ingest_answer`` needs, plus where it came from."""

    persona_id: str
    session_id: str
    ts: str
    raw_answer: str
    source: str  # "<participant_id>/<log name>", for reporting only


def all_answer_entries(bus: FolderBus) -> list[AnswerEntry]:
    """Every answer in the engagement, live **and archived**, in chronological order (P17b).

    The graph is re-derivable from the Answer Logs (`answer-log.schema.json`, ADR #4), and this is
    the function that makes that promise real: it is the complete input to a rebuild.

    **Archived folders are included, and that is load-bearing.** Retiring somebody archives their
    folder rather than deleting it precisely so their knowledge survives (ADR #30); a rebuild that
    walked only ``participants/`` would delete a departed colleague's entire contribution the first
    time it ran, quietly turning retirement into the graph deletion ADR #30 refused to build.

    **Sorted by timestamp across everybody**, not per person, because merge order is not neutral: a
    merge appends provenance but keeps the FIRST contributor's canonical name and description, so
    ingesting one person's whole history before another's would attribute shared nodes differently
    than the interviews actually happened. Entries with no usable timestamp sort last, keeping the
    order total and deterministic rather than raising.
    """
    entries: list[AnswerEntry] = []
    for participant_id, folder in _log_folders(bus):
        profile = _read_json(folder / "profile.json")
        persona_id = str(profile.get("persona_id") or participant_id)
        log_dir = folder / "answer_logs"
        if not log_dir.is_dir():
            continue
        for path in sorted(p for p in log_dir.iterdir() if p.suffix == ".json"):
            log = _read_json(path)
            session_id = str(log.get("session_id") or path.stem)
            for e in log.get("entries", []):
                raw = (e.get("raw_answer") or "").strip()
                if not raw:
                    continue
                entries.append(
                    AnswerEntry(
                        persona_id=persona_id,
                        session_id=session_id,
                        ts=str(e.get("ts") or ""),
                        raw_answer=raw,
                        source=f"{participant_id}/{path.name}",
                    )
                )
    # "" sorts before every real ISO timestamp, so push the unstamped to the end explicitly.
    entries.sort(key=lambda e: (e.ts == "", e.ts, e.source))
    return entries


def _log_folders(bus: FolderBus) -> list[tuple[str, Path]]:
    """``(participant_id, folder)`` for every live participant, then every archived one."""
    out = [(pid, bus.participant_dir(pid)) for pid in bus.list_participants()]
    archive = bus.archive_dir
    if archive.is_dir():
        for d in sorted(p for p in archive.iterdir() if p.is_dir()):
            # Archive folders are named "<participant_id>__<date>" (see `retire_participant`).
            out.append((d.name.split("__")[0], d))
    return out


def _read_json(path: Path) -> dict:
    import json

    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@dataclass
class RosterEntry:
    id: str
    display_name: str
    role_title: str
    retired: bool
    answer_logs: int = 0
    briefs: int = 0
    last_seen: str = ""
    retired_at: str = ""


def roster(bus: FolderBus) -> list[RosterEntry]:
    """Who is in this engagement — live participants first, then the retired, both id-sorted."""
    live: list[RosterEntry] = []
    for pid in bus.list_participants():
        profile = bus.read_profile(pid)
        live.append(
            RosterEntry(
                id=pid,
                display_name=str(profile.get("display_name", "")),
                role_title=str(profile.get("role_title", "")),
                retired=False,
                answer_logs=len(bus.list_answer_logs(pid)),
                briefs=_count_json(bus.participant_dir(pid) / "briefs"),
                last_seen=str(profile.get("last_seen", "")),
            )
        )
    gone = [
        RosterEntry(
            id=str(r.get("id", "")),
            display_name=str(r.get("display_name", "")),
            role_title=str(r.get("role_title", "")),
            retired=True,
            retired_at=str(r.get("retired_at", "")),
        )
        for r in bus.retired_records()
    ]
    return sorted(live, key=lambda e: e.id) + sorted(gone, key=lambda e: e.id)


def effective_retired(bus: FolderBus) -> set[str]:
    """Who is *actually* retired: marked in ``_retired.json`` AND absent from the bus.

    The folder IS the registry (P8). So if an operator restores someone from ``_archive/`` without
    clearing their marker, the folder wins and the stale marker is ignored. Without this the
    restored person would fall into a silent hole — ``cycle`` would map their folder happily while
    the Planner excluded them from ``live_personas()``, so they'd receive no brief and nothing
    would say why.
    """
    return bus.list_retired() - set(bus.list_participants())


def persona_display_names(bus: FolderBus) -> dict[str, str]:
    """``persona_id -> "Rahul Mehta (Business Analyst)"`` for the deliverable's source lines.

    Personas are keyed by the profile's ``persona_id`` (1:1 with the participant in the prototype,
    ADR #17) because that is what provenance is stamped with. Anyone without a declared name is
    simply left out, so the renderer falls back to the raw id rather than printing a blank.
    """
    out: dict[str, str] = {}
    for pid in bus.list_participants():
        profile = bus.read_profile(pid)
        label = _label(profile.get("display_name"), profile.get("role_title"))
        if label:
            out[str(profile.get("persona_id") or pid)] = label
    for r in bus.retired_records():
        rid = str(r.get("id", ""))
        label = _label(r.get("display_name"), r.get("role_title"))
        if rid and label:
            out[rid] = f"{label}, retired"
    return out


def _label(display_name, role_title) -> str:
    name = str(display_name or "").strip()
    role = str(role_title or "").strip()
    if not name:
        return ""
    return f"{name} ({role})" if role else name


# --- reset the whole engagement -------------------------------------------------------------------


def reset_engagement(
    bus: FolderBus,
    graph_root: str | Path,
    state_paths: list[str | Path],
    *,
    dry_run: bool = False,
    keep_archive: bool = False,
) -> ResetResult:
    """Wipe the engagement back to empty: participants, graph, retirement roster, local state.

    Everything here is re-creatable — participants re-register the moment someone runs a session,
    and the graph is re-derivable from Answer Logs (ADR #4) *if* any were kept. This is destructive
    on purpose; the CLI gates it behind an explicit ``--yes`` and offers ``--dry-run``.
    """
    result = ResetResult(dry_run=dry_run)

    result.participants_removed = list(bus.list_participants())
    graph_path = Path(graph_root)
    result.graph_removed = graph_path.is_dir()
    result.retired_removed = bus.retired_path.is_file()
    result.archive_removed = bus.archive_dir.is_dir() and not keep_archive
    existing_state = [Path(p) for p in state_paths if Path(p).exists()]
    result.state_files_removed = [str(p) for p in existing_state]

    if dry_run:
        return result

    for pid in result.participants_removed:
        shutil.rmtree(bus.participant_dir(pid), ignore_errors=True)
    if result.graph_removed:
        shutil.rmtree(graph_path, ignore_errors=True)
    if result.retired_removed:
        bus.retired_path.unlink(missing_ok=True)
    if result.archive_removed:
        shutil.rmtree(bus.archive_dir, ignore_errors=True)
    for p in existing_state:
        # Stale vectors are the classic half-reset failure: a graph rebuilt from scratch against an
        # old embedding table produces shape/`matmul` errors rather than an obvious "you missed a
        # step". Clearing them here is what makes the reset atomic in practice.
        p.unlink(missing_ok=True)
    return result
