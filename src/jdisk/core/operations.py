"""High-level operations for SJTU Netdisk."""

import logging
from pathlib import Path
from typing import Callable, Optional

from ..models.data import DirectoryInfo, FileInfo, UploadResult
from ..utils.errors import AuthenticationError, DownloadError, UploadError
from ..utils.validators import validate_file_path, validate_remote_path

logger = logging.getLogger(__name__)


class NetdiskOperations:
    """High-level operations for SJTU Netdisk."""

    def __init__(self, session_manager, api_client, uploader=None, downloader=None):
        """Initialize operations manager.

        Args:
            session_manager: Session manager instance
            api_client: API client instance
            uploader: File uploader instance
            downloader: File downloader instance

        """
        self.session_manager = session_manager
        self.api_client = api_client
        self.uploader = uploader
        self.downloader = downloader

    def _ensure_authenticated(self):
        """Ensure user is authenticated.

        Raises:
            AuthenticationError: If not authenticated

        """
        if not self.session_manager.is_authenticated():
            raise AuthenticationError("Authentication required. Run 'jdisk auth' first.")

    def list_files(self, remote_path: str = "/") -> DirectoryInfo:
        """List files and directories.

        Args:
            remote_path: Remote directory path

        Returns:
            DirectoryInfo: Directory information

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If path is invalid

        """
        self._ensure_authenticated()

        try:
            remote_path = validate_remote_path(remote_path)

            # Create auth service instance for API calls
            from ..services.auth_service import AuthService

            auth_service = AuthService()
            auth_service.load_session()

            # Create file client for directory listing
            from ..services.file_client import FileClient

            client = FileClient(auth_service)
            return client.list_directory(remote_path)

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise

    def upload_file(
        self,
        local_path: str,
        remote_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        overwrite: bool = False,
    ) -> UploadResult:
        """Upload a file.

        Args:
            local_path: Local file path
            remote_path: Remote file path
            progress_callback: Progress callback function
            overwrite: Whether to overwrite existing files

        Returns:
            UploadResult: Upload result

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If paths are invalid
            UploadError: If upload fails

        """
        self._ensure_authenticated()

        try:
            # Validate local file
            local_file = validate_file_path(local_path)

            # Determine remote path
            if not remote_path:
                remote_path = f"/{local_file.name}"
            else:
                remote_path = validate_remote_path(remote_path)

            # Use uploader service
            if not self.uploader:
                raise UploadError("File uploader not initialized")

            result = self.uploader.upload_file(
                local_path=str(local_file),
                remote_path=remote_path,
                progress_callback=progress_callback,
                overwrite=overwrite,
            )

            logger.info(f"Successfully uploaded {local_file.name} to {remote_path}")
            return result

        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise

    def download_file(
        self,
        remote_path: str,
        local_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """Download a file.

        Args:
            remote_path: Remote file path
            local_path: Local file path
            progress_callback: Progress callback function

        Returns:
            str: Local file path where file was saved

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If paths are invalid
            DownloadError: If download fails

        """
        self._ensure_authenticated()

        try:
            remote_path = validate_remote_path(remote_path)

            # Determine local path
            if not local_path:
                local_path = Path(remote_path).name

            # Use downloader service
            if not self.downloader:
                raise DownloadError("File downloader not initialized")

            result_path = self.downloader.download_file(
                remote_path=remote_path,
                local_path=local_path,
                progress_callback=progress_callback,
            )

            logger.info(f"Successfully downloaded {remote_path} to {result_path}")
            return result_path

        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            raise

    def delete_file(self, remote_path: str, recursive: bool = False) -> bool:
        """Delete a file or directory.

        Args:
            remote_path: Remote path to delete
            recursive: Whether to delete directories recursively

        Returns:
            bool: True if deleted successfully

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If path is invalid

        """
        self._ensure_authenticated()

        try:
            remote_path = validate_remote_path(remote_path)

            # Create auth service instance for API calls
            from ..services.auth_service import AuthService

            auth_service = AuthService()
            auth_service.load_session()

            # Create file client for file deletion
            from ..services.file_client import FileClient

            client = FileClient(auth_service)

            # Check if path exists and is directory
            file_info = client.get_file_info(remote_path)
            if file_info and file_info.is_dir and not recursive:
                from ..utils.errors import ValidationError

                raise ValidationError(f"Cannot delete directory {remote_path} without recursive flag")

            # Delete file/directory
            success = client.delete_file(remote_path)
            if success:
                logger.info(f"Successfully deleted {remote_path}")

            return success

        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            raise

    def get_file_info(self, remote_path: str) -> Optional[FileInfo]:
        """Get file information.

        Args:
            remote_path: Remote file path

        Returns:
            Optional[FileInfo]: File information or None if not found

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If path is invalid

        """
        self._ensure_authenticated()

        try:
            remote_path = validate_remote_path(remote_path)
            session = self.session_manager.get_current_session()

            response_data = self.api_client.get(
                self.api_client.endpoints.file_info(
                    session.library_id,
                    session.space_id,
                    remote_path,
                ),
                params={"access_token": session.access_token, "info": ""},
            )

            # Parse file info from response
            file_info = FileInfo(
                name=response_data.get("name", ""),
                path=response_data.get("path", []),
                size=int(response_data.get("size", 0)),
                type=response_data.get("type", ""),
                modification_time=response_data.get("modificationTime", ""),
                download_url=response_data.get("downloadUrl"),
                is_dir=response_data.get("type") == "dir",
                file_id=response_data.get("id"),
                crc64=response_data.get("crc64"),
                content_type=response_data.get("contentType"),
                hash=response_data.get("hash") or response_data.get("checksum"),
            )

            return file_info

        except Exception as e:
            logger.debug(f"Failed to get file info for {remote_path}: {e}")
            return None

    def create_directory(self, dir_path: str, create_parents: bool = False) -> bool:
        """Create a directory.

        Args:
            dir_path: Directory path to create
            create_parents: Whether to create parent directories

        Returns:
            bool: True if created successfully

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If path is invalid

        """
        self._ensure_authenticated()

        try:
            from ..utils.validators import validate_directory_path

            dir_path = validate_directory_path(dir_path)

            # Create auth service instance for API calls
            from ..services.auth_service import AuthService

            auth_service = AuthService()
            auth_service.load_session()

            # Create file client for directory creation
            from ..services.file_client import FileClient

            client = FileClient(auth_service)

            if create_parents:
                # Create parent directories recursively
                path_parts = [part for part in dir_path.split("/") if part]
                current_path = ""

                for part in path_parts:
                    current_path += "/" + part

                    # Check if directory already exists
                    try:
                        client.get_file_info(current_path)
                        continue  # Directory exists, skip
                    except:
                        pass  # Directory doesn't exist, create it

                    # Create this directory
                    success = client.create_directory(current_path)
                    if not success:
                        logger.warning(f"Failed to create parent directory: {current_path}")

            else:
                # Create single directory
                # Check if already exists
                try:
                    client.get_file_info(dir_path)
                    return True  # Directory already exists
                except:
                    pass  # Directory doesn't exist, create it

                success = client.create_directory(dir_path)
                if success:
                    logger.info(f"Successfully created directory {dir_path}")

                return success

            return True

        except Exception as e:
            logger.error(f"Failed to create directory: {e}")
            raise

    def move_file(self, from_path: str, to_path: str) -> bool:
        """Move/rename a file or directory.

        Args:
            from_path: Source path
            to_path: Destination path

        Returns:
            bool: True if moved successfully

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If paths are invalid

        """
        self._ensure_authenticated()

        try:
            from_path = validate_remote_path(from_path)
            to_path = validate_remote_path(to_path)

            # Create auth service instance for API calls
            from ..services.auth_service import AuthService

            auth_service = AuthService()
            auth_service.load_session()

            # Create file client for file moving
            from ..services.file_client import FileClient

            client = FileClient(auth_service)

            # Move file/directory
            success = client.move_file(from_path, to_path)
            if success:
                logger.info(f"Successfully moved {from_path} to {to_path}")

            return success

        except Exception as e:
            logger.error(f"Failed to move file: {e}")
            raise
