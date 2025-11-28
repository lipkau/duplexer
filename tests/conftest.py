"""Test fixtures and utilities."""

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_labeled_page(width: float, height: float, label: str) -> PdfWriter:
    """
    Create a PDF page with a text label using reportlab.

    Args:
        width: Page width in points
        height: Page height in points
        label: Text to display on the page

    Returns:
        PdfWriter with a single labeled page
    """
    import io

    # Create PDF in memory
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # Draw label in center
    c.setFont("Helvetica-Bold", 48)
    text_width = c.stringWidth(label, "Helvetica-Bold", 48)
    x = (width - text_width) / 2
    y = height / 2
    c.drawString(x, y, label)

    c.save()

    # Convert to PdfWriter
    buffer.seek(0)
    reader = PdfReader(buffer)
    writer = PdfWriter()
    writer.add_page(reader.pages[0])

    return writer


def create_test_pdf(output_path: Path, page_labels: list[str]) -> None:
    """
    Create a test PDF with labeled pages.

    Args:
        output_path: Where to write the PDF
        page_labels: List of labels for each page (e.g., ["F1", "F2", "B2", "B1"])
    """
    writer = PdfWriter()

    for label in page_labels:
        page_writer = create_labeled_page(letter[0], letter[1], label)
        writer.add_page(page_writer.pages[0])

    with open(output_path, "wb") as f:
        writer.write(f)


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directory structure for testing."""
    ingest = tmp_path / "ingest"
    completed = tmp_path / "completed"
    archive = ingest / "archive"
    failed = ingest / "failed"

    ingest.mkdir()
    completed.mkdir()
    archive.mkdir()
    failed.mkdir()

    return {
        "root": tmp_path,
        "ingest": ingest,
        "completed": completed,
        "archive": archive,
        "failed": failed,
    }


@pytest.fixture
def sample_duplex_pdf(tmp_path):
    """Create a sample duplex-scanned PDF: F1, F2, F3, B3, B2, B1."""
    pdf_path = tmp_path / "sample.pdf"
    create_test_pdf(pdf_path, ["F1", "F2", "F3", "B3", "B2", "B1"])
    return pdf_path


@pytest.fixture
def odd_page_pdf(tmp_path):
    """Create a PDF with odd page count: F1, F2, B2, B1."""
    pdf_path = tmp_path / "odd.pdf"
    create_test_pdf(pdf_path, ["F1", "F2", "F3", "B3", "B2"])
    return pdf_path


@pytest.fixture
def even_no_reverse_pdf(tmp_path):
    """Create a PDF with backs not reversed: F1, F2, B1, B2."""
    pdf_path = tmp_path / "no_reverse.pdf"
    create_test_pdf(pdf_path, ["F1", "F2", "B1", "B2"])
    return pdf_path
