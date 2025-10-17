"""Utility functions and classes for SJTU Netdisk."""

from .errors import (
    APIError,
    AuthenticationError,
    DownloadError,
    NetworkError,
    SJTUNetdiskError,
    UploadError,
    ValidationError,
)
from .helpers import (
    calculate_file_hash,
    format_file_size,
    setup_session_headers,
)
from .validators import (
    validate_file_path,
    validate_remote_path,
    validate_session_data,
)

__all__ = [
    "SJTUNetdiskError",
    "AuthenticationError",
    "UploadError",
    "DownloadError",
    "APIError",
    "NetworkError",
    "ValidationError",
    "validate_file_path",
    "validate_remote_path",
    "validate_session_data",
    "format_file_size",
    "calculate_file_hash",
    "setup_session_headers",
]
