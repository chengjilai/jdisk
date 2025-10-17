"""Main CLI entry point for SJTU Netdisk."""

import logging
import warnings

# Suppress the RuntimeWarning about module being found in sys.modules
warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    """Enter the CLI application."""
    try:
        from .commands import CommandHandler

        handler = CommandHandler()
        return handler.run()

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"CLI error: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
