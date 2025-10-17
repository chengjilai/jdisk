"""jdisk."""

import os
import sys
import warnings

# Suppress the RuntimeWarning about module being found in sys.modules
warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")

# Add src to path if running directly
if __name__ == "__main__" and "src" not in sys.path:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(script_dir)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

# Import the new CLI main function
try:
    from jdisk.cli.main import main as cli_main
except ImportError:
    # Fallback to relative import
    from .cli.main import main as cli_main


def main():
    """Enter the CLI application."""
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
