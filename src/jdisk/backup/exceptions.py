"""Custom exceptions for SJTU Netdisk operations"""


class SJTUNetdiskError(Exception):
    """Base exception for SJTU Netdisk operations"""


class AuthenticationError(SJTUNetdiskError):
    """Authentication related errors"""


class UploadError(SJTUNetdiskError):
    """Upload related errors"""


class DownloadError(SJTUNetdiskError):
    """Download related errors"""


class APIError(SJTUNetdiskError):
    """API call related errors"""


class NetworkError(SJTUNetdiskError):
    """Network related errors"""


class ValidationError(SJTUNetdiskError):
    """Validation related errors"""
