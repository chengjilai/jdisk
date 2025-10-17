"""Base API client for SJTU Netdisk operations."""

import json
import time
from typing import Any, Dict

import requests

from ..constants import DEFAULT_TIMEOUT, MAX_RETRIES, RETRY_BACKOFF_FACTOR, STATUS_SUCCESS
from ..models.responses import APIResponse
from ..utils.errors import APIError, NetworkError, RateLimitError, SessionExpiredError
from ..utils.helpers import exponential_backoff, setup_session_headers


class BaseAPIClient:
    """Base API client with common functionality."""

    def __init__(self, base_url: str = None, timeout: int = DEFAULT_TIMEOUT):
        """Initialize base API client.

        Args:
            base_url: Base URL for API requests
            timeout: Default timeout for requests

        """
        from ..constants import BASE_URL
        from .endpoints import APIEndpoints

        self.base_url = base_url or BASE_URL
        self.timeout = timeout
        self.endpoints = APIEndpoints(self.base_url)
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self):
        """Setup session with default headers."""
        headers = setup_session_headers()
        self.session.headers.update(headers)

    def _make_request(
        self,
        method: str,
        url: str,
        params: Dict[str, Any] = None,
        data: Any = None,
        json_data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
        stream: bool = False,
        allow_redirects: bool = True,
    ) -> requests.Response:
        """Make HTTP request with error handling and retry logic.

        Args:
            method: HTTP method
            url: Request URL
            params: Query parameters
            data: Request data
            json_data: JSON request data
            headers: Additional headers
            timeout: Request timeout
            stream: Whether to stream response
            allow_redirects: Whether to allow redirects

        Returns:
            requests.Response: HTTP response

        Raises:
            NetworkError: For network-related errors
            APIError: For API-related errors
            RateLimitError: For rate limit errors

        """
        last_error = None
        actual_timeout = timeout or self.timeout

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=headers,
                    timeout=actual_timeout,
                    stream=stream,
                    allow_redirects=allow_redirects,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError("Rate limit exceeded, please try again later", 429)

                # Handle session expiration
                if response.status_code == 401:
                    raise SessionExpiredError("Session expired, please authenticate again")

                # Handle other HTTP errors
                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                        message = error_data.get("message", f"HTTP {response.status_code}")
                        error_code = error_data.get("error")
                    except (json.JSONDecodeError, ValueError):
                        message = f"HTTP {response.status_code}: {response.text[:200]}"
                        error_code = None

                    raise APIError(message, response.status_code, error_code)

                return response

            except requests.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    # Exponential backoff for retryable errors
                    delay = exponential_backoff(attempt, RETRY_BACKOFF_FACTOR)
                    time.sleep(delay)
                    continue
                raise NetworkError(f"Network error after {MAX_RETRIES} attempts: {e}")

        # Should not reach here
        if last_error:
            raise NetworkError(f"Request failed: {last_error}")
        raise NetworkError("Unknown request error")

    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse JSON response with error handling.

        Args:
            response: HTTP response

        Returns:
            Dict[str, Any]: Parsed JSON data

        Raises:
            APIError: If response cannot be parsed

        """
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise APIError(f"Failed to parse response JSON: {e}")

    def _check_api_response(self, data: Dict[str, Any]) -> APIResponse:
        """Check API response for errors.

        Args:
            data: Parsed response data

        Returns:
            APIResponse: Parsed response

        Raises:
            APIError: If API returned an error

        """
        api_response = APIResponse.from_dict(data)

        if not api_response.is_success():
            raise APIError(api_response.message, error_code=api_response.status)

        return api_response

    def get(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """Make GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout

        Returns:
            Dict[str, Any]: Response data

        """
        response = self._make_request("GET", endpoint, params=params, headers=headers, timeout=timeout)
        return self._parse_response(response)

    def post(
        self,
        endpoint: str,
        data: Any = None,
        json_data: Dict[str, Any] = None,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """Make POST request.

        Args:
            endpoint: API endpoint
            data: Request data
            json_data: JSON request data
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout

        Returns:
            Dict[str, Any]: Response data

        """
        response = self._make_request(
            "POST",
            endpoint,
            data=data,
            json_data=json_data,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def put(
        self,
        endpoint: str,
        data: Any = None,
        json_data: Dict[str, Any] = None,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """Make PUT request.

        Args:
            endpoint: API endpoint
            data: Request data
            json_data: JSON request data
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout

        Returns:
            Dict[str, Any]: Response data

        """
        response = self._make_request(
            "PUT",
            endpoint,
            data=data,
            json_data=json_data,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def delete(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """Make DELETE request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout

        Returns:
            Dict[str, Any]: Response data

        """
        response = self._make_request("DELETE", endpoint, params=params, headers=headers, timeout=timeout)

        # DELETE might return 204 with no content
        if response.status_code == 204:
            return {"status": STATUS_SUCCESS, "message": "Delete successful"}

        return self._parse_response(response)

    def download_stream(self, url: str, headers: Dict[str, str] = None) -> requests.Response:
        """Create a streaming download request.

        Args:
            url: Download URL
            headers: Additional headers

        Returns:
            requests.Response: Streaming response

        """
        return self._make_request("GET", url, headers=headers, stream=True)

    def upload_stream(
        self,
        method: str,
        url: str,
        data: Any,
        headers: Dict[str, str] = None,
        params: Dict[str, Any] = None,
    ) -> requests.Response:
        """Create a streaming upload request.

        Args:
            method: HTTP method (usually PUT)
            url: Upload URL
            data: Data to upload
            headers: Additional headers
            params: Query parameters

        Returns:
            requests.Response: Upload response

        """
        return self._make_request(
            method,
            url,
            data=data,
            headers=headers,
            params=params,
            timeout=None,  # No timeout for uploads
        )

    def set_auth_cookie(self, name: str, value: str, domain: str = None):
        """Set authentication cookie.

        Args:
            name: Cookie name
            value: Cookie value
            domain: Cookie domain

        """
        self.session.cookies.set(name, value, domain=domain)

    def set_auth_header(self, token: str):
        """Set authorization header.

        Args:
            token: Authorization token

        """
        self.session.headers["Authorization"] = f"Bearer {token}"

    def clear_auth(self):
        """Clear authentication credentials."""
        self.session.cookies.clear()
        self.session.headers.pop("Authorization", None)

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
