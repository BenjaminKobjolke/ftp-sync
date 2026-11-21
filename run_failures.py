"""Track file operation failures for the current process."""

import threading

OP_TRANSFER = "transfer"
OP_DELETE = "delete"


class FailureTally:
    """Thread-safe count of failed file operations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0

    def record(self, operation: str, path: str) -> None:
        """Record one failed operation."""
        with self._lock:
            self._count += 1

    @property
    def count(self) -> int:
        """Return the number of failures recorded so far."""
        with self._lock:
            return self._count

    def reset(self) -> None:
        """Clear the count for a new run or an isolated test."""
        with self._lock:
            self._count = 0


run_failures = FailureTally()
