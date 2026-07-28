"""The sync-bus seam (Phase 8).

The bus is the manual, free transport between the phone (runner) and the laptop (brain): the runner
drops Answer Logs in, the brain reads new ones and writes each persona's next Session Brief back.
The folder layout below **is** the participant registry — a new user is just a new folder, so anyone
can be added at any time with no config (docs/02 §3.2, §3.4, §14).

    {root}/participants/{participant_id}/
        profile.json        # registry entry: id, persona mapping, which logs are already ingested
        answer_logs/*.json   # runner -> brain (immutable; the source of truth)
        briefs/*.json        # brain -> runner (the next Session Brief)
    {root}/_retired.json     # P13: who has been retired from the engagement (see below)
    {root}/_archive/         # P13: retired participants' folders, moved aside

**Retirement (P13).** A participant leaves by having their folder moved out of `participants/`.
That alone isn't enough, because the Planner enumerates personas from *graph provenance*, not from
the bus — so the brain would keep planning for them and `write_brief` would recreate the folder.
`_retired.json` is the explicit marker that closes that loop, and it lets the round tell two very
different situations apart: a deliberately retired person (skip silently) versus a folder that
simply hasn't synced down from Drive yet (warn loudly). Retiring NEVER touches the graph (ADR #30).

`FolderBus` is the shared-folder implementation; a networked sync endpoint can be swapped in behind
this same interface later (AGENTS.md "Everything swappable").
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Bus(ABC):
    """Transport between the runner and the brain. Implementations are storage, never logic."""

    @abstractmethod
    def list_participants(self) -> list[str]:
        """Every participant id currently on the bus (the live registry), sorted."""

    @abstractmethod
    def ensure_participant(self, participant_id: str) -> None:
        """Create the folder layout for a participant if it doesn't exist (idempotent)."""

    @abstractmethod
    def read_profile(self, participant_id: str) -> dict:
        """The participant's `profile.json`, or an empty dict if there is none yet."""

    @abstractmethod
    def write_profile(self, participant_id: str, profile: dict) -> None:
        """Persist the participant's `profile.json` (overwrite)."""

    @abstractmethod
    def list_answer_logs(self, participant_id: str) -> list[str]:
        """Filenames of every Answer Log this participant has dropped, sorted."""

    @abstractmethod
    def read_answer_log(self, participant_id: str, name: str) -> dict:
        """Parse one Answer Log by filename."""

    @abstractmethod
    def write_brief(self, participant_id: str, name: str, brief: dict) -> None:
        """Write a Session Brief into the participant's `briefs/` folder."""

    # --- retirement registry (P13) ---------------------------------------------------------

    @abstractmethod
    def retired_records(self) -> list[dict]:
        """Every retirement record, newest last. Empty when nobody has been retired."""

    def list_retired(self) -> set[str]:
        """Ids of everyone retired from this engagement. Cheap wrapper over the records."""
        return {str(r["id"]) for r in self.retired_records() if r.get("id")}

    @abstractmethod
    def mark_retired(self, record: dict) -> None:
        """Append one retirement record (id + display name + role + when + where archived)."""
