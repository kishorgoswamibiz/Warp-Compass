"""P14 — retrying transient sync-drive failures instead of aborting the round.

The failure being defended against is Google Drive's FS driver returning
``WinError 1450 ERROR_NO_SYSTEM_RESOURCES`` for *every* operation on the drive once its request
pool is exhausted — reads and ``stat`` included, not just writes. These tests inject that error
rather than requiring a real Drive mount, and use ``base_delay=0`` so nothing actually sleeps.
"""

from __future__ import annotations

import errno
import json

import pytest

from warp_compass_brain import fsretry
from warp_compass_brain.bus import FolderBus


def _oserror(winerror: int, *, err: int = errno.EINVAL) -> OSError:
    """An OSError shaped like the ones Windows raises (both ``errno`` and ``winerror`` set)."""
    exc = OSError(err, "Insufficient system resources exist to complete the requested service")
    exc.winerror = winerror
    return exc


@pytest.fixture(autouse=True)
def _fast_retries():
    """Retry promptly during tests, and restore the real budget afterwards."""
    fsretry.configure(attempts=4, base_delay=0.0)
    yield
    fsretry.configure(attempts=6, base_delay=0.5)


class _Flaky:
    """Fails with `exc` for the first `fail_times` calls, then returns `value`."""

    def __init__(self, exc: BaseException, fail_times: int, value=None) -> None:
        self._exc = exc
        self._left = fail_times
        self._value = value
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self._left > 0:
            self._left -= 1
            raise self._exc
        return self._value


# --- the retry primitive ------------------------------------------------------------------------


def test_retries_winerror_1450_then_succeeds():
    op = _Flaky(_oserror(1450), fail_times=3, value="ok")
    assert fsretry.retry_fs(op, what="test") == "ok"
    assert op.calls == 4


def test_raises_the_original_error_once_attempts_run_out():
    op = _Flaky(_oserror(1450), fail_times=99)
    with pytest.raises(OSError) as excinfo:
        fsretry.retry_fs(op, what="test")
    assert excinfo.value.winerror == 1450  # not wrapped or replaced
    assert op.calls == 4  # exactly the configured budget, no more


def test_does_not_retry_a_real_failure():
    """A missing file or a genuine bad path must fail on the first attempt, not 15s later."""
    op = _Flaky(FileNotFoundError(errno.ENOENT, "no such file"), fail_times=99)
    with pytest.raises(FileNotFoundError):
        fsretry.retry_fs(op, what="test")
    assert op.calls == 1


def test_attempts_one_disables_retrying():
    fsretry.configure(attempts=1, base_delay=0.0)
    op = _Flaky(_oserror(1450), fail_times=99)
    with pytest.raises(OSError):
        fsretry.retry_fs(op, what="test")
    assert op.calls == 1


def test_warns_once_on_the_first_retry_only(capsys):
    fsretry.retry_fs(_Flaky(_oserror(1450), fail_times=3, value=1), what="write profile.json")
    err = capsys.readouterr().err
    assert err.count("[fs-retry]") == 1  # one line per operation, not one per attempt
    assert "write profile.json" in err  # names what stalled, so the operator can act


def test_transient_classification():
    assert fsretry.is_transient(_oserror(1450))
    assert fsretry.is_transient(_oserror(32))  # sharing violation
    assert not fsretry.is_transient(_oserror(2))  # ERROR_FILE_NOT_FOUND is real
    assert not fsretry.is_transient(ValueError("not even an OSError"))
    # No winerror (POSIX): fall back to errno, and EACCES there is a real permission error.
    assert fsretry.is_transient(OSError(errno.EBUSY, "busy"))
    assert not fsretry.is_transient(OSError(errno.EACCES, "denied"))


# --- atomic_write_text --------------------------------------------------------------------------


