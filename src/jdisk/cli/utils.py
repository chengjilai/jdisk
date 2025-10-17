"""CLI utility functions."""

import sys
from typing import Any, List


def format_output(data: Any, format_type: str = "text") -> str:
    """Format output data.

    Args:
        data: Data to format
        format_type: Output format (text, json, etc.)

    Returns:
        str: Formatted output

    """
    if format_type == "json":
        import json

        return json.dumps(data, indent=2, ensure_ascii=False)
    return str(data)


def confirm_action(message: str, default: bool = False) -> bool:
    """Ask for user confirmation.

    Args:
        message: Confirmation message
        default: Default response if user just presses Enter

    Returns:
        bool: True if user confirms

    """
    suffix = " [Y/n]" if default else " [y/N]"
    response = input(f"{message}{suffix}: ").strip().lower()

    if not response:
        return default

    return response in ["y", "yes", "true", "1"]


def print_success(message: str):
    """Print success message.

    Args:
        message: Success message

    """
    print(f"✅ {message}")


def print_error(message: str):
    """Print error message.

    Args:
        message: Error message

    """
    print(f"❌ {message}", file=sys.stderr)


def print_warning(message: str):
    """Print warning message.

    Args:
        message: Warning message

    """
    print(f"⚠️  {message}")


def print_info(message: str):
    """Print info message.

    Args:
        message: Info message

    """
    print(f"ℹ️  {message}")


def progress_bar(current: int, total: int, width: int = 50, prefix: str = "Progress") -> str:
    """Create a progress bar string.

    Args:
        current: Current progress
        total: Total items
        width: Bar width
        prefix: Progress bar prefix

    Returns:
        str: Progress bar string

    """
    if total == 0:
        percentage = 100
    else:
        percentage = int(current / total * 100)

    filled = int(width * current // total)
    bar = "█" * filled + "░" * (width - filled)
    return f"{prefix}: |{bar}| {percentage}% ({current}/{total})"


def paginate_list(items: List[str], page_size: int = 20) -> List[str]:
    """Paginate a list of items with user interaction.

    Args:
        items: List of items to paginate
        page_size: Items per page

    Returns:
        List[str]: Selected items (for interactive mode)

    """
    if len(items) <= page_size:
        return items

    total_pages = (len(items) + page_size - 1) // page_size
    current_page = 0

    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(items))
        page_items = items[start_idx:end_idx]

        print(f"\n--- Page {current_page + 1}/{total_pages} ---")
        for i, item in enumerate(page_items):
            print(f"{start_idx + i + 1:3d}. {item}")

        if current_page < total_pages - 1:
            action = input("\nPress Enter for next page, 'q' to quit: ").strip().lower()
            if action == "q":
                break
            current_page += 1
        else:
            input("\nEnd of list. Press Enter to continue: ")
            break

    return items


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        str: Truncated text

    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
