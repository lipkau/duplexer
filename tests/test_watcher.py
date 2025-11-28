"""Tests for directory watcher and file processing integration."""

import shutil
import time
from pathlib import Path
from threading import Thread

from conftest import create_test_pdf
from duplexer.io_utils import is_file_stable
from duplexer.watcher import FileWatcher


def test_file_stability_check(tmp_path):
    """Test file stability detection."""
    test_file = tmp_path / "test.pdf"
    test_file.write_text("content")

    # File just created should not be stable
    assert not is_file_stable(test_file, 1.0)

    # Wait and check again
    time.sleep(1.1)
    assert is_file_stable(test_file, 1.0)


def test_watcher_scan_once(temp_dirs):
    """Test single scan of directory."""
    # Create test PDF
    test_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(test_pdf, ["F1", "F2", "B2", "B1"])

    # Make it stable by touching it in the past
    time.sleep(0.1)

    processed = []

    def callback(path: Path):
        processed.append(path.name)

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.05,
    )

    count = watcher.scan_once()

    assert count == 1
    assert "test.pdf" in processed


def test_watcher_ignores_ready_files(temp_dirs):
    """Test that .ready files are not processed as PDFs."""
    test_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(test_pdf, ["F1", "B1"])

    ready_file = temp_dirs["ingest"] / "test.pdf.ready"
    ready_file.touch()

    time.sleep(0.1)

    processed = []

    def callback(path: Path):
        processed.append(path.name)

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.05,
    )

    count = watcher.scan_once()

    # Should process only test.pdf, not test.pdf.ready
    assert count == 1
    assert "test.pdf" in processed
    assert "test.pdf.ready" not in processed


def test_watcher_processes_only_stable_files(temp_dirs):
    """Test that unstable files are not processed."""
    test_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(test_pdf, ["F1", "B1"])

    # File just created - should be unstable
    processed = []

    def callback(path: Path):
        processed.append(path.name)

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=10.0,  # Long stability requirement
    )

    count = watcher.scan_once()

    # Should not process unstable file
    assert count == 0
    assert len(processed) == 0


def test_watcher_require_ready_file(temp_dirs):
    """Test ready file requirement."""
    test_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(test_pdf, ["F1", "B1"])

    time.sleep(0.1)

    processed = []

    def callback(path: Path):
        processed.append(path.name)

    # Without ready file
    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.05,
        require_ready_file=True,
    )

    count = watcher.scan_once()
    assert count == 0

    # Add ready file
    ready_file = temp_dirs["ingest"] / "test.pdf.ready"
    ready_file.touch()

    count = watcher.scan_once()
    assert count == 1
    assert "test.pdf" in processed


def test_watcher_no_duplicate_processing(temp_dirs):
    """Test that files are not processed multiple times."""
    test_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(test_pdf, ["F1", "B1"])

    time.sleep(0.1)

    processed = []

    def callback(path: Path):
        processed.append(path.name)

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.05,
    )

    # Scan twice
    count1 = watcher.scan_once()
    count2 = watcher.scan_once()

    assert count1 == 1
    assert count2 == 0  # Should not process again
    assert len(processed) == 1


def test_watcher_pattern_matching(temp_dirs):
    """Test that only files matching pattern are processed."""
    pdf1 = temp_dirs["ingest"] / "test.pdf"
    pdf2 = temp_dirs["ingest"] / "test.txt"

    create_test_pdf(pdf1, ["F1", "B1"])
    pdf2.write_text("not a pdf")

    time.sleep(0.1)

    processed = []

    def callback(path: Path):
        processed.append(path.name)

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.05,
    )

    count = watcher.scan_once()

    assert count == 1
    assert "test.pdf" in processed
    assert "test.txt" not in processed


