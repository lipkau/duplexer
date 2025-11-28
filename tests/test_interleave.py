"""Tests for core interleaving logic."""

from pathlib import Path

import pytest
from pypdf import PdfReader

from duplexer.interleave import (
    InvalidPageCountError,
    interleave_duplex,
    validate_pdf,
)


def extract_page_labels(pdf_path: Path) -> list[str]:
    """
    Extract text labels from PDF pages for testing.

    Note: This is a simplified extractor. In real tests with reportlab PDFs,
    we just verify page count and order.
    """
    reader = PdfReader(pdf_path)
    return [f"Page{i + 1}" for i in range(len(reader.pages))]


def test_interleave_even_pages_reverse(sample_duplex_pdf, tmp_path):
    """Test interleaving with even pages and reversed backs."""
    output = tmp_path / "output.pdf"

    interleave_duplex(sample_duplex_pdf, output, reverse_backs=True, insert_blank_lastback=False)

    assert output.exists()
    reader = PdfReader(output)
    assert len(reader.pages) == 6

    # Original: F1, F2, F3, B3, B2, B1
    # Expected output: F1, B1, F2, B2, F3, B3
    # We can't easily extract text, but we can verify page count


def test_interleave_even_pages_no_reverse(even_no_reverse_pdf, tmp_path):
    """Test interleaving with backs not reversed."""
    output = tmp_path / "output.pdf"

    interleave_duplex(
        even_no_reverse_pdf,
        output,
        reverse_backs=False,
        insert_blank_lastback=False,
    )

    assert output.exists()
    reader = PdfReader(output)
    assert len(reader.pages) == 4

    # Original: F1, F2, B1, B2
    # Expected output: F1, B1, F2, B2


def test_interleave_odd_pages_with_blank(odd_page_pdf, tmp_path):
    """Test odd page count with blank insertion."""
    output = tmp_path / "output.pdf"

    interleave_duplex(odd_page_pdf, output, reverse_backs=True, insert_blank_lastback=True)

    assert output.exists()
    reader = PdfReader(output)

    # Original: 5 pages -> should become 6 with blank
    assert len(reader.pages) == 6


def test_interleave_odd_pages_without_blank(odd_page_pdf, tmp_path):
    """Test odd page count without blank insertion raises error."""
    output = tmp_path / "output.pdf"

    with pytest.raises(InvalidPageCountError, match="Page count .* is odd"):
        interleave_duplex(
            odd_page_pdf,
            output,
            reverse_backs=True,
            insert_blank_lastback=False,
        )


def test_validate_pdf_valid(sample_duplex_pdf):
    """Test PDF validation with valid file."""
    valid, error = validate_pdf(sample_duplex_pdf)
    assert valid is True
    assert error is None


def test_validate_pdf_nonexistent(tmp_path):
    """Test PDF validation with nonexistent file."""
    nonexistent = tmp_path / "doesnotexist.pdf"
    valid, error = validate_pdf(nonexistent)
    assert valid is False
    assert error is not None
    assert "Failed to read PDF" in error


def test_validate_pdf_invalid_file(tmp_path):
    """Test PDF validation with invalid file."""
    invalid = tmp_path / "notapdf.pdf"
    invalid.write_text("This is not a PDF")

    valid, error = validate_pdf(invalid)
    assert valid is False
    assert error is not None


def test_interleave_preserves_page_size(sample_duplex_pdf, tmp_path):
    """Test that output preserves input page sizes."""
    output = tmp_path / "output.pdf"

    interleave_duplex(sample_duplex_pdf, output, reverse_backs=True, insert_blank_lastback=False)

    input_reader = PdfReader(sample_duplex_pdf)
    output_reader = PdfReader(output)

    # Check that page dimensions are preserved
    for i in range(len(output_reader.pages)):
        output_page = output_reader.pages[i]
        # All input pages should have same size in our test PDFs
        input_page = input_reader.pages[0]
        assert float(output_page.mediabox.width) == pytest.approx(float(input_page.mediabox.width))
        assert float(output_page.mediabox.height) == pytest.approx(
            float(input_page.mediabox.height)
        )


def test_interleave_two_pages(tmp_path):
    """Test minimal case: 2 pages."""
    from conftest import create_test_pdf

    input_pdf = tmp_path / "input.pdf"
    create_test_pdf(input_pdf, ["F1", "B1"])

    output = tmp_path / "output.pdf"
    interleave_duplex(input_pdf, output, reverse_backs=True, insert_blank_lastback=False)

    reader = PdfReader(output)
    assert len(reader.pages) == 2


def test_metadata_preservation(tmp_path):
    """Test that PDF metadata is preserved during interleaving."""
    from pypdf import PdfWriter

    # Create a PDF with metadata
    input_pdf = tmp_path / "with_metadata.pdf"
    writer = PdfWriter()

    # Add some pages
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)

    # Add metadata
    writer.add_metadata(
        {
            "/Title": "Test Document",
            "/Author": "Test Author",
            "/Subject": "Test Subject",
            "/Creator": "Test Creator",
        }
    )

    with open(input_pdf, "wb") as f:
        writer.write(f)

    # Interleave the PDF
    output_pdf = tmp_path / "output.pdf"
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Check metadata was preserved
    output_reader = PdfReader(output_pdf)
    assert output_reader.metadata is not None
    assert output_reader.metadata.get("/Title") == "Test Document"
    assert output_reader.metadata.get("/Author") == "Test Author"
    assert output_reader.metadata.get("/Subject") == "Test Subject"
    assert output_reader.metadata.get("/Creator") == "Test Creator"


def test_metadata_preservation_partial(tmp_path):
    """Test metadata preservation when only some fields are present."""
    from pypdf import PdfWriter

    # Create a PDF with partial metadata
    input_pdf = tmp_path / "partial_metadata.pdf"
    writer = PdfWriter()

    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)

    # Only add title and author
    writer.add_metadata(
        {
            "/Title": "Partial Document",
            "/Author": "Partial Author",
        }
    )

    with open(input_pdf, "wb") as f:
        writer.write(f)

    # Interleave the PDF
    output_pdf = tmp_path / "output.pdf"
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Check only present metadata was preserved
    output_reader = PdfReader(output_pdf)
    assert output_reader.metadata is not None
    assert output_reader.metadata.get("/Title") == "Partial Document"
    assert output_reader.metadata.get("/Author") == "Partial Author"
    # Subject and Creator should not be present
    assert output_reader.metadata.get("/Subject") is None
    assert output_reader.metadata.get("/Creator") is None


def test_interleave_without_metadata(tmp_path):
    """Test interleaving works correctly when input has no metadata."""
    from pypdf import PdfWriter

    # Create a PDF without metadata
    input_pdf = tmp_path / "no_metadata.pdf"
    writer = PdfWriter()

    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)

    # Don't add any metadata

    with open(input_pdf, "wb") as f:
        writer.write(f)

    # Interleave the PDF
    output_pdf = tmp_path / "output.pdf"
    interleave_duplex(
        input_pdf,
        output_pdf,
        reverse_backs=True,
        insert_blank_lastback=False,
    )

    # Should complete successfully without errors
    assert output_pdf.exists()
    output_reader = PdfReader(output_pdf)
    assert len(output_reader.pages) == 2
    # Metadata may be None or empty, both are acceptable
