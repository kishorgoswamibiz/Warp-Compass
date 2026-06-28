"""Phase-8 RoundRunner tests — the daily cycle over the bus, with scripted ingestor + planner so the
orchestration logic (register / ingest-new-only / distribute / resume) is verified without Neo4j or
the network. Mirrors the brief's test plan."""

from __future__ import annotations

import json
from dataclasses import dataclass

from warp_compass_brain.bus import FolderBus
from warp_compass_brain.cycle import RoundRunner
from warp_compass_brain.ingest import IngestSummary


class FakeIngestor:
    """Records every ingest call; returns a fixed summary so totals are checkable."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def ingest_answer(self, answer, *, persona_id, session_id, ts) -> IngestSummary:
        self.calls.append(
            {"answer": answer, "persona_id": persona_id, "session_id": session_id, "ts": ts}
        )
        return IngestSummary(created=["n1"], merged=[], conflicts=[], quarantined=0, edges=1)


@dataclass
class FakeBrief:
    persona_id: str

    def to_dict(self) -> dict:
        return {"session_id": "s_next", "persona_id": self.persona_id, "cold_start": False,
                "open_threads": []}


class FakePlanner:
    """Plans one brief per persona that has contributed (here: whoever was ingested)."""

    def __init__(self, ingestor: FakeIngestor) -> None:
        self._ing = ingestor

    def plan_all(self, *, session_id):
        personas = sorted({c["persona_id"] for c in self._ing.calls})
        return [FakeBrief(persona_id=p) for p in personas]


def _drop_log(bus: FolderBus, pid: str, name: str, entries: list[str], session_id="s1") -> None:
    bus.ensure_participant(pid)
    log = {
        "session_id": session_id,
        "persona_id": pid,
        "participant_id": pid,
        "entries": [{"kind": "guided", "raw_answer": e, "ts": "2026-06-29T00:00:00Z"} for e in entries],
    }
    (bus._dir(pid) / "answer_logs" / name).write_text(json.dumps(log), encoding="utf-8")


def test_two_participants_register_ingest_and_get_one_brief_each(tmp_path):
    bus = FolderBus(tmp_path)
    _drop_log(bus, "p_alice", "s1.json", ["I take the order", "then I check stock"])
    _drop_log(bus, "p_bob", "s1.json", ["I approve the discount"])

    ing = FakeIngestor()
    runner = RoundRunner(bus, ing, FakePlanner(ing), now="2026-06-29T12:00:00Z")
    summary = runner.run(session_id="s_next")

    # Both registered and ingested (3 entries total).
    assert sorted(summary.registered) == ["p_alice", "p_bob"]
    assert summary.entries_ingested == 3
    assert len(ing.calls) == 3
    # Each persona's brief landed in ITS OWN folder, and nowhere else.
    assert sorted(summary.briefs_written) == ["p_alice/s_next.json", "p_bob/s_next.json"]
    assert json.loads((bus._dir("p_alice") / "briefs" / "s_next.json").read_text())["persona_id"] == "p_alice"
    assert json.loads((bus._dir("p_bob") / "briefs" / "s_next.json").read_text())["persona_id"] == "p_bob"
    # The ingested log is recorded for resume.
    assert bus.read_profile("p_alice")["ingested_logs"] == ["s1.json"]


def test_rerun_does_not_reingest_and_new_participant_is_picked_up(tmp_path):
    bus = FolderBus(tmp_path)
    _drop_log(bus, "p_alice", "s1.json", ["first answer"])

    ing = FakeIngestor()
    RoundRunner(bus, ing, FakePlanner(ing), now="t1").run(session_id="s_next")
    assert len(ing.calls) == 1

    # Second round: same log must NOT be re-ingested...
    ing2 = FakeIngestor()
    # ...but a brand-new participant folder (no config) and a new log for alice are.
    _drop_log(bus, "p_bob", "s1.json", ["bob answer"])
    _drop_log(bus, "p_alice", "s2.json", ["alice second session"])
    summary = RoundRunner(bus, ing2, FakePlanner(ing2), now="t2").run(session_id="s_next2")

    answers = sorted(c["answer"] for c in ing2.calls)
    assert answers == ["alice second session", "bob answer"]  # NOT "first answer"
    assert "p_bob" in summary.registered  # auto-onboarded
    assert bus.read_profile("p_alice")["ingested_logs"] == ["s1.json", "s2.json"]


def test_ingest_uses_registry_persona_and_log_session(tmp_path):
    bus = FolderBus(tmp_path)
    _drop_log(bus, "p_alice", "s1.json", ["hello"], session_id="s_morning")

    ing = FakeIngestor()
    RoundRunner(bus, ing, FakePlanner(ing), now="t1").run(session_id="s_next")

    call = ing.calls[0]
    assert call["persona_id"] == "p_alice"  # registry (folder) is authoritative
    assert call["session_id"] == "s_morning"  # provenance stamped with the log's own session
