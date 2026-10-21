"""Process-local disk serialization shared by protocol and legacy CLI tools."""
from contextlib import contextmanager
import os
import threading
import time

from .protocol import BackendError, ErrorCode

_guard = threading.Lock()
_locks = {}


@contextmanager
def disk_access(paths, timeout=30.0):
    keys = sorted({os.path.normcase(os.path.realpath(path)) for path in paths if path})
    with _guard:
        entries = []
        for key in keys:
            lock, users = _locks.get(key, (threading.RLock(), 0))
            _locks[key] = (lock, users + 1)
            entries.append((key, lock))
    acquired = []
    deadline = time.monotonic() + timeout
    try:
        for _, lock in entries:
            if not lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
                raise BackendError(ErrorCode.TIMEOUT, "Disk queue deadline exceeded; process was not started")
            acquired.append(lock)
        yield
    finally:
        for lock in reversed(acquired):
            lock.release()
        with _guard:
            for key, lock in entries:
                _, users = _locks[key]
                if users == 1:
                    del _locks[key]
                else:
                    _locks[key] = (lock, users - 1)
