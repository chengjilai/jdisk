"""Main API client for SJTU Netdisk."""

import json
from typing import Any, Dict, List, Optional

import requests

from .auth import SJTUAuth
from .constants import (
    BASE_URL,
    CREATE_DIRECTORY_URL,
    DIRECTORY_INFO_URL,
    FILE_DELETE_URL,
    FILE_INFO_URL,
    FILE_MOVE_URL,
    STATUS_ERROR,
    STATUS_SUCCESS,
    USER_AGENT,
)
from .exceptions import APIError, NetworkError
from .models import DirectoryInfo, FileInfo


class SJTUNetdiskClient:
    """Main API client for SJTU Netdisk"""

    CHUNK_SIZE = 4 * 1024 * 1024  # 4MB

    def __init__(self, auth: SJTUAuth):
        self.auth = auth
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
        """Make HTTP request with error handling

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Request URL
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response: HTTP response

        Raises:
            NetworkError: For network-related errors
            APIError: For API-related errors

        """
        try:
            resp = self.session.request(method, url, **kwargs)
            return resp
        except requests.RequestException as e:
            raise NetworkError(f"Network error: {e}")

    def _check_response(self, resp: requests.Response) -> Dict[str, Any]:
        """Check response and return JSON data

        Args:
            resp: HTTP response

        Returns:
            Dict[str, Any]: Response JSON data

        Raises:
            APIError: For API-related errors

        """
        try:
            if resp.status_code not in [200, 201]:
                raise APIError(f"API request failed with status {resp.status_code}")

            data = resp.json()

            # Check if API returned an error
            if isinstance(data, dict) and data.get("status") == STATUS_ERROR:
                raise APIError(f"API error: {data.get('message', 'Unknown error')}")

            return data

        except json.JSONDecodeError as e:
            raise APIError(f"Failed to parse response JSON: {e}")

    def get_personal_space_info(self) -> Dict[str, Any]:
        """Get personal space information (using auth's method)

        Returns:
            Dict[str, Any]: Personal space information

        """
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        return self.auth._get_personal_space_info(self.auth.user_token)

    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """Get file information

        Args:
            file_path: Remote file path (e.g., "/path/to/file.txt")

        Returns:
            Optional[FileInfo]: File information or None if not found

        Raises:
            APIError: For API-related errors
            NetworkError: For network-related errors

        """
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

    def list_directory(self, dir_path: str = "/", page: int = 1, page_size: int = 50, order_by: str = "name", order_type: str = "asc") -> Optional[DirectoryInfo]:
        """List directory contents

        Args:
            dir_path: Directory path (e.g., "/path/to/dir")
            page: Page number (default: 1)
            page_size: Items per page (default: 50)
            order_by: Sort field (name, size, modified_time)
            order_type: Sort direction (asc, desc)

        Returns:
            Optional[DirectoryInfo]: Directory information or None if not found

        Raises:
            APIError: For API-related errors
            NetworkError: For network-related errors

        """
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
        """Create a directory

        Args:
            dir_path: Directory path to create (e.g., "/path/to/newdir")

        Returns:
            bool: True if directory created successfully

        Raises:
            APIError: For API-related errors
            NetworkError: For network-related errors

        """
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

            return data.get("status") == STATUS_SUCCESS

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to create directory: {e}")

    def make_directory(self, dir_path: str, create_parents: bool = False) -> bool:
        """Create a directory with optional parent creation

        Args:
            dir_path: Directory path to create (e.g., "/path/to/newdir")
            create_parents: If True, create parent directories as needed

        Returns:
            bool: True if directory created successfully

        Raises:
            APIError: For API-related errors
            NetworkError: For network-related errors

        """
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            if create_parents:
                # Create parent directories first
                path_parts = dir_path.strip("/").split("/")
                current_path = ""

                for i, part in enumerate(path_parts):
                    current_path += "/" + part

                    # Check if directory already exists
                    try:
                        self.get_file_info(current_path)
                        continue  # Directory exists, skip
                    except:
                        pass  # Directory doesn't exist, create it

                    # Create this directory
                    url = f"{BASE_URL}{CREATE_DIRECTORY_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=current_path)}"

                    params = {
                        "conflict_resolution_strategy": "ask",
                        "access_token": self.auth.access_token,
                    }

                    resp = self._make_request("PUT", url, params=params)

                    # Try to check response, but handle case where directory might already exist
                    try:
                        data = self._check_response(resp)
                        if data.get("status") != STATUS_SUCCESS:
                            # If creation failed, it might be because the directory already exists
                            # Check if it exists now
                            try:
                                self.get_file_info(current_path)
                                continue  # Directory exists after all
                            except:
                                raise APIError(f"Failed to create parent directory: {current_path}")
                    except APIError:
                        # Check if directory exists despite API error
                        try:
                            self.get_file_info(current_path)
                            continue  # Directory exists after all
                        except:
                            raise APIError(f"Failed to create parent directory: {current_path}")

                return True
            # Single directory creation (existing method)
            # Check if directory already exists first
            try:
                self.get_file_info(dir_path)
                return True  # Directory already exists
            except:
                pass  # Directory doesn't exist, create it
            return self.create_directory(dir_path)

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to make directory: {e}")

    def batch_move(self, from_paths: List[str], to_path: str) -> bool:
        """Batch move/copy files and directories

        Args:
            from_paths: List of source paths
            to_path: Destination directory path

        Returns:
            bool: True if operation successful

        Raises:
            APIError: For API-related errors
            NetworkError: For network-related errors

        """
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            url = f"{BASE_URL}/api/v1/batch/{self.auth.library_id}/{self.auth.space_id}"

            params = {
                "move": "",
                "access_token": self.auth.access_token,
            }

            # Prepare batch data
            batch_data = []
            for from_path in from_paths:
                # Get file info to determine type
                file_info = self.get_file_info(from_path)
                if not file_info:
                    continue

                item_type = "file" if not file_info.is_dir else ""
                to_full_path = f"{to_path.rstrip('/')}/{file_info.name}" if to_path != "/" else f"/{file_info.name}"

                batch_data.append(
                    {
                        "from": from_path,
                        "to": to_full_path,
                        "type": item_type,
                        "conflict_resolution_strategy": "rename",
                        "move_authority": file_info.is_dir,
                    },
                )

            resp = self._make_request("POST", url, params=params, json=batch_data)
            data = self._check_response(resp)

            return data.get("status") == STATUS_SUCCESS

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to batch move: {e}")

    def delete_file(self, file_path: str) -> bool:
        """Delete a file or directory

        Args:
            file_path: Path to the file or directory to delete

        Returns:
            bool: True if deletion successful

        Raises:
            APIError: For API-related errors
            NetworkError: For network-related errors

        """
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
        """Move/rename a file or directory

        Args:
            from_path: Source path
            to_path: Destination path

        Returns:
            bool: True if move successful

        Raises:
            APIError: For API-related errors
            NetworkError: For network-related errors

        """
        if not self.auth.is_authenticated():
            raise APIError("Not authenticated")

        try:
            url = f"{BASE_URL}{FILE_MOVE_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=from_path)}"

            params = {
                "move": "",
                "access_token": self.auth.access_token,
            }

            # Move data with destination path
            move_data = {
                "to": to_path,
                "conflict_resolution_strategy": "rename",
            }

            resp = self._make_request("POST", url, params=params, json=move_data)
            data = self._check_response(resp)

            return data.get("status") == STATUS_SUCCESS

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise APIError(f"Failed to move file: {e}")
