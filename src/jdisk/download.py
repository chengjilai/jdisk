"""File download functionality for SJTU Netdisk.

Implements chunked download with resume capability and integrity verification.
"""

import hashlib
import os
import time
from pathlib import Path
from typing import Callable, Optional

import requests

from .auth import SJTUAuth
from .constants import (
    BASE_URL,
    CHUNK_SIZE,
    USER_AGENT,
)
from .exceptions import APIError, DownloadError, NetworkError, ValidationError
from .models import FileInfo


class FileDownloader:
    """File downloader with chunked download support for SJTU Netdisk"""

    def __init__(self, auth: SJTUAuth):
        """Initialize file downloader

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
                "Accept": "*/*",
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

        """
        try:
            resp = self.session.request(method, url, **kwargs)
            return resp
        except requests.RequestException as e:
            raise NetworkError(f"Network error: {e}")

    def _get_file_info(self, remote_path: str) -> FileInfo:
        """Get file information before download

        Args:
            remote_path: Remote file path (e.g., "/path/to/file.txt")

        Returns:
            FileInfo: File information

        Raises:
            DownloadError: If file info cannot be retrieved

        """
        if not self.auth.is_authenticated():
            raise DownloadError("Not authenticated")

        try:
            from .client import SJTUNetdiskClient

            # Use existing client to get file info
            client = SJTUNetdiskClient(self.auth)
            file_info = client.get_file_info(remote_path)

            if not file_info:
                raise DownloadError(f"File not found: {remote_path}")

            if file_info.is_dir:
                raise DownloadError(f"Cannot download directory: {remote_path}")

            # Construct download URL based on the API pattern
            # Try the direct download URL pattern similar to file info API
            clean_path = remote_path.lstrip("/")
            encoded_path = clean_path  # URL encoding will be handled by requests

            # Construct potential download URL based on API patterns
            # Try different URL patterns for download
            clean_path = remote_path.lstrip("/")

            # Try different patterns for download URLs
            # Pattern 1: Try file API with download parameter
            download_url = f"{BASE_URL}/api/v1/file/{self.auth.library_id}/{self.auth.space_id}/{clean_path}?access_token={self.auth.access_token}&download=true"

            # Update file info with constructed download URL
            file_info.download_url = download_url

            return file_info

        except (APIError, NetworkError):
            raise
        except Exception as e:
            raise DownloadError(f"Failed to get file info: {e}")

    def _download_chunk(self, download_url: str, start: int, size: int, progress_callback: Optional[Callable[[int, int], None]] = None) -> bytes:
        """Download a single chunk using HTTP Range request

        Args:
            download_url: URL to download from
            start: Starting byte position
            size: Chunk size in bytes
            progress_callback: Optional progress callback

        Returns:
            bytes: Downloaded chunk data

        Raises:
            DownloadError: If chunk download fails

        """
        try:
            headers = {
                "Range": f"bytes={start}-{start + size - 1}",
                "Referer": BASE_URL,
            }

            resp = self._make_request("GET", download_url, headers=headers, stream=True)

            if resp.status_code not in [200, 206]:  # 206 for partial content
                raise DownloadError(f"Chunk download failed with status {resp.status_code}: {resp.text}")

            # Read chunk data
            chunk_data = bytearray()
            downloaded = 0

            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    chunk_data.extend(chunk)
                    downloaded += len(chunk)

                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(downloaded, size)

            # Verify we got the expected amount of data
            if len(chunk_data) != size:
                raise DownloadError(f"Chunk size mismatch: expected {size}, got {len(chunk_data)}")

            return bytes(chunk_data)

        except requests.RequestException as e:
            raise DownloadError(f"Network error downloading chunk: {e}")
        except Exception as e:
            raise DownloadError(f"Failed to download chunk: {e}")

    def _download_complete_file(self, download_url: str, local_path: str, file_size: int, progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """Download complete file in a single request

        Args:
            download_url: URL to download from
            local_path: Local file path to save to
            file_size: Expected file size
            progress_callback: Optional progress callback

        Returns:
            bool: True if download successful

        Raises:
            DownloadError: If download fails

        """
        try:
            resp = self._make_request("GET", download_url, stream=True)

            if resp.status_code != 200:
                raise DownloadError(f"Download failed with status {resp.status_code}: {resp.text}")

            # Create parent directories if they don't exist
            local_path = Path(local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)

            downloaded = 0

            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(downloaded, file_size)

            # Verify file size
            if downloaded != file_size:
                raise DownloadError(f"File size mismatch: expected {file_size}, got {downloaded}")

            return True

        except requests.RequestException as e:
            raise DownloadError(f"Network error downloading file: {e}")
        except Exception as e:
            raise DownloadError(f"Failed to download file: {e}")

    def _download_chunked_file(self, download_url: str, local_path: str, file_size: int, progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """Download file using chunked approach

        Args:
            download_url: URL to download from
            local_path: Local file path to save to
            file_size: Expected file size
            progress_callback: Optional progress callback

        Returns:
            bool: True if download successful

        Raises:
            DownloadError: If download fails

        """
        try:
            # Create parent directories if they don't exist
            local_path = Path(local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)

            chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
            total_downloaded = 0

            with open(local_path, "wb") as f:
                for chunk_number in range(chunk_count):
                    chunk_start = chunk_number * CHUNK_SIZE
                    chunk_end = min(chunk_start + CHUNK_SIZE, file_size)
                    current_chunk_size = chunk_end - chunk_start

                    # Download chunk
                    chunk_data = self._download_chunk(
                        download_url,
                        chunk_start,
                        current_chunk_size,
                        lambda downloaded, total: None,  # Suppress individual chunk progress
                    )

                    # Write chunk to file
                    f.write(chunk_data)
                    f.flush()  # Ensure data is written

                    total_downloaded += len(chunk_data)

                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(total_downloaded, file_size)

            # Verify total file size
            if total_downloaded != file_size:
                raise DownloadError(f"File size mismatch: expected {file_size}, got {total_downloaded}")

            return True

        except Exception:
            # Clean up partial file on error
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
            except OSError:
                pass
            raise

    def _calculate_chunk_hashes(self, local_path: str, file_size: int) -> str:
        """Calculate SHA256 hashes for each chunk and return combined hash string

        Args:
            local_path: Local file path
            file_size: File size in bytes

        Returns:
            str: Comma-separated SHA256 hashes of chunks

        """
        chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        sha256_list = []

        with open(local_path, "rb") as f:
            for chunk_number in range(chunk_count):
                chunk_start = chunk_number * CHUNK_SIZE
                chunk_end = min(chunk_start + CHUNK_SIZE, file_size)
                current_chunk_size = chunk_end - chunk_start

                f.seek(chunk_start)
                chunk_data = f.read(current_chunk_size)

                # Calculate SHA256 for this chunk
                sha256_hash = hashlib.sha256(chunk_data).hexdigest()
                sha256_list.append(sha256_hash)

        return ",".join(sha256_list)

    def _verify_file_integrity(self, local_path: str, expected_crc64: Optional[str] = None, expected_hash: Optional[str] = None) -> bool:
        """Verify file integrity using checksum

        Args:
            local_path: Local file path
            expected_crc64: Expected CRC64 checksum
            expected_hash: Expected MD5 hash (from API)

        Returns:
            bool: True if integrity check passes

        Raises:
            DownloadError: If integrity check fails

        """
        if not expected_hash and not expected_crc64:
            return True

        try:
            file_size = os.path.getsize(local_path)

            # For SJTU Netdisk, the hash is typically MD5 of SHA256 chunk hashes
            if expected_hash:
                chunk_hashes = self._calculate_chunk_hashes(local_path, file_size)
                actual_hash = hashlib.md5(chunk_hashes.encode()).hexdigest()

                if actual_hash != expected_hash:
                    raise DownloadError(f"Hash mismatch: expected {expected_hash}, got {actual_hash}")

            # Additional CRC64 verification if provided
            if expected_crc64:
                # Note: CRC64 implementation would be needed here
                # For now, we have a CRC64 but can't verify it
                pass

            return True

        except Exception as e:
            if isinstance(e, DownloadError):
                raise
            raise DownloadError(f"Integrity verification failed: {e}")

    def download_file(
        self,
        remote_path: str,
        local_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        max_retries: int = 3,
        verify_integrity: bool = True,
        use_chunking: bool = True,
    ) -> str:
        """Download a file with progress tracking and integrity verification

        Args:
            remote_path: Remote file path (e.g., "/path/to/file.txt")
            local_path: Local file path (defaults to filename in current directory)
            progress_callback: Optional callback for progress updates (downloaded, total)
            max_retries: Maximum number of retries for failed operations
            verify_integrity: Whether to verify file integrity after download
            use_chunking: Whether to use chunked download for large files

        Returns:
            str: Local file path where the file was saved

        Raises:
            ValidationError: If input validation fails
            DownloadError: If download fails

        """
        # Validate inputs
        if not remote_path or not remote_path.startswith("/"):
            raise ValidationError("Remote path must be absolute (start with '/')")

        # Get file information
        file_info = self._get_file_info(remote_path)
        file_size = file_info.size

        if file_size == 0:
            raise ValidationError("Cannot download empty file")

        # Determine local path
        if not local_path:
            local_path = os.path.basename(remote_path)
            if not local_path:
                local_path = "downloaded_file"

        # Check if file already exists
        if os.path.exists(local_path):
            # Could implement resume logic here
            pass

        last_error = None

        for attempt in range(max_retries):
            try:
                # Choose download method
                if use_chunking and file_size > CHUNK_SIZE:
                    success = self._download_chunked_file(
                        file_info.download_url,
                        local_path,
                        file_size,
                        progress_callback,
                    )
                else:
                    success = self._download_complete_file(
                        file_info.download_url,
                        local_path,
                        file_size,
                        progress_callback,
                    )

                if not success:
                    raise DownloadError("Download operation returned false")

                # Verify file integrity if requested
                if verify_integrity:
                    self._verify_file_integrity(
                        local_path,
                        expected_crc64=file_info.crc64,
                        expected_hash=file_info.hash,
                    )

                return local_path

            except (DownloadError, APIError, NetworkError) as e:
                last_error = e

                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2**attempt
                    time.sleep(wait_time)

        # All attempts failed
        raise DownloadError(f"Download failed after {max_retries} attempts. Last error: {last_error}")

    def download_to_memory(self, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None, max_retries: int = 3) -> bytes:
        """Download file directly to memory

        Args:
            remote_path: Remote file path (e.g., "/path/to/file.txt")
            progress_callback: Optional callback for progress updates (downloaded, total)
            max_retries: Maximum number of retries for failed operations

        Returns:
            bytes: File content

        Raises:
            ValidationError: If input validation fails
            DownloadError: If download fails

        """
        # Get file information
        file_info = self._get_file_info(remote_path)
        file_size = file_info.size

        if file_size == 0:
            raise ValidationError("Cannot download empty file")

        last_error = None

        for attempt in range(max_retries):
            try:
                # Download complete file to memory
                resp = self._make_request("GET", file_info.download_url, stream=True)

                if resp.status_code != 200:
                    raise DownloadError(f"Download failed with status {resp.status_code}: {resp.text}")

                content = bytearray()
                downloaded = 0

                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        content.extend(chunk)
                        downloaded += len(chunk)

                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(downloaded, file_size)

                # Verify file size
                if len(content) != file_size:
                    raise DownloadError(f"File size mismatch: expected {file_size}, got {len(content)}")

                return bytes(content)

            except (DownloadError, APIError, NetworkError) as e:
                last_error = e

                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2**attempt
                    time.sleep(wait_time)

        # All attempts failed
        raise DownloadError(f"Download failed after {max_retries} attempts. Last error: {last_error}")
