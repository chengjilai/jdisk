"""jdisk - Shanghai Jiao Tong University Netdisk client.

A simple Python implementation for Shanghai Jiao Tong University Netdisk client.
"""

__version__ = "0.2.3"
__author__ = "chengjilai"

# Core imports
from .core.session import SessionManager
from .core.operations import NetdiskOperations

# API imports
from .api.client import BaseAPIClient

# Services imports
from .services.uploader import FileUploader
from .services.downloader import FileDownloader

# Models imports
from .models.data import FileInfo, DirectoryInfo, Session, UploadResult
from .models.responses import APIResponse, AuthResponse, FileListResponse

# Utils imports
from .utils.errors import (
    APIError,
    AuthenticationError,
    DownloadError,
    SJTUNetdiskError,
    UploadError,
    ValidationError,
)

# CLI imports
from .cli.main import main

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