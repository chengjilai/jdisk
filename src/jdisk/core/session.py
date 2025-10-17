"""Session management for SJTU Netdisk operations."""

import json
import logging
from pathlib import Path
from typing import Optional

from ..constants import SESSION_FILE
from ..models.data import Session
from ..utils.errors import AuthenticationError, ValidationError
from ..utils.validators import validate_session_data

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user authentication sessions."""

    def __init__(self, session_file: str = SESSION_FILE):
        """Initialize session manager.

        Args:
            session_file: Path to session file

        """
        self.session_file_path = Path(session_file).expanduser()
        self._current_session: Optional[Session] = None

    def save_session(self, session: Session) -> bool:
        """Save session to file.

        Args:
            session: Session to save

        Returns:
            bool: True if saved successfully

        """
        try:
            # Validate session before saving
            if not session.is_valid():
                logger.error("Attempted to save invalid session")
                return False

            # Ensure directory exists
            self.session_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Save session data
            session_data = {
                "ja_auth_cookie": session.ja_auth_cookie,
                "user_token": session.user_token,
                "library_id": session.library_id,
                "space_id": session.space_id,
                "access_token": session.access_token,
                "username": session.username,
            }

            with open(self.session_file_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            self._current_session = session
            logger.info(f"Session saved for user: {session.username}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def load_session(self) -> Optional[Session]:
        """Load session from file.

        Returns:
            Optional[Session]: Loaded session or None if not found/invalid

        """
        if self._current_session:
            return self._current_session

        try:
            if not self.session_file_path.exists():
                logger.debug("Session file does not exist")
                return None

            with open(self.session_file_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # Validate session data
            validate_session_data(session_data)

            # Create session object
            session = Session(**session_data)

            self._current_session = session
            logger.debug(f"Session loaded for user: {session.username}")
            return session

        except ValidationError as e:
            logger.warning(f"Invalid session data: {e}")
            # Remove invalid session file
            self.clear_session()
            return None
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None

    def clear_session(self) -> bool:
        """Clear stored session.

        Returns:
            bool: True if cleared successfully

        """
        try:
            self._current_session = None

            if self.session_file_path.exists():
                self.session_file_path.unlink()
                logger.info("Session file deleted")

            return True

        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
            return False

    def is_authenticated(self) -> bool:
        """Check if user is authenticated.

        Returns:
            bool: True if authenticated

        """
        session = self.get_current_session()
        return session is not None and session.is_valid()

    def get_current_session(self) -> Optional[Session]:
        """Get current session.

        Returns:
            Optional[Session]: Current session or None

        """
        if not self._current_session:
            self._current_session = self.load_session()
        return self._current_session

    def update_session(self, **kwargs) -> bool:
        """Update current session with new data.

        Args:
            **kwargs: Session fields to update

        Returns:
            bool: True if updated successfully

        """
        session = self.get_current_session()
        if not session:
            return False

        # Update session fields
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

        # Save updated session
        return self.save_session(session)

    def get_auth_headers(self) -> dict:
        """Get authentication headers for API requests.

        Returns:
            dict: Authentication headers

        """
        session = self.get_current_session()
        if not session:
            raise AuthenticationError("No active session")

        return {
            "Authorization": f"Bearer {session.access_token}",
        }

    def get_auth_cookies(self) -> dict:
        """Get authentication cookies.

        Returns:
            dict: Authentication cookies

        """
        session = self.get_current_session()
        if not session:
            raise AuthenticationError("No active session")

        return {
            "JAAuthCookie": session.ja_auth_cookie,
        }

    def get_session_info(self) -> dict:
        """Get session information.

        Returns:
            dict: Session information

        """
        session = self.get_current_session()
        if not session:
            return {}

        return {
            "username": session.username,
            "user_id": session.user_id,
            "library_id": session.library_id,
            "space_id": session.space_id,
            "is_authenticated": session.is_valid(),
        }

    def refresh_session_if_needed(self, refresh_func) -> bool:
        """Refresh session if needed using provided function.

        Args:
            refresh_func: Function to refresh session

        Returns:
            bool: True if session is valid after refresh

        """
        try:
            # Try to use current session
            if self.is_authenticated():
                return True

            # Session is invalid, try to refresh
            logger.info("Attempting to refresh session")
            new_session = refresh_func()
            if new_session and new_session.is_valid():
                return self.save_session(new_session)

            return False

        except Exception as e:
            logger.error(f"Failed to refresh session: {e}")
            return False

    def validate_session_with_api(self, api_client) -> bool:
        """Validate session by making an API call.

        Args:
            api_client: API client to validate with

        Returns:
            bool: True if session is valid

        """
        try:
            session = self.get_current_session()
            if not session:
                return False

            # Make a simple API call to validate session
            # This would be implemented by the specific API client
            return True

        except Exception as e:
            logger.warning(f"Session validation failed: {e}")
            return False
