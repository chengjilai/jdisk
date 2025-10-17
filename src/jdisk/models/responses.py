"""API response models for SJTU Netdisk API."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .data import FileInfo


@dataclass
class APIResponse:
    """Base API response model."""

    status: int
    message: str
    data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIResponse":
        """Create APIResponse from dictionary."""
        return cls(
            status=data.get("status", 1),
            message=data.get("message", ""),
            data=data,
        )

    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.status == 0


@dataclass
class AuthResponse(APIResponse):
    """Authentication response model."""

    status: int = 0
    message: str = "Success"
    data: Optional[Dict[str, Any]] = None
    user_token: Optional[str] = None
    library_id: Optional[str] = None
    space_id: Optional[str] = None
    username: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthResponse":
        """Create AuthResponse from dictionary."""
        base_response = super().from_dict(data)

        # Extract organizations data
        orgs = data.get("organizations", [])
        library_id = None
        username = None

        if orgs:
            org = orgs[0]
            library_id = org.get("libraryId")
            org_user = org.get("orgUser", {})
            username = org_user.get("nickname", library_id)

        return cls(
            status=base_response.status,
            message=base_response.message,
            data=base_response.data,
            user_token=data.get("userToken"),
            library_id=library_id,
            space_id=data.get("spaceId"),
            username=username,
        )


@dataclass
class FileListResponse(APIResponse):
    """File list response model."""

    status: int = 0
    message: str = "Success"
    data: Optional[Dict[str, Any]] = None
    path: List[str] = None
    contents: List[FileInfo] = None
    file_count: int = 0
    sub_dir_count: int = 0
    total_num: int = 0

    def __post_init__(self):
        """Initialize optional fields after dataclass creation."""
        if self.path is None:
            self.path = []
        if self.contents is None:
            self.contents = []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileListResponse":
        """Create FileListResponse from dictionary."""
        contents = []
        for item in data.get("contents", []):
            file_info = FileInfo(
                name=item.get("name", ""),
                path=item.get("path", []),
                size=int(item.get("size", 0)),
                type=item.get("type", ""),
                modification_time=item.get("modificationTime", ""),
                is_dir=item.get("type") == "dir",
                file_id=item.get("id"),
                crc64=item.get("crc64"),
                content_type=item.get("contentType"),
            )
            contents.append(file_info)

        return cls(
            status=0,  # File list responses don't have status field on success
            message="Success",
            data=data,
            path=data.get("path", []),
            contents=contents,
            file_count=data.get("fileCount", 0),
            sub_dir_count=data.get("subDirCount", 0),
            total_num=data.get("totalNum", 0),
        )


@dataclass
class PersonalSpaceResponse(APIResponse):
    """Personal space response model."""

    status: int = 0
    message: str = "Success"
    data: Optional[Dict[str, Any]] = None
    library_id: str = ""
    space_id: str = ""
    access_token: str = ""
    expires_in: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalSpaceResponse":
        """Create PersonalSpaceResponse from dictionary."""
        return cls(
            status=data.get("status", 0),
            message=data.get("message", ""),
            data=data,
            library_id=data["libraryId"],
            space_id=data["spaceId"],
            access_token=data["accessToken"],
            expires_in=data["expiresIn"],
        )
