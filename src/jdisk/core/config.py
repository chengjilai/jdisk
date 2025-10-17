"""Configuration management for SJTU Netdisk."""

from pathlib import Path
from typing import Any, Dict, Optional

from ..constants import SESSION_FILE
from ..utils.errors import ValidationError


class Config:
    """Configuration manager for SJTU Netdisk."""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration manager.

        Args:
            config_file: Path to configuration file

        """
        self.config_dir = Path.home() / ".jdisk"
        self.config_file = Path(config_file) if config_file else self.config_dir / "config.json"
        self.session_file = Path(SESSION_FILE).expanduser()

        self._config_data: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                import json

                with open(self.config_file, "r", encoding="utf-8") as f:
                    self._config_data = json.load(f)
            else:
                self._config_data = self._get_default_config()
        except Exception:
            self._config_data = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration.

        Returns:
            Dict[str, Any]: Default configuration

        """
        return {
            "api": {
                "base_url": "https://pan.sjtu.edu.cn",
                "timeout": 30,
                "max_retries": 3,
                "chunk_size": 4 * 1024 * 1024,  # 4MB
            },
            "upload": {
                "overwrite": False,
                "show_progress": True,
                "verify_integrity": True,
            },
            "download": {
                "show_progress": True,
                "verify_integrity": True,
                "resume": True,
            },
            "ui": {
                "pagination_size": 50,
                "show_hidden": False,
                "human_readable": True,
            },
            "logging": {
                "level": "WARNING",
                "file": None,
            },
        }

    def save_config(self) -> bool:
        """Save configuration to file.

        Returns:
            bool: True if saved successfully

        """
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)

            import json

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)

            return True

        except Exception:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found

        Returns:
            Any: Configuration value

        """
        keys = key.split(".")
        value = self._config_data

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> bool:
        """Set configuration value.

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set

        Returns:
            bool: True if set successfully

        """
        keys = key.split(".")
        config = self._config_data

        try:
            # Navigate to the parent of the target key
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            # Set the value
            config[keys[-1]] = value
            return True

        except Exception:
            return False

    def get_api_base_url(self) -> str:
        """Get API base URL.

        Returns:
            str: API base URL

        """
        return self.get("api.base_url", "https://pan.sjtu.edu.cn")

    def get_timeout(self) -> int:
        """Get request timeout.

        Returns:
            int: Timeout in seconds

        """
        return self.get("api.timeout", 30)

    def get_max_retries(self) -> int:
        """Get maximum retry attempts.

        Returns:
            int: Maximum retry attempts

        """
        return self.get("api.max_retries", 3)

    def get_chunk_size(self) -> int:
        """Get upload/download chunk size.

        Returns:
            int: Chunk size in bytes

        """
        return self.get("api.chunk_size", 4 * 1024 * 1024)

    def show_upload_progress(self) -> bool:
        """Whether to show upload progress.

        Returns:
            bool: True if progress should be shown

        """
        return self.get("upload.show_progress", True)

    def show_download_progress(self) -> bool:
        """Whether to show download progress.

        Returns:
            bool: True if progress should be shown

        """
        return self.get("download.show_progress", True)

    def get_pagination_size(self) -> int:
        """Get pagination size for file listings.

        Returns:
            int: Number of items per page

        """
        return self.get("ui.pagination_size", 50)

    def human_readable_sizes(self) -> bool:
        """Whether to show human-readable file sizes.

        Returns:
            bool: True if human-readable format should be used

        """
        return self.get("ui.human_readable", True)

    def ensure_config_dir(self) -> Path:
        """Ensure configuration directory exists.

        Returns:
            Path: Configuration directory path

        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return self.config_dir

    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults.

        Returns:
            bool: True if reset successfully

        """
        self._config_data = self._get_default_config()
        return self.save_config()

    def validate_config(self) -> bool:
        """Validate configuration values.

        Returns:
            bool: True if configuration is valid

        Raises:
            ValidationError: If configuration is invalid

        """
        # Validate timeout
        timeout = self.get_timeout()
        if timeout <= 0:
            raise ValidationError("API timeout must be positive")

        # Validate max retries
        max_retries = self.get_max_retries()
        if max_retries < 0:
            raise ValidationError("Max retries must be non-negative")

        # Validate chunk size
        chunk_size = self.get_chunk_size()
        if chunk_size <= 0:
            raise ValidationError("Chunk size must be positive")

        # Validate pagination size
        pagination_size = self.get_pagination_size()
        if pagination_size <= 0:
            raise ValidationError("Pagination size must be positive")

        return True
