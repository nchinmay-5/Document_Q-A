"""Typed environment readers so settings.py stays declarative."""
import os
from pathlib import Path

from dotenv import load_dotenv

_TRUE_VALUES = {"1", "true", "yes", "on"}


def load_env_file(base_dir: Path) -> None:
    """Load key=value pairs from the project .env, if present."""
    load_dotenv(base_dir / ".env")


def get_str(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    return value.strip()


def get_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def get_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return raw in _TRUE_VALUES if raw else default


def get_list(name: str, default: list[str]) -> list[str]:
    """Read a comma-separated variable into a list of trimmed values."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]
