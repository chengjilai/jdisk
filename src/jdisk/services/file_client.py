"""File client for SJTU Netdisk operations."""

import json
from typing import Any, Dict, List, Optional

import requests

from ..constants import (
    BASE_URL,
    BATCH_MOVE_URL,
    CREATE_DIRECTORY_URL,
    DIRECTORY_INFO_URL,
    FILE_DELETE_URL,
    FILE_INFO_URL,
    STATUS_ERROR,
    STATUS_SUCCESS,
    USER_AGENT,
)
from ..models.data import DirectoryInfo, FileInfo
from ..utils.errors import APIError, NetworkError


class FileClient:
    """File client for SJTU Netdisk operations."""

    def __init__(self, auth_service):
        """Initialize file client.

        Args:
            auth_service: Authentication service instance

        """
        self.auth = auth_service
        self.session = requests.Session()
        self._setup_headers()

    def _setup_headers(self):
        """Setup common headers"""
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
            },
        )

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with error handling"""
        try:
            resp = self.session.request(method, url, **kwargs)
            return resp
        except requests.RequestException as e:
            raise NetworkError(f"Network error: {e}")

    def _check_response(self, resp: requests.Response) -> Dict[str, Any]:
        """Check response and return JSON data"""
        try:
            if resp.status_code not in [200, 201]:
                # Check for specific cases that are actually successes
                if resp.status_code == 409:
                    # Directory already exists - this is okay for mkdir operations
                    pass
                else:
                    raise APIError(f"API request failed with status {resp.status_code}")

            data = resp.json()

            # Check if API returned an error
            if isinstance(data, dict) and data.get("status") == STATUS_ERROR:
                raise APIError(f"API error: {data.get('message', 'Unknown error')}")

            return data

        except json.JSONDecodeError as e:
            raise APIError(f"Failed to parse response JSON: {e}")

    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """Get file information"""
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            url = f"{BASE_URL}{FILE_INFO_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=file_path)}"

            params = {
                "info": "",
                "access_token": self.auth.access_token,
            }

            resp = self._make_request("GET", url, params=params)
            data = self._check_response(resp)

            return FileInfo(
                name=data.get("name", ""),
                path=data.get("path", []),
                size=int(data.get("size", 0)),
                type=data.get("type", ""),
                modification_time=data.get("modificationTime", ""),
                download_url=data.get("downloadUrl"),
                is_dir=data.get("type") == "dir",
                file_id=data.get("id"),
                crc64=data.get("crc64"),
                content_type=data.get("contentType"),
                hash=data.get("hash") or data.get("checksum"),
            )

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to get file info: {e}")

    def list_directory(self, dir_path: str = "/", page: int = 1, page_size: int = 50, order_by: str = "name", order_type: str = "asc") -> DirectoryInfo:
        """List directory contents"""
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            # Handle path formatting - remove leading slash for formatting
            clean_path = dir_path.lstrip("/")
            url = f"{BASE_URL}{DIRECTORY_INFO_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=clean_path)}"

            params = {
                "access_token": self.auth.access_token,
                "page": page,
                "page_size": page_size,
                "order_by": order_by,
                "order_by_type": order_type,
            }

            resp = self._make_request("GET", url, params=params)
            data = self._check_response(resp)

            # Parse file contents
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

            return DirectoryInfo(
                path=data.get("path", []),
                contents=contents,
                file_count=data.get("fileCount", 0),
                sub_dir_count=data.get("subDirCount", 0),
                total_num=data.get("totalNum", 0),
            )

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to list directory: {e}")

    def create_directory(self, dir_path: str) -> bool:
        """Create a directory"""
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            url = f"{BASE_URL}{CREATE_DIRECTORY_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=dir_path)}"

            params = {
                "conflict_resolution_strategy": "ask",
                "access_token": self.auth.access_token,
            }

            resp = self._make_request("PUT", url, params=params)
            data = self._check_response(resp)

            # Check for success or if directory already exists
            if data.get("status") == STATUS_SUCCESS:
                return True
            if data.get("code") == "SameNameDirectoryOrFileExists":
                # Directory already exists - this is okay
                return True
            if "creationTime" in data:
                # Directory created successfully - API returns creationTime on success
                return True
            return False

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to create directory: {e}")

    def delete_file(self, file_path: str) -> bool:
        """Delete a file or directory"""
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            url = f"{BASE_URL}{FILE_DELETE_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=file_path)}"

            params = {
                "access_token": self.auth.access_token,
            }

            resp = self._make_request("DELETE", url, params=params)

            # Check if deletion was successful (status 204 or 200)
            if resp.status_code in [200, 204]:
                return True
            # Try to parse error response
            try:
                data = resp.json()
                if data.get("status") == STATUS_ERROR:
                    raise APIError(f"Delete failed: {data.get('message', 'Unknown error')}")
            except (json.JSONDecodeError, ValueError):
                pass
            raise APIError(f"Delete failed with status {resp.status_code}")

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to delete file: {e}")

    def move_file(self, from_path: str, to_path: str) -> bool:
        """Move/rename a file or directory using batch move API"""
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            # Use batch move API like JboxTransfer does
            return self._batch_move([from_path], to_path)

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to move file: {e}")

    def _batch_move(self, from_paths: List[str], to_path: str) -> bool:
        """Batch move files/directories to destination"""
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            url = f"{BASE_URL}{BATCH_MOVE_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id)}"

            params = {
                "move": "",
                "access_token": self.auth.access_token,
            }

            # Prepare batch move data following JboxTransfer pattern
            batch_data = []
            for from_path in from_paths:
                # Extract filename from path (remove leading /)
                clean_from_path = from_path.lstrip("/")
                filename = clean_from_path.split("/")[-1]

                # Construct destination path:
                # If to_path ends with '/', it's a directory - append filename
                # If to_path doesn't end with '/', it's the full destination path
                if to_path.endswith("/"):
                    dest_path = to_path + filename
                else:
                    dest_path = to_path

                # Get file info to determine if it's a directory
                file_info = self.get_file_info(from_path)
                if not file_info:
                    raise APIError(f"Source file not found: {from_path}")

                is_dir = file_info.is_dir
                file_type = "" if is_dir else "file"

                batch_data.append(
                    {
                        "from": clean_from_path,  # Use path without leading slash
                        "to": dest_path.lstrip("/"),  # Remove leading slash from destination too
                        "type": file_type,
                        "conflict_resolution_strategy": "rename",
                        "moveAuthority": is_dir,
                    }
                )

            resp = self._make_request("POST", url, params=params, json=batch_data)

            # Check response status code first (HTTP 200, 201, 207 are all valid for batch operations)
            if resp.status_code not in [200, 201, 207]:
                try:
                    error_data = resp.json()
                    if error_data.get("status") == STATUS_ERROR:
                        raise APIError(f"Batch move failed: {error_data.get('message', 'Unknown error')}")
                except (json.JSONDecodeError, ValueError):
                    pass
                raise APIError(f"Batch move failed with HTTP {resp.status_code}")

            # Parse successful response
            data = resp.json()

            # Check if all moves were successful
            results = data.get("result", [])
            if not results:
                raise APIError("No results returned from batch move operation")

            # All entries should have status 200 for success (HTTP OK)
            for result in results:
                status = result.get("status")
                from_item = result.get("from", [])
                from_str = "/".join(from_item) if from_item else "unknown"
                if status != 200:  # HTTP 200 OK = success for batch move
                    raise APIError(f"Move failed for: {from_str} (status: {status})")

            return True

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to batch move files: {e}")
