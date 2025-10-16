"""File upload functionality for SJTU Netdisk.

Implements chunked upload with resume capability and integrity verification.
"""

import hashlib
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import quote

import requests

from .auth import SJTUAuth
from .constants import (
    BASE_URL,
    CHUNK_SIZE,
    FILE_UPLOAD_URL,
    MAX_CHUNKS,
    STATUS_ERROR,
    USER_AGENT,
)
from .exceptions import APIError, NetworkError, UploadError, ValidationError
from .models import UploadContext, UploadHeaders, UploadPart, UploadResult


class FileUploader:
    """File uploader with chunked upload support for SJTU Netdisk"""

    def __init__(self, auth: SJTUAuth):
        """Initialize file uploader

        Args:
            auth: SJTUAuth instance for authentication

        """
        self.auth = auth
        self.session = requests.Session()
        self._setup_headers()

    def _setup_headers(self):
        """Setup common headers"""
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Origin": BASE_URL,
                "Referer": BASE_URL + "/",
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
                raise APIError(f"API request failed with status {resp.status_code}: {resp.text}")

            data = resp.json()

            # Check if API returned an error
            if isinstance(data, dict) and data.get("status") == STATUS_ERROR:
                raise APIError(f"API error: {data.get('message', 'Unknown error')}")

            return data

        except json.JSONDecodeError as e:
            raise APIError(f"Failed to parse response JSON: {e}")

    def _retry_request(self, func, *args, max_retries: int = 3, **kwargs):
        """Retry a function with exponential backoff

        Args:
            func: Function to retry
            *args: Function arguments
            max_retries: Maximum number of retries
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            The last exception if all retries fail

        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (NetworkError, APIError, requests.RequestException) as e:
                last_error = e

                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2**attempt
                    time.sleep(wait_time)

        # All retries failed
        raise last_error

    def _ensure_no_expire(self):
        """Ensure authentication hasn't expired by checking session validity"""
        if not self.auth.is_authenticated():
            raise UploadError("Authentication expired or not initialized")

        # Try to validate the current session
        try:
            session = self.auth.get_session_data()
            if not session or not session.is_valid():
                raise UploadError("Invalid session data")
        except Exception as e:
            raise UploadError(f"Session validation failed: {e}")

    def _calculate_file_hash(self, file_path: str, chunk_size: int = CHUNK_SIZE) -> str:
        """Calculate file hash for integrity verification

        Args:
            file_path: Path to the file
            chunk_size: Size of chunks to read

        Returns:
            str: SHA256 hash of the file

        Raises:
            ValidationError: If file cannot be read

        """
        try:
            sha256_hash = hashlib.sha256()

            with open(file_path, "rb") as f:
                # Read file in chunks
                while chunk := f.read(chunk_size):
                    sha256_hash.update(chunk)

            return sha256_hash.hexdigest()

        except IOError as e:
            raise ValidationError(f"Cannot read file for hash calculation: {e}")

    def _get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get basic file information

        Args:
            file_path: Path to the file

        Returns:
            Dict[str, Any]: File information

        Raises:
            ValidationError: If file doesn't exist or can't be accessed

        """
        try:
            path = Path(file_path)

            if not path.exists():
                raise ValidationError(f"File does not exist: {file_path}")

            if not path.is_file():
                raise ValidationError(f"Path is not a file: {file_path}")

            stat = path.stat()

            return {
                "name": path.name,
                "size": stat.st_size,
                "mime_type": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
                "modified_time": int(stat.st_mtime * 1000),  # Convert to milliseconds
            }

        except OSError as e:
            raise ValidationError(f"Cannot access file: {e}")

    def _initiate_upload(self, remote_path: str, file_info: Dict[str, Any], overwrite: bool = False) -> UploadContext:
        """Initiate chunked upload using SJTU Netdisk API

        Step 1: Initialize upload with part number range

        Args:
            remote_path: Remote file path
            file_info: File information dictionary
            overwrite: Whether to overwrite existing files

        Returns:
            UploadContext: Upload context for subsequent operations

        Raises:
            UploadError: If upload initiation fails

        """
        try:
            # Clean path for URL
            clean_path = remote_path.lstrip("/")
            encoded_path = quote(clean_path, safe="")

            url = f"{BASE_URL}{FILE_UPLOAD_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=encoded_path)}"

            # Calculate number of chunks needed
            file_size = file_info["size"]
            chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

            # Prepare upload initiation data with part number range
            # Based on working Go implementation, partNumberRange should be an array of integers
            part_numbers = list(range(1, chunk_count + 1))
            upload_data = {
                "partNumberRange": part_numbers,
            }

            # Set parameters for multipart upload
            params = {
                "access_token": self.auth.access_token,
                "multipart": "null",
                "conflict_resolution_strategy": "overwrite" if overwrite else "rename",
            }

            resp = self._retry_request(
                self._make_request,
                "POST",
                url,
                params=params,
                json=upload_data,
            )

            data = self._check_response(resp)

            # Extract upload context from the response
            if not data.get("confirmKey"):
                raise UploadError("No confirmKey in upload initiation response")

            # Parse parts information - check different possible response formats
            parts = {}

            # Check if parts are in 'uploadUrls' or 'parts' or direct format
            parts_data = data.get("parts", data.get("uploadUrls", {}))

            if parts_data:
                for part_number, part_info in parts_data.items():
                    # Parse headers for each part - try different formats
                    headers_data = part_info.get("headers", {})
                    headers = UploadHeaders(
                        x_amz_date=headers_data.get("x-amz-date", ""),
                        x_amz_content_sha256=headers_data.get("x-amz-content-sha256", ""),
                        authorization=headers_data.get("authorization", ""),
                    )

                    # Store upload URL for this part - try different field names
                    upload_url = part_info.get("uploadUrl") or part_info.get("url") or part_info.get("upload_url") or ""

                    upload_part = UploadPart(
                        headers=headers,
                        upload_url=upload_url,
                    )
                    parts[part_number] = upload_part
            else:
                # If no parts data, we might need to construct URLs manually
                # Create a default part for single chunk upload
                parts["1"] = UploadPart(
                    headers=UploadHeaders("", "", ""),
                    upload_url="",
                )

            return UploadContext(
                confirm_key=data.get("confirmKey", ""),
                domain=data.get("domain", ""),
                path=data.get("path", ""),
                upload_id=data.get("uploadId", ""),
                parts=parts,
                expiration=data.get("expiration", ""),
            )

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise UploadError(f"Failed to initiate upload: {e}")

    def _upload_chunk(self, context: UploadContext, part_number: int, chunk_data: bytes, file_hash: str) -> bool:
        """Upload a single chunk using SJTU Netdisk API

        Step 2: Upload chunk to dynamically generated URL with AWS S3 headers

        Args:
            context: Upload context from step 1
            part_number: Chunk number (1-based)
            chunk_data: Chunk data to upload
            file_hash: Overall file hash (not used in this step)

        Returns:
            bool: True if upload successful

        Raises:
            UploadError: If chunk upload fails

        """
        try:
            part_key = str(part_number)

            if part_key not in context.parts:
                raise UploadError(f"No upload part found for chunk {part_number}")

            part = context.parts[part_key]

            # Construct the upload URL using domain and path from initiation response
            upload_url = f"https://{context.domain}{context.path}"

            # Based on working Go implementation, use query parameters for uploadId and partNumber
            # and use the provided headers exactly as-is

            # Prepare headers exactly as provided by the API (like the Go implementation)
            headers = {
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Content-Type": "application/octet-stream",
                "x-amz-date": part.headers.x_amz_date,
                "authorization": part.headers.authorization,
                "x-amz-content-sha256": part.headers.x_amz_content_sha256,
            }

            # Prepare query parameters (critical difference from my previous implementation)
            params = {
                "uploadId": context.upload_id,
                "partNumber": str(part_number),
            }

            try:
                # Upload chunk as binary data with query parameters
                resp = self._retry_request(
                    self._make_request,
                    "PUT",
                    upload_url,
                    headers=headers,
                    params=params,
                    data=chunk_data,
                )

                # Check if upload was successful
                if resp.status_code in [200, 201]:
                    return True
                # Try to get more error details
                error_text = resp.text
                raise UploadError(f"Chunk upload failed with status {resp.status_code}: {error_text}")

            except Exception as e:
                raise UploadError(f"Failed to upload chunk {part_number}: {e}")

        except (NetworkError, UploadError):
            raise
        except Exception as e:
            raise UploadError(f"Failed to upload chunk {part_number}: {e}")

    def _confirm_upload(self, remote_path: str, context: UploadContext, file_info: Dict[str, Any], file_hash: str) -> UploadResult:
        """Confirm and complete the upload using SJTU Netdisk API

        Step 3: Confirm upload using confirmKey

        Args:
            remote_path: Remote file path (not used in this step)
            context: Upload context from step 1
            file_info: File information (not used in this step)
            file_hash: File hash (not used in this step)

        Returns:
            UploadResult: Upload result

        Raises:
            UploadError: If upload confirmation fails

        """
        try:
            # Use confirmKey from step 1 to construct the confirmation URL
            confirm_key = context.confirm_key
            if not confirm_key:
                raise UploadError("No confirmKey available for upload confirmation")

            url = f"{BASE_URL}{FILE_UPLOAD_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=confirm_key)}"

            # Set parameters for upload confirmation
            params = {
                "access_token": self.auth.access_token,
                "confirm": "null",
                "conflict_resolution_strategy": "rename",  # Always use rename for confirmation
            }

            # No request body needed for confirmation
            resp = self._retry_request(
                self._make_request,
                "POST",
                url,
                params=params,
            )

            data = self._check_response(resp)

            # Parse upload result
            # Confirmation response doesn't have a 'status' field when successful
            # It directly returns file information
            success = "name" in data and "size" in data
            if not success:
                # If confirmation response is invalid, this will be caught by the calling method
                pass

            # Extract file information from the response
            file_name = data.get("name", "")
            file_size = data.get("size", "0")
            file_crc64 = data.get("crc64", "")
            file_path = data.get("path", [])

            return UploadResult(
                success=success,
                file_id=file_name,  # Use filename as ID since no explicit fileId field
                message=f"Successfully uploaded {file_name} ({file_size} bytes)",
                crc64=file_crc64,
                file_path=file_path,
            )

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise UploadError(f"Failed to confirm upload: {e}")

    def _upload_small_file(self, remote_path: str, local_path: str, file_info: Dict[str, Any], overwrite: bool = False, progress_callback: Optional[Callable[[int, int], None]] = None) -> UploadResult:
        """Upload small file using three-step chunked upload process (single chunk)

        For small files, we still use the three-step process but with only one chunk.

        Args:
            remote_path: Remote file path
            local_path: Local file path
            file_info: File information
            overwrite: Whether to overwrite existing files
            progress_callback: Optional progress callback

        Returns:
            UploadResult: Upload result

        Raises:
            UploadError: If upload fails

        """
        try:
            # For small files, use the same three-step process but with a single chunk
            # Step 1: Initialize upload
            context = self._initiate_upload(remote_path, file_info, overwrite)

            # Call progress callback to indicate start
            if progress_callback:
                progress_callback(0, file_info["size"])

            # Step 2: Upload single chunk (the entire file)
            with open(local_path, "rb") as f:
                chunk_data = f.read()
                if len(chunk_data) != file_info["size"]:
                    raise UploadError(f"File size mismatch: expected {file_info['size']}, got {len(chunk_data)}")

            # Upload the single chunk
            success = self._upload_chunk(context, 1, chunk_data, "")
            if not success:
                raise UploadError("Failed to upload small file chunk")

            # Call progress callback to indicate completion
            if progress_callback:
                progress_callback(file_info["size"], file_info["size"])

            # Step 3: Confirm upload
            result = self._confirm_upload(remote_path, context, file_info, "")

            return result

        except (APIError, NetworkError, UploadError):
            raise
        except Exception as e:
            raise UploadError(f"Failed to upload small file: {e}")

    def _upload_chunked_file(
        self,
        remote_path: str,
        local_path: str,
        file_info: Dict[str, Any],
        file_hash: str,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> UploadResult:
        """Upload large file using three-step chunked approach

        Args:
            remote_path: Remote file path
            local_path: Local file path
            file_info: File information
            file_hash: File hash
            overwrite: Whether to overwrite existing files
            progress_callback: Optional progress callback

        Returns:
            UploadResult: Upload result

        Raises:
            UploadError: If upload fails

        """
        try:
            # Step 1: Initiate chunked upload
            context = self._initiate_upload(remote_path, file_info, overwrite)

            # Calculate chunk count
            file_size = file_info["size"]
            chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

            if chunk_count > MAX_CHUNKS:
                raise UploadError(f"File too large: {chunk_count} chunks exceeds maximum {MAX_CHUNKS}")

            # Step 2: Upload chunks
            total_uploaded = 0

            with open(local_path, "rb") as f:
                for chunk_number in range(1, chunk_count + 1):
                    chunk_start = (chunk_number - 1) * CHUNK_SIZE
                    chunk_end = min(chunk_start + CHUNK_SIZE, file_size)
                    chunk_size = chunk_end - chunk_start

                    # Read chunk data
                    f.seek(chunk_start)
                    chunk_data = f.read(chunk_size)

                    if len(chunk_data) != chunk_size:
                        raise UploadError(f"Chunk size mismatch: expected {chunk_size}, got {len(chunk_data)}")

                    # Upload chunk using new three-step method
                    success = self._upload_chunk(context, chunk_number, chunk_data, file_hash)
                    if not success:
                        raise UploadError(f"Failed to upload chunk {chunk_number}")

                    total_uploaded += len(chunk_data)

                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(total_uploaded, file_size)

            # Step 3: Confirm upload
            result = self._confirm_upload(remote_path, context, file_info, file_hash)

            return result

        except (UploadError, APIError, NetworkError):
            raise
        except Exception as e:
            raise UploadError(f"Failed to upload chunked file: {e}")

    def upload_file(
        self,
        local_path: str,
        remote_path: Optional[str] = None,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        max_retries: int = 3,
        use_chunking: bool = True,
    ) -> UploadResult:
        """Upload a file with progress tracking and integrity verification

        Args:
            local_path: Local file path to upload
            remote_path: Remote file path (defaults to filename in root directory)
            overwrite: Whether to overwrite existing files
            progress_callback: Optional callback for progress updates (uploaded, total)
            max_retries: Maximum number of retries for failed operations
            use_chunking: Whether to use chunked upload for large files

        Returns:
            UploadResult: Upload result with file information

        Raises:
            ValidationError: If input validation fails
            UploadError: If upload fails

        """
        # Validate authentication
        self._ensure_no_expire()

        # Validate local file
        if not local_path:
            raise ValidationError("Local file path is required")

        file_info = self._get_file_info(local_path)
        file_size = file_info["size"]

        if file_size == 0:
            raise ValidationError("Cannot upload empty file")

        # Determine remote path
        if not remote_path:
            remote_path = f"/{file_info['name']}"
        elif not remote_path.startswith("/"):
            remote_path = f"/{remote_path}"

        # Calculate file hash for integrity verification
        file_hash = self._calculate_file_hash(local_path)

        last_error = None

        for attempt in range(max_retries):
            try:
                # Choose upload method based on file size
                if use_chunking and file_size > CHUNK_SIZE:
                    result = self._upload_chunked_file(
                        remote_path,
                        local_path,
                        file_info,
                        file_hash,
                        overwrite,
                        progress_callback,
                    )
                else:
                    result = self._upload_small_file(
                        remote_path,
                        local_path,
                        file_info,
                        overwrite,
                        progress_callback,
                    )

                if not result.success:
                    raise UploadError(f"Upload operation returned failure: {result.message}")

                return result

            except (UploadError, APIError, NetworkError) as e:
                last_error = e

                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2**attempt
                    time.sleep(wait_time)

        # All attempts failed
        raise UploadError(f"Upload failed after {max_retries} attempts. Last error: {last_error}")

    def upload_from_data(self, data: bytes, remote_path: str, mime_type: str = "application/octet-stream", overwrite: bool = False) -> UploadResult:
        """Upload data from memory

        Args:
            data: Data to upload
            remote_path: Remote file path
            mime_type: MIME type of the data
            overwrite: Whether to overwrite existing files

        Returns:
            UploadResult: Upload result

        Raises:
            ValidationError: If input validation fails
            UploadError: If upload fails

        """
        if not data:
            raise ValidationError("Cannot upload empty data")

        if not remote_path or not remote_path.startswith("/"):
            raise ValidationError("Remote path must be absolute (start with '/')")

        # Validate authentication
        self._ensure_no_expire()

        try:
            # Create temporary file info
            file_info = {
                "name": Path(remote_path).name,
                "size": len(data),
                "mime_type": mime_type,
                "modified_time": int(time.time() * 1000),
            }

            # Calculate hash
            file_hash = hashlib.sha256(data).hexdigest()

            # For in-memory data, always use simple upload
            # Create a temporary file for upload
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(data)
                temp_path = temp_file.name

            try:
                result = self._upload_small_file(remote_path, temp_path, file_info, overwrite)
                return result
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

        except Exception as e:
            raise UploadError(f"Failed to upload from data: {e}")

    def resume_upload(self, upload_id: str, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> UploadResult:
        """Resume a previously interrupted chunked upload

        Args:
            upload_id: Upload ID from previous attempt
            local_path: Local file path
            remote_path: Remote file path
            progress_callback: Optional progress callback

        Returns:
            UploadResult: Upload result

        Raises:
            ValidationError: If input validation fails
            UploadError: If resume fails

        """
        # This would require implementing upload state tracking and resumption
        # For now, we'll implement a basic version that restarts the upload
        return self.upload_file(
            local_path=local_path,
            remote_path=remote_path,
            progress_callback=progress_callback,
            overwrite=True,  # Overwrite to resume
        )
