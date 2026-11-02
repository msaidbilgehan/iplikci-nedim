"""Locks across processes, each on a file of its own: fcntl's on macOS and Linux, msvcrt's on Windows. The service,
the command line and the MCP server are separate processes that change the same data folder."""

import os
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import IO


class LockTimeout(Exception):
    """Another holder kept the lock for longer than the wait."""


if sys.platform == "win32":
    import msvcrt

    def try_lock(f: IO[str]) -> bool:
        f.seek(0)  # Windows locks bytes from the file position: always the first one
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:  # held by another process
            return False
        return True

    def unlock(f: IO[str]) -> None:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def try_lock(f: IO[str]) -> bool:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def unlock(f: IO[str]) -> None:
        fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def held(path: Path, timeout: float, pause: float = 0.05) -> Generator[None]:
    """The lock in the file at path for the block; LockTimeout when it stays held past timeout seconds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_RDWR | os.O_CREAT, 0o600), "r+") as f:
        deadline = time.monotonic() + timeout
        while not try_lock(f):
            if time.monotonic() > deadline:
                raise LockTimeout(path.name)
            time.sleep(pause)
        try:
            yield
        finally:
            unlock(f)
