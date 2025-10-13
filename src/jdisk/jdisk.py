"""SJTU Netdisk command line interface."""

import sys

from .cli import main as cli_main


def main():
    """Enter the CLI application."""
    sys.exit(cli_main())


if __name__ == "__main__":
    main()
