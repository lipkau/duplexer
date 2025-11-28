"""PDF interleaving logic for duplex scanning."""

import logging
from pathlib import Path

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


class DuplexError(Exception):
    """Base exception for duplex interleaving errors."""

    pass


class InvalidPageCountError(DuplexError):
    """Raised when page count cannot be evenly split."""

    pass


def copy_metadata(reader: PdfReader, writer: PdfWriter) -> None:
    """
    Copy document metadata from reader to writer.

    Args:
        reader: Source PDF reader
        writer: Destination PDF writer
    """
    if reader.metadata:
        metadata = {}
        if "/Title" in reader.metadata:
            metadata["/Title"] = reader.metadata["/Title"]
        if "/Author" in reader.metadata:
            metadata["/Author"] = reader.metadata["/Author"]
        if "/Subject" in reader.metadata:
            metadata["/Subject"] = reader.metadata["/Subject"]
        if "/Creator" in reader.metadata:
            metadata["/Creator"] = reader.metadata["/Creator"]

        if metadata:
            writer.add_metadata(metadata)
            logger.debug(f"Copied metadata: {metadata}")


def interleave_duplex(
    input_path: Path,
    output_path: Path,
    reverse_backs: bool = True,
    insert_blank_lastback: bool = False,
) -> None:
    """
    Interleave a manually duplex-scanned PDF.

    Input PDF pages are ordered: F1, F2, ..., Fn, Bn, B(n-1), ..., B1
    Output PDF pages are ordered: F1, B1, F2, B2, ..., Fn, Bn

    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        reverse_backs: If True, back pages are in reverse order (default: True)
        insert_blank_lastback: If True and page count is odd, insert a blank back page

    Raises:
        DuplexError: If PDF cannot be processed
        InvalidPageCountError: If page count is odd and blank insertion is disabled
    """
    logger.info(f"Interleaving {input_path.name} -> {output_path.name}")
    logger.debug(
        f"Options: reverse_backs={reverse_backs}, insert_blank_lastback={insert_blank_lastback}"
    )

    try:
        reader = PdfReader(input_path)
    except Exception as e:
        raise DuplexError(f"Failed to read PDF: {e}") from e

    if reader.is_encrypted:
        raise DuplexError("PDF is password-protected")

    total_pages = len(reader.pages)
    logger.debug(f"Total pages: {total_pages}")

    # Handle odd page count
    pages_to_process = total_pages
    appended_blank = False

    if total_pages % 2 != 0:
        if insert_blank_lastback:
            logger.info(f"Odd page count ({total_pages}), will insert blank last back page")
            pages_to_process = total_pages + 1
            appended_blank = True
        else:
            raise InvalidPageCountError(
                f"Page count {total_pages} is odd and INSERT_BLANK_LASTBACK is disabled"
            )

    # Split into fronts and backs
    n = pages_to_process // 2
    front_pages = list(range(n))
    back_pages = list(range(n, total_pages))

    # Reverse backs if needed
    if reverse_backs:
        back_pages.reverse()

    logger.debug(f"Front pages indices: {front_pages[:5]}{'...' if len(front_pages) > 5 else ''}")
    logger.debug(f"Back pages indices: {back_pages[:5]}{'...' if len(back_pages) > 5 else ''}")

    # Create output
    writer = PdfWriter()

    # Interleave pages
    for i in range(n):
        # Add front page
        front_page = reader.pages[front_pages[i]]
        writer.add_page(front_page)

        # Add back page (or blank if we need to append one)
        if appended_blank and i == n - 1:
            # Get dimensions from last front page
            mediabox = front_page.mediabox
            width = float(mediabox.width)
            height = float(mediabox.height)
            logger.debug(f"Adding blank back page: {width}x{height}")
            writer.add_blank_page(width=width, height=height)
        else:
            back_page = reader.pages[back_pages[i]]
            writer.add_page(back_page)

    # Copy metadata
    copy_metadata(reader, writer)

    # Write output
    try:
        with open(output_path, "wb") as f:
            writer.write(f)
        logger.info(f"Successfully wrote {len(writer.pages)} pages to {output_path.name}")
    except Exception as e:
        raise DuplexError(f"Failed to write output PDF: {e}") from e


def validate_pdf(input_path: Path) -> tuple[bool, str | None]:
    """
    Validate that a file is a readable PDF.

    Args:
        input_path: Path to PDF file

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> valid, error = validate_pdf(Path("test.pdf"))
        >>> if not valid:
        ...     print(f"Invalid: {error}")
    """
    try:
        reader = PdfReader(input_path)
        if reader.is_encrypted:
            return False, "PDF is password-protected"
        if len(reader.pages) == 0:
            return False, "PDF has no pages"
        return True, None
    except Exception as e:
        return False, f"Failed to read PDF: {e}"
