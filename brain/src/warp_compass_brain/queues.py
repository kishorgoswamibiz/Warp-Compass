"""Append-only review queues (JSONL). Nothing is ever discarded — the BA promotes later (§7).

Two queues: quarantine (candidates that failed the create gate) and pending-taxonomy
(category codes proposed but not yet in the registry).
"""

from __future__ import annotations

import json
from pathlib import Path


class JsonlQueue:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