def test_watcher_detects_new_files_after_start(temp_dirs, tmp_path):
    """Test that watcher detects and processes files created after startup.

    This tests the actual continuous watching behavior with watchdog/polling,
    not just the scan_once() method.
    """
    # Create a test PDF outside the watched directory
    source_pdf = tmp_path / "source.pdf"
    create_test_pdf(source_pdf, ["F1", "F2", "B2", "B1"])

    # Track processed files
    processed = []

    def callback(path: Path):
        processed.append(path.name)

    # Start watcher with short stability time
    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.5,
        poll_interval=0.5,
    )

    # Run watcher in background thread
    watcher_thread = Thread(target=watcher.watch, daemon=True)
    watcher_thread.start()

    # Give watcher time to initialize
    time.sleep(0.3)

    # Verify directory is empty initially
    assert len(list(temp_dirs["ingest"].glob("*.pdf"))) == 0

    # Now copy the file into the watched directory
    dest_pdf = temp_dirs["ingest"] / "new_file.pdf"
    shutil.copy(source_pdf, dest_pdf)

    # Wait for file to be detected, stabilized, and processed
    max_wait = 3
    start_time = time.time()
    while len(processed) == 0 and (time.time() - start_time) < max_wait:
        time.sleep(0.1)

    # Stop watcher
    watcher.stop()
    time.sleep(0.2)

    # Verify file was processed
    assert len(processed) == 1, f"Expected 1 file processed, got {len(processed)}: {processed}"
    assert "new_file.pdf" in processed


def test_watcher_processes_multiple_files_in_sequence(temp_dirs, tmp_path):
    """Test that watcher can process multiple files added over time.

    This catches issues where the watcher stops working after the first file
    or where event handlers aren't properly persistent.
    """
    # Create test PDFs outside the watched directory
    source_pdf1 = tmp_path / "source1.pdf"
    source_pdf2 = tmp_path / "source2.pdf"
    source_pdf3 = tmp_path / "source3.pdf"
    create_test_pdf(source_pdf1, ["F1", "B1"])
    create_test_pdf(source_pdf2, ["F1", "F2", "B2", "B1"])
    create_test_pdf(source_pdf3, ["F1", "F2", "F3", "B3", "B2", "B1"])

    # Track processed files with timestamps
    processed = []

    def callback(path: Path):
        processed.append((path.name, time.time()))

    # Start watcher
    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.5,
    )

    watcher_thread = Thread(target=watcher.watch, daemon=True)
    watcher_thread.start()
    time.sleep(0.3)

    # Copy files one at a time with delays
    shutil.copy(source_pdf1, temp_dirs["ingest"] / "file1.pdf")
    time.sleep(1)  # Wait for first to be processed

    shutil.copy(source_pdf2, temp_dirs["ingest"] / "file2.pdf")
    time.sleep(1)  # Wait for second to be processed

    shutil.copy(source_pdf3, temp_dirs["ingest"] / "file3.pdf")
    time.sleep(1)  # Wait for third to be processed

    watcher.stop()
    time.sleep(0.2)

    # Verify all files were processed
    assert len(processed) == 3, (
        f"Expected 3 files, got {len(processed)}: {[p[0] for p in processed]}"
    )
    processed_names = [p[0] for p in processed]
    assert "file1.pdf" in processed_names
    assert "file2.pdf" in processed_names
    assert "file3.pdf" in processed_names

    # Verify they were processed in order (roughly)
    timestamps = [p[1] for p in processed]
    assert timestamps[1] > timestamps[0], "Second file should be processed after first"
    assert timestamps[2] > timestamps[1], "Third file should be processed after second"


def test_watcher_handles_rapid_file_modifications(temp_dirs, tmp_path):
    """Test that multiple modifications to same file don't cause duplicate processing.

    This tests the timer cancellation logic when a file is modified multiple times.
    """
    source_pdf = tmp_path / "source.pdf"
    create_test_pdf(source_pdf, ["F1", "B1"])

    processed = []

    def callback(path: Path):
        processed.append(path.name)

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=1.0,  # Longer stability to allow multiple modifications
    )

    watcher_thread = Thread(target=watcher.watch, daemon=True)
    watcher_thread.start()
    time.sleep(0.3)

    dest_pdf = temp_dirs["ingest"] / "modified.pdf"

    # Rapidly modify the file multiple times
    shutil.copy(source_pdf, dest_pdf)
    time.sleep(0.2)
    dest_pdf.touch()  # Modify timestamp
    time.sleep(0.2)
    dest_pdf.touch()  # Modify again
    time.sleep(0.2)
    dest_pdf.touch()  # And again

    # Wait for stability period to pass
    time.sleep(2)

    watcher.stop()
    time.sleep(0.2)

    # Should only be processed once despite multiple modifications
    assert len(processed) == 1, f"Expected 1 processing, got {len(processed)}: {processed}"
    assert "modified.pdf" in processed


