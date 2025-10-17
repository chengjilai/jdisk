"""Authentication API for SJTU Netdisk."""

from typing import Any, Dict

from ..models.responses import AuthResponse
from ..utils.errors import AuthenticationError


class AuthAPI:
    """Authentication API client."""

    def __init__(self, base_client):
        """Initialize auth API.

        Args:
            base_client: Base API client

        """
        self.client = base_client

    def login_with_qrcode(self) -> AuthResponse:
        """Login using QR code authentication.

        Returns:
            AuthResponse: Authentication response

        Raises:
            AuthenticationError: If authentication fails

        """
        raise AuthenticationError("QR code authentication not yet fully implemented in refactored version")

    def exchange_token(self, auth_code: str) -> AuthResponse:
        """Exchange authorization code for access token.

        Args:
            auth_code: Authorization code from OAuth flow

        Returns:
            AuthResponse: Authentication response

        Raises:
            AuthenticationError: If token exchange fails

        """
        raise AuthenticationError("Token exchange not yet fully implemented in refactored version")

    def get_personal_space(self, user_token: str) -> Dict[str, Any]:
        """Get personal space information.

        Args:
            user_token: User authentication token

        Returns:
            Dict[str, Any]: Personal space information

        Raises:
            AuthenticationError: If request fails

        """
        raise AuthenticationError("Personal space API not yet fully implemented in refactored version")
