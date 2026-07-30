import os
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


def load_env(path: str = ".env") -> None:
    """Load environment variables from a local file."""
    load_dotenv(path)


def load_yaml(path: str) -> Dict[str, Any]:
    """Load a YAML file and return a dictionary."""
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
