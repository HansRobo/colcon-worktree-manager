"""Cross-process serialization of CWM worktree lifecycle operations.

Uses POSIX advisory locks (fcntl.flock, LOCK_EX) on .cwm/lock so concurrent
agent/CLI invocations cannot corrupt .git/worktrees or the per-branch metadata
under .cwm/worktrees/.  Linux/POSIX only (ROS 2 dev environment); intentionally
not portable to Windows.

Invariant relied upon for correctness: WorktreeStateManager lifecycle methods never call one
another, so cwm_lock is never re-acquired through a second open file
description in the same process.  flock on Linux would deadlock on such
re-entry.  Do not introduce nested lifecycle calls.
"""

from __future__ import annotations

import errno
import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cwm.errors import CWMError

LOCK_FILENAME = "lock"


@contextmanager
def cwm_lock(cwm_dir: Path) -> Iterator[None]:
    """Hold an exclusive flock on ``cwm_dir/lock`` for the duration of the body.

    Blocks until the lock is acquired.  The lock file is created if missing and
    is intentionally never deleted (flock is bound to the inode; unlinking it
    would race a concurrent holder).  Exceptions raised inside the ``with`` body
    propagate unchanged and the lock is always released.  Raises CWMError only
    if the lock file cannot be opened or the lock cannot be acquired.
    """
    cwm_dir.mkdir(parents=True, exist_ok=True)
    lock_path = cwm_dir / LOCK_FILENAME
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as exc:
        raise CWMError(f"Cannot open CWM lock file {lock_path}: {exc}") from exc
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                break
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise CWMError(f"Cannot acquire CWM lock {lock_path}: {exc}") from exc
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
