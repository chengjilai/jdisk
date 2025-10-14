"""jdisk.

A simple Python implementation for Shanghai Jiao Tong University Netdisk client.
"""

__version__ = "0.2.3"
__author__ = "chengjilai"

from .auth import SJTUAuth
from .client import SJTUNetdiskClient
from .download import FileDownloader
from .exceptions import (
    APIError,
    AuthenticationError,
    DownloadError,
    SJTUNetdiskError,
    UploadError,
)
from .jdisk import main
from .models import DirectoryInfo, FileInfo, Session, UploadResult
from .upload import FileUploader

__all__ = [
    "SJTUAuth",
    "SJTUNetdiskClient",
    "FileUploader",
    "FileDownloader",
    "FileInfo",
    "DirectoryInfo",
    "UploadResult",
    "Session",
    "SJTUNetdiskError",
    "AuthenticationError",
    "UploadError",
    "DownloadError",
    "APIError",
    "main",
]
