"""Tests for process_pdf_file function."""

from conftest import create_test_pdf
from duplexer.cli import process_pdf_file


def test_process_pdf_file_success(temp_dirs):
    """Test successful PDF processing."""
    # Create input PDF
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(input_pdf, ["F1", "F2", "B2", "B1"])

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Check output exists
    output_pdf = temp_dirs["completed"] / "test.duplex.pdf"
    assert output_pdf.exists()

    # Check original archived
    archived = temp_dirs["archive"] / "test.pdf"
    assert archived.exists()
    assert not input_pdf.exists()


def test_process_pdf_file_invalid_pdf(temp_dirs):
    """Test handling of invalid PDF."""
    # Create invalid PDF
    input_pdf = temp_dirs["ingest"] / "invalid.pdf"
    input_pdf.write_text("not a pdf")

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Check moved to failed
    failed_pdf = temp_dirs["failed"] / "invalid.pdf"
    assert failed_pdf.exists()
    assert not input_pdf.exists()

    # No output created
    output_pdf = temp_dirs["completed"] / "invalid.duplex.pdf"
    assert not output_pdf.exists()


def test_process_pdf_file_odd_pages_no_blank(temp_dirs):
    """Test odd page count without blank insertion."""
    # Create odd-page PDF
    input_pdf = temp_dirs["ingest"] / "odd.pdf"
    create_test_pdf(input_pdf, ["F1", "F2", "B2"])

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Should move to failed
    failed_pdf = temp_dirs["failed"] / "odd.pdf"
    assert failed_pdf.exists()
    assert not input_pdf.exists()


def test_process_pdf_file_odd_pages_with_blank(temp_dirs):
    """Test odd page count with blank insertion."""
    # Create odd-page PDF
    input_pdf = temp_dirs["ingest"] / "odd.pdf"
    create_test_pdf(input_pdf, ["F1", "F2", "B2"])

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=True,
    )

    # Should succeed
    output_pdf = temp_dirs["completed"] / "odd.duplex.pdf"
    assert output_pdf.exists()

    archived = temp_dirs["archive"] / "odd.pdf"
    assert archived.exists()


def test_process_pdf_file_already_processed(temp_dirs):
    """Test skipping already processed files."""
    # Create and process a file
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(input_pdf, ["F1", "B1"])

    output_pdf = temp_dirs["completed"] / "test.duplex.pdf"
    create_test_pdf(output_pdf, ["F1", "B1"])

    # Archive the original
    archived = temp_dirs["archive"] / "test.pdf"
    archived.parent.mkdir(parents=True, exist_ok=True)
    input_pdf.rename(archived)

    # Create new input with same name
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(input_pdf, ["F1", "F2", "B2", "B1"])

    # Should skip
    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Original should still exist (skipped)
    assert input_pdf.exists()


def test_process_pdf_file_reprocess_when_input_newer(temp_dirs):
    """Test reprocessing when input file is newer than output."""
    import time

    # Create and process a file first
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(input_pdf, ["F1", "B1"])

    output_pdf = temp_dirs["completed"] / "test.duplex.pdf"
    create_test_pdf(output_pdf, ["F1", "B1"])

    # Wait a moment to ensure timestamp difference
    time.sleep(0.1)

    # Update input file to have newer timestamp
    input_pdf.touch()

    # Should reprocess since input is newer
    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Input should be archived (processed)
    archived = temp_dirs["archive"] / "test.pdf"
    assert archived.exists()
    assert not input_pdf.exists()

    # Output should still exist
    assert output_pdf.exists()


def test_process_pdf_file_with_ready_file(temp_dirs):
    """Test cleanup of .ready sidecar file."""
    # Create input PDF and ready file
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    ready_file = temp_dirs["ingest"] / "test.pdf.ready"
    create_test_pdf(input_pdf, ["F1", "B1"])
    ready_file.touch()

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Ready file should be cleaned up
    assert not ready_file.exists()

    # Output should exist
    output_pdf = temp_dirs["completed"] / "test.duplex.pdf"
    assert output_pdf.exists()


def test_process_pdf_file_no_reverse_backs(temp_dirs):
    """Test processing without reversing back pages."""
    # Create input PDF where backs are in forward order
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(input_pdf, ["F1", "F2", "B1", "B2"])

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=False,
        insert_blank_lastback=False,
    )

    # Should succeed
    output_pdf = temp_dirs["completed"] / "test.duplex.pdf"
    assert output_pdf.exists()

    archived = temp_dirs["archive"] / "test.pdf"
    assert archived.exists()


