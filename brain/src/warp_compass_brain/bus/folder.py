"""Shared-folder implementation of the `Bus` (Phase 8; retirement added in P13).

A plain directory tree — works with any file-sync product (Drive/Dropbox/OneDrive) or a USB stick,
which is exactly the "manual stand-in for networked v1" the design calls for (DECISION #8). Reads
are tolerant (a half-synced or malformed file is skipped, never crashes a round); writes are atomic
(write to a temp file, then replace) so a brief is never read half-written.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .base import Bus

#: Bus-root entries that are bookkeeping, not participants. Minted participant ids can never start
#: with ``_`` (the PWA's slugger guarantees a leading alphanumeric), so the prefix is a safe marker.
ARCHIVE_DIRNAME = "_archive"
RETIRED_FILENAME = "_retired.json"


class FolderBus(Bus):
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    # ── layout helpers ─────────────────────────────────────────────────────────
    @property
    def root(self) -> Path:
        return self._root

    @property
    def _participants_dir(self) -> Path:
        return self._root / "participants"

    def _dir(self, participant_id: str) -> Path:
        return self._participants_dir / participant_id

    def participant_dir(self, participant_id: str) -> Path:
        """On-disk folder for a participant (may not exist). Public for the lifecycle commands."""
        return self._dir(participant_id)

    @property
    def archive_dir(self) -> Path:
        return self._root / ARCHIVE_DIRNAME

    @property
    def retired_path(self) -> Path:
        return self._root / RETIRED_FILENAME

    # ── registry ───────────────────────────────────────────────────────────────
    def list_participants(self) -> list[str]:
        base = self._participants_dir
        if not base.is_dir():
            return []
        # `_`-prefixed entries are bookkeeping (an archive someone dropped in here by hand), never
        # a person — a minted id always starts with an alphanumeric.
        return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith("_"))

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

    # ── retirement registry (P13) ───────────────────────────────────────────────
    def retired_records(self) -> list[dict]:
        path = self.retired_path
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []  # tolerant, like every other read here
        records = data.get("retired") if isinstance(data, dict) else data
        return [r for r in records if isinstance(r, dict)] if isinstance(records, list) else []

    def mark_retired(self, record: dict) -> None:
        """Append a retirement record, replacing any earlier one for the same id (idempotent)."""
        rid = str(record.get("id", ""))
        kept = [r for r in self.retired_records() if str(r.get("id", "")) != rid]
        self._root.mkdir(parents=True, exist_ok=True)
        self._atomic_write(self.retired_path, {"retired": [*kept, record]})

    def move_to_archive(self, participant_id: str, archive_name: str) -> Path:
        """Move a participant's folder into ``_archive/``. Returns the new path.

        A pre-existing destination is suffixed rather than merged into — an operator retiring the
        same id twice in one day must never silently overwrite the first archive.
        """
        src = self._dir(participant_id)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        dest = self.archive_dir / archive_name
        n = 2
        while dest.exists():
            dest = self.archive_dir / f"{archive_name}-{n}"
            n += 1
        shutil.move(str(src), str(dest))
        return dest

    # ── internals ───────────────────────────────────────────────────────────────
    @staticmethod
    def _atomic_write(path: Path, data: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)  # atomic on the same filesystem
