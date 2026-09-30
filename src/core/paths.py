from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def resource_directory() -> Path:
    """Find immutable assets in the checkout or a PyInstaller bundle."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def data_directory() -> Path:
    """Keep settings and voice downloads independent of the executable."""
    override = os.environ.get("TARS_DATA_DIR")
    return Path(override).expanduser().resolve() if override else Path.home() / ".tars"


def temporary_directory(name: str) -> Path:
    return Path(tempfile.gettempdir()) / name
