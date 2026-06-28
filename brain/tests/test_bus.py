"""Phase-8 FolderBus tests — the folder IS the registry; reads tolerant, writes atomic."""

from __future__ import annotations

import json

from warp_compass_brain.bus import FolderBus


def test_ensure_and_list_participants(tmp_path):
    bus = FolderBus(tmp_path)
    assert bus.list_participants() == []

    bus.ensure_participant("p_b")
    bus.ensure_participant("p_a")
    assert bus.list_participants() == ["p_a", "p_b"]  # sorted
    assert (tmp_path / "participants" / "p_a" / "answer_logs").is_dir()
    assert (tmp_path / "participants" / "p_a" / "briefs").is_dir()


def test_profile_roundtrip_and_tolerant_read(tmp_path):
    bus = FolderBus(tmp_path)
    assert bus.read_profile("p1") == {}  # none yet

    bus.write_profile("p1", {"participant_id": "p1", "persona_id": "p1", "ingested_logs": []})
    assert bus.read_profile("p1")["persona_id"] == "p1"

    # A malformed profile is skipped, never raised.
    (tmp_path / "participants" / "p1" / "profile.json").write_text("{not json", encoding="utf-8")
    assert bus.read_profile("p1") == {}


def test_answer_logs_listed_and_read(tmp_path):
    bus = FolderBus(tmp_path)
    bus.ensure_participant("p1")
    logs = tmp_path / "participants" / "p1" / "answer_logs"
    (logs / "s_2.json").write_text(json.dumps({"session_id": "s_2", "entries": []}), encoding="utf-8")
    (logs / "s_1.json").write_text(json.dumps({"session_id": "s_1", "entries": []}), encoding="utf-8")
    (logs / "notes.txt").write_text("ignore me", encoding="utf-8")

    assert bus.list_answer_logs("p1") == ["s_1.json", "s_2.json"]  # sorted, .json only
    assert bus.read_answer_log("p1", "s_1.json")["session_id"] == "s_1"


def test_write_brief(tmp_path):
    bus = FolderBus(tmp_path)
    bus.write_brief("p1", "s_next.json", {"session_id": "s_next", "persona_id": "p1"})
    written = tmp_path / "participants" / "p1" / "briefs" / "s_next.json"
    assert json.loads(written.read_text(encoding="utf-8"))["persona_id"] == "p1"
    # No leftover temp file from the atomic write.
    assert list((tmp_path / "participants" / "p1" / "briefs").glob("*.tmp")) == []
