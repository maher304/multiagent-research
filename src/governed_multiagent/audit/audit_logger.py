"""Append-only JSON Lines audit logger.

Design and limitations
----------------------
* One :class:`AuditEvent` is serialised per line as deterministic JSON.
* Events are appended to the end of the file; earlier lines are not rewritten.
* Writes are synchronised with an in-process lock and a best-effort lock file so
  a local prototype with several threads/processes does not interleave lines.
* ``os.fsync`` is called before success is reported.
* This is **not** tamper-proof, immutable, or cryptographically verifiable.
  A process that can write the file can alter it. Tamper-evidence would require
  an external guarantees (e.g. hash chaining + anchored storage) that are not
  implemented here.
* A crashed process can leave a stale ``.lock`` file; delete it manually if no
  writer is running.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from governed_multiagent.contracts.audit_events import AuditEvent
from governed_multiagent.contracts.common import PolicyContractError


class AuditError(RuntimeError):
    """Base class for audit persistence errors."""


class AuditWriteError(AuditError):
    """Raised when an audit event cannot be persisted."""


class AuditReadError(AuditError):
    """Raised when the audit file cannot be read or contains invalid data."""


class _FileLock:
    """Best-effort cross-process lock implemented with an exclusive lock file."""

    def __init__(self, path: Path, timeout: float) -> None:
        self._path = path
        self._timeout = timeout
        self._fd: int | None = None

    def acquire(self) -> None:
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                self._fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, str(os.getpid()).encode("ascii"))
                return
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise AuditWriteError(
                        f"timed out waiting for audit lock {self._path}; "
                        "another writer may be active or a stale lock may remain"
                    )
                time.sleep(0.05)

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass


class AuditLogger:
    """Persist and retrieve :class:`AuditEvent` records as JSON Lines."""

    def __init__(self, path: str | os.PathLike[str], *, lock_timeout: float = 10.0) -> None:
        self._path = Path(path)
        self._lock_path = self._path.with_name(self._path.name + ".lock")
        self._lock_timeout = lock_timeout
        self._thread_lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def _synchronised(self) -> Iterator[None]:
        with self._thread_lock:
            lock = _FileLock(self._lock_path, self._lock_timeout)
            lock.acquire()
            try:
                yield
            finally:
                lock.release()

    def append_event(self, event: AuditEvent) -> None:
        """Validate and append one event. Raises :class:`AuditWriteError` on failure."""

        if not isinstance(event, AuditEvent):
            raise AuditWriteError("append_event() requires an AuditEvent instance")

        try:
            line = event.to_json_line()
        except (PolicyContractError, TypeError, ValueError) as exc:
            raise AuditWriteError(f"event could not be serialised: {exc}") from exc

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AuditWriteError(f"could not create audit directory {self._path.parent}: {exc}") from exc

        try:
            with self._synchronised():
                with self._path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(line)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
        except AuditWriteError:
            raise
        except OSError as exc:
            raise AuditWriteError(f"could not append audit event to {self._path}: {exc}") from exc

    def read_events(self, request_id: str | None = None) -> list[AuditEvent]:
        """Read events, optionally filtered by correlation (request) identifier."""

        if not self._path.exists():
            return []
        events: list[AuditEvent] = []
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                for line_number, raw in enumerate(handle, start=1):
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        event = AuditEvent.from_dict(payload)
                    except (json.JSONDecodeError, PolicyContractError, TypeError, ValueError) as exc:
                        raise AuditReadError(
                            f"invalid audit event at {self._path}:{line_number}: {exc}"
                        ) from exc
                    if request_id is None or event.correlation_id == request_id:
                        events.append(event)
        except OSError as exc:
            raise AuditReadError(f"could not read audit file {self._path}: {exc}") from exc
        return events