def test_atomic_write_retries_and_leaves_no_tmp_file(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "node.md"
    real_replace = fsretry.os.replace
    state = {"left": 2}

    def flaky_replace(src, dst):
        if state["left"] > 0:
            state["left"] -= 1
            raise _oserror(1450)
        real_replace(src, dst)

    monkeypatch.setattr(fsretry.os, "replace", flaky_replace)
    fsretry.atomic_write_text(target, "body\n", what="write node", newline="\n")

    assert target.read_text(encoding="utf-8") == "body\n"
    assert list(target.parent.glob("*.tmp")) == []  # the promoted tmp is gone, not orphaned


# --- read_text_or_none: absence and a busy drive must not look alike ----------------------------


def test_read_text_or_none_returns_none_only_for_real_absence(tmp_path):
    assert fsretry.read_text_or_none(tmp_path / "nope.json", what="read") is None


def test_read_text_or_none_raises_rather_than_reporting_absence(tmp_path, monkeypatch):
    """The whole point of P14: a busy drive must never be reported as "the file isn't there"."""
    path = tmp_path / "profile.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(type(path), "is_file", lambda self: (_ for _ in ()).throw(_oserror(1450)))
    with pytest.raises(OSError):
        fsretry.read_text_or_none(path, what="read profile.json")


# --- the consequence at the bus layer -----------------------------------------------------------


def test_busy_drive_never_makes_an_existing_profile_read_as_empty(tmp_path, monkeypatch):
    """An empty read would re-register the participant and re-ingest every log through DeepSeek."""
    bus = FolderBus(tmp_path)
    bus.write_profile("p1", {"participant_id": "p1", "ingested_logs": ["s_1.json"]})
    profile_path = tmp_path / "participants" / "p1" / "profile.json"

    real_read = type(profile_path).read_text
    state = {"left": 2}

    def flaky_read(self, *a, **kw):
        if self == profile_path and state["left"] > 0:
            state["left"] -= 1
            raise _oserror(1450)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(type(profile_path), "read_text", flaky_read)
    assert bus.read_profile("p1")["ingested_logs"] == ["s_1.json"]  # recovered, not reported empty


def test_malformed_profile_is_still_tolerated(tmp_path):
    """Retrying must not have made the Phase-8 tolerant-read contract stricter."""
    bus = FolderBus(tmp_path)
    bus.ensure_participant("p1")
    (tmp_path / "participants" / "p1" / "profile.json").write_text("{trunc", encoding="utf-8")
    assert bus.read_profile("p1") == {}


def test_ensure_participant_survives_a_transient_mkdir_failure(tmp_path, monkeypatch):
    """The exact call that killed the reported round: mkdir(exist_ok=True) raising WinError 1450."""
    bus = FolderBus(tmp_path)
    from pathlib import Path

    real_mkdir = Path.mkdir
    state = {"left": 3}

    def flaky_mkdir(self, *a, **kw):
        if state["left"] > 0:
            state["left"] -= 1
            raise _oserror(1450)
        return real_mkdir(self, *a, **kw)

    monkeypatch.setattr(Path, "mkdir", flaky_mkdir)
    bus.ensure_participant("p1")
    assert (tmp_path / "participants" / "p1" / "answer_logs").is_dir()


def test_briefs_and_retirement_still_round_trip(tmp_path):
    """Smoke-test the paths that were rewritten to go through fsretry."""
    bus = FolderBus(tmp_path)
    bus.write_brief("p1", "s_next.json", {"persona_id": "p1"})
    written = tmp_path / "participants" / "p1" / "briefs" / "s_next.json"
    assert json.loads(written.read_text(encoding="utf-8"))["persona_id"] == "p1"

    bus.mark_retired({"id": "p1", "display_name": "Someone", "retired_at": "2026-07-28"})
    bus.mark_retired({"id": "p1", "display_name": "Someone", "retired_at": "2026-07-29"})
    records = bus.retired_records()
    assert [r["id"] for r in records] == ["p1"]  # idempotent, replaced not appended
    assert records[0]["retired_at"] == "2026-07-29"
