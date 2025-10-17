"""Helper functions for SJTU Netdisk operations."""

import hashlib
import mimetypes
import time
from typing import Dict

from ..constants import USER_AGENT


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Formatted size string

    """
    if size_bytes == 0:
        return "0B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    if i == 0:
        return f"{int(size)}{size_names[i]}"
    return f"{size:.1f}{size_names[i]}"


def calculate_file_hash(file_path: str, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """Calculate hash of a file.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha1, sha256, etc.)
        chunk_size: Size of chunks to read

    Returns:
        str: Hexadecimal hash digest

    Raises:
        ValidationError: If file cannot be read

    """
    from pathlib import Path

    from .errors import ValidationError

    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ValidationError(f"Cannot read file for hash calculation: {file_path}")

    hash_func = hashlib.new(algorithm)

    try:
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except IOError as e:
        raise ValidationError(f"Cannot read file for hash calculation: {e}")


def calculate_chunk_hashes(file_path: str, chunk_size: int) -> str:
    """Calculate SHA256 hashes for each chunk and return combined hash string.

    Args:
        file_path: Local file path
        chunk_size: Chunk size in bytes

    Returns:
        str: Comma-separated SHA256 hashes of chunks

    """
    from pathlib import Path

    path = Path(file_path)
    file_size = path.stat().st_size
    chunk_count = (file_size + chunk_size - 1) // chunk_size
    sha256_list = []

    with open(path, "rb") as f:
        for chunk_number in range(chunk_count):
            chunk_start = chunk_number * chunk_size
            chunk_end = min(chunk_start + chunk_size, file_size)
            current_chunk_size = chunk_end - chunk_start

            f.seek(chunk_start)
            chunk_data = f.read(current_chunk_size)

            # Calculate SHA256 for this chunk
            sha256_hash = hashlib.sha256(chunk_data).hexdigest()
            sha256_list.append(sha256_hash)

    return ",".join(sha256_list)


def get_mime_type(file_path: str) -> str:
    """Get MIME type for a file.

    Args:
        file_path: Path to the file

    Returns:
        str: MIME type

    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def setup_session_headers(additional_headers: Dict[str, str] = None) -> Dict[str, str]:
    """Setup standard session headers.

    Args:
        additional_headers: Additional headers to include

    Returns:
        Dict[str, str]: Headers dictionary

    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
    }

    if additional_headers:
        headers.update(additional_headers)

    return headers


def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        float: Delay in seconds

    """
    delay = base_delay * (2**attempt)
    return min(delay, max_delay)


def get_current_timestamp_ms() -> int:
    """Get current timestamp in milliseconds.

    Returns:
        int: Current timestamp in milliseconds

    """
    return int(time.time() * 1000)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage.

    Args:
        filename: Original filename

    Returns:
        str: Sanitized filename

    """
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Remove leading/trailing spaces and dots
    filename = filename.strip(" .")

    # Ensure filename is not empty
    if not filename:
        filename = "unnamed_file"

    return filename


def parse_file_size(size_str: str) -> int:
    """Parse file size string to bytes.

    Args:
        size_str: Size string (e.g., "10MB", "1.5GB")

    Returns:
        int: Size in bytes

    Raises:
        ValidationError: If size string is invalid

    """
    from .errors import ValidationError

    size_str = size_str.strip().upper()
    if not size_str:
        raise ValidationError("Size string cannot be empty")

    # Parse number and unit
    import re

    match = re.match(r"^(\d+(?:\.\d+)?)\s*([A-Z]*)$", size_str)
    if not match:
        raise ValidationError(f"Invalid size format: {size_str}")

    number_str, unit = match.groups()
    try:
        number = float(number_str)
    except ValueError:
        raise ValidationError(f"Invalid number in size: {number_str}")

    # Convert to bytes
    multipliers = {
        "": 1,
        "B": 1,
        "K": 1024,
        "KB": 1024,
        "M": 1024**2,
        "MB": 1024**2,
        "G": 1024**3,
        "GB": 1024**3,
        "T": 1024**4,
        "TB": 1024**4,
    }

    multiplier = multipliers.get(unit)
    if multiplier is None:
        raise ValidationError(f"Unknown unit in size: {unit}")

    return int(number * multiplier)
