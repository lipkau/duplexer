"""Integration test for live file watching."""

import shutil
import time
from pathlib import Path
from threading import Thread

from conftest import create_test_pdf
from duplexer.watcher import FileWatcher


def test_live_file_watching(temp_dirs, tmp_path):
    """Test that watcher detects and processes files added after startup."""
    # Create a test PDF outside the watched directory
    source_pdf = tmp_path / "source.pdf"
    create_test_pdf(source_pdf, ["F1", "F2", "B2", "B1"])

    # Track processed files
    processed = []
    process_completed = []

    def callback(path: Path):
        processed.append(path.name)
        # Simulate processing by creating output
        output = temp_dirs["completed"] / f"{path.stem}.duplex{path.suffix}"
        output.write_text("processed")
        process_completed.append(True)

    # Start watcher with very short stability time for faster test
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
    time.sleep(1)

    # Now copy the file into the watched directory
    dest_pdf = temp_dirs["ingest"] / "test.pdf"
    shutil.copy(source_pdf, dest_pdf)

    # Wait for file to be stable and processed (stability + processing time)
    max_wait = 5
    start_time = time.time()
    while len(processed) == 0 and (time.time() - start_time) < max_wait:
        time.sleep(0.2)

    # Stop watcher
    watcher.stop()
    time.sleep(0.5)

    # Verify file was processed
    assert len(processed) == 1, f"Expected 1 file processed, got {len(processed)}"
    assert "test.pdf" in processed
    assert (temp_dirs["completed"] / "test.duplex.pdf").exists()


def test_live_file_watching_with_modification(temp_dirs, tmp_path):
    """Test that watcher processes file after it becomes stable."""
    processed = []

    def callback(path: Path):
        processed.append(path.name)

    watcher = FileWatcher(
        input_dir=temp_dirs["ingest"],
        process_callback=callback,
        pattern="*.pdf",
        stability_seconds=0.5,
    )

    # Run watcher in background
    watcher_thread = Thread(target=watcher.watch, daemon=True)
    watcher_thread.start()
    time.sleep(1)

    # Create a file and keep modifying it
    test_file = temp_dirs["ingest"] / "growing.pdf"
    create_test_pdf(test_file, ["F1", "B1"])

    # Modify it a few times
    for _i in range(3):
        time.sleep(0.2)
        test_file.touch()

    # Now wait for stability + processing
    time.sleep(1.5)

    watcher.stop()
    time.sleep(0.5)

    # Should be processed exactly once after becoming stable
    assert len(processed) == 1
    assert "growing.pdf" in processed
