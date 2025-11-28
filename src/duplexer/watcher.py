"""Directory watcher for continuous PDF processing."""

from __future__ import annotations

import logging
import signal
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver

logger = logging.getLogger(__name__)

# Try to import watchdog, fall back to polling if unavailable
try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
    logger.debug("Using watchdog for file system monitoring")
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.debug("Watchdog not available, will use polling")


class ProcessingHandler(FileSystemEventHandler):
    """Watchdog event handler for processing files."""

    def __init__(
        self,
        pattern: str,
        process_callback: Callable[[Path], None],
        require_ready_file: bool,
        stability_seconds: float,
    ):
        """
        Initialize handler.

        Args:
            pattern: Glob pattern for files to process (e.g., "*.pdf")
            process_callback: Function to call for each file
            require_ready_file: If True, only process when .ready file exists
            stability_seconds: Seconds to wait for file stability
        """
        super().__init__()
        self.pattern = pattern
        self.process_callback = process_callback
        self.require_ready_file = require_ready_file
        self.stability_seconds = stability_seconds
        self.processed_files: set[Path] = set()

        # Pending files: {path: timer}
        self.pending_files: dict[Path, threading.Timer] = {}
        self.pending_lock = threading.Lock()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(str(event.src_path))  # Ensure string conversion from bytes
        logger.debug(f"File created event: {file_path}")
        self._mark_pending(file_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(str(event.src_path))  # Ensure string conversion from bytes
        logger.debug(f"File modified event: {file_path}")
        self._mark_pending(file_path)

    def _mark_pending(self, file_path: Path) -> None:
        """Mark a file as pending for stability check."""
        if not file_path.match(self.pattern):
            return
        if file_path in self.processed_files:
            return
        if file_path.name.endswith(".ready"):
            return

        with self.pending_lock:
            if file_path in self.pending_files:
                # File already pending, cancel old timer and reschedule
                old_timer = self.pending_files[file_path]
                old_timer.cancel()

            # Schedule stability check
            timer = threading.Timer(
                self.stability_seconds, self._check_file_ready, args=(file_path,)
            )
            timer.daemon = True
            self.pending_files[file_path] = timer
            timer.start()
            logger.debug(
                f"Marked {file_path.name} as pending, will check in {self.stability_seconds}s"
            )

    def _check_file_ready(self, file_path: Path) -> None:
        """Check if a file is ready and process it."""
        from duplexer.io_utils import is_file_ready

        with self.pending_lock:
            # Remove from pending
            if file_path in self.pending_files:
                del self.pending_files[file_path]

            # Skip if already processed
            if file_path in self.processed_files:
                return

            # Check if file is ready
            if is_file_ready(file_path, self.require_ready_file, self.stability_seconds):
                self.processed_files.add(file_path)
            else:
                logger.debug(f"{file_path.name} not ready yet, skipping")
                return

        # Process outside the lock
        try:
            self.process_callback(file_path)
        except Exception as e:
            logger.error(f"Failed to process {file_path.name}: {e}")


class FileWatcher:
    """Watch directory for new PDF files and process them."""

    def __init__(
        self,
        input_dir: Path,
        process_callback: Callable[[Path], None],
        pattern: str = "*.pdf",
        poll_interval: float = 2.0,
        stability_seconds: float = 5.0,
        require_ready_file: bool = False,
        use_polling: bool = False,
    ):
        """
        Initialize file watcher.

        Args:
            input_dir: Directory to watch
            process_callback: Function to call for each file
            pattern: Glob pattern for files to watch
            poll_interval: Polling interval in seconds
            stability_seconds: Time file must be stable before processing
            require_ready_file: If True, require .ready sidecar file
            use_polling: If True, force polling even if watchdog is available
        """
        self.input_dir = input_dir
        self.process_callback = process_callback
        self.pattern = pattern
        self.poll_interval = poll_interval
        self.stability_seconds = stability_seconds
        self.require_ready_file = require_ready_file
        self.use_polling = use_polling or not WATCHDOG_AVAILABLE
        self.running = False
        self.observer: BaseObserver | None = None
        self.processed_files: set[Path] = set()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.info(
            f"FileWatcher initialized: {input_dir} (pattern={pattern}, polling={self.use_polling})"
        )

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def scan_once(self) -> int:
        """
        Scan directory once and process all ready files.

        Returns:
            Number of files processed
        """
        from duplexer.io_utils import is_file_ready

        processed_count = 0
        files = sorted(self.input_dir.glob(self.pattern))

        logger.debug(f"Scanning {self.input_dir}, found {len(files)} matching files")

        for file_path in files:
            if file_path in self.processed_files:
                continue

            if file_path.name.endswith(".ready"):
                continue

            if is_file_ready(file_path, self.require_ready_file, self.stability_seconds):
                self.processed_files.add(file_path)
                try:
                    self.process_callback(file_path)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to process {file_path.name}: {e}")

        return processed_count

    def watch_polling(self) -> None:
        """Watch directory using polling."""
        logger.info(f"Watching {self.input_dir} with polling (interval={self.poll_interval}s)")
        self.running = True

        try:
            while self.running:
                self.scan_once()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.running = False
            logger.info("Polling watcher stopped")

    def watch_observer(self) -> None:
        """Watch directory using watchdog observer."""
        logger.info(f"Watching {self.input_dir} with watchdog")
        self.running = True

        handler = ProcessingHandler(
            pattern=self.pattern,
            process_callback=self.process_callback,
            require_ready_file=self.require_ready_file,
            stability_seconds=self.stability_seconds,
        )

        self.observer = Observer()
        self.observer.schedule(handler, str(self.input_dir), recursive=False)
        self.observer.start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            if self.observer:
                self.observer.stop()
                self.observer.join()
            self.running = False
            logger.info("Watchdog observer stopped")

    def watch(self) -> None:
        """
        Start watching directory continuously.

        Uses watchdog if available and not disabled, otherwise falls back to polling.
        """
        # Do an initial scan to catch any existing files
        initial_count = self.scan_once()
        if initial_count > 0:
            logger.info(f"Processed {initial_count} existing file(s)")

        if self.use_polling:
            self.watch_polling()
        else:
            self.watch_observer()

    def stop(self) -> None:
        """Stop watching."""
        self.running = False
        if self.observer:
            self.observer.stop()
