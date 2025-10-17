"""Input validation functions for SJTU Netdisk operations."""

import os
from pathlib import Path
from typing import Any, Dict

from .errors import ValidationError


def validate_file_path(file_path: str) -> Path:
    """Validate local file path.

    Args:
        file_path: Local file path to validate

    Returns:
        Path: Validated Path object

    Raises:
        ValidationError: If file path is invalid

    """
    if not file_path:
        raise ValidationError("File path cannot be empty")

    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise ValidationError(f"File does not exist: {file_path}")

    if not path.is_file():
        raise ValidationError(f"Path is not a file: {file_path}")

    if not os.access(path, os.R_OK):
        raise ValidationError(f"File is not readable: {file_path}")

    return path


def validate_remote_path(remote_path: str) -> str:
    """Validate remote file path.

    Args:
        remote_path: Remote file path to validate

    Returns:
        str: Validated remote path

    Raises:
        ValidationError: If remote path is invalid

    """
    if not remote_path:
        raise ValidationError("Remote path cannot be empty")

    # Ensure path starts with /
    if not remote_path.startswith("/"):
        remote_path = "/" + remote_path

    # Check for invalid characters
    invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]
    for char in invalid_chars:
        if char in remote_path:
            raise ValidationError(f"Remote path contains invalid character '{char}': {remote_path}")

    # Check for reserved Windows names (if accessing from Windows)
    reserved_names = ["CON", "PRN", "AUX", "NUL"] + [f"COM{i}" for i in range(1, 10)] + [f"LPT{i}" for i in range(1, 10)]

    path_parts = [part for part in remote_path.split("/") if part]
    for part in path_parts:
        if part.upper() in reserved_names:
            raise ValidationError(f"Remote path contains reserved name: {part}")

    return remote_path


def validate_session_data(session_data: Dict[str, Any]) -> bool:
    """Validate session data.

    Args:
        session_data: Session data dictionary

    Returns:
        bool: True if session data is valid

    Raises:
        ValidationError: If session data is invalid

    """
    required_fields = ["ja_auth_cookie", "user_token", "library_id", "space_id", "access_token"]

    for field in required_fields:
        if not session_data.get(field):
            raise ValidationError(f"Missing required session field: {field}")

    # Validate user token format (should be 128 characters)
    user_token = session_data.get("user_token", "")
    if len(user_token) != 128:
        raise ValidationError("Invalid user token format")

    return True


def validate_directory_path(dir_path: str) -> str:
    """Validate directory path.

    Args:
        dir_path: Directory path to validate

    Returns:
        str: Validated directory path

    Raises:
        ValidationError: If directory path is invalid

    """
    if not dir_path:
        raise ValidationError("Directory path cannot be empty")

    # Ensure path starts with /
    if not dir_path.startswith("/"):
        dir_path = "/" + dir_path

    # Path should not end with / unless it's root
    if dir_path != "/" and dir_path.endswith("/"):
        dir_path = dir_path.rstrip("/")

    return dir_path


def validate_chunk_size(chunk_size: int, file_size: int) -> int:
    """Validate and adjust chunk size.

    Args:
        chunk_size: Proposed chunk size
        file_size: Total file size

    Returns:
        int: Validated chunk size

    Raises:
        ValidationError: If chunk size is invalid

    """
    from ..constants import CHUNK_SIZE, MAX_CHUNKS

    if chunk_size <= 0:
        raise ValidationError("Chunk size must be positive")

    if chunk_size > file_size:
        chunk_size = file_size

    # Ensure we don't exceed maximum chunks
    required_chunks = (file_size + chunk_size - 1) // chunk_size
    if required_chunks > MAX_CHUNKS:
        chunk_size = (file_size + MAX_CHUNKS - 1) // MAX_CHUNKS

    # Use minimum of validated chunk size and default chunk size
    return min(chunk_size, CHUNK_SIZE)
