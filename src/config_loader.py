"""Configuration loader module with environment variable support."""

import os
from pathlib import Path
from typing import Any, Dict
import yaml


def get_project_root() -> Path:
    """Return the root path of the project."""
    return Path(__file__).resolve().parent.parent


def load_yaml(file_path: str | Path) -> Dict[str, Any]:
    """Safely load a YAML configuration file.

    Args:
        file_path: Path to the YAML file.

    Returns:
        Dictionary representation of configuration.
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = get_project_root() / path

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    return config


def load_pipeline_config(config_path: str | Path = "config/config.yaml") -> Dict[str, Any]:
    """Load main pipeline configuration with optional environment variable overrides."""
    config = load_yaml(config_path)

    # Allow environment variable overrides for sensitive salt
    if "PIPELINE_HMAC_SALT" in os.environ:
        config["pipeline"]["hmac_secret_salt"] = os.environ["PIPELINE_HMAC_SALT"]

    if "PIPELINE_ENV" in os.environ:
        config["pipeline"]["environment"] = os.environ["PIPELINE_ENV"]

    return config


def load_privacy_rules(rules_path: str | Path = "config/privacy_rules.yaml") -> Dict[str, Any]:
    """Load privacy transformation and minimization rules."""
    return load_yaml(rules_path)
