"""Tests for I/O utilities."""

import time
from pathlib import Path

from duplexer.io_utils import (
    already_processed,
    cleanup_ready_file,
    ensure_dir,
    get_output_path,
    has_ready_file,
    is_file_ready,
    is_file_stable,
    safe_move,
)


def test_ensure_dir(tmp_path):
    """Test that ensure_dir creates a directory if it doesn't exist."""
    new_dir = tmp_path / "new_dir"
    assert not new_dir.exists()
    ensure_dir(new_dir)
    assert new_dir.exists()
    # Test that it doesn't fail if directory already exists
    ensure_dir(new_dir)
    assert new_dir.exists()


def test_is_file_stable(tmp_path):
    """Test file stability checks."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial content")

    # Should not be stable immediately
    assert not is_file_stable(test_file, 1.0)

    # Wait for stability period
    time.sleep(1.1)
    assert is_file_stable(test_file, 1.0)

    # Test non-existent file
    assert not is_file_stable(tmp_path / "nonexistent.txt", 1.0)


def test_has_ready_file(tmp_path):
    """Test .ready file detection."""
    test_file = tmp_path / "test.txt"
    test_file.touch()

    assert not has_ready_file(test_file)

    ready_file = tmp_path / "test.txt.ready"
    ready_file.touch()

    assert has_ready_file(test_file)


def test_is_file_ready(tmp_path):
    """Test logic for determining if a file is ready for processing."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    # Mode: require_ready_file = True
    assert not is_file_ready(test_file, require_ready_file=True, stability_seconds=1.0)
    (test_file.parent / f"{test_file.name}.ready").touch()
    assert is_file_ready(test_file, require_ready_file=True, stability_seconds=1.0)

    # Mode: stability-based
    assert not is_file_ready(test_file, require_ready_file=False, stability_seconds=2.0)
    time.sleep(1.1)
    assert is_file_ready(test_file, require_ready_file=False, stability_seconds=1.0)


def test_already_processed(temp_dirs):
    """Test detection of already processed files."""
    ingest_dir = temp_dirs["ingest"]
    output_dir = temp_dirs["completed"]
    archive_dir = temp_dirs["archive"]
    suffix = ".duplex"

    input_file = ingest_dir / "test.pdf"
    input_file.touch()
    time.sleep(0.1)

    # Case 1: Output file exists and is newer
    output_file = output_dir / "test.duplex.pdf"
    output_file.touch()
    assert already_processed(input_file, output_dir, archive_dir, suffix)

    # Case 2: Output file exists but is older
    output_file.unlink()
    output_file.touch()
    time.sleep(0.1)
    input_file.touch()
    assert not already_processed(input_file, output_dir, archive_dir, suffix)

    # Case 3: File exists in archive
    archive_file = archive_dir / "test.pdf"
    archive_file.touch()
    assert already_processed(input_file, output_dir, archive_dir, suffix)

    # Case 4: Not processed
    output_file.unlink()
    archive_file.unlink()
    assert not already_processed(input_file, output_dir, archive_dir, suffix)


def test_safe_move(tmp_path):
    """Test safe_move functionality."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()

    source_file = source_dir / "move_me.txt"
    source_file.write_text("content")

    # Basic move
    moved_path = safe_move(source_file, dest_dir)
    assert moved_path is not None
    assert moved_path == dest_dir / "move_me.txt"
    assert not source_file.exists()
    assert moved_path.exists()

    # Move with name conflict
    source_file.write_text("content 2")
    conflict_file = dest_dir / "move_me.txt"
    assert conflict_file.exists()

    moved_path_conflict = safe_move(source_file, dest_dir)
    assert moved_path_conflict is not None
    assert moved_path_conflict == dest_dir / "move_me_1.txt"
    assert not source_file.exists()
    assert moved_path_conflict.exists()


def test_get_output_path():
    """Test output path generation."""
    input_path = Path("/scans/document.pdf")
    output_dir = Path("/processed")
    suffix = ".done"
    expected = Path("/processed/document.done.pdf")
    assert get_output_path(input_path, output_dir, suffix) == expected


def test_cleanup_ready_file(tmp_path):
    """Test removal of .ready sidecar file."""
    test_file = tmp_path / "test.txt"
    ready_file = tmp_path / "test.txt.ready"

    test_file.touch()
    ready_file.touch()

    assert ready_file.exists()
    cleanup_ready_file(test_file)
    assert not ready_file.exists()

    # Test that it doesn't fail if ready file doesn't exist
    cleanup_ready_file(test_file)
    assert not ready_file.exists()
