"""Core data models for SJTU Netdisk API."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class FileInfo:
    """File information model."""

    name: str
    path: List[str]
    size: int
    type: str  # 'file' or 'dir'
    modification_time: str
    download_url: Optional[str] = None
    is_dir: bool = False
    file_id: Optional[str] = None
    crc64: Optional[str] = None
    content_type: Optional[str] = None
    hash: Optional[str] = None  # MD5 hash for integrity verification

    def full_path(self) -> str:
        """Get full path string."""
        return "/" + "/".join(self.path)

    def size_human(self) -> str:
        """Get human-readable size string."""
        size = self.size
        for unit in ["B", "K", "M", "G"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}T"


@dataclass
class DirectoryInfo:
    """Directory information model."""

    path: List[str]
    contents: List[FileInfo]
    file_count: int
    sub_dir_count: int
    total_num: int

    def full_path(self) -> str:
        """Get full path string."""
        return "/" + "/".join(self.path)

    def get_files(self) -> List[FileInfo]:
        """Get only files from contents."""
        return [item for item in self.contents if not item.is_dir]

    def get_directories(self) -> List[FileInfo]:
        """Get only directories from contents."""
        return [item for item in self.contents if item.is_dir]


@dataclass
class UploadResult:
    """Upload result model."""

    success: bool
    file_id: Optional[str] = None
    message: str = ""
    crc64: Optional[str] = None
    file_path: Optional[List[str]] = None


@dataclass
class Session:
    """Session data model."""

    ja_auth_cookie: str
    user_token: str
    library_id: str
    space_id: str
    access_token: str
    username: str

    def is_valid(self) -> bool:
        """Check if session is valid."""
        return all(
            [
                self.ja_auth_cookie,
                self.user_token,
                self.library_id,
                self.space_id,
                self.access_token,
            ]
        )

    @property
    def user_id(self) -> str:
        """Get user ID (alias for library_id)."""
        return self.library_id

    @property
    def expires_at(self) -> str:
        """Get session expiration (placeholder)."""
        return "Unknown"


@dataclass
class PersonalSpaceInfo:
    """Personal space information model."""

    library_id: str
    space_id: str
    access_token: str
    expires_in: int
    status: int
    message: str


@dataclass
class UploadContext:
    """Upload context for chunked uploads."""

    confirm_key: str
    domain: str
    path: str
    upload_id: str
    parts: Dict[str, "UploadPart"]
    expiration: str


@dataclass
class UploadPart:
    """Upload part information."""

    headers: "UploadHeaders"
    upload_url: str = ""


@dataclass
class UploadHeaders:
    """Upload headers for AWS S3 compatible upload."""

    x_amz_date: str
    x_amz_content_sha256: str
    authorization: str
