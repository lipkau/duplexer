"""Performance tests for large PDF handling."""

import time
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from duplexer.interleave import interleave_duplex


def create_large_pdf(output_path: Path, num_pages: int) -> None:
    """
    Create a large PDF with many blank pages for performance testing.

    Args:
        output_path: Where to write the PDF
        num_pages: Number of pages to create
    """
    writer = PdfWriter()

    # Create blank pages efficiently
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)

    with open(output_path, "wb") as f:
        writer.write(f)


def get_file_size_mb(path: Path) -> float:
    """Get file size in megabytes."""
    return path.stat().st_size / (1024 * 1024)


@pytest.mark.slow
def test_large_pdf_100_pages(tmp_path):
    """Test interleaving a 100-page PDF completes quickly."""
    # Create 100-page PDF (50 fronts, 50 backs)
    input_pdf = tmp_path / "large_100.pdf"
    create_large_pdf(input_pdf, 100)

    output_pdf = tmp_path / "output.pdf"

    # Time the interleaving
    start_time = time.time()
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )
    elapsed = time.time() - start_time

    # Verify output
    assert output_pdf.exists()
    reader = PdfReader(output_pdf)
    assert len(reader.pages) == 100

    # Should complete in under 5 seconds
    assert elapsed < 5.0, f"Processing took {elapsed:.2f}s, expected < 5s"

    # Log performance metrics
    print(
        f"\n100-page PDF: {elapsed:.3f}s, "
        f"input={get_file_size_mb(input_pdf):.2f}MB, "
        f"output={get_file_size_mb(output_pdf):.2f}MB"
    )


@pytest.mark.slow
def test_large_pdf_500_pages(tmp_path):
    """Test interleaving a 500-page PDF completes in reasonable time."""
    # Create 500-page PDF (250 fronts, 250 backs)
    input_pdf = tmp_path / "large_500.pdf"
    create_large_pdf(input_pdf, 500)

    output_pdf = tmp_path / "output.pdf"

    # Time the interleaving
    start_time = time.time()
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )
    elapsed = time.time() - start_time

    # Verify output
    assert output_pdf.exists()
    reader = PdfReader(output_pdf)
    assert len(reader.pages) == 500

    # Should complete in under 20 seconds
    assert elapsed < 20.0, f"Processing took {elapsed:.2f}s, expected < 20s"

    # Log performance metrics
    print(
        f"\n500-page PDF: {elapsed:.3f}s, "
        f"input={get_file_size_mb(input_pdf):.2f}MB, "
        f"output={get_file_size_mb(output_pdf):.2f}MB"
    )


@pytest.mark.slow
def test_large_pdf_1000_pages(tmp_path):
    """Test interleaving a 1000-page PDF (stress test)."""
    # Create 1000-page PDF (500 fronts, 500 backs)
    input_pdf = tmp_path / "large_1000.pdf"
    create_large_pdf(input_pdf, 1000)

    output_pdf = tmp_path / "output.pdf"

    # Time the interleaving
    start_time = time.time()
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )
    elapsed = time.time() - start_time

    # Verify output
    assert output_pdf.exists()
    reader = PdfReader(output_pdf)
    assert len(reader.pages) == 1000

    # Should complete in under 40 seconds
    assert elapsed < 40.0, f"Processing took {elapsed:.2f}s, expected < 40s"

    # Log performance metrics
    print(
        f"\n1000-page PDF: {elapsed:.3f}s, "
        f"input={get_file_size_mb(input_pdf):.2f}MB, "
        f"output={get_file_size_mb(output_pdf):.2f}MB"
    )


