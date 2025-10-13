"""Data models for SJTU Netdisk API."""

from dataclasses import dataclass


@dataclass
class FileInfo:
    """File information model"""

    name: str
    path: list[str]
    size: int
    type: str  # 'file' or 'dir'
    modification_time: str
    download_url: str | None = None
    is_dir: bool = False
    file_id: None | str = None
    crc64: str | None = None
    content_type: None | str = None
    hash: None | str = None  # MD5 hash for integrity verification

    def full_path(self) -> str:
        """Get full path string"""
        return "/" + "/".join(self.path)


@dataclass
class DirectoryInfo:
    """Directory information model."""

    path: list[str]
    contents: list[FileInfo]
    file_count: int
    sub_dir_count: int
    total_num: int

    def full_path(self) -> str:
        """Get full path string"""
        return "/" + "/".join(self.path)


@dataclass
class UploadResult:
    """Upload result model"""

    success: bool
    file_id: None | str = None
    message: str = ""
    crc64: None | str = None
    file_path: None | list[str] = None


@dataclass
class Session:
    """Session data model"""

    ja_auth_cookie: str
    user_token: str
    library_id: str
    space_id: str
    access_token: str
    username: str

    def is_valid(self) -> bool:
        """Check if session is valid"""
        return all(
            [
                self.ja_auth_cookie,
                self.user_token,
                self.library_id,
                self.space_id,
                self.access_token,
            ],
        )

    @property
    def user_id(self) -> str:
        """Get user ID (alias for library_id)"""
        return self.library_id

    @property
    def expires_at(self) -> str:
        """Get session expiration (placeholder)"""
        return "Unknown"


@dataclass
class PersonalSpaceInfo:
    """Personal space information model"""

    library_id: str
    space_id: str
    access_token: str
    expires_in: int
    status: int
    message: str


@dataclass
class UploadContext:
    """Upload context for chunked uploads"""

    confirm_key: str
    domain: str
    path: str
    upload_id: str
    parts: dict[str, "UploadPart"]
    expiration: str


@dataclass
class UploadPart:
    """Upload part information"""

    headers: "UploadHeaders"
    upload_url: str = ""


@dataclass
class UploadHeaders:
    """Upload headers for AWS S3 compatible upload"""

    x_amz_date: str
    x_amz_content_sha256: str
    authorization: str