def test_process_pdf_file_failed_name_collision(temp_dirs):
    """Test handling of failed directory name collision."""
    # Create first invalid PDF
    input_pdf1 = temp_dirs["ingest"] / "invalid.pdf"
    input_pdf1.write_text("not a pdf")

    process_pdf_file(
        file_path=input_pdf1,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # First invalid file should be in failed
    failed_first = temp_dirs["failed"] / "invalid.pdf"
    assert failed_first.exists()
    assert not input_pdf1.exists()

    # Create second invalid PDF with same name
    input_pdf2 = temp_dirs["ingest"] / "invalid.pdf"
    input_pdf2.write_text("also not a pdf")

    process_pdf_file(
        file_path=input_pdf2,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Second should get incremented name in failed directory
    assert failed_first.exists()
    failed_second = temp_dirs["failed"] / "invalid_1.pdf"
    assert failed_second.exists()
    assert failed_second.read_text() == "also not a pdf"
    assert not input_pdf2.exists()


def test_process_pdf_file_skips_if_already_archived(temp_dirs):
    """Test that files are skipped if same name already in archive."""
    # Create input file
    input_pdf = temp_dirs["ingest"] / "already_done.pdf"
    create_test_pdf(input_pdf, ["F1", "B1"])

    # Simulate it's already been archived
    archived = temp_dirs["archive"] / "already_done.pdf"
    archived.parent.mkdir(parents=True, exist_ok=True)
    create_test_pdf(archived, ["F1", "B1"])

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Should skip processing - file still in ingest
    assert input_pdf.exists()

    # No new output created
    output_pdf = temp_dirs["completed"] / "already_done.duplex.pdf"
    assert not output_pdf.exists()


def test_process_pdf_file_corrupted_pdf(temp_dirs):
    """Test handling of corrupted PDF files."""
    # Create a file that looks like PDF but is corrupted
    input_pdf = temp_dirs["ingest"] / "corrupted.pdf"
    # PDF files start with %PDF- but this has garbage content
    input_pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ngarbage data not valid pdf")

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Should be moved to failed
    failed_pdf = temp_dirs["failed"] / "corrupted.pdf"
    assert failed_pdf.exists()
    assert not input_pdf.exists()

    # No output created
    output_pdf = temp_dirs["completed"] / "corrupted.duplex.pdf"
    assert not output_pdf.exists()


def test_process_pdf_file_encrypted_pdf(temp_dirs):
    """Test handling of password-protected/encrypted PDFs."""
    from pypdf import PdfWriter

    # Create an encrypted PDF
    input_pdf = temp_dirs["ingest"] / "encrypted.pdf"

    # Create a simple PDF and encrypt it
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    # Encrypt with password
    writer.encrypt(user_password="secret", owner_password="owner")

    with open(input_pdf, "wb") as f:
        writer.write(f)

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Should be moved to failed
    failed_pdf = temp_dirs["failed"] / "encrypted.pdf"
    assert failed_pdf.exists()
    assert not input_pdf.exists()

    # No output created
    output_pdf = temp_dirs["completed"] / "encrypted.duplex.pdf"
    assert not output_pdf.exists()


def test_process_pdf_file_empty_pdf(temp_dirs):
    """Test handling of PDF with no pages."""
    from pypdf import PdfWriter

    # Create a PDF with no pages
    input_pdf = temp_dirs["ingest"] / "empty.pdf"

    writer = PdfWriter()
    # Don't add any pages

    with open(input_pdf, "wb") as f:
        writer.write(f)

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Should be moved to failed
    failed_pdf = temp_dirs["failed"] / "empty.pdf"
    assert failed_pdf.exists()
    assert not input_pdf.exists()

    # No output created
    output_pdf = temp_dirs["completed"] / "empty.duplex.pdf"
    assert not output_pdf.exists()


def test_process_pdf_file_completely_invalid_file(temp_dirs):
    """Test handling of file that is not a PDF at all."""
    # Create a file with no PDF structure
    input_pdf = temp_dirs["ingest"] / "notpdf.pdf"
    input_pdf.write_text("This is just plain text, not a PDF")

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Should be moved to failed
    failed_pdf = temp_dirs["failed"] / "notpdf.pdf"
    assert failed_pdf.exists()
    assert not input_pdf.exists()

    # No output created
    output_pdf = temp_dirs["completed"] / "notpdf.duplex.pdf"
    assert not output_pdf.exists()


def test_process_pdf_file_output_permission_error(temp_dirs, monkeypatch):
    """Test handling of permission error during atomic rename."""
    from pathlib import Path as OrigPath

    # Create valid input PDF
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(input_pdf, ["F1", "B1"])

    # Mock Path.replace to raise PermissionError
    def mock_replace(self, target):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(OrigPath, "replace", mock_replace)

    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Should be moved to failed due to DuplexError from replace failure
    failed_pdf = temp_dirs["failed"] / "test.pdf"
    assert failed_pdf.exists()
    assert not input_pdf.exists()

    # No output created (temp file should be cleaned up)
    output_pdf = temp_dirs["completed"] / "test.duplex.pdf"
    assert not output_pdf.exists()


def test_process_pdf_file_archive_failure_scenario(temp_dirs):
    """Test complete failure path: interleave succeeds but archiving fails.

    Scenario: PDF is valid and interleaves successfully, but archiving the
    original fails (e.g., due to filesystem issues or permission loss).
    Expected: Output is created, but input is moved to failed directory,
    and warning is logged about archive failure.
    """
    # Create valid input PDF
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(input_pdf, ["F1", "B1"])

    # Make archive directory read-only to simulate permission denied
    archive_dir = temp_dirs["archive"]
    archive_dir.chmod(0o444)

    # Capture logs to verify warning
    with _capture_logs() as logs:
        process_pdf_file(
            file_path=input_pdf,
            output_dir=temp_dirs["completed"],
            archive_dir=archive_dir,
            failed_dir=temp_dirs["failed"],
            output_suffix=".duplex",
            reverse_backs=True,
            insert_blank_lastback=False,
        )

    # Restore permissions for cleanup
    archive_dir.chmod(0o755)

    # Output should still exist (interleave succeeded)
    output_pdf = temp_dirs["completed"] / "test.duplex.pdf"
    assert output_pdf.exists()

    # Input should still exist (archive failed)
    assert input_pdf.exists()

    # Verify warning was logged
    assert any("Failed to archive" in log for log in logs)


def test_process_pdf_file_complete_failure_all_steps(temp_dirs, monkeypatch):
    """Test complete error recovery chain: temp file cleanup on all failures.

    This test verifies that when processing fails at any point, all cleanup
    steps are executed:
    1. Temp file is cleaned up
    2. Original is moved to failed directory
    3. Ready file (if present) is cleaned up
    """
    # Create input PDF with ready file
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    ready_file = temp_dirs["ingest"] / "test.pdf.ready"
    create_test_pdf(input_pdf, ["F1", "B1"])
    ready_file.touch()

    # Mock interleave_duplex to raise DuplexError
    def mock_interleave(*args, **kwargs):
        from duplexer.cli import DuplexError

        raise DuplexError("Simulated interleave failure")

    monkeypatch.setattr("duplexer.cli.interleave_duplex", mock_interleave)

    # Process should handle error gracefully
    process_pdf_file(
        file_path=input_pdf,
        output_dir=temp_dirs["completed"],
        archive_dir=temp_dirs["archive"],
        failed_dir=temp_dirs["failed"],
        output_suffix=".duplex",
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Verify error recovery chain
    # 1. Input moved to failed
    failed_pdf = temp_dirs["failed"] / "test.pdf"
    assert failed_pdf.exists()
    assert not input_pdf.exists()

    # 2. Ready file cleaned up
    assert not ready_file.exists()

    # 3. No temp files left behind
    temp_files = list(temp_dirs["completed"].glob("*.pdf*"))
    assert len(temp_files) == 0

    # 4. No partial output created
    output_pdf = temp_dirs["completed"] / "test.duplex.pdf"
    assert not output_pdf.exists()


def test_process_pdf_file_output_dir_missing(temp_dirs):
    """Test handling of missing output directory.

    Scenario: Output directory is deleted after temp file creation but
    before atomic rename. This tests robustness of error handling.
    """
    # Create valid input PDF
    input_pdf = temp_dirs["ingest"] / "test.pdf"
    create_test_pdf(input_pdf, ["F1", "B1"])

    # Create a minimal output dir for temp file creation
    output_dir = temp_dirs["completed"]

    # Mock get_output_path to return a path in a non-existent directory
    def mock_get_output_path(file_path, out_dir, suffix):
        nonexistent_dir = temp_dirs["root"] / "nonexistent"
        return nonexistent_dir / f"{file_path.stem}{suffix}.pdf"

    import duplexer.cli

    original_get_output_path = duplexer.cli.get_output_path
    duplexer.cli.get_output_path = mock_get_output_path

    try:
        process_pdf_file(
            file_path=input_pdf,
            output_dir=output_dir,
            archive_dir=temp_dirs["archive"],
            failed_dir=temp_dirs["failed"],
            output_suffix=".duplex",
            reverse_backs=True,
            insert_blank_lastback=False,
        )

        # Input should be moved to failed on error
        failed_pdf = temp_dirs["failed"] / "test.pdf"
        assert failed_pdf.exists()
        assert not input_pdf.exists()

        # No output created
        assert not list(temp_dirs["root"].glob("**/test.duplex.pdf"))

    finally:
        # Restore original function
        duplexer.cli.get_output_path = original_get_output_path


def _capture_logs():
    """Context manager to capture log messages."""
    import logging
    from contextlib import contextmanager

    @contextmanager
    def capture():
        logs = []
        handler = logging.Handler()
        handler.emit = lambda record: logs.append(record.getMessage())
        logger = logging.getLogger("duplexer.cli")
        logger.addHandler(handler)
        try:
            yield logs
        finally:
            logger.removeHandler(handler)

    return capture()