def test_watcher_signal_handler_registration(temp_dirs):
    """Test that signal handlers are registered correctly on initialization."""
    import signal

    # Save original handlers
    original_sigterm = signal.getsignal(signal.SIGTERM)
    original_sigint = signal.getsignal(signal.SIGINT)

    def callback(path: Path):
        pass

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.05,
    )

    # Check that handlers were registered
    current_sigterm = signal.getsignal(signal.SIGTERM)
    current_sigint = signal.getsignal(signal.SIGINT)

    # Handlers should have changed from original
    assert current_sigterm != original_sigterm
    assert current_sigint != original_sigint

    # Verify the handlers point to the watcher's signal handler
    assert current_sigterm == watcher._signal_handler
    assert current_sigint == watcher._signal_handler

    # Restore original handlers for other tests
    signal.signal(signal.SIGTERM, original_sigterm)
    signal.signal(signal.SIGINT, original_sigint)


def test_watcher_stop_during_continuous_watch(temp_dirs):
    """Test that stop() method works during continuous watching."""
    processed = []

    def callback(path: Path):
        processed.append(path.name)

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.05,
        use_polling=True,  # Use polling for simpler testing
    )

    # Start watcher in background
    watcher_thread = Thread(target=watcher.watch, daemon=True)
    watcher_thread.start()

    # Wait for watcher to start
    time.sleep(0.5)

    # Verify it's running
    assert watcher.running

    # Stop the watcher
    watcher.stop()
    time.sleep(0.3)

    # Should be stopped now
    assert not watcher.running

    # Thread should terminate
    watcher_thread.join(timeout=2.0)
    assert not watcher_thread.is_alive()


def test_watcher_observer_cleanup_on_stop(temp_dirs):
    """Test that watchdog observer is properly cleaned up on stop."""

    def callback(path: Path):
        pass

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.05,
        use_polling=False,  # Use watchdog observer
    )

    # Start watcher
    watcher_thread = Thread(target=watcher.watch, daemon=True)
    watcher_thread.start()
    time.sleep(0.5)

    # Verify observer is running
    assert watcher.running
    if watcher.observer is not None:
        assert watcher.observer.is_alive()

    # Stop watcher
    watcher.stop()
    time.sleep(0.5)

    # Observer should be stopped and joined
    assert not watcher.running
    if watcher.observer is not None:
        # Observer should have been stopped
        assert not watcher.observer.is_alive()

    # Clean up
    watcher_thread.join(timeout=2.0)


def test_watcher_stability_check_uses_configured_seconds(temp_dirs, tmp_path):
    """Test that stability check uses the configured stability_seconds, not hardcoded value."""
    import time

    source_pdf = tmp_path / "source.pdf"
    create_test_pdf(source_pdf, ["F1", "B1"])

    processed = []
    process_times = []

    def callback(path: Path):
        processed.append(path.name)
        process_times.append(time.time())

    # Use a longer stability period
    stability_time = 1.5
    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=stability_time,
    )

    watcher_thread = Thread(target=watcher.watch, daemon=True)
    watcher_thread.start()
    time.sleep(0.3)

    # Copy file and record when
    start_time = time.time()
    dest_pdf = temp_dirs["ingest"] / "test.pdf"
    shutil.copy(source_pdf, dest_pdf)

    # Wait for processing (stability + some buffer)
    time.sleep(stability_time + 1.0)

    watcher.stop()
    time.sleep(0.2)

    # Should have been processed
    assert len(processed) == 1
    assert "test.pdf" in processed

    # Check that processing happened after stability period
    elapsed = process_times[0] - start_time
    # Should be at least stability_time (with small tolerance for scheduling)
    assert elapsed >= stability_time - 0.2, (
        f"Processing happened too early: {elapsed:.2f}s < {stability_time}s"
    )
