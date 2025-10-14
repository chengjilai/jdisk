"""SJTU Netdisk command line interface."""

import warnings

# Suppress the RuntimeWarning about module being found in sys.modules
warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")

from .cli import main as cli_main


def main():
    """Enter the CLI application."""
    import sys
    sys.exit(cli_main())


if __name__ == "__main__":
    main()
