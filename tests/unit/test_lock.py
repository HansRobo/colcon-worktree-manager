"""Unit tests for cwm_lock (fcntl.flock-based serialization)."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path

import pytest

from cwm.util.lock import cwm_lock


def _can_acquire_nonblocking(lock_path: Path) -> bool:
    """Return True if an independent fd can grab the lock without blocking."""
    fd = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except BlockingIOError:
        return False
    finally:
        os.close(fd)


def test_creates_lock_file(tmp_path: Path) -> None:
    cwm_dir = tmp_path / ".cwm"  # intentionally does not exist yet
    with cwm_lock(cwm_dir):
        pass
    assert (cwm_dir / "lock").exists()


def test_lock_file_not_deleted_on_exit(tmp_path: Path) -> None:
    cwm_dir = tmp_path / ".cwm"
    cwm_dir.mkdir()
    with cwm_lock(cwm_dir):
        pass
    assert (cwm_dir / "lock").exists()


def test_body_exception_propagates_and_releases(tmp_path: Path) -> None:
    cwm_dir = tmp_path / ".cwm"
    cwm_dir.mkdir()

    class Sentinel(Exception):
        pass

    # The body exception must propagate unchanged (not wrapped in CWMError).
    with pytest.raises(Sentinel):
        with cwm_lock(cwm_dir):
            raise Sentinel()

    # ...and the lock must have been released by the finally clause.
    assert _can_acquire_nonblocking(cwm_dir / "lock")


def test_held_lock_blocks_second_nonblocking_acquirer(tmp_path: Path) -> None:
    cwm_dir = tmp_path / ".cwm"
    cwm_dir.mkdir()
    with cwm_lock(cwm_dir):
        # A distinct open file description cannot grab the lock while it is held.
        assert not _can_acquire_nonblocking(cwm_dir / "lock")


def test_lock_released_allows_subsequent_nonblocking_acquire(tmp_path: Path) -> None:
    cwm_dir = tmp_path / ".cwm"
    cwm_dir.mkdir()
    with cwm_lock(cwm_dir):
        pass
    assert _can_acquire_nonblocking(cwm_dir / "lock")
