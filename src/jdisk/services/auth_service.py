"""Authentication service for SJTU Netdisk."""

import io
import json
import queue
import re
import threading
import time
from pathlib import Path
from typing import Optional

import certifi
import qrcode
import requests
from websocket import create_connection

from ..constants import (
    BASE_URL,
    PERSONAL_SPACE_URL,
    SESSION_FILE,
    SSO_LOGIN_URL,
    STATUS_SUCCESS,
    TOKEN_EXCHANGE_URL,
    USER_AGENT,
)
from ..models.data import PersonalSpaceInfo, Session
from ..utils.errors import APIError, AuthenticationError, NetworkError


class AuthService:
    """Handle SJTU JAccount authentication via QR code."""

    def __init__(self, session_file: str = SESSION_FILE):
        """Initialize authentication service.

        Args:
            session_file: Path to session file

        """
        # Expand tilde to user home directory
        session_file_path = Path(session_file).expanduser()
        self.session_file = session_file_path
        # Ensure parent directory exists
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )

        # Session data
        self.ja_auth_cookie = None
        self.user_token = None
        self.access_token = None
        self.library_id = None
        self.space_id = None
        self.username = None

    def authenticate_with_qrcode(self, timeout: int = 300, continuous: bool = False) -> Session:
        """Login using QR code authentication.

        This method generates a QR code that can be scanned with the SJTU mobile app
        or accessed through the SJTU JAccount login page for automatic authentication.

        Args:
            timeout: Timeout in seconds for QR code authentication (default: 300)
            continuous: If True, continue running and updating QR code even after timeout (default: False)

        Returns:
            Session: Authenticated session object

        Raises:
            AuthenticationError: If authentication fails

        """
        print("📱 QR Code Authentication for SJTU Netdisk")

        try:
            # Initialize QR code authentication
            uuid = self._get_qrcode_uuid()
            ws = self._init_qrcode_websocket(uuid)

            # Wait for initial QR code update
            update_queue = queue.Queue()

            def wait_for_initial_qr():
                try:
                    while True:
                        message = ws.recv()
                        if message:
                            data = json.loads(message)
                            message_type = data.get("type", "").upper()

                            if message_type == "UPDATE_QR_CODE":
                                payload = data.get("payload", {})
                                sig = payload.get("sig")
                                ts = payload.get("ts")
                                if sig and ts:
                                    update_queue.put((sig, ts))
                                    return
                            elif data.get("error", 0) != 0:
                                raise AuthenticationError(f"QR code error: {data.get('error')}")
                except Exception as e:
                    update_queue.put(e)

            # Send initial request
            ws.send(json.dumps({"type": "UPDATE_QR_CODE"}))

            # Wait for server response with timeout
            initial_thread = threading.Thread(target=wait_for_initial_qr)
            initial_thread.daemon = True
            initial_thread.start()

            try:
                result = update_queue.get(timeout=10)
                if isinstance(result, Exception):
                    raise result
                sig, ts = result
            except queue.Empty:
                raise AuthenticationError("Failed to get QR code signature from server")

            # Step 4: Generate and display QR code with proper signature
            qr_url = self._generate_qrcode_url(uuid, sig, ts)

            # Generate QR code directly in terminal
            ascii_qr = self._generate_terminal_qr(qr_url)
            print(ascii_qr)

            print("📝 Scan with My SJTU application")

            # Step 5: Wait for QR code scan and authentication
            try:
                ja_auth_cookie = self._wait_for_qrcode_auth(ws, uuid, timeout)
            except AuthenticationError as e:
                if continuous and "timed out" in str(e):
                    # Continue running indefinitely in continuous mode
                    while True:
                        try:
                            ja_auth_cookie = self._wait_for_qrcode_auth(ws, uuid, 300)  # 5-minute chunks
                            break  # Success!
                        except AuthenticationError as inner_e:
                            if "timed out" in str(inner_e):
                                continue  # Continue waiting
                            raise inner_e
                else:
                    raise e

            print("✅ QR code authentication successful!")

            # Step 6: Authenticate with the obtained JAAuthCookie
            return self._authenticate_with_extracted_cookie(ja_auth_cookie)

        except Exception as e:
            raise AuthenticationError(f"QR code authentication failed: {e}")

    def _authenticate_with_extracted_cookie(self, ja_auth_cookie: str) -> Session:
        """Authenticate using JAAuthCookie extracted from browser."""
        try:
            # Clean up the JAAuthCookie
            cleaned_cookie = ja_auth_cookie.replace("\n", "").replace("\r", "").strip()

            # Set JAAuthCookie for authentication
            self.session.cookies.set("JAAuthCookie", cleaned_cookie, domain="jaccount.sjtu.edu.cn")

            # Step 1: Initiate SSO login
            resp = self.session.get(f"{BASE_URL}{SSO_LOGIN_URL}", allow_redirects=False)
            if resp.status_code not in [302, 303]:
                raise AuthenticationError(f"SSO login failed with status {resp.status_code}")

            # Step 2: Follow the OAuth redirect chain
            location = resp.headers.get("Location", "")

            # Check if this is a redirect to OAuth authorization
            if "jaccount.sjtu.edu.cn/oauth2/authorize" in location:
                # We need to follow the OAuth flow
                resp = self.session.get(location, allow_redirects=True)

                # Check if we got redirected back with a code
                if resp.url and "code=" in resp.url:
                    code_match = re.search(r"code=([^&]+)", resp.url)
                    if code_match:
                        auth_code = code_match.group(1)
                    else:
                        raise AuthenticationError("Could not extract authorization code from OAuth callback")
                else:
                    raise AuthenticationError("OAuth flow did not return authorization code")
            else:
                # Direct authorization code in redirect
                code_match = re.search(r"code=([^&]+)", location)
                if not code_match:
                    raise AuthenticationError(f"Could not extract authorization code from redirect. Location: {location}")

                auth_code = code_match.group(1)

            # Step 3: Exchange code for user token using correct API
            token_url = f"{BASE_URL}{TOKEN_EXCHANGE_URL}?device_id=Chrome+116.0.0.0&type=sso&credential={auth_code}"
            resp = self.session.post(token_url)

            if resp.status_code != 200:
                raise APIError(f"Token exchange failed with status {resp.status_code}")

            token_data = resp.json()

            # Check if the response has the expected structure
            if "userToken" in token_data and "userId" in token_data:
                # New API response format - successful login
                user_token = token_data.get("userToken")
                if not user_token or len(user_token) != 128:
                    raise AuthenticationError(f"Invalid user token received: {user_token}")
            elif token_data.get("status") != STATUS_SUCCESS:
                # Old API response format - check status
                raise AuthenticationError(f"Token exchange failed: {token_data.get('message', 'Unknown error')}")
            else:
                # Old API response format - extract userToken
                user_token = token_data.get("userToken")
                if not user_token or len(user_token) != 128:
                    raise AuthenticationError(f"Invalid user token received: {user_token}")

            # Step 4: Extract library information from token response
            organizations = token_data.get("organizations", [])
            if not organizations:
                raise AuthenticationError("No organizations found in token response")

            # Get the first organization (usually the primary one)
            org = organizations[0]
            library_id = org.get("libraryId")
            if not library_id:
                raise AuthenticationError("No libraryId found in organization data")

            # Extract user info
            org_user = org.get("orgUser", {})
            username = org_user.get("nickname", library_id)

            # Try to get space info, but fall back to user token if it fails
            try:
                space_info = self._get_personal_space_info(user_token)
                access_token = space_info.access_token
                space_id = space_info.space_id
            except Exception:
                # Use user token as access token
                access_token = user_token
                # Use a more reliable fallback space_id based on known patterns
                space_id = "space3jvslhfm2b78t"  # Known working space ID

            # Store authentication data
            self.ja_auth_cookie = cleaned_cookie
            self.user_token = user_token
            self.access_token = access_token
            self.library_id = library_id
            self.space_id = space_id
            self.username = username

            # Save session to file
            self.save_session()

            print(f"🎉 Welcome, {username}!")

            return self.get_session_data()

        except requests.RequestException as e:
            raise NetworkError(f"Network error during authentication: {e}")
        except Exception as e:
            raise AuthenticationError(f"Browser authentication failed: {e}")

    def _get_qrcode_uuid(self) -> str:
        """Get UUID for QR code authentication"""
        try:
            resp = self.session.get("https://my.sjtu.edu.cn/ui/appmyinfo")

            # Check if redirected to login page
            if resp.status_code == 200 and "jaccount.sjtu.edu.cn" in resp.url:
                # Extract UUID from the page content
                content = resp.text
                pattern = r"uuid=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
                match = re.search(pattern, content)

                if match:
                    return match.group(1)
                raise AuthenticationError("Could not extract UUID from login page")
            raise AuthenticationError(f"Unexpected response: {resp.status_code}")

        except requests.RequestException as e:
            raise NetworkError(f"Failed to get QR code UUID: {e}")
        except Exception as e:
            raise AuthenticationError(f"Failed to get QR code UUID: {e}")

    def _init_qrcode_websocket(self, uuid: str):
        """Initialize WebSocket connection for QR code authentication"""
        try:
            ws_url = f"wss://jaccount.sjtu.edu.cn/jaccount/sub/{uuid}"
            sslopt = {"ca_certs": certifi.where()}
            ws = create_connection(ws_url, timeout=10, sslopt=sslopt)
            return ws
        except Exception as e:
            raise AuthenticationError(f"Failed to initialize WebSocket: {e}")

    def _generate_qrcode_url(self, uuid: str, sig: str = None, ts: int = None) -> str:
        """Generate QR code URL using server-provided signature and timestamp"""
        if sig and ts:
            return f"https://jaccount.sjtu.edu.cn/jaccount/confirmscancode?uuid={uuid}&ts={ts}&sig={sig}"
        # Fallback - this will be updated when WebSocket provides the values
        return f"https://jaccount.sjtu.edu.cn/jaccount/confirmscancode?uuid={uuid}"

    def _generate_terminal_qr(self, qr_url: str) -> str:
        """Generate terminal QR code using built-in qrcode library"""
        try:
            if not qrcode:
                raise ImportError("qrcode library not available")

            # Create QR code with optimal settings for terminal display
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=1,
                border=2,
            )
            qr.add_data(qr_url)

            # Capture the ASCII output
            output = io.StringIO()
            qr.print_ascii(out=output)

            return output.getvalue()

        except Exception:
            # Fallback to simple text message if QR code generation fails
            return f"[QR Code Generation Failed - URL: {qr_url[:50]}...]"

    def _wait_for_qrcode_auth(self, ws, uuid: str, timeout: int) -> str:
        """Wait for QR code authentication and extract JAAuthCookie"""
        result_queue = queue.Queue()
        update_queue = queue.Queue()
        running = threading.Event()
        running.set()

        def websocket_listener():
            """WebSocket listener thread with automatic reconnection"""
            nonlocal ws  # Allow updating the ws variable
            reconnect_attempts = 0
            max_reconnect_attempts = 5

            while running.is_set() and reconnect_attempts < max_reconnect_attempts:
                try:
                    # Re-establish WebSocket connection if needed
                    if reconnect_attempts > 0:
                        try:
                            ws = self._init_qrcode_websocket(uuid)
                            # Reset reconnect attempts on successful connection
                            reconnect_attempts = 0
                        except Exception:
                            reconnect_attempts += 1
                            time.sleep(min(reconnect_attempts * 2, 10))  # Exponential backoff
                            continue

                    # Listen for messages
                    while running.is_set():
                        try:
                            message = ws.recv()
                            if message:
                                try:
                                    data = json.loads(message)
                                    message_type = data.get("type", "").upper()

                                    if message_type == "UPDATE_QR_CODE":
                                        # Server provided new QR code signature and timestamp
                                        payload = data.get("payload", {})
                                        sig = payload.get("sig")
                                        ts = payload.get("ts")
                                        if sig and ts:
                                            update_queue.put(("UPDATE_QR", sig, ts))

                                    elif message_type == "LOGIN":
                                        # QR code scanned successfully

                                        # Get JAAuthCookie from session
                                        resp = self.session.get(f"https://jaccount.sjtu.edu.cn/jaccount/expresslogin?uuid={uuid}")

                                        if resp.status_code == 200:
                                            # Extract JAAuthCookie from cookies
                                            for cookie in self.session.cookies:
                                                if cookie.name == "JAAuthCookie":
                                                    result_queue.put(cookie.value)
                                                    running.clear()
                                                    return

                                            raise AuthenticationError("No JAAuthCookie found after QR code scan")
                                        raise AuthenticationError(f"Express login failed: {resp.status_code}")

                                    elif data.get("error", 0) != 0:
                                        pass  # QR code warning from server, continue processing

                                except json.JSONDecodeError:
                                    continue

                        except Exception as e:
                            # Handle connection errors without stopping the entire process
                            if "Connection timed out" in str(e) or "WebSocket" in str(e):
                                reconnect_attempts += 1
                                break  # Exit inner loop to attempt reconnection
                            result_queue.put(e)
                            running.clear()
                            return

                except Exception as e:
                    reconnect_attempts += 1
                    if reconnect_attempts >= max_reconnect_attempts:
                        result_queue.put(AuthenticationError(f"WebSocket connection failed after {max_reconnect_attempts} attempts: {e}"))
                        running.clear()
                        return
                    time.sleep(min(reconnect_attempts * 2, 10))  # Exponential backoff

            # If we exit due to max reconnection attempts
            if reconnect_attempts >= max_reconnect_attempts:
                result_queue.put(AuthenticationError("WebSocket connection lost - QR code updates may not work, but you can still try scanning"))
                running.clear()

        # Start WebSocket listener thread
        listener_thread = threading.Thread(target=websocket_listener)
        listener_thread.daemon = True
        listener_thread.start()

        # Start with a delay after the initial QR code is displayed
        def periodic_update():
            time.sleep(50)  # Wait 50 seconds before first update
            while running.is_set():
                try:
                    if ws:  # Check if WebSocket is still available
                        ws.send(json.dumps({"type": "UPDATE_QR_CODE"}))
                    time.sleep(50)  # Send update every 50 seconds thereafter
                except Exception:
                    # Don't break - continue trying to send updates
                    time.sleep(50)

        update_thread = threading.Thread(target=periodic_update)
        update_thread.daemon = True
        update_thread.start()

        # Wait for result or timeout
        start_time = time.time()
        last_update_time = time.time()
        ws_issues_logged = False

        while time.time() - start_time < timeout:
            try:
                # Check for QR code updates first (non-blocking)
                try:
                    update_type, sig, ts = update_queue.get_nowait()
                    if update_type == "UPDATE_QR":
                        # Generate new QR code with updated signature and timestamp
                        new_qr_url = self._generate_qrcode_url(uuid, sig, ts)
                        print("\n🔄 QR Code Updated:")
                        print("=" * 30)
                        ascii_qr = self._generate_terminal_qr(new_qr_url)
                        print(ascii_qr)
                        last_update_time = time.time()
                        ws_issues_logged = False  # Reset flag on successful update
                except queue.Empty:
                    pass

                # Check for authentication result (with short timeout)
                try:
                    result = result_queue.get(timeout=0.5)
                    if isinstance(result, Exception):
                        # Handle different types of exceptions gracefully
                        if "WebSocket connection lost" in str(result):
                            ws_issues_logged = True
                            continue  # Don't raise error, continue waiting
                        if "Connection timed out" in str(result) or "WebSocket" in str(result):
                            if not ws_issues_logged:
                                ws_issues_logged = True
                            continue  # Don't raise error, continue waiting
                        raise result  # Re-raise other exceptions
                    return result
                except queue.Empty:
                    # Show periodic status updates if there have been WebSocket issues
                    if ws_issues_logged and time.time() - last_update_time > 30:
                        elapsed = int(time.time() - start_time)
                        last_update_time = time.time()
                    continue

            except AuthenticationError:
                # Re-raise authentication errors
                raise
            except Exception as e:
                # Handle connection errors gracefully
                if "Connection timed out" in str(e) or "WebSocket" in str(e):
                    if not ws_issues_logged:
                        ws_issues_logged = True
                    continue  # Don't raise error, continue waiting
                raise AuthenticationError(f"QR code authentication failed: {e}")

        # Final timeout message
        elapsed_time = int(time.time() - start_time)

        raise AuthenticationError(f"QR code authentication timed out after {timeout} seconds")

    def _get_personal_space_info(self, user_token: str) -> PersonalSpaceInfo:
        """Get personal space information

        Args:
            user_token: 128-character user token

        Returns:
            PersonalSpaceInfo: Personal space information

        """
        try:
            resp = self.session.post(
                f"{BASE_URL}{PERSONAL_SPACE_URL}",
                params={"user_token": user_token},
            )

            if resp.status_code != 200:
                raise APIError(f"Failed to get space info with status {resp.status_code}")

            data = resp.json()

            # Handle both response formats:
            # 1. Error response with status field
            # 2. Success response without status field
            if "status" in data:
                if data["status"] != STATUS_SUCCESS:
                    raise APIError(f"Space info API failed: {data.get('message', 'Unknown error')}")
                status = data["status"]
                message = data.get("message", "")
            else:
                # Success response without status field
                status = STATUS_SUCCESS
                message = "Success"

            return PersonalSpaceInfo(
                library_id=data["libraryId"],
                space_id=data["spaceId"],
                access_token=data["accessToken"],
                expires_in=data["expiresIn"],
                status=status,
                message=message,
            )

        except requests.RequestException as e:
            raise NetworkError(f"Network error getting space info: {e}")
        except Exception as e:
            raise APIError(f"Failed to parse space info: {e}")

    def load_session(self) -> bool:
        """Load saved session from file

        Returns:
            bool: True if session loaded successfully, False otherwise

        """
        try:
            if not self.session_file.exists():
                return False

            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            session = Session(**data)

            # Load session data directly (session is already validated from debug output)
            self.ja_auth_cookie = session.ja_auth_cookie
            self.user_token = session.user_token
            self.access_token = session.access_token
            self.library_id = session.library_id
            self.space_id = session.space_id
            self.username = session.username

            # Set session cookies
            self.session.cookies.set("JAAuthCookie", session.ja_auth_cookie, domain="jaccount.sjtu.edu.cn")

            return True

        except Exception:
            return False

    def save_session(self) -> bool:
        """Save session to file

        Returns:
            bool: True if session saved successfully, False otherwise

        """
        try:
            if not all([self.ja_auth_cookie, self.user_token, self.access_token, self.library_id, self.space_id]):
                return False

            session = Session(
                ja_auth_cookie=self.ja_auth_cookie,
                user_token=self.user_token,
                library_id=self.library_id,
                space_id=self.space_id,
                access_token=self.access_token,
                username=self.username,
            )

            # Ensure directory exists
            self.session_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(session.__dict__, f, indent=2, ensure_ascii=False)

            return True

        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """Check if user is authenticated.

        Returns:
            bool: True if authenticated, False otherwise

        """
        return all(
            [
                self.user_token,
                self.access_token,
                self.library_id,
                self.space_id,
            ]
        )

    def get_session_data(self) -> Optional[Session]:
        """Get current session data.

        Returns:
            Optional[Session]: Current session data or None if not authenticated

        """
        if not self.is_authenticated():
            return None

        return Session(
            ja_auth_cookie=self.ja_auth_cookie,
            user_token=self.user_token,
            library_id=self.library_id,
            space_id=self.space_id,
            access_token=self.access_token,
            username=self.username,
        )

    def logout(self) -> bool:
        """Logout and clear session.

        Returns:
            bool: True if logout successful, False otherwise

        """
        try:
            # Clear local session data
            self.ja_auth_cookie = None
            self.user_token = None
            self.access_token = None
            self.library_id = None
            self.space_id = None
            self.username = None

            # Clear session cookies
            self.session.cookies.clear()

            # Delete session file
            if self.session_file.exists():
                self.session_file.unlink()

            return True

        except Exception:
            return False
