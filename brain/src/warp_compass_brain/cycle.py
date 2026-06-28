"""The daily cycle (Phase 8): collect → register → ingest → plan → distribute, over the sync bus.

One `RoundRunner.run()` is one batch round (§3.2). It enumerates the bus (the folder IS the
registry), auto-onboards any new participant, ingests every **new** Answer Log into the single
shared graph, then re-plans and writes each persona's next Session Brief back to its folder.

Design notes:
- **Auto-onboarding:** a participant exists the moment its folder does; we mint a `profile.json` on
  first sight. The prototype maps **persona 1:1 to participant** (`persona_id = participant_id`) —
  there is no `:Persona` node (ADR #17); a persona is registered in the graph implicitly via the
  provenance `said_by` set on ingest.
- **Resumable:** `profile.json["ingested_logs"]` records which log filenames are already ingested;
  the profile is persisted after *each* log, so a transient DeepSeek failure mid-round never
  re-ingests a done log on retry. Re-ingesting would be safe anyway (the graph merges by id), but
  skipping avoids paying for the LLM twice.
- **Dependency-injected:** the runner takes an ingestor + planner (the brain's real ones in the CLI,
  scripted fakes in tests), so the cycle logic is verifiable without Neo4j or the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .ingest import IngestSummary


class IngestorLike(Protocol):
    def ingest_answer(
        self, answer: str, *, persona_id: str, session_id: str, ts: str
    ) -> IngestSummary: ...


class BriefLike(Protocol):
    persona_id: str
    def to_dict(self) -> dict: ...


class PlannerLike(Protocol):
    def plan_all(self, *, session_id: str) -> list[BriefLike]: ...


@dataclass
class ParticipantResult:
    participant_id: str
    persona_id: str
    newly_registered: bool
    logs_ingested: int
    entries_ingested: int
    brief_written: str | None = None


@dataclass
class RoundSummary:
    participants: list[str] = field(default_factory=list)
    registered: list[str] = field(default_factory=list)
    logs_ingested: int = 0
    entries_ingested: int = 0
    created: int = 0
    merged: int = 0
    conflicts: int = 0
    quarantined: int = 0
    edges: int = 0
    briefs_written: list[str] = field(default_factory=list)
    per_participant: list[ParticipantResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)


class RoundRunner:
    def __init__(
        self,
        bus: Any,  # Bus (duck-typed so tests can pass a FolderBus over a tmp dir)
        ingestor: IngestorLike,
        planner: PlannerLike,
        *,
        now: str,
    ) -> None:
        self._bus = bus
        self._ingestor = ingestor
        self._planner = planner
        self._now = now

    def run(self, *, session_id: str) -> RoundSummary:
        summary = RoundSummary()

        # ── 1. enumerate + register + ingest new logs ───────────────────────────
        persona_to_participant: dict[str, str] = {}
        for pid in self._bus.list_participants():
            result = self._process_participant(pid, summary)
            persona_to_participant[result.persona_id] = pid
            summary.per_participant.append(result)
            summary.participants.append(pid)

        # ── 2. re-plan from the now-updated single graph ─────────────────────────
        briefs = self._planner.plan_all(session_id=session_id)

        # ── 3. distribute each persona's brief to its participant folder ─────────
        result_by_pid = {r.participant_id: r for r in summary.per_participant}
        for brief in briefs:
            participant_id = persona_to_participant.get(brief.persona_id, brief.persona_id)
            name = f"{session_id}.json"
            self._bus.write_brief(participant_id, name, brief.to_dict())
            label = f"{participant_id}/{name}"
            summary.briefs_written.append(label)
            if participant_id in result_by_pid:
                result_by_pid[participant_id].brief_written = name

        return summary

    # ── internals ───────────────────────────────────────────────────────────────
    def _process_participant(self, participant_id: str, summary: RoundSummary) -> ParticipantResult:
        self._bus.ensure_participant(participant_id)
        profile = self._bus.read_profile(participant_id)

        newly_registered = not profile
        if newly_registered:
            profile = {
                "participant_id": participant_id,
                "persona_id": participant_id,  # prototype: persona 1:1 with participant
                "created_ts": self._now,
                "ingested_logs": [],
            }
            self._bus.write_profile(participant_id, profile)
            summary.registered.append(participant_id)

        persona_id = profile.get("persona_id") or participant_id
        already: set[str] = set(profile.get("ingested_logs", []))

        logs_ingested = 0
        entries_ingested = 0
        for name in self._bus.list_answer_logs(participant_id):
            if name in already:
                continue
            entries_ingested += self._ingest_log(participant_id, name, persona_id, summary)
            logs_ingested += 1
            # Persist progress immediately so a crash never re-ingests this log.
            profile.setdefault("ingested_logs", []).append(name)
            profile["last_round_ts"] = self._now
            self._bus.write_profile(participant_id, profile)

        return ParticipantResult(
            participant_id=participant_id,
            persona_id=persona_id,
            newly_registered=newly_registered,
            logs_ingested=logs_ingested,
            entries_ingested=entries_ingested,
        )

    def _ingest_log(
        self, participant_id: str, name: str, persona_id: str, summary: RoundSummary
    ) -> int:
        log = self._bus.read_answer_log(participant_id, name)
        # The log carries its own session_id (the session the answers were given in); ingest stamps
        # provenance with it. The registry's persona_id is authoritative (the folder IS registry).
        session_id = log.get("session_id", name)
        entries = 0
        for entry in log.get("entries", []):
            raw = (entry.get("raw_answer") or "").strip()
            if not raw:
                continue
            res = self._ingestor.ingest_answer(
                raw,
                persona_id=persona_id,
                session_id=session_id,
                ts=entry.get("ts") or self._now,
            )
            entries += 1
            summary.created += len(res.created)
            summary.merged += len(res.merged)
            summary.conflicts += len(res.conflicts)
            summary.quarantined += res.quarantined
            summary.edges += res.edges
        summary.logs_ingested += 1
        summary.entries_ingested += entries
        return entries
