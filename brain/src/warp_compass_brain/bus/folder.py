"""Shared-folder implementation of the `Bus` (Phase 8; retirement added in P13).

A plain directory tree — works with any file-sync product (Drive/Dropbox/OneDrive) or a USB stick,
which is exactly the "manual stand-in for networked v1" the design calls for (DECISION #8). Reads
are tolerant (a half-synced or malformed file is skipped, never crashes a round); writes are atomic
(write to a temp file, then replace) so a brief is never read half-written.

Every operation goes through `fsretry` (P14), because a Drive-backed bus fails *whole* — when
Google's user-mode FS driver runs out of resources, `stat` and `mkdir` fail alongside writes. Note
the split that module insists on: absent-or-malformed still reads as empty (the P8 contract), while
a busy drive retries and then raises rather than reporting emptiness. Silently reporting an existing
`profile.json` as `{}` would re-register the participant and re-ingest every Answer Log.
"""

from __future__ import annotations

import json
import shutil
from functools import partial
from pathlib import Path

from ..fsretry import atomic_write_text, read_text_or_none, retry_fs
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

        def _scan() -> list[str]:
            if not base.is_dir():
                return []
            # `_`-prefixed entries are bookkeeping (an archive someone dropped in here by hand),
            # never a person — a minted id always starts with an alphanumeric.
            return sorted(
                p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")
            )

        return retry_fs(_scan, what=f"list participants in {base}")

    def ensure_participant(self, participant_id: str) -> None:
        for sub in ("answer_logs", "briefs"):
            target = self._dir(participant_id) / sub
            retry_fs(
                partial(target.mkdir, parents=True, exist_ok=True),
                what=f"create {participant_id}/{sub}",
            )

    def read_profile(self, participant_id: str) -> dict:
        return self._read_json_tolerant(
            self._dir(participant_id) / "profile.json", what=f"read {participant_id}/profile.json"
        )

    def write_profile(self, participant_id: str, profile: dict) -> None:
        self.ensure_participant(participant_id)
        self._atomic_write(
            self._dir(participant_id) / "profile.json",
            profile,
            what=f"write {participant_id}/profile.json",
        )

    # ── answer logs (runner -> brain) ───────────────────────────────────────────
    def list_answer_logs(self, participant_id: str) -> list[str]:
        d = self._dir(participant_id) / "answer_logs"

        def _scan() -> list[str]:
            if not d.is_dir():
                return []
            return sorted(p.name for p in d.iterdir() if p.is_file() and p.suffix == ".json")

        return retry_fs(_scan, what=f"list {participant_id}/answer_logs")

    def read_answer_log(self, participant_id: str, name: str) -> dict:
        path = self._dir(participant_id) / "answer_logs" / name
        text = retry_fs(
            partial(path.read_text, encoding="utf-8"),
            what=f"read {participant_id}/answer_logs/{name}",
        )
        return json.loads(text)

    # ── briefs (brain -> runner) ────────────────────────────────────────────────
    def write_brief(self, participant_id: str, name: str, brief: dict) -> None:
        d = self._dir(participant_id) / "briefs"
        retry_fs(
            partial(d.mkdir, parents=True, exist_ok=True), what=f"create {participant_id}/briefs"
        )
        self._atomic_write(d / name, brief, what=f"write {participant_id}/briefs/{name}")

    # ── retirement registry (P13) ───────────────────────────────────────────────
    def retired_records(self) -> list[dict]:
        data = self._read_json_any(self.retired_path, what=f"read {RETIRED_FILENAME}")
        records = data.get("retired") if isinstance(data, dict) else data
        return [r for r in records if isinstance(r, dict)] if isinstance(records, list) else []

    def mark_retired(self, record: dict) -> None:
        """Append a retirement record, replacing any earlier one for the same id (idempotent)."""
        rid = str(record.get("id", ""))
        kept = [r for r in self.retired_records() if str(r.get("id", "")) != rid]
        retry_fs(
            partial(self._root.mkdir, parents=True, exist_ok=True), what=f"create {self._root}"
        )
        self._atomic_write(
            self.retired_path, {"retired": [*kept, record]}, what=f"write {RETIRED_FILENAME}"
        )

    def move_to_archive(self, participant_id: str, archive_name: str) -> Path:
        """Move a participant's folder into ``_archive/``. Returns the new path.

        A pre-existing destination is suffixed rather than merged into — an operator retiring the
        same id twice in one day must never silently overwrite the first archive.
        """
        src = self._dir(participant_id)
        retry_fs(
            partial(self.archive_dir.mkdir, parents=True, exist_ok=True),
            what=f"create {ARCHIVE_DIRNAME}/",
        )
        dest = self.archive_dir / archive_name
        n = 2
        while retry_fs(dest.exists, what=f"stat {ARCHIVE_DIRNAME}/{dest.name}"):
            dest = self.archive_dir / f"{archive_name}-{n}"
            n += 1
        retry_fs(
            partial(shutil.move, str(src), str(dest)), what=f"archive {participant_id}"
        )
        return dest

    # ── internals ───────────────────────────────────────────────────────────────
    @staticmethod
    def _atomic_write(path: Path, data: dict, *, what: str) -> None:
        atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False), what=what)

    @staticmethod
    def _read_json_any(path: Path, *, what: str):
        """Parse a JSON file; ``{}`` when absent or malformed. A busy drive retries, then raises.

        The absent/malformed tolerance is the Phase 8 contract: a file the sync client has only
        half-written must never crash a round. A transient drive error is deliberately *not*
        tolerated here — see the `fsretry` module docstring for what an empty read would cost.
        """
        text = read_text_or_none(path, what=what)
        if text is None:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    @classmethod
    def _read_json_tolerant(cls, path: Path, *, what: str) -> dict:
        data = cls._read_json_any(path, what=what)
        return data if isinstance(data, dict) else {}
