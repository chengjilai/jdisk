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
    """Authenticate with SJTU JAccount using QR code

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
        print(f"❌ Authentication failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def upload_file(local_path, remote_path=None):
    """Upload a file to SJTU Netdisk"""
    if not os.path.exists(local_path):
        print(f"❌ File '{local_path}' does not exist")
        return False

    if remote_path is None:
        remote_path = os.path.basename(local_path)

    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("❌ No valid session. Please authenticate first.")
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
        print(f"✅ Uploaded: {result.file_id}")
        return True

    except (AuthenticationError, UploadError, SJTUNetdiskError) as e:
        print(f"❌ Upload failed: {e}")
        return False


def download_file(remote_path, local_path=None):
    """Download a file from SJTU Netdisk"""
    if local_path is None:
        local_path = os.path.basename(remote_path)

    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("❌ No valid session. Please authenticate first.")
            return False

        downloader = FileDownloader(auth)
        success = downloader.download_file(remote_path, local_path)
        if success:
            print(f"✅ Downloaded: {local_path}")
            return True
        print("❌ Download failed")
        return False

    except (AuthenticationError, DownloadError, SJTUNetdiskError) as e:
        print(f"❌ Download failed: {e}")
        return False


def list_files(remote_path="/"):
    """List files and directories in SJTU Netdisk"""
    try:
        auth = SJTUAuth()
        if not auth.load_session():
            print("❌ No valid session. Please authenticate first.")
            return False

        client = SJTUNetdiskClient(auth)
        result = client.list_directory(remote_path)

        files = [item for item in result.contents if not item.is_dir]
        directories = [item for item in result.contents if item.is_dir]

        if files:
            for file_info in files:
                size_mb = file_info.size / (1024 * 1024)
                print(f"  {file_info.name} ({size_mb:.2f} MB)")

        if directories:
            for dir_info in directories:
                print(f"  {dir_info.name}/")

        if not files and not directories:
            print("  (empty)")

        return True

    except (AuthenticationError, SJTUNetdiskError) as e:
        print(f"❌ List failed: {e}")
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
  jdisk list                    # List root directory contents
  jdisk list docs/              # List docs/ directory contents
  jdisk ls                      # List root directory contents (short form)
  jdisk ls docs/                # List docs/ directory contents (short form)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Authenticate with SJTU JAccount using QR code")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload a file")
    upload_parser.add_argument("local_path", help="Local file path to upload")
    upload_parser.add_argument("remote_path", nargs="?", help="Remote path (default: same as filename)")

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a file")
    download_parser.add_argument("remote_path", help="Remote file path to download")
    download_parser.add_argument("local_path", nargs="?", help="Local path to save (default: same as filename)")

    # List command
    list_parser = subparsers.add_parser("list", help="List directory contents")
    list_parser.add_argument("remote_path", nargs="?", default="/", help="Remote directory path (default: /)")

    # LS command (shorter version of list)
    ls_parser = subparsers.add_parser("ls", help="List directory contents (short form)")
    ls_parser.add_argument("remote_path", nargs="?", default="/", help="Remote directory path (default: /)")

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    success = False

    if args.command == "auth":
        success = authenticate() is not None
    elif args.command == "upload":
        success = upload_file(args.local_path, args.remote_path)
    elif args.command == "download":
        success = download_file(args.remote_path, args.local_path)
    elif args.command == "list":
        success = list_files(args.remote_path)
    elif args.command == "ls":
        success = list_files(args.remote_path)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
