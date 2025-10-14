"""SJTU Netdisk command line interface."""

import os
import sys

# Add the src directory to Python path to avoid relative import issues
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jdisk.cli import main as cli_main


def main():
    """Enter the CLI application."""
    sys.exit(cli_main())


if __name__ == "__main__":
    main()
