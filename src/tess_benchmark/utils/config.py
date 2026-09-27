"""
Configuration loading and validation utility.
"""
from pathlib import Path
from typing import Any, Dict
import yaml


def load_config(config_path: str | Path) -> Dict[str, Any]:
    """
    Load a YAML configuration file.

    Parameters
    ----------
    config_path : str | Path
        Path to the YAML file.

    Returns
    -------
    Dict[str, Any]
        Parsed configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If configuration file does not exist.
    """
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Invalid configuration format in {path}. Expected mapping/dict.")

    return config
