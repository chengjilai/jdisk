"""SJTU Netdisk command line interface."""

import argparse
import os
import sys

from .auth import SJTUAuth
from .client import SJTUNetdiskClient
from .download import FileDownloader
from .exceptions import AuthenticationError, DownloadError, SJTUNetdiskError, UploadError
from .models import Session
from .upload import FileUploader


# CLI Functions
def authenticate():
    """Authenticate with SJTU JAccount using QR code.

    Returns:
        Session: Authenticated session object or None if failed

    """
    auth = SJTUAuth()
    return _qrcode_auth(auth)


def _qrcode_auth(auth):
    """QR code authentication"""
    try:
        session = auth.login_with_qrcode()
        return session

    except AuthenticationError as e:
        print(f"Authentication failed: {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def upload_file(local_path, remote_path=None):
    """Upload a file to SJTU Netdisk"""
    if not os.path.exists(local_path):
        print(f"File not found: {local_path}")
        return False

    if remote_path is None:
        remote_path = os.path.basename(local_path)

    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("Authentication required. Run 'jdisk auth' first.")
            return False

        # Create session object from auth data
        session = Session(
            access_token=auth.access_token,
            username=auth.username or "Unknown",
            user_token=auth.user_token,
            ja_auth_cookie=auth.ja_auth_cookie,
            library_id=auth.library_id,
            space_id=auth.space_id,
        )

        uploader = FileUploader(auth)
        result = uploader.upload_file(local_path, remote_path)
        return True

    except (AuthenticationError, UploadError, SJTUNetdiskError) as e:
        print(f"Upload failed: {e}")
        return False


def download_file(remote_path, local_path=None):
    """Download a file from SJTU Netdisk"""
    if local_path is None:
        local_path = os.path.basename(remote_path)

    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("Authentication required. Run 'jdisk auth' first.")
            return False

        downloader = FileDownloader(auth)
        success = downloader.download_file(remote_path, local_path)
        return success

    except (AuthenticationError, DownloadError, SJTUNetdiskError) as e:
        print(f"Download failed: {e}")
        return False


def list_files(remote_path="/"):
    """List files and directories in SJTU Netdisk"""
    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("Authentication required. Run 'jdisk auth' first.")
            return False

        client = SJTUNetdiskClient(auth)
        result = client.list_directory(remote_path)

        files = [item for item in result.contents if not item.is_dir]
        directories = [item for item in result.contents if item.is_dir]

        # Directories first
        if directories:
            for dir_info in directories:
                print(f"{dir_info.name}/")

        # Then files
        if files:
            for file_info in files:
                size_mb = file_info.size / (1024 * 1024)
                if size_mb >= 1.0:
                    print(f"{file_info.name} ({size_mb:.1f}M)")
                elif size_mb >= 0.001:
                    size_kb = file_info.size / 1024
                    print(f"{file_info.name} ({size_kb:.1f}K)")
                else:
                    print(f"{file_info.name}")

        return True

    except (AuthenticationError, SJTUNetdiskError):
        print("jdisk auth to authenticate first")
        return False


def remove_file(remote_path, recursive=False, interactive=False, force=False, dir_only=False):
    """Remove a file or directory from SJTU Netdisk"""
    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("Authentication required. Run 'jdisk auth' first.")
            return False

        client = SJTUNetdiskClient(auth)

        # Check if path exists and get info
        try:
            file_info = client.get_file_info(remote_path)
        except:
            if not force:
                print(f"Cannot remove '{remote_path}': No such file or directory")
            return not force

        # Handle interactive mode
        if interactive and not force:
            response = input(f"Remove {file_info.name}? (y/N) ")
            if response.lower() not in ["y", "yes"]:
                return True

        # Handle directory removal
        if file_info.is_dir:
            if dir_only and not recursive:
                # Only remove empty directory with -d flag
                dir_info = client.list_directory(remote_path)
                if dir_info.contents:
                    if not force:
                        print(f"Cannot remove '{remote_path}': Directory not empty")
                    return not force

            elif not recursive:
                if not force:
                    print(f"Cannot remove '{remote_path}': Is a directory")
                return not force

        # Perform deletion
        success = client.delete_file(remote_path)
        return success

    except (AuthenticationError, SJTUNetdiskError) as e:
        if not force:
            print(f"Remove failed: {e}")
        return False


def move_file(from_path, to_path):
    """Move/rename a file or directory in SJTU Netdisk"""
    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("Authentication required. Run 'jdisk auth' first.")
            return False

        client = SJTUNetdiskClient(auth)
        return client.move_file(from_path, to_path)

    except (AuthenticationError, SJTUNetdiskError) as e:
        print(f"Move failed: {e}")
        return False


def make_directory(dir_path, create_parents=False):
    """Create a directory in SJTU Netdisk"""
    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("Authentication required. Run 'jdisk auth' first.")
            return False

        client = SJTUNetdiskClient(auth)
        return client.make_directory(dir_path, create_parents)

    except (AuthenticationError, SJTUNetdiskError) as e:
        print(f"Directory creation failed: {e}")
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="A CLI tool for SJTU Netdisk",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  jdisk auth                    # QR code authentication
  jdisk upload file.txt         # Upload file.txt to root directory
  jdisk upload file.txt docs/   # Upload file.txt to docs/ directory
  jdisk download file.txt       # Download file.txt from root directory
  jdisk download docs/file.txt  # Download file.txt from docs/ directory
  jdisk ls                      # List root directory contents
  jdisk ls docs/                # List docs/ directory contents
  jdisk mkdir new_folder        # Create new_folder directory
  jdisk mkdir -p path/to/nested # Create nested directories with parents
  jdisk rm file.txt             # Remove file.txt
  jdisk rm -r docs/             # Remove docs/ directory recursively
  jdisk rm -i file.txt          # Remove file.txt with confirmation
  jdisk rm -f nonexistent.txt   # Force remove (ignore errors)
  jdisk rm -d empty_dir/        # Remove empty directory
  jdisk mv old.txt new.txt      # Rename old.txt to new.txt
  jdisk mv file.txt docs/       # Move file.txt to docs/ directory
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Authenticate using QR code")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="")
    upload_parser.add_argument("local_path", help="Local file path to upload")
    upload_parser.add_argument("remote_path", nargs="?", help="Remote path (default: same as filename)")

    # Download command
    download_parser = subparsers.add_parser("download", help="")
    download_parser.add_argument("remote_path", help="Remote file path to download")
    download_parser.add_argument("local_path", nargs="?", help="Local path to save (default: same as filename)")

    # List command (ls)
    ls_parser = subparsers.add_parser("ls", help="List directory contents")
    ls_parser.add_argument("remote_path", nargs="?", default="/", help="Remote directory path (default: /)")

    # Remove command (rm)
    rm_parser = subparsers.add_parser("rm", help="Remove a file or directory")
    rm_parser.add_argument("remote_path", help="Remote file or directory path to remove")
    rm_parser.add_argument("-r", "--recursive", action="store_true", help="Remove directories and their contents recursively")
    rm_parser.add_argument("-i", "--interactive", action="store_true", help="Prompt before every removal")
    rm_parser.add_argument("-f", "--force", action="store_true", help="Ignore nonexistent files and arguments, never prompt")
    rm_parser.add_argument("-d", "--dir", action="store_true", help="Remove empty directories")

    # Move command (mv)
    mv_parser = subparsers.add_parser("mv", help="Move/rename a file or directory")
    mv_parser.add_argument("from_path", help="Source path")
    mv_parser.add_argument("to_path", help="Destination path")

    # Make directory command (mkdir)
    mkdir_parser = subparsers.add_parser("mkdir", help="Create a directory")
    mkdir_parser.add_argument("dir_path", help="Directory path to create")
    mkdir_parser.add_argument("-p", "--parents", action="store_true", help="Create parent directories as needed")

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        # Custom help output without the first three lines
        help_text = parser.format_help()
        lines = help_text.split("\n")
        # Skip the first three lines (usage, description, and empty line)
        filtered_lines = lines[3:]
        # Replace "positional arguments:" with "command:"
        for i, line in enumerate(filtered_lines):
            if line.strip() == "positional arguments:":
                filtered_lines[i] = "command:"
        # Remove the next two lines after "command:" (the brace line and "Available commands" line)
        new_filtered_lines = []
        skip_next = 0
        for line in filtered_lines:
            if skip_next > 0:
                skip_next -= 1
                continue
            if line.strip() == "command:":
                new_filtered_lines.append(line)
                skip_next = 2  # Skip the next 2 lines
            else:
                new_filtered_lines.append(line)
        print("\n".join(new_filtered_lines))
        return 0

    # Execute command
    success = False

    if args.command == "auth":
        success = authenticate() is not None
    elif args.command == "upload":
        success = upload_file(args.local_path, args.remote_path)
    elif args.command == "download":
        success = download_file(args.remote_path, args.local_path)
    elif args.command == "ls":
        success = list_files(args.remote_path)
    elif args.command == "rm":
        success = remove_file(
            args.remote_path,
            recursive=args.recursive,
            interactive=args.interactive,
            force=args.force,
            dir_only=args.dir,
        )
    elif args.command == "mv":
        success = move_file(args.from_path, args.to_path)
    elif args.command == "mkdir":
        success = make_directory(args.dir_path, args.parents)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
