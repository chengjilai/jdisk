"""File upload service for SJTU Netdisk."""

import logging
import os
from typing import Callable, Optional

import requests

from ..constants import BASE_URL, FILE_UPLOAD_URL
from ..models.data import UploadResult
from ..utils.errors import UploadError

logger = logging.getLogger(__name__)


class FileUploader:
    """File uploader service."""

    def __init__(self, auth_service):
        """Initialize file uploader.

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
            raise UploadError(f"Network error: {e}")

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        overwrite: bool = False,
    ) -> UploadResult:
        """Upload a file using three-step S3-like multipart upload.

        Args:
            local_path: Local file path
            remote_path: Remote file path
            progress_callback: Progress callback function
            overwrite: Whether to overwrite existing files

        Returns:
            UploadResult: Upload result

        Raises:
            UploadError: If upload fails

        """
        if not self.auth.is_authenticated():
            raise UploadError("Not authenticated")

        try:
            # Validate local file
            if not os.path.exists(local_path):
                raise UploadError(f"Local file not found: {local_path}")

            file_size = os.path.getsize(local_path)
            if file_size == 0:
                raise UploadError("Cannot upload empty file")

            logger.info(f"Starting upload: {local_path} -> {remote_path} ({file_size} bytes)")

            # Step 1: Initiate upload
            upload_info = self._initiate_upload(remote_path, overwrite)

            # Step 2: Upload file chunks
            self._upload_chunks(local_path, upload_info, progress_callback)

            # Step 3: Confirm upload
            result = self._confirm_upload(upload_info)

            file_name = result.file_path[-1] if result.file_path else "unknown"
            logger.info(f"Upload completed: {file_name}")
            return result

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise UploadError(f"Failed to upload file: {e}")

    def _initiate_upload(self, remote_path: str, overwrite: bool) -> dict:
        """Step 1: Initiate upload and get S3 upload URLs"""
        try:
            url = f"{BASE_URL}{FILE_UPLOAD_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id, path=remote_path)}"

            params = {
                "access_token": self.auth.access_token,
                "multipart": "null",
                "conflict_resolution_strategy": "overwrite" if overwrite else "rename",
            }

            # Request single chunk upload for simplicity
            data = {"partNumberRange": [1]}

            resp = self._make_request("POST", url, params=params, json=data)

            if resp.status_code not in [200, 201]:
                logger.debug(f"Initiate upload response: {resp.status_code} - {resp.text}")
                raise UploadError(f"Failed to initiate upload: HTTP {resp.status_code}")

            upload_info = resp.json()
            logger.info(f"Upload initiated successfully: {list(upload_info.keys())}")
            logger.debug(f"Upload initiated: {upload_info}")

            return upload_info

        except Exception as e:
            raise UploadError(f"Failed to initiate upload: {e}")

    def _upload_chunks(self, local_path: str, upload_info: dict, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Step 2: Upload file chunks to S3"""
        try:
            with open(local_path, "rb") as f:
                file_data = f.read()

            total_size = len(file_data)
            uploaded_bytes = 0

            # Check if this is form-based upload (single chunk)
            if "form" in upload_info:
                return self._upload_form_based(local_path, upload_info, progress_callback)

            # Otherwise use multipart upload approach
            return self._upload_multipart(local_path, upload_info, progress_callback)

        except Exception as e:
            raise UploadError(f"Failed to upload chunks: {e}")

    def _upload_form_based(self, local_path: str, upload_info: dict, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Upload using form-based approach (single chunk)"""
        try:
            with open(local_path, "rb") as f:
                file_data = f.read()

            # Get form data
            form_data = upload_info["form"]
            domain = upload_info.get("domain")
            path = upload_info.get("path")

            if not all([domain, path, form_data]):
                raise UploadError("Invalid form upload response from server")

            # Construct upload URL
            upload_url = f"https://{domain}{path}"

            # Prepare form data
            files = {}
            data = {}

            # Add form fields
            for key, value in form_data.items():
                if key == "key":
                    files[key] = (value, file_data, "application/octet-stream")
                else:
                    data[key] = value

            logger.debug(f"Uploading via form to {upload_url}")

            resp = self._make_request("POST", upload_url, data=data, files=files)

            if resp.status_code not in [200, 201, 204]:
                logger.debug(f"Form upload response: {resp.status_code} - {resp.text}")
                raise UploadError(f"Failed to upload via form: HTTP {resp.status_code}")

            # Update progress
            if progress_callback:
                progress_callback(len(file_data), len(file_data))

            logger.debug("Form upload completed successfully")

        except Exception as e:
            raise UploadError(f"Failed to upload via form: {e}")

    def _upload_multipart(self, local_path: str, upload_info: dict, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Upload using multipart approach"""
        try:
            with open(local_path, "rb") as f:
                file_data = f.read()

            total_size = len(file_data)
            uploaded_bytes = 0

            # Get upload info
            domain = upload_info.get("domain")
            path = upload_info.get("path")
            upload_id = upload_info.get("uploadId")
            parts = upload_info.get("parts", {})

            if not all([domain, path, upload_id]):
                raise UploadError("Invalid multipart upload response from server")

            # Upload each chunk
            for part_number_str, part_info in parts.items():
                chunk_number = int(part_number_str)

                # Construct S3 upload URL
                upload_url = f"https://{domain}{path}"
                params = {
                    "uploadId": upload_id,
                    "partNumber": str(chunk_number),
                }

                # Get headers from part info
                part_headers = part_info.get("headers", {})

                # Prepare headers
                headers = {
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(file_data)),
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                }

                # Add AWS S3 headers from part info
                for key, value in part_headers.items():
                    headers[key] = value

                logger.debug(f"Uploading chunk {chunk_number} to {upload_url}")
                logger.debug(f"Headers: {dict(list(headers.items())[:5])}...")  # Show first 5 headers

                resp = self._make_request("PUT", upload_url, params=params, data=file_data, headers=headers)

                if resp.status_code not in [200, 201]:
                    logger.debug(f"Chunk upload response: {resp.status_code} - {resp.text}")
                    raise UploadError(f"Failed to upload chunk {chunk_number}: HTTP {resp.status_code}")

                # Update progress
                uploaded_bytes = len(file_data)
                if progress_callback:
                    progress_callback(uploaded_bytes, total_size)

                logger.debug(f"Chunk {chunk_number} uploaded successfully")

        except Exception as e:
            raise UploadError(f"Failed to upload chunks: {e}")

    def _confirm_upload(self, upload_info: dict) -> UploadResult:
        """Step 3: Confirm upload completion"""
        try:
            confirm_key = upload_info.get("confirmKey")
            if not confirm_key:
                raise UploadError("Missing confirmKey in upload response")

            url = f"{BASE_URL}/api/v1/file/{self.auth.library_id}/{self.auth.space_id}/{confirm_key}"

            params = {
                "access_token": self.auth.access_token,
                "confirm": "null",
                "conflict_resolution_strategy": "rename",
            }

            resp = self._make_request("POST", url, params=params)

            if resp.status_code not in [200, 201]:
                raise UploadError(f"Failed to confirm upload: HTTP {resp.status_code}")

            result_data = resp.json()
            logger.debug(f"Upload confirmed: {result_data}")

            # Parse upload result
            return UploadResult(
                success=True,
                file_id=result_data.get("eTag", ""),  # Use eTag as file_id
                message=f"Successfully uploaded {result_data.get('name', 'unknown')}",
                crc64=result_data.get("crc64", ""),
                file_path=result_data.get("path", []),
            )

        except Exception as e:
            raise UploadError(f"Failed to confirm upload: {e}")
