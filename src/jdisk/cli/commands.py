"""CLI command handlers for SJTU Netdisk."""

import argparse
from typing import Optional

from ..api.client import BaseAPIClient
from ..core.session import SessionManager
from ..utils.errors import SJTUNetdiskError


class CommandHandler:
    """Handle CLI commands."""

    def __init__(self):
        """Initialize command handler."""
        self.session_manager = SessionManager()
        self.api_client = BaseAPIClient()

    def run(self) -> int:
        """Run the CLI application.

        Returns:
            int: Exit code

        """
        parser = self._create_parser()
        args = parser.parse_args()

        if not args.command:
            self._show_help(parser)
            return 0

        try:
            return self._execute_command(args)
        except SJTUNetdiskError as e:
            print(f"Error: {e}")
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}")
            return 1

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser.

        Returns:
            argparse.ArgumentParser: Configured parser

        """
        parser = argparse.ArgumentParser(
            description="A CLI tool for SJTU Netdisk",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # Auth command
        auth_parser = subparsers.add_parser("auth", help="Authenticate using QR code")

        # Upload command
        upload_parser = subparsers.add_parser("upload", help="Upload a file")
        upload_parser.add_argument("local_path", help="Local file path to upload")
        upload_parser.add_argument("remote_path", nargs="?", help="Remote path (default: same as filename)")

        # Download command
        download_parser = subparsers.add_parser("download", help="Download a file")
        download_parser.add_argument("remote_path", help="Remote file path to download")
        download_parser.add_argument("local_path", nargs="?", help="Local path to save (default: same as filename)")

        # List command
        ls_parser = subparsers.add_parser("ls", help="List directory contents")
        ls_parser.add_argument("remote_path", nargs="?", default="/", help="Remote directory path (default: /)")
        ls_parser.add_argument("-l", "--long", action="store_true", help="Use long listing format")
        ls_parser.add_argument("-a", "--all", action="store_true", help="Show all files, including hidden ones")
        ls_parser.add_argument("-H", "--human-readable", action="store_true", help="Show sizes in human readable format")
        ls_parser.add_argument("-t", "--time", action="store_true", help="Sort by modification time")
        ls_parser.add_argument("-S", "--size", action="store_true", help="Sort by file size")
        ls_parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sort order")
        ls_parser.add_argument("-R", "--recursive", action="store_true", help="List subdirectories recursively")

        # Remove command
        rm_parser = subparsers.add_parser("rm", help="Remove a file or directory")
        rm_parser.add_argument("remote_path", help="Remote file or directory path to remove")
        rm_parser.add_argument("-r", "--recursive", action="store_true", help="Remove directories recursively")

        # Move command
        mv_parser = subparsers.add_parser("mv", help="Move/rename a file or directory")
        mv_parser.add_argument("from_path", help="Source path")
        mv_parser.add_argument("to_path", help="Destination path")

        # Make directory command
        mkdir_parser = subparsers.add_parser("mkdir", help="Create a directory")
        mkdir_parser.add_argument("dir_path", help="Directory path to create")
        mkdir_parser.add_argument("-p", "--parents", action="store_true", help="Create parent directories")

        return parser

    def _show_help(self, parser: argparse.ArgumentParser):
        """Show custom help.

        Args:
            parser: Argument parser

        """
        help_text = parser.format_help()
        lines = help_text.split("\n")
        # Skip the first three lines (usage, description, and empty line)
        filtered_lines = lines[3:]
        # Replace "positional arguments:" with "command:"
        for i, line in enumerate(filtered_lines):
            if line.strip() == "positional arguments:":
                filtered_lines[i] = "command:"
        print("\n".join(filtered_lines))

    def _execute_command(self, args) -> int:
        """Execute a command.

        Args:
            args: Parsed arguments

        Returns:
            int: Exit code

        """
        if args.command == "auth":
            return self._handle_auth()
        if args.command == "upload":
            return self._handle_upload(args.local_path, args.remote_path)
        if args.command == "download":
            return self._handle_download(args.remote_path, args.local_path)
        if args.command == "ls":
            return self._handle_ls(args.remote_path, args)
        if args.command == "rm":
            return self._handle_rm(args.remote_path, args.recursive)
        if args.command == "mv":
            return self._handle_mv(args.from_path, args.to_path)
        if args.command == "mkdir":
            return self._handle_mkdir(args.dir_path, args.parents)
        print(f"Unknown command: {args.command}")
        return 1

    def _handle_auth(self) -> int:
        """Handle authentication command.

        Returns:
            int: Exit code

        """
        try:
            # Check if already authenticated
            if self.session_manager.is_authenticated():
                session = self.session_manager.get_current_session()
                print(f"Already authenticated as: {session.username}")
                return 0

            # Use the new authentication service
            from ..services.auth_service import AuthService

            auth_service = AuthService()
            session = auth_service.authenticate_with_qrcode()

            if session:
                # Save the session using the session manager
                self.session_manager.save_session(session)
                return 0
            return 1

        except KeyboardInterrupt:
            print("\nAuthentication cancelled by user")
            return 1
        except Exception as e:
            print(f"Authentication failed: {e}")
            return 1

    def _handle_upload(self, local_path: str, remote_path: Optional[str]) -> int:
        """Handle upload command.

        Args:
            local_path: Local file path
            remote_path: Remote file path

        Returns:
            int: Exit code

        """
        try:
            # Create auth service and load session
            from ..services.auth_service import AuthService

            auth_service = AuthService()
            if not auth_service.load_session():
                print("Authentication required. Run 'jdisk auth' first.")
                return 1

            # Create uploader service
            from ..services.uploader import FileUploader

            uploader = FileUploader(auth_service)

            # Progress callback function
            def progress_callback(uploaded: int, total: int):
                if total > 0:
                    percent = (uploaded / total) * 100
                    bar_length = 50
                    filled_length = int(bar_length * uploaded // total)
                    bar = "█" * filled_length + "-" * (bar_length - filled_length)
                    print(f"\rUploading: |{bar}| {percent:.1f}% ({uploaded}/{total} bytes)", end="")
                else:
                    print(f"\rUploading: {uploaded} bytes", end="")

            # Determine remote path
            if not remote_path:
                import os

                remote_path = f"/{os.path.basename(local_path)}"

            print(f"Uploading: {local_path} -> {remote_path}")

            # Perform upload
            result = uploader.upload_file(local_path, remote_path, progress_callback)

            # Print final result (clear progress line)
            if result.success:
                file_name = result.file_path[-1] if result.file_path else "unknown"
                print(f"\nUpload completed: {file_name}")
            else:
                print(f"\nUpload failed: {result.message}")
            return 0

        except Exception as e:
            print(f"\nUpload failed: {e}")
            return 1

    def _handle_download(self, remote_path: str, local_path: Optional[str]) -> int:
        """Handle download command.

        Args:
            remote_path: Remote file path
            local_path: Local file path

        Returns:
            int: Exit code

        """
        try:
            # Create auth service and load session
            from ..services.auth_service import AuthService

            auth_service = AuthService()
            if not auth_service.load_session():
                print("Authentication required. Run 'jdisk auth' first.")
                return 1

            # Create downloader service
            from ..services.downloader import FileDownloader

            downloader = FileDownloader(auth_service)

            # Progress callback function
            def progress_callback(downloaded: int, total: int):
                if total > 0:
                    percent = (downloaded / total) * 100
                    bar_length = 50
                    filled_length = int(bar_length * downloaded // total)
                    bar = "█" * filled_length + "-" * (bar_length - filled_length)
                    print(f"\rDownloading: |{bar}| {percent:.1f}% ({downloaded}/{total} bytes)", end="")
                else:
                    print(f"\rDownloading: {downloaded} bytes", end="")

            print(f"Downloading: {remote_path} -> {local_path or 'local file'}")

            # Perform download
            result_path = downloader.download_file(remote_path, local_path, progress_callback)

            # Print final result (clear progress line)
            print(f"\nDownload completed: {result_path}")
            return 0

        except Exception as e:
            print(f"\nDownload failed: {e}")
            return 1

    def _handle_ls(self, remote_path: str, args) -> int:
        """Handle list command.

        Args:
            remote_path: Remote directory path
            args: Parsed command arguments

        Returns:
            int: Exit code

        """
        try:
            # Use the core operations to list files
            from ..core.operations import NetdiskOperations
            from ..services.auth_service import AuthService

            # Create auth service and load session
            auth_service = AuthService()
            if not auth_service.load_session():
                print("Authentication required. Run 'jdisk auth' first.")
                return 1

            # Create operations manager
            operations = NetdiskOperations(self.session_manager, self.api_client)

            # List directory recursively if requested
            if args.recursive:
                return self._list_recursive(operations, remote_path, args)
            return self._list_directory(operations, remote_path, args)

        except Exception as e:
            print(f"List failed: {e}")
            return 1

    def _list_directory(self, operations, remote_path: str, args) -> int:
        """List a single directory with various formatting options."""
        dir_info = operations.list_files(remote_path)

        # Get files and directories
        files = dir_info.get_files()
        directories = dir_info.get_directories()

        # Apply filters
        if not args.all:
            # Filter out hidden files/directories (starting with .)
            files = [f for f in files if not f.name.startswith(".")]
            directories = [d for d in directories if not d.name.startswith(".")]

        # Apply sorting
        if args.time:
            # Sort by modification time
            files.sort(key=lambda x: x.modification_time or "", reverse=not args.reverse)
            directories.sort(key=lambda x: x.modification_time or "", reverse=not args.reverse)
        elif args.size:
            # Sort by file size (directories first, then files by size)
            files.sort(key=lambda x: int(x.size), reverse=not args.reverse)
            directories.sort(key=lambda x: 0, reverse=not args.reverse)  # Directories have size 0
        else:
            # Sort by name (default)
            files.sort(key=lambda x: x.name.lower(), reverse=args.reverse)
            directories.sort(key=lambda x: x.name.lower(), reverse=args.reverse)

        # Display the listing
        if args.long:
            self._print_long_listing(directories, files, args)
        else:
            self._print_simple_listing(directories, files, args)

        return 0

    def _list_recursive(self, operations, remote_path: str, args) -> int:
        """List directories recursively."""

        def list_recursive_helper(path: str, prefix: str = ""):
            try:
                dir_info = operations.list_files(path)
                files = dir_info.get_files()
                directories = dir_info.get_directories()

                # Apply filters
                if not args.all:
                    files = [f for f in files if not f.name.startswith(".")]
                    directories = [d for d in directories if not d.name.startswith(".")]

                # Sort
                directories.sort(key=lambda x: x.name.lower())
                files.sort(key=lambda x: x.name.lower())

                # Print current directory header if not root
                if path != "/":
                    print(f"{prefix}{path}:")

                # Display contents
                if args.long:
                    self._print_long_listing(directories, files, args, prefix)
                else:
                    self._print_simple_listing(directories, files, args, prefix)

                # Recursively list subdirectories
                for directory in directories:
                    sub_path = f"{path.rstrip('/')}/{directory.name}"
                    list_recursive_helper(sub_path, prefix + "  ")

            except Exception as e:
                print(f"Error listing {path}: {e}")

        list_recursive_helper(remote_path)
        return 0

    def _print_simple_listing(self, directories, files, args, prefix: str = ""):
        """Print files and directories in simple format."""
        # Print directories first
        for directory in directories:
            print(f"{prefix}{directory.name}/")

        # Print files
        for file in files:
            if args.human_readable:
                size_str = file.size_human()
                print(f"{prefix}{file.name} ({size_str})")
            else:
                print(f"{prefix}{file.name}")

    def _print_long_listing(self, directories, files, args, prefix: str = ""):
        """Print files and directories in long format similar to Unix ls -l."""
        # Calculate column widths
        name_width = 0
        size_width = 0
        date_width = 0

        all_items = directories + files
        for item in all_items:
            name_width = max(name_width, len(item.name))
            if hasattr(item, "size") and not item.is_dir:
                size_width = max(size_width, len(str(item.size)))
                if args.human_readable:
                    size_width = max(size_width, len(item.size_human()))
            if hasattr(item, "modification_time") and item.modification_time:
                date_width = max(date_width, len(self._format_date(item.modification_time)))

        # Print directories
        for directory in directories:
            date_str = self._format_date(directory.modification_time) if directory.modification_time else ""
            name = f"{prefix}{directory.name}/"
            print(f"{name:<{name_width + 2}} <DIR>           {date_str}")

        # Print files
        for file in files:
            date_str = self._format_date(file.modification_time) if file.modification_time else ""
            if args.human_readable:
                size_str = file.size_human()
            else:
                size_str = str(file.size)
            name = f"{prefix}{file.name}"
            print(f"{name:<{name_width + 2}} {size_str:>{size_width}} {date_str}")

    def _format_date(self, date_str: str) -> str:
        """Format modification date for display."""
        try:
            # Parse the ISO format date and format it like ls does
            from datetime import datetime

            if "T" in date_str:
                # ISO format: 2025-01-15T10:30:00.000Z
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                # Format like Unix ls: Jan 15 10:30
                return dt.strftime("%b %d %H:%M")
            return date_str
        except:
            return date_str

    def _handle_rm(self, remote_path: str, recursive: bool) -> int:
        """Handle remove command.

        Args:
            remote_path: Remote path to remove
            recursive: Whether to remove recursively

        Returns:
            int: Exit code

        """
        try:
            # Use the core operations to delete files
            from ..core.operations import NetdiskOperations
            from ..services.auth_service import AuthService

            # Create auth service and load session
            auth_service = AuthService()
            if not auth_service.load_session():
                print("Authentication required. Run 'jdisk auth' first.")
                return 1

            # Create operations manager
            operations = NetdiskOperations(self.session_manager, self.api_client)
            success = operations.delete_file(remote_path, recursive)

            if success:
                print(f"Deleted: {remote_path}")
                return 0
            print(f"Failed to delete: {remote_path}")
            return 1

        except Exception as e:
            print(f"Delete failed: {e}")
            return 1

    def _handle_mv(self, from_path: str, to_path: str) -> int:
        """Handle move command.

        Args:
            from_path: Source path
            to_path: Destination path

        Returns:
            int: Exit code

        """
        try:
            # Use the core operations to move files
            from ..core.operations import NetdiskOperations
            from ..services.auth_service import AuthService

            # Create auth service and load session
            auth_service = AuthService()
            if not auth_service.load_session():
                print("Authentication required. Run 'jdisk auth' first.")
                return 1

            # Create operations manager
            operations = NetdiskOperations(self.session_manager, self.api_client)
            success = operations.move_file(from_path, to_path)

            if success:
                print(f"Moved: {from_path} -> {to_path}")
                return 0
            print(f"Failed to move: {from_path} -> {to_path}")
            return 1

        except Exception as e:
            print(f"Move failed: {e}")
            return 1

    def _handle_mkdir(self, dir_path: str, create_parents: bool) -> int:
        """Handle make directory command.

        Args:
            dir_path: Directory path to create
            create_parents: Whether to create parent directories

        Returns:
            int: Exit code

        """
        try:
            # Use the core operations to create directory
            from ..core.operations import NetdiskOperations
            from ..services.auth_service import AuthService

            # Create auth service and load session
            auth_service = AuthService()
            if not auth_service.load_session():
                print("Authentication required. Run 'jdisk auth' first.")
                return 1

            # Create operations manager
            operations = NetdiskOperations(self.session_manager, self.api_client)
            success = operations.create_directory(dir_path, create_parents)

            if success:
                print(f"Directory created: {dir_path}")
                return 0
            print(f"Failed to create directory: {dir_path}")
            return 1

        except Exception as e:
            print(f"Make directory failed: {e}")
            return 1
