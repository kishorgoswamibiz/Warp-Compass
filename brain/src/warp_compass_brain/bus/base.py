"""The sync-bus seam (Phase 8).

The bus is the manual, free transport between the phone (runner) and the laptop (brain): the runner
drops Answer Logs in, the brain reads new ones and writes each persona's next Session Brief back.
The folder layout below **is** the participant registry — a new user is just a new folder, so anyone
can be added at any time with no config (docs/02 §3.2, §3.4, §14).

    {root}/participants/{participant_id}/
        profile.json        # registry entry: id, persona mapping, which logs are already ingested
        answer_logs/*.json   # runner -> brain (immutable; the source of truth)
        briefs/*.json        # brain -> runner (the next Session Brief)

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
