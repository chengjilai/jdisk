"""API endpoint definitions for SJTU Netdisk."""

from ..constants import (
    BASE_URL,
    CREATE_DIRECTORY_URL,
    DIRECTORY_INFO_URL,
    FILE_DELETE_URL,
    FILE_INFO_URL,
    FILE_MOVE_URL,
    FILE_UPLOAD_URL,
    PERSONAL_SPACE_URL,
    SSO_LOGIN_URL,
    TOKEN_EXCHANGE_URL,
)


class APIEndpoints:
    """Centralized API endpoint management."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")

    # Authentication endpoints
    @property
    def sso_login(self) -> str:
        """SSO login endpoint."""
        return f"{self.base_url}{SSO_LOGIN_URL}"

    @property
    def token_exchange(self) -> str:
        """Token exchange endpoint."""
        return f"{self.base_url}{TOKEN_EXCHANGE_URL}"

    @property
    def personal_space(self) -> str:
        """Personal space info endpoint."""
        return f"{self.base_url}{PERSONAL_SPACE_URL}"

    # File operations endpoints
    def directory_info(self, library_id: str, space_id: str, path: str) -> str:
        """Get directory info endpoint."""
        clean_path = path.lstrip("/")
        return f"{self.base_url}{DIRECTORY_INFO_URL.format(library_id=library_id, space_id=space_id, path=clean_path)}"

    def file_info(self, library_id: str, space_id: str, path: str) -> str:
        """Get file info endpoint."""
        clean_path = path.lstrip("/")
        return f"{self.base_url}{FILE_INFO_URL.format(library_id=library_id, space_id=space_id, path=clean_path)}"

    def file_upload(self, library_id: str, space_id: str, path: str) -> str:
        """File upload endpoint."""
        clean_path = path.lstrip("/")
        return f"{self.base_url}{FILE_UPLOAD_URL.format(library_id=library_id, space_id=space_id, path=clean_path)}"

    def create_directory(self, library_id: str, space_id: str, path: str) -> str:
        """Create directory endpoint."""
        return f"{self.base_url}{CREATE_DIRECTORY_URL.format(library_id=library_id, space_id=space_id, path=path)}"

    def delete_file(self, library_id: str, space_id: str, path: str) -> str:
        """Delete file endpoint."""
        return f"{self.base_url}{FILE_DELETE_URL.format(library_id=library_id, space_id=space_id, path=path)}"

    def move_file(self, library_id: str, space_id: str, path: str) -> str:
        """Move file endpoint."""
        return f"{self.base_url}{FILE_MOVE_URL.format(library_id=library_id, space_id=space_id, path=path)}"

    def batch_operations(self, library_id: str, space_id: str) -> str:
        """Batch operations endpoint."""
        return f"{self.base_url}/api/v1/batch/{library_id}/{space_id}"

    # External endpoints
    @property
    def my_sjtu_info(self) -> str:
        """My SJTU info page for QR code UUID."""
        return "https://my.sjtu.edu.cn/ui/appmyinfo"

    def jaccount_qr_ws(self, uuid: str) -> str:
        """JAccount QR code WebSocket endpoint."""
        return f"wss://jaccount.sjtu.edu.cn/jaccount/sub/{uuid}"

    def jaccount_qr_url(self, uuid: str, sig: str = None, ts: int = None) -> str:
        """JAccount QR code URL."""
        url = f"https://jaccount.sjtu.edu.cn/jaccount/confirmscancode?uuid={uuid}"
        if sig and ts:
            url += f"&ts={ts}&sig={sig}"
        return url

    def jaccount_express_login(self, uuid: str) -> str:
        """JAccount express login endpoint."""
        return f"https://jaccount.sjtu.edu.cn/jaccount/expresslogin?uuid={uuid}"

    def oauth_authorize(self, client_id: str, redirect_uri: str, state: str = None) -> str:
        """OAuth authorize endpoint."""
        url = f"https://jaccount.sjtu.edu.cn/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
        if state:
            url += f"&state={state}"
        return url
