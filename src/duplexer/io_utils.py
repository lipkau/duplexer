"""I/O utilities for atomic writes and file stability checks."""

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_dir(path: Path) -> None:
    """
    Ensure directory exists, creating it if necessary.

    Args:
        path: Directory path to create
    """
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created directory: {path}")


def is_file_stable(file_path: Path, stability_seconds: float) -> bool:
    """
    Check if file size has been stable for the specified duration.

    Args:
        file_path: Path to file to check
        stability_seconds: Time in seconds file must be unchanged

    Returns:
        True if file is stable, False otherwise
    """
    if not file_path.exists():
        return False

    try:
        stat = file_path.stat()
        current_time = time.time()
        modified_time = stat.st_mtime

        # Check if enough time has passed since last modification
        time_since_modified = current_time - modified_time

        if time_since_modified >= stability_seconds:
            logger.debug(
                f"{file_path.name} is stable "
                f"(modified {time_since_modified:.1f}s ago >= {stability_seconds}s)"
            )
            return True
        else:
            logger.debug(
                f"{file_path.name} is not stable yet "
                f"(modified {time_since_modified:.1f}s ago < {stability_seconds}s)"
            )
            return False
    except Exception as e:
        logger.warning(f"Failed to check file stability for {file_path}: {e}")
        return False


def has_ready_file(file_path: Path) -> bool:
    """
    Check if a .ready sidecar file exists for the given file.

    Args:
        file_path: Path to check for ready file

    Returns:
        True if .ready file exists
    """
    ready_path = Path(str(file_path) + ".ready")
    exists = ready_path.exists()
    if exists:
        logger.debug(f"Found ready file: {ready_path.name}")
    return exists


def is_file_ready(file_path: Path, require_ready_file: bool, stability_seconds: float) -> bool:
    """
    Determine if file is ready for processing.

    Args:
        file_path: Path to file to check
        require_ready_file: If True, require .ready sidecar file
        stability_seconds: Seconds file must be stable if not using ready file

    Returns:
        True if file is ready to process
    """
    if require_ready_file:
        return has_ready_file(file_path)
    else:
        return is_file_stable(file_path, stability_seconds)


def already_processed(
    input_path: Path, output_dir: Path, archive_dir: Path, output_suffix: str
) -> bool:
    """
    Check if file has already been processed.

    Args:
        input_path: Input file path
        output_dir: Output directory
        archive_dir: Archive directory
        output_suffix: Suffix added to output files (e.g., ".duplex")

    Returns:
        True if file has already been processed
    """
    stem = input_path.stem
    ext = input_path.suffix

    # Check if output exists and is newer than input
    output_name = f"{stem}{output_suffix}{ext}"
    output_path = output_dir / output_name

    if output_path.exists():
        try:
            input_mtime = input_path.stat().st_mtime
            output_mtime = output_path.stat().st_mtime
            if output_mtime >= input_mtime:
                logger.debug(f"{input_path.name} already processed (output {output_name} is newer)")
                return True
        except Exception as e:
            logger.warning(f"Failed to compare timestamps: {e}")

    # Check if file exists in archive
    archive_path = archive_dir / input_path.name
    if archive_path.exists():
        logger.debug(f"{input_path.name} already archived")
        return True

    return False


def safe_move(source: Path, dest_dir: Path) -> Path | None:
    """
    Safely move a file to destination directory, handling name conflicts.

    Args:
        source: Source file path
        dest_dir: Destination directory

    Returns:
        Final destination path, or None if move failed
    """
    ensure_dir(dest_dir)
    dest = dest_dir / source.name

    # Handle name conflicts
    if dest.exists():
        base = source.stem
        ext = source.suffix
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{base}_{counter}{ext}"
            counter += 1
        logger.debug(f"Destination exists, using: {dest.name}")

    try:
        source.rename(dest)
        logger.info(f"Moved {source.name} -> {dest}")
        return dest
    except Exception as e:
        logger.error(f"Failed to move {source} to {dest_dir}: {e}")
        return None


def get_output_path(input_path: Path, output_dir: Path, output_suffix: str) -> Path:
    """
    Construct output path for a given input file.

    Args:
        input_path: Input file path
        output_dir: Output directory
        output_suffix: Suffix to add before extension

    Returns:
        Output file path

    Example:
        >>> get_output_path(Path("scan.pdf"), Path("/out"), ".duplex")
        PosixPath('/out/scan.duplex.pdf')
    """
    stem = input_path.stem
    ext = input_path.suffix
    output_name = f"{stem}{output_suffix}{ext}"
    return output_dir / output_name


def cleanup_ready_file(file_path: Path) -> None:
    """
    Remove .ready sidecar file if it exists.

    Args:
        file_path: Original file path
    """
    ready_path = Path(str(file_path) + ".ready")
    if ready_path.exists():
        try:
            ready_path.unlink()
            logger.debug(f"Removed ready file: {ready_path.name}")
        except Exception as e:
            logger.warning(f"Failed to remove ready file {ready_path}: {e}")
