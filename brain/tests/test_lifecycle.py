"""Phase 13 — participant lifecycle: retiring one person, and resetting a whole engagement.

The load-bearing assertion in this file is `test_retiring_leaves_the_graph_byte_identical`. The
whole design rests on retirement being a bus-level operation (ADR #30): if that ever stops being
true, the cost model, the hallucination argument, and the orphan-thread story all collapse
together. So we hash the graph tree before and after and demand they match exactly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from warp_compass_brain.bus import FolderBus
from warp_compass_brain.lifecycle import (
    LifecycleError,
    effective_retired,
    persona_display_names,
    reset_engagement,
    retire_participant,
    roster,
)

NOW = "2026-07-28T09:12:00+00:00"


def _seed_participant(bus: FolderBus, pid: str, *, name: str, role: str, logs: int = 1) -> None:
    bus.ensure_participant(pid)
    bus.write_profile(
        pid,
        {
            "participant_id": pid,
            "persona_id": pid,
            "display_name": name,
            "role_title": role,
            "ingested_logs": [f"s{i}.json" for i in range(1, logs + 1)],
            "last_seen": "2026-07-27T10:00:00Z",
        },
    )
    for i in range(1, logs + 1):
        (bus.participant_dir(pid) / "answer_logs" / f"s{i}.json").write_text(
            json.dumps({"session_id": f"s{i}", "persona_id": pid, "entries": []}), encoding="utf-8"
        )
    (bus.participant_dir(pid) / "briefs" / "s_next.json").write_text("{}", encoding="utf-8")


def _seed_graph(root: Path) -> None:
    (root / "activities").mkdir(parents=True, exist_ok=True)
    (root / "activities" / "act.check-stock.md").write_text(
        "---\ntype: Activity\nid: act.check-stock\n---\n# Check stock\n", encoding="utf-8"
    )
    (root / "index.md").write_text("# graph\n", encoding="utf-8")


def _tree_hash(root: Path) -> str:
    """Content hash of every file under `root` — path and bytes both."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).replace("\\", "/").encode())
            h.update(p.read_bytes())
    return h.hexdigest()


# --- retire ------------------------------------------------------------------------------------


def test_retiring_archives_the_folder_and_records_the_retirement(tmp_path):
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "rahul-ba-3c1f", name="Rahul Mehta", role="Business Analyst", logs=2)

    result = retire_participant(bus, "rahul-ba-3c1f", now=NOW)

    assert result.display_name == "Rahul Mehta"
    assert result.role_title == "Business Analyst"
    assert result.answer_logs == 2
    assert result.briefs == 1
    # Gone from the live registry...
    assert bus.list_participants() == []
    assert not bus.participant_dir("rahul-ba-3c1f").exists()
    # ...but archived, not destroyed, with a sortable date stamp.
    archived = tmp_path / "_archive" / "rahul-ba-3c1f__2026-07-28"
    assert archived.is_dir()
    assert (archived / "answer_logs" / "s1.json").is_file()
    assert result.archived_to == str(archived)
    # And marked, which is what stops the next round recreating the folder.
    assert bus.list_retired() == {"rahul-ba-3c1f"}
    assert bus.retired_records()[0]["retired_at"] == NOW


def test_retiring_leaves_the_graph_byte_identical(tmp_path):
    """ADR #30: retirement never touches the graph. This is the assertion that enforces it."""
    bus = FolderBus(tmp_path)
    graph_root = tmp_path / "graph"
    _seed_graph(graph_root)
    _seed_participant(bus, "rahul-ba-3c1f", name="Rahul", role="BA")

    before = _tree_hash(graph_root)
    retire_participant(bus, "rahul-ba-3c1f", now=NOW)
    assert _tree_hash(graph_root) == before


def test_hard_delete_skips_the_archive(tmp_path):
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep")

    result = retire_participant(bus, "asha-rep-1a2b", now=NOW, hard_delete=True)

    assert result.hard_deleted is True
    assert result.archived_to is None
    assert not (tmp_path / "_archive").exists()
    assert bus.list_retired() == {"asha-rep-1a2b"}


def test_dry_run_reports_but_changes_nothing(tmp_path):
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep", logs=3)
    before = _tree_hash(tmp_path)

    result = retire_participant(bus, "asha-rep-1a2b", now=NOW, dry_run=True)

    assert result.dry_run is True
    assert result.answer_logs == 3
    assert result.archived_to.endswith("asha-rep-1a2b__2026-07-28")
    assert _tree_hash(tmp_path) == before  # nothing moved, nothing marked
    assert bus.list_retired() == set()


def test_retiring_an_unknown_id_fails_loudly_and_lists_who_is_there(tmp_path):
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep")

    with pytest.raises(LifecycleError, match="asha-rep-1a2b"):
        retire_participant(bus, "typo-id", now=NOW)


def test_retiring_the_same_id_twice_never_overwrites_the_first_archive(tmp_path):
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep")
    retire_participant(bus, "asha-rep-1a2b", now=NOW)

    # They come back, then leave again on the same day.
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep")
    second = retire_participant(bus, "asha-rep-1a2b", now=NOW)

    assert (tmp_path / "_archive" / "asha-rep-1a2b__2026-07-28").is_dir()
    assert second.archived_to.endswith("asha-rep-1a2b__2026-07-28-2")
    # One record per person, not a duplicate.
    assert [r["id"] for r in bus.retired_records()] == ["asha-rep-1a2b"]


def test_a_corrupt_retired_file_is_tolerated_like_every_other_bus_read(tmp_path):
    bus = FolderBus(tmp_path)
    bus.retired_path.write_text("{not json", encoding="utf-8")
    assert bus.retired_records() == []
    assert bus.list_retired() == set()


