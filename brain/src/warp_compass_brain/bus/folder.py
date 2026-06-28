"""Shared-folder implementation of the `Bus` (Phase 8).

A plain directory tree — works with any file-sync product (Drive/Dropbox/OneDrive) or a USB stick,
which is exactly the "manual stand-in for networked v1" the design calls for (DECISION #8). Reads
are tolerant (a half-synced or malformed file is skipped, never crashes a round); writes are atomic
(write to a temp file, then replace) so a brief is never read half-written.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .base import Bus


class FolderBus(Bus):
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    # ── layout helpers ─────────────────────────────────────────────────────────
    @property
    def _participants_dir(self) -> Path:
        return self._root / "participants"

    def _dir(self, participant_id: str) -> Path:
        return self._participants_dir / participant_id

    # ── registry ───────────────────────────────────────────────────────────────
    def list_participants(self) -> list[str]:
        base = self._participants_dir
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir() if p.is_dir())

    def ensure_participant(self, participant_id: str) -> None:
        (self._dir(participant_id) / "answer_logs").mkdir(parents=True, exist_ok=True)
        (self._dir(participant_id) / "briefs").mkdir(parents=True, exist_ok=True)

    def read_profile(self, participant_id: str) -> dict:
        path = self._dir(participant_id) / "profile.json"
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def write_profile(self, participant_id: str, profile: dict) -> None:
        self.ensure_participant(participant_id)
        self._atomic_write(self._dir(participant_id) / "profile.json", profile)

    # ── answer logs (runner -> brain) ───────────────────────────────────────────
    def list_answer_logs(self, participant_id: str) -> list[str]:
        d = self._dir(participant_id) / "answer_logs"
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir() if p.is_file() and p.suffix == ".json")

    def read_answer_log(self, participant_id: str, name: str) -> dict:
        path = self._dir(participant_id) / "answer_logs" / name
        return json.loads(path.read_text(encoding="utf-8"))

    # ── briefs (brain -> runner) ────────────────────────────────────────────────
    def write_brief(self, participant_id: str, name: str, brief: dict) -> None:
        d = self._dir(participant_id) / "briefs"
        d.mkdir(parents=True, exist_ok=True)
        self._atomic_write(d / name, brief)

    # ── internals ───────────────────────────────────────────────────────────────
    @staticmethod
    def _atomic_write(path: Path, data: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)  # atomic on the same filesystem
