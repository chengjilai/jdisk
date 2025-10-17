"""File download service for SJTU Netdisk."""

import logging
import os
from typing import Callable, Optional

import requests

from ..constants import BASE_URL, FILE_DOWNLOAD_URL, FILE_INFO_URL
from ..utils.errors import DownloadError

logger = logging.getLogger(__name__)


class FileDownloader:
    """File downloader service."""

    def __init__(self, auth_service):
        """Initialize file downloader.

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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
            raise DownloadError(f"Network error: {e}")

    def download_file(
        self,
        remote_path: str,
        local_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """Download a file using S3 presigned URLs.

        Args:
            remote_path: Remote file path
            local_path: Local file path (if None, uses filename from remote path)
            progress_callback: Progress callback function

        Returns:
            str: Local file path where file was saved

        Raises:
            DownloadError: If download fails

        """
        if not self.auth.is_authenticated():
            raise DownloadError("Not authenticated")

        try:
            # Get file info first
            file_info = self._get_file_info(remote_path)
            if not file_info:
                raise DownloadError(f"File not found: {remote_path}")

            # Determine local path
            if not local_path:
                local_path = os.path.basename(remote_path)
                if not local_path or local_path == "/":
                    local_path = file_info.name

            logger.info(f"Starting download: {remote_path} -> {local_path} ({file_info.size} bytes)")

            # Step 1: Get download URL from SJTU Netdisk API
            download_url = self._get_download_url(remote_path)

            # Step 2: Download file from S3
            self._download_from_s3(download_url, local_path, file_info.size, progress_callback)

            logger.info(f"Download completed: {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise DownloadError(f"Failed to download file: {e}")

    def _get_file_info(self, remote_path: str):
        """Get file information from API"""
        try:
            url = f"{BASE_URL}{FILE_INFO_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=remote_path)}"

            params = {
                "info": "",
                "access_token": self.auth.access_token,
            }

            resp = self._make_request("GET", url, params=params)

            if resp.status_code == 404:
                return None

            if resp.status_code not in [200, 201]:
                raise DownloadError(f"Failed to get file info: HTTP {resp.status_code}")

            data = resp.json()
            from ..models.data import FileInfo

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

        except Exception as e:
            raise DownloadError(f"Failed to get file info: {e}")

    def _get_download_url(self, remote_path: str) -> str:
        """Get S3 presigned download URL"""
        try:
            url = f"{BASE_URL}{FILE_DOWNLOAD_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=remote_path)}"

            params = {
                "access_token": self.auth.access_token,
                "download": "true",
            }

            # Allow redirects to get S3 URL
            resp = self._make_request("GET", url, params=params, allow_redirects=False)

            if resp.status_code not in [302, 200, 201]:
                raise DownloadError(f"Failed to get download URL: HTTP {resp.status_code}")

            # Check if we got a redirect to S3
            if resp.status_code == 302:
                download_url = resp.headers.get("Location")
                if not download_url:
                    raise DownloadError("No redirect location in response")
                logger.debug("Got S3 redirect URL")
                return download_url
            # If no redirect, try to get download URL from response
            data = resp.json()
            download_url = data.get("downloadUrl")
            if not download_url:
                raise DownloadError("No download URL in response")
            logger.debug("Got download URL from response")
            return download_url

        except Exception as e:
            raise DownloadError(f"Failed to get download URL: {e}")

    def _download_from_s3(self, download_url: str, local_path: str, expected_size: int, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Download file from S3 with progress tracking"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)

            # Download with streaming
            resp = self._make_request("GET", download_url, stream=True)

            if resp.status_code not in [200, 201]:
                raise DownloadError(f"Failed to download from S3: HTTP {resp.status_code}")

            downloaded_bytes = 0

            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)

                        # Update progress
                        if progress_callback and expected_size > 0:
                            progress_callback(downloaded_bytes, expected_size)

            logger.debug(f"Downloaded {downloaded_bytes} bytes to {local_path}")

        except Exception as e:
            # Clean up partial file
            if os.path.exists(local_path):
                os.remove(local_path)
            raise DownloadError(f"Failed to download from S3: {e}")
