"""Custom exceptions for SJTU Netdisk operations."""

from typing import Optional


class SJTUNetdiskError(Exception):
    """Base exception for SJTU Netdisk operations."""

    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class AuthenticationError(SJTUNetdiskError):
    """Authentication related errors."""


class UploadError(SJTUNetdiskError):
    """Upload related errors."""


class DownloadError(SJTUNetdiskError):
    """Download related errors."""


class APIError(SJTUNetdiskError):
    """API call related errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        super().__init__(message, error_code)
        self.status_code = status_code


class NetworkError(SJTUNetdiskError):
    """Network related errors."""


class ValidationError(SJTUNetdiskError):
    """Validation related errors."""


class SessionExpiredError(AuthenticationError):
    """Session expired error."""


class FileNotFoundError(DownloadError):
    """File not found error."""


class InsufficientSpaceError(UploadError):
    """Insufficient storage space error."""


class RateLimitError(APIError):
    """Rate limit exceeded error."""
