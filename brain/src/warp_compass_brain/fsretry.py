"""Retry wrapper for transient filesystem failures on sync-backed drives (P14).

The bus — and, unless ``GRAPH_ROOT`` moves it, the graph bundle — can live on a Google Drive /
Dropbox / OneDrive virtual drive. Those are not real filesystems. Google Drive for Desktop mounts
its drive letter through **Dokan**, a user-mode FS driver, and when Dokan's kernel request pool is
exhausted (sustained small-file churn plus system memory pressure will do it) *every* operation on
that drive fails with ``WinError 1450 ERROR_NO_SYSTEM_RESOURCES`` — reads and ``stat`` included. A
``mkdir(parents=True, exist_ok=True)`` on a directory that plainly exists is then enough to abort a
whole round, because even the ``exist_ok`` fallback ``is_dir()`` raises.

Those failures are transient: the driver recovers once its queue drains. So the fix is to back off
and try again rather than to die. A round is already resumable via
``profile.json["ingested_logs"]``, so this buys the operator an uninterrupted round, not
correctness.

Two rules the callers depend on:

* **Retry, then raise.** After the final attempt the original ``OSError`` propagates untouched.
  Nothing here swallows a failure.
* **Never let a transient error masquerade as "absent".** ``FolderBus`` and ``OkfGraphStore`` both
  read tolerantly on purpose — a half-synced or malformed file is skipped, never fatal. That is
  right for a truncated JSON/YAML file and badly wrong for ``WinError 1450``: a ``profile.json``
  that reads as ``{}`` makes ``cycle`` treat an existing participant as brand new, which re-ingests
  every Answer Log through DeepSeek and overwrites the real profile. Use `read_text_or_none` for
  those reads so absence and a busy drive stay distinguishable.
"""

from __future__ import annotations

import errno
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

#: Windows error codes meaning "the drive is busy, try again", not "this can never work".
#:     5 ERROR_ACCESS_DENIED       — sync client or AV holding a handle mid-upload
#:     6 ERROR_INVALID_HANDLE      — Drive FS remounting the volume underneath us
#:    32 ERROR_SHARING_VIOLATION   — file locked by the sync client
#:    33 ERROR_LOCK_VIOLATION      — byte-range lock, same cause
#:  1450 ERROR_NO_SYSTEM_RESOURCES — the Dokan/Drive-FS failure this module exists for
#:  1453 ERROR_WORKING_SET_QUOTA / 1816 ERROR_NOT_ENOUGH_QUOTA — the same exhaustion, other paths
TRANSIENT_WINERRORS = frozenset({5, 6, 32, 33, 1450, 1453, 1816})

#: POSIX equivalents, for a bus on a network mount or macOS Drive FS. Deliberately narrower than
#: the Windows set: ``EACCES`` on POSIX is a real permission error, so it is NOT retried there,
#: unlike ``WinError 5`` which Drive FS returns spuriously.
TRANSIENT_ERRNOS = frozenset({errno.EAGAIN, errno.EBUSY, errno.ENOMEM, errno.ENFILE, errno.EMFILE})

_attempts = 6
_base_delay = 0.5
_MAX_DELAY = 8.0


def configure(*, attempts: int, base_delay: float) -> None:
    """Apply the retry budget from settings. ``attempts=1`` disables retrying entirely.

    Called once by the CLI before any command touches a path, so tests and library users get the
    defaults without needing to configure anything.
    """
    global _attempts, _base_delay
    _attempts = max(1, attempts)
    _base_delay = max(0.0, base_delay)


def is_transient(exc: BaseException) -> bool:
    """Is this an ``OSError`` worth retrying (a busy sync drive) rather than a real failure?"""
    if not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror is not None:
        return winerror in TRANSIENT_WINERRORS
    return exc.errno in TRANSIENT_ERRNOS


def retry_fs[T](op: Callable[[], T], *, what: str) -> T:
    """Run a filesystem operation, retrying transient sync-drive failures with exponential backoff.

    ``what`` labels the one-line warning printed on the first retry — an operator watching a
    stalled round needs to know the drive is the problem, not the brain.
    """
    delay = _base_delay
    for attempt in range(1, _attempts + 1):
        try:
            return op()
        except OSError as exc:
            if attempt == _attempts or not is_transient(exc):
                raise
            if attempt == 1:
                _warn(f"{what}: {exc.strerror or exc} — sync drive busy, retrying")
            time.sleep(delay)
            delay = min(delay * 2, _MAX_DELAY)
    raise AssertionError("unreachable: the loop above either returns or raises")


def read_text_or_none(path: Path, *, what: str) -> str | None:
    """Read a UTF-8 file, retrying a busy drive. ``None`` only if the file genuinely isn't there.

    This is the seam that stops a transient ``WinError 1450`` being mistaken for "no such file"
    (see the module docstring). A *persistent* transient error raises; a real absence returns None.
    """

    def _read() -> str | None:
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None  # raced with a delete between the stat and the open
        except IsADirectoryError:
            return None

    return retry_fs(_read, what=what)


def atomic_write_text(path: Path, text: str, *, what: str, newline: str | None = None) -> None:
    """Write ``text`` to ``path`` atomically (tmp file + ``os.replace``), retrying a busy drive.

    The tmp-then-replace dance is what keeps a Drive-synced file from ever being read half-written.
    It is also the single most expensive thing you can ask Drive FS to do — ``os.replace`` needs a
    delete-approval round-trip to Google per call — which is why keeping high-churn files off the
    synced drive matters more than retrying them. Retried as one unit, so a failed replace rewrites
    the tmp file from scratch and a partially flushed tmp is never promoted.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8", newline=newline)
        os.replace(tmp, path)  # atomic on the same filesystem

    retry_fs(_write, what=what)


def _warn(msg: str) -> None:
    print(f"[fs-retry] WARNING: {msg}", file=sys.stderr)
