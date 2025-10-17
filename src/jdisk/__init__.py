"""jdisk, A CLI tool for SJTU Netdisk.

A simple Python implementation.
"""

__version__ = "0.3.1"
__author__ = "chengjilai"

# Core imports
# API imports
from .api.client import BaseAPIClient

# CLI imports
from .cli.main import main
from .core.operations import NetdiskOperations
from .core.session import SessionManager

# Models imports
from .models.data import DirectoryInfo, FileInfo, Session, UploadResult
from .models.responses import APIResponse, AuthResponse, FileListResponse
from .services.downloader import FileDownloader

# Services imports
from .services.uploader import FileUploader

# Utils imports
from .utils.errors import (
    APIError,
    AuthenticationError,
    DownloadError,
    SJTUNetdiskError,
    UploadError,
    ValidationError,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Core components
    "SessionManager",
    "NetdiskOperations",
    # API components
    "BaseAPIClient",
    # Services
    "FileUploader",
    "FileDownloader",
    # Models
    "FileInfo",
    "DirectoryInfo",
    "Session",
    "UploadResult",
    "APIResponse",
    "AuthResponse",
    "FileListResponse",
    # Exceptions
    "SJTUNetdiskError",
    "AuthenticationError",
    "UploadError",
    "DownloadError",
    "APIError",
    "ValidationError",
    # CLI
    "main",
]
