"""User configuration management."""

from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python
    except ImportError:
        tomllib = None  # type: ignore


class Config:
    """User configuration manager."""

    def __init__(self):
        """Initialize config with defaults."""
        self.config_dir = Path.home() / ".config" / "musictl"
        self.config_file = self.config_dir / "config.toml"
        self._config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load config from file or return defaults."""
        defaults = {
            "encoding": {
                "default_source": "cp1251",
            },
            "scan": {
                "hires_threshold": 48000,
            },
            "dupes": {
                "default_mode": "exact",
            },
            "general": {
                "dry_run": True,
                "recursive": True,
            },
        }

        if not self.config_file.exists():
            return defaults

        if tomllib is None:
            # Can't read TOML, use defaults
            return defaults

        try:
            with open(self.config_file, "rb") as f:
                user_config = tomllib.load(f)
                # Merge user config with defaults
                return self._merge_configs(defaults, user_config)
        except Exception:
            # On any error, fall back to defaults
            return defaults

    def _merge_configs(self, defaults: dict, user: dict) -> dict:
        """Recursively merge user config into defaults."""
        result = defaults.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a config value."""
        return self._config.get(section, {}).get(key, default)

    def create_example_config(self) -> None:
        """Create an example config file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        example = """# musictl configuration file
# Location: ~/.config/musictl/config.toml

[encoding]
# Default source encoding for fix-encoding command
default_source = "cp1251"

[scan]
# Default threshold for hi-res detection (in Hz)
hires_threshold = 48000

[dupes]
# Default duplicate detection mode: "exact" or "fuzzy"
default_mode = "exact"

[general]
# Run commands in dry-run mode by default (require --apply)
dry_run = true

# Scan directories recursively by default
recursive = true
"""

        with open(self.config_file, "w") as f:
            f.write(example)


# Global config instance
_config = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