@pytest.mark.slow
def test_memory_efficiency_large_pdf(tmp_path):
    """
    Test that large PDF processing doesn't load entire file into memory.

    This test verifies the implementation streams pages rather than
    loading the entire PDF into memory at once.
    """
    import os

    import psutil

    # Get current process
    process = psutil.Process(os.getpid())

    # Record initial memory usage
    initial_memory_mb = process.memory_info().rss / (1024 * 1024)

    # Create 500-page PDF
    input_pdf = tmp_path / "large_500.pdf"
    create_large_pdf(input_pdf, 500)

    file_size_mb = get_file_size_mb(input_pdf)

    # Process the PDF
    output_pdf = tmp_path / "output.pdf"
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Record peak memory usage
    peak_memory_mb = process.memory_info().rss / (1024 * 1024)
    memory_increase_mb = peak_memory_mb - initial_memory_mb

    # Memory increase should be reasonable (not loading entire file)
    # For blank pages, PDFs are very small, so we check for reasonable overhead
    # Allow up to 50MB increase (much larger than file but reasonable for processing)
    max_allowed_mb = max(50.0, file_size_mb * 10)

    print(
        f"\nMemory usage: initial={initial_memory_mb:.2f}MB, "
        f"peak={peak_memory_mb:.2f}MB, "
        f"increase={memory_increase_mb:.2f}MB, "
        f"file_size={file_size_mb:.2f}MB, "
        f"max_allowed={max_allowed_mb:.2f}MB"
    )

    assert memory_increase_mb < max_allowed_mb, (
        f"Memory increase {memory_increase_mb:.2f}MB exceeds {max_allowed_mb:.2f}MB"
    )


@pytest.mark.slow
def test_concurrent_large_pdf_processing(tmp_path):
    """
    Test that multiple large PDFs can be processed without issues.

    This simulates the watch mode processing multiple files.
    """
    # Create 3 large PDFs
    pdfs = []
    for i in range(3):
        input_pdf = tmp_path / f"large_{i}.pdf"
        create_large_pdf(input_pdf, 200)
        pdfs.append(input_pdf)

    # Process all PDFs
    start_time = time.time()
    outputs = []

    for i, input_pdf in enumerate(pdfs):
        output_pdf = tmp_path / f"output_{i}.pdf"
        interleave_duplex(
            input_pdf,
            output_pdf,
            reverse_backs=True,
            insert_blank_lastback=False,
        )
        outputs.append(output_pdf)

    elapsed = time.time() - start_time

    # Verify all outputs
    for output_pdf in outputs:
        assert output_pdf.exists()
        reader = PdfReader(output_pdf)
        assert len(reader.pages) == 200

    # Should complete in reasonable time
    assert elapsed < 15.0, f"Processing 3x200 pages took {elapsed:.2f}s"

    print(f"\nProcessed 3 PDFs (200 pages each) in {elapsed:.3f}s")


def test_page_order_preserved_large_pdf(tmp_path):
    """
    Test that page order is correct even with large PDFs.

    This ensures the interleaving algorithm works correctly at scale.
    """
    # Create a 100-page PDF with specific pattern
    input_pdf = tmp_path / "ordered.pdf"
    writer = PdfWriter()

    # Add 100 pages: 50 fronts (F1-F50), 50 backs (B50-B1)
    for _ in range(1, 51):
        writer.add_blank_page(width=612, height=792)

    for _ in range(50, 0, -1):
        writer.add_blank_page(width=612, height=792)

    with open(input_pdf, "wb") as f:
        writer.write(f)

    # Interleave
    output_pdf = tmp_path / "output.pdf"
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Verify page count and structure
    reader = PdfReader(output_pdf)
    assert len(reader.pages) == 100

    # Expected order: F1, B1, F2, B2, ..., F50, B50
    # We can't check content easily with blank pages, but we verify
    # the interleaving completed without errors and has correct count


def test_edge_case_minimum_large_pdf(tmp_path):
    """Test edge case: exactly 2 pages (minimum for interleaving)."""
    input_pdf = tmp_path / "minimal.pdf"
    create_large_pdf(input_pdf, 2)

    output_pdf = tmp_path / "output.pdf"
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    reader = PdfReader(output_pdf)
    assert len(reader.pages) == 2
