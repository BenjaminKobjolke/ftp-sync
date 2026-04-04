"""File system watcher for automatic FTP sync on changes."""

import logging
import threading
import time
from collections.abc import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 2.0


class _DebouncedHandler(FileSystemEventHandler):
    """Collects file system events and triggers a sync after a debounce period."""

    def __init__(self, sync_func: Callable[[], None], ignore_dirs: set[str]) -> None:
        super().__init__()
        self._sync_func = sync_func
        self._ignore_dirs = ignore_dirs
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _should_ignore(self, path: str) -> bool:
        """Check if the event path is in an ignored directory."""
        parts = path.replace("\\", "/").split("/")
        return any(part in self._ignore_dirs for part in parts)

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if self._should_ignore(str(event.src_path)):
            return

        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SECONDS, self._trigger_sync)
            self._timer.start()

    def _trigger_sync(self) -> None:
        logger.info("Changes detected, syncing...")
        try:
            self._sync_func()
        except Exception:
            logger.exception("Sync failed during watch")


def watch_and_sync(
    directories: tuple[str, ...],
    sync_func: Callable[[], None],
    ignore_dirs: set[str] | None = None,
) -> None:
    """Watch directories for changes and trigger sync_func after a debounce period.

    Blocks until interrupted with Ctrl+C.
    """
    handler = _DebouncedHandler(sync_func, ignore_dirs or set())
    observer = Observer()

    for directory in directories:
        observer.schedule(handler, directory, recursive=True)
        logger.info("Watching: %s", directory)

    observer.start()
    logger.info("Watcher started (debounce: %.0fs). Press Ctrl+C to stop.", DEBOUNCE_SECONDS)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping watcher...")
        observer.stop()

    observer.join()