# --- roster + display names -----------------------------------------------------------------------


def test_roster_lists_live_then_retired(tmp_path):
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep", logs=2)
    _seed_participant(bus, "rahul-ba-3c1f", name="Rahul Mehta", role="Business Analyst")
    retire_participant(bus, "rahul-ba-3c1f", now=NOW)

    entries = roster(bus)
    assert [(e.id, e.retired) for e in entries] == [
        ("asha-rep-1a2b", False),
        ("rahul-ba-3c1f", True),
    ]
    assert entries[0].answer_logs == 2
    assert entries[1].display_name == "Rahul Mehta"
    assert entries[1].retired_at == NOW


def test_persona_display_names_cover_live_and_retired(tmp_path):
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep")
    _seed_participant(bus, "rahul-ba-3c1f", name="Rahul Mehta", role="Business Analyst")
    retire_participant(bus, "rahul-ba-3c1f", now=NOW)

    names = persona_display_names(bus)
    assert names["asha-rep-1a2b"] == "Asha (Sales Rep)"
    assert names["rahul-ba-3c1f"] == "Rahul Mehta (Business Analyst), retired"


def test_a_participant_with_no_declared_name_is_left_to_render_as_its_id(tmp_path):
    bus = FolderBus(tmp_path)
    bus.ensure_participant("p_legacy-uuid")
    bus.write_profile("p_legacy-uuid", {"participant_id": "p_legacy-uuid", "persona_id": "p_legacy-uuid"})

    assert persona_display_names(bus) == {}  # renderer falls back to the raw id, never a blank


# --- reset ---------------------------------------------------------------------------------------


def test_reset_wipes_participants_graph_state_and_the_retired_roster(tmp_path):
    bus = FolderBus(tmp_path)
    graph_root = tmp_path / "graph"
    _seed_graph(graph_root)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep")
    _seed_participant(bus, "rahul-ba-3c1f", name="Rahul", role="BA")
    retire_participant(bus, "rahul-ba-3c1f", now=NOW)
    vectors = tmp_path / "_state" / "vectors.sqlite"
    vectors.parent.mkdir(parents=True, exist_ok=True)
    vectors.write_bytes(b"stale embeddings")

    result = reset_engagement(bus, graph_root, [vectors, tmp_path / "_state" / "missing.jsonl"])

    assert result.participants_removed == ["asha-rep-1a2b"]
    assert result.graph_removed is True
    assert result.retired_removed is True
    assert result.archive_removed is True
    assert result.state_files_removed == [str(vectors)]  # the absent one isn't claimed
    assert bus.list_participants() == []
    assert bus.list_retired() == set()
    assert not graph_root.exists()
    assert not vectors.exists()  # stale vectors are the classic half-reset failure
    assert not (tmp_path / "_archive").exists()


def test_reset_dry_run_changes_nothing(tmp_path):
    bus = FolderBus(tmp_path)
    graph_root = tmp_path / "graph"
    _seed_graph(graph_root)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep")
    before = _tree_hash(tmp_path)

    result = reset_engagement(bus, graph_root, [], dry_run=True)

    assert result.dry_run is True
    assert result.participants_removed == ["asha-rep-1a2b"]
    assert result.graph_removed is True
    assert _tree_hash(tmp_path) == before


def test_reset_can_keep_the_archive(tmp_path):
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "rahul-ba-3c1f", name="Rahul", role="BA")
    retire_participant(bus, "rahul-ba-3c1f", now=NOW)

    result = reset_engagement(bus, tmp_path / "graph", [], keep_archive=True)

    assert result.archive_removed is False
    assert (tmp_path / "_archive" / "rahul-ba-3c1f__2026-07-28").is_dir()


def test_reset_on_an_empty_bus_is_a_no_op(tmp_path):
    bus = FolderBus(tmp_path)
    result = reset_engagement(bus, tmp_path / "graph", [])
    assert result.participants_removed == []
    assert result.graph_removed is False
    assert result.state_files_removed == []


def test_reset_only_touches_the_state_files_it_is_handed(tmp_path):
    """Guard for a footgun caught in smoke testing: `_state/` is global to the brain install, not
    to a bus, so resetting a scratch bus must not destroy the configured engagement's embeddings.
    The CLI enforces that by passing an EMPTY state list for a non-configured bus; this proves the
    primitive honours it."""
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "asha-rep-1a2b", name="Asha", role="Sales Rep")
    elsewhere = tmp_path / "elsewhere" / "vectors.sqlite"
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    elsewhere.write_bytes(b"someone else's embeddings")

    result = reset_engagement(bus, tmp_path / "graph", [])

    assert result.state_files_removed == []
    assert elsewhere.read_bytes() == b"someone else's embeddings"


def test_a_restored_participant_is_no_longer_treated_as_retired(tmp_path):
    """The folder IS the registry: restoring someone by hand must un-retire them automatically.

    Otherwise they land in a silent hole — `cycle` maps their folder while the Planner excludes
    them from `live_personas()`, so they get no brief and nothing explains why.
    """
    bus = FolderBus(tmp_path)
    _seed_participant(bus, "rahul-ba-3c1f", name="Rahul", role="BA")
    retire_participant(bus, "rahul-ba-3c1f", now=NOW)
    assert effective_retired(bus) == {"rahul-ba-3c1f"}

    # The operator drags the folder back out of _archive/ but forgets the marker.
    _seed_participant(bus, "rahul-ba-3c1f", name="Rahul", role="BA")

    assert bus.list_retired() == {"rahul-ba-3c1f"}  # the stale marker is still on disk...
    assert effective_retired(bus) == set()  # ...but the folder wins
