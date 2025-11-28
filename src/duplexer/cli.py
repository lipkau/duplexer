"""Command-line interface for duplexer."""

import logging
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import click

from duplexer.interleave import DuplexError, InvalidPageCountError, interleave_duplex
from duplexer.io_utils import (
    already_processed,
    cleanup_ready_file,
    ensure_dir,
    get_output_path,
    safe_move,
)
from duplexer.watcher import FileWatcher

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging.

    Args:
        verbose: If True, set DEBUG level; otherwise use LOG_LEVEL env var
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if verbose:
        log_level = "DEBUG"

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def str_to_bool(value: str) -> bool:
    """Convert string to boolean."""
    return value.lower() in ("true", "1", "yes", "on")


def process_pdf_file(
    file_path: Path,
    output_dir: Path,
    archive_dir: Path,
    failed_dir: Path,
    output_suffix: str,
    reverse_backs: bool,
    insert_blank_lastback: bool,
) -> None:
    """
    Process a single PDF file for duplex interleaving.

    Args:
        file_path: Path to input PDF file
        output_dir: Directory for processed output
        archive_dir: Directory to archive successfully processed files
        failed_dir: Directory to move failed/invalid files
        output_suffix: Suffix to add to output filename
        reverse_backs: Whether back pages are in reverse order
        insert_blank_lastback: Whether to insert blank page for odd counts

    Raises:
        Does not raise - all errors are handled internally with logging
    """
    logger.info(f"Processing: {file_path.name}")

    # Check if already processed
    if already_processed(file_path, output_dir, archive_dir, output_suffix):
        logger.info(f"Skipping {file_path.name} (already processed)")
        return

    # Validate PDF
    from duplexer.interleave import validate_pdf

    valid, error = validate_pdf(file_path)
    if not valid:
        logger.error(f"Invalid PDF {file_path.name}: {error}")
        safe_move(file_path, failed_dir)
        cleanup_ready_file(file_path)
        return

    # Prepare output path
    output_path = get_output_path(file_path, output_dir, output_suffix)

    # Process in temp file then move atomically
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".pdf", delete=False, dir=output_dir
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)

        interleave_duplex(
            file_path,
            tmp_path,
            reverse_backs=reverse_backs,
            insert_blank_lastback=insert_blank_lastback,
        )

        # Atomic move to final location
        try:
            tmp_path.replace(output_path)
            logger.info(f"Successfully created: {output_path.name}")
        except Exception as e:
            # Clean up temp file if replace fails
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()
            raise DuplexError(f"Failed to write output file: {e}") from e

        # Archive original
        archive_result = safe_move(file_path, archive_dir)
        if archive_result:
            cleanup_ready_file(file_path)
        else:
            logger.warning(f"Failed to archive {file_path.name}")

    except InvalidPageCountError as e:
        logger.error(f"Invalid page count for {file_path.name}: {e}")
        # Clean up temp file
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        safe_move(file_path, failed_dir)
        cleanup_ready_file(file_path)
    except DuplexError as e:
        logger.error(f"Duplex error for {file_path.name}: {e}")
        # Clean up temp file
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        safe_move(file_path, failed_dir)
        cleanup_ready_file(file_path)
    except Exception as e:
        logger.exception(f"Unexpected error processing {file_path.name}: {e}")
        # Clean up temp file
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        safe_move(file_path, failed_dir)
        cleanup_ready_file(file_path)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Duplexer - Interleave manually duplex-scanned PDFs."""
    pass


@cli.command()
@click.argument("input_pdf", type=click.Path(exists=True, path_type=Path))
@click.argument("output_pdf", type=click.Path(path_type=Path))
@click.option(
    "--reverse-backs/--no-reverse-backs",
    default=True,
    help="Reverse back pages (default: True)",
)
@click.option(
    "--insert-blank-lastback/--no-insert-blank-lastback",
    default=False,
    help="Insert blank last back page if odd count (default: False)",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def interleave(
    input_pdf: Path,
    output_pdf: Path,
    reverse_backs: bool,
    insert_blank_lastback: bool,
    verbose: bool,
):
    """
    Interleave a single PDF file.

    INPUT_PDF: Source PDF with fronts then backs
    OUTPUT_PDF: Destination for interleaved PDF
    """
    setup_logging(verbose)

    try:
        interleave_duplex(
            input_pdf,
            output_pdf,
            reverse_backs=reverse_backs,
            insert_blank_lastback=insert_blank_lastback,
        )
        click.echo(f"Successfully wrote {output_pdf}")
        sys.exit(0)
    except InvalidPageCountError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    except DuplexError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        logger.exception("Unexpected error during interleave")
        sys.exit(1)


def load_watch_config(
    pattern: str | None,
    stability_seconds: float | None,
    require_ready_file: bool | None,
) -> dict:
    """
    Load watch configuration from environment with CLI overrides.

    Args:
        pattern: CLI pattern override (or None to use env var)
        stability_seconds: CLI stability override (or None to use env var)
        require_ready_file: CLI ready file override (or None to use env var)

    Returns:
        Dictionary with all configuration values
    """
    scan_pattern = pattern or os.getenv("SCAN_GLOB", "*.pdf")
    stability_seconds_val = stability_seconds or float(os.getenv("FILE_STABILITY_SECONDS", "5.0"))

    if require_ready_file is None:
        require_ready_file = str_to_bool(os.getenv("REQUIRE_READY_FILE", "false"))

    reverse_backs = str_to_bool(os.getenv("REVERSE_BACKS", "true"))
    insert_blank_lastback = str_to_bool(os.getenv("INSERT_BLANK_LASTBACK", "false"))
    output_suffix = os.getenv("OUTPUT_SUFFIX", ".duplex")

    return {
        "scan_pattern": scan_pattern,
        "stability_seconds": stability_seconds_val,
        "require_ready_file": require_ready_file,
        "reverse_backs": reverse_backs,
        "insert_blank_lastback": insert_blank_lastback,
        "output_suffix": output_suffix,
    }


def log_watch_config(
    input_dir: Path,
    output_dir: Path,
    archive_dir: Path,
    failed_dir: Path,
    config: dict,
) -> None:
    """
    Log the watch configuration for user visibility.

    Args:
        input_dir: Input directory path
        output_dir: Output directory path
        archive_dir: Archive directory path
        failed_dir: Failed directory path
        config: Configuration dictionary from load_watch_config
    """
    logger.info("=== Duplexer Configuration ===")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Archive directory: {archive_dir}")
    logger.info(f"Failed directory: {failed_dir}")
    logger.info(f"Scan pattern: {config['scan_pattern']}")
    logger.info(f"Stability seconds: {config['stability_seconds']}s")
    logger.info(f"Require ready file: {config['require_ready_file']}")
    logger.info(f"Reverse backs: {config['reverse_backs']}")
    logger.info(f"Insert blank last back: {config['insert_blank_lastback']}")
    logger.info(f"Output suffix: {config['output_suffix']}")
    logger.info("=" * 30)


def setup_watch_directories(
    input_dir: Path,
    output_dir: Path,
    archive_dir: Path,
    failed_dir: Path,
) -> None:
    """
    Validate input directory exists and create output directories.

    Args:
        input_dir: Input directory path (must exist)
        output_dir: Output directory path (will be created)
        archive_dir: Archive directory path (will be created)
        failed_dir: Failed directory path (will be created)

    Raises:
        SystemExit: If input directory does not exist
    """
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)

    ensure_dir(output_dir)
    ensure_dir(archive_dir)
    ensure_dir(failed_dir)


def create_process_callback(
    output_dir: Path,
    archive_dir: Path,
    failed_dir: Path,
    output_suffix: str,
    reverse_backs: bool,
    insert_blank_lastback: bool,
) -> Callable[[Path], None]:
    """
    Create a process callback function with configuration captured in closure.

    Args:
        output_dir: Output directory for processed files
        archive_dir: Archive directory for originals
        failed_dir: Failed directory for invalid files
        output_suffix: Suffix to add to output filenames
        reverse_backs: Whether back pages are reversed
        insert_blank_lastback: Whether to insert blank for odd pages

    Returns:
        Callable that accepts a file path and processes it
    """

    def process_file(file_path: Path) -> None:
        """Wrapper for process_pdf_file with captured configuration."""
        process_pdf_file(
            file_path=file_path,
            output_dir=output_dir,
            archive_dir=archive_dir,
            failed_dir=failed_dir,
            output_suffix=output_suffix,
            reverse_backs=reverse_backs,
            insert_blank_lastback=insert_blank_lastback,
        )

    return process_file


@cli.command()
@click.option("--once", is_flag=True, help="Process existing files once and exit")
@click.option("--stability-seconds", type=float, help="File stability wait time")
@click.option("--pattern", type=str, help="File pattern to watch (e.g., '*.pdf')")
@click.option("--require-ready-file", type=bool, help="Require .ready sidecar file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def watch(
    once: bool,
    stability_seconds: float | None,
    pattern: str | None,
    require_ready_file: bool | None,
    verbose: bool,
):
    """
    Watch directory for new PDFs and process them.

    Configuration is read from environment variables with CLI overrides.
    """
    setup_logging(verbose)

    # Hardcoded paths
    input_dir = Path("/ingest")
    output_dir = Path("/completed")
    archive_dir = Path("/ingest/archive")
    failed_dir = Path("/ingest/failed")

    # Load configuration
    config = load_watch_config(pattern, stability_seconds, require_ready_file)

    # Log configuration
    log_watch_config(input_dir, output_dir, archive_dir, failed_dir, config)

    # Setup directories
    setup_watch_directories(input_dir, output_dir, archive_dir, failed_dir)

    # Create process callback
    process_file = create_process_callback(
        output_dir=output_dir,
        archive_dir=archive_dir,
        failed_dir=failed_dir,
        output_suffix=config["output_suffix"],
        reverse_backs=config["reverse_backs"],
        insert_blank_lastback=config["insert_blank_lastback"],
    )

    # Create watcher
    watcher = FileWatcher(
        input_dir=input_dir,
        process_callback=process_file,
        pattern=config["scan_pattern"],
        stability_seconds=config["stability_seconds"],
        require_ready_file=config["require_ready_file"],
    )

    if once:
        count = watcher.scan_once()
        logger.info(f"Processed {count} file(s)")
        sys.exit(0)
    else:
        logger.info("Starting continuous watch mode (Ctrl+C to stop)")
        watcher.watch()


if __name__ == "__main__":
    cli()
